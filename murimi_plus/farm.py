"""Farm records and reminders, stored on this computer only (SQLite).

A record is a dated note about an animal, a herd or a plot ("dipped 12 cattle",
"sprayed plot 2 for armyworm"). A reminder is a due date with optional repeat.
The app suggests only one reminder by itself: weekly dipping from the start of
the hot wet season, which is what knowledge entry B5 says. Vaccination and
dosing schedules are entered by the farmer or vet, never invented here.
"""
from contextlib import contextmanager
from datetime import date, timedelta
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    subject TEXT NOT NULL,
    note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    due TEXT NOT NULL,
    text TEXT NOT NULL,
    repeat_days INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT '',
    done INTEGER NOT NULL DEFAULT 0
);
"""

SUGGESTED = {
    "dipping": {"text": "Take cattle to the dip tank (weekly in the hot wet season)", "repeat_days": 7,
                "source": "Knowledge entry B5: dip weekly from the start of the hot wet season (about November)."},
}

MAX_TEXT = 300


def default_path():
    base = os.environ.get("MURIMIFARA_DATA_DIR") or os.getcwd()
    return os.path.join(base, "farm_records.sqlite3")


def _day(value):
    """ISO date string, checked. Raises ValueError for anything else."""
    return date.fromisoformat(str(value).strip()).isoformat()


def _text(value, field):
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueError(f"{field} is empty")
    return text[:MAX_TEXT]


class Farm:
    def __init__(self, path=None):
        self.path = str(path or default_path())
        with self._db() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    # -- records
    def add_record(self, day, subject, note):
        with self._db() as db:
            cur = db.execute("INSERT INTO records (day, subject, note) VALUES (?, ?, ?)",
                             (_day(day), _text(subject, "subject"), _text(note, "note")))
            return cur.lastrowid

    def records(self, limit=200):
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM records ORDER BY day DESC, id DESC LIMIT ?", (limit,))]

    # -- reminders
    def add_reminder(self, due, text, repeat_days=0, source=""):
        repeat_days = int(repeat_days or 0)
        if not 0 <= repeat_days <= 366:
            raise ValueError("repeat must be 0-366 days")
        with self._db() as db:
            cur = db.execute("INSERT INTO reminders (due, text, repeat_days, source) VALUES (?, ?, ?, ?)",
                             (_day(due), _text(text, "reminder"), repeat_days, str(source)[:MAX_TEXT]))
            return cur.lastrowid

    def add_suggested(self, key, start):
        s = SUGGESTED[key]
        return self.add_reminder(start, s["text"], s["repeat_days"], s["source"])

    def reminders(self, today=None, days_ahead=14):
        today = today or date.today()
        with self._db() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM reminders WHERE done = 0 ORDER BY due, id")]
        for r in rows:
            due = date.fromisoformat(r["due"])
            r["overdue"] = due < today
            r["soon"] = today <= due <= today + timedelta(days=days_ahead)
        return rows

    def complete(self, reminder_id, on=None):
        """Mark done. A repeating reminder moves to its next due date instead."""
        on = on or date.today()
        with self._db() as db:
            row = db.execute("SELECT * FROM reminders WHERE id = ? AND done = 0", (int(reminder_id),)).fetchone()
            if row is None:
                return False
            if row["repeat_days"]:
                nxt = date.fromisoformat(row["due"])
                while nxt <= on:
                    nxt += timedelta(days=row["repeat_days"])
                db.execute("UPDATE reminders SET due = ? WHERE id = ?", (nxt.isoformat(), row["id"]))
            else:
                db.execute("UPDATE reminders SET done = 1 WHERE id = ?", (row["id"],))
            db.execute("INSERT INTO records (day, subject, note) VALUES (?, ?, ?)",
                       (on.isoformat(), "Reminder done", row["text"]))
            return True

    def delete_reminder(self, reminder_id):
        with self._db() as db:
            return db.execute("DELETE FROM reminders WHERE id = ?", (int(reminder_id),)).rowcount == 1
