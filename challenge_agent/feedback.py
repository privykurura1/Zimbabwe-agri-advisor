"""Officer feedback, and getting it back to the Murimi Fara team without internet.

Three pieces:
  * record():      what was wrong with a draft (category), the officer's corrected
                   answer and any missing topic - saved with the decision and
                   recorded in the tamper-evident audit log.
  * export_file(): one anonymised JSON file of all reviews on this laptop, to carry
                   on a flash drive or phone (Bluetooth/USB) and send on later.
  * sms_code():    a short text like "MF B3 R UNSAFE K7Q2" that fits in one SMS,
                   for fast warnings about wrong or unsafe advice.

What leaves the laptop: the question and draft text (with phone numbers and
ID-like numbers removed), knowledge entry IDs, the decision, category, reason,
correction and missing topic. NOT included: officer names, farmer names typed into
separate fields (there are none), or anything from farm records.
"""
from datetime import datetime, timezone
import hashlib
import json
import re
import secrets

FORMAT = "murimi-fara-reviews/1"

CATEGORIES = {
    "NONE": "Nothing wrong",
    "WRONG": "Wrong condition",
    "MISSING": "Advice missing or incomplete",
    "UNSAFE": "Unsafe or harmful advice",
    "UNCLEAR": "Hard for a farmer to understand",
    "LANG": "Language or translation problem",
    "SCOPE": "Topic not covered by the knowledge base",
    "OTHER": "Other",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    advisory_id TEXT PRIMARY KEY REFERENCES advisories(id),
    category TEXT NOT NULL,
    correction TEXT NOT NULL DEFAULT '',
    missing TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS purpose (
    advisory_id TEXT PRIMARY KEY REFERENCES advisories(id),
    purpose TEXT NOT NULL CHECK(purpose IN ('test','real')));
"""

PURPOSES = {"test": "Test question - checking Murimi Fara's answer",
            "real": "Real farmer's question"}

_PHONE = re.compile(r"(?:\+?\d[\d\s\-()]{7,}\d)")
_ID_NUMBER = re.compile(r"\b\d{2}[\s-]?\d{6,7}[\s-]?[A-Z][\s-]?\d{2}\b", re.I)   # Zimbabwe national ID shape
_ENTRY = re.compile(r"^[A-Z]\d{1,2}$")


def scrub(text):
    """Remove phone numbers and national-ID-like numbers before text leaves the laptop.
    Only runs of 9+ digits count as phone numbers, so dates (2026-10-15) survive."""
    text = _ID_NUMBER.sub("[number removed]", text or "")
    return _PHONE.sub(lambda m: "[number removed]" if sum(c.isdigit() for c in m.group()) >= 9 else m.group(),
                      text)


def _ensure(store):
    with store.connect() as db:
        db.executescript(SCHEMA)


def installation_id(store):
    """Random 4-character code for this laptop, made once. Identifies the laptop in
    exports and SMS codes without naming the office or the officer."""
    _ensure(store)
    with store.transaction() as db:
        row = db.execute("SELECT value FROM meta WHERE key='installation'").fetchone()
        if row:
            return row[0]
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"            # no 0/O or 1/I mix-ups
        code = "".join(secrets.choice(alphabet) for _ in range(4))
        db.execute("INSERT INTO meta VALUES ('installation', ?)", (code,))
        return code


def record(store, advisory_id, category, correction="", missing=""):
    category = (category or "NONE").upper()
    if category not in CATEGORIES:
        raise ValueError("Unknown problem category")
    correction = " ".join((correction or "").split())[:2000]
    missing = " ".join((missing or "").split())[:300]
    _ensure(store)
    with store.transaction() as db:
        if db.execute("SELECT 1 FROM advisories WHERE id=?", (advisory_id,)).fetchone() is None:
            raise ValueError("Unknown advisory")
        if db.execute("SELECT 1 FROM feedback WHERE advisory_id=?", (advisory_id,)).fetchone():
            raise ValueError("Feedback already recorded for this advisory")
        db.execute("INSERT INTO feedback VALUES (?,?,?,?,?)",
                   (advisory_id, category, correction, missing, datetime.now(timezone.utc).isoformat()))
        store._audit(db, "feedback_recorded", "officer",
                     {"id": advisory_id, "category": category,
                      "correction_sha256": hashlib.sha256(correction.encode()).hexdigest(),
                      "missing": bool(missing)})


def set_purpose(store, advisory_id, purpose):
    """Whether the officer asked this to test the advisor or for a real farmer.
    Set once, when the draft is made; tests are reported separately."""
    if purpose not in PURPOSES:
        raise ValueError("Purpose must be 'test' or 'real'")
    _ensure(store)
    with store.transaction() as db:
        db.execute("INSERT OR IGNORE INTO purpose VALUES (?,?)", (advisory_id, purpose))
        store._audit(db, "purpose_recorded", "officer", {"id": advisory_id, "purpose": purpose})


def get_purpose(store, advisory_id):
    _ensure(store)
    with store.connect() as db:
        row = db.execute("SELECT purpose FROM purpose WHERE advisory_id=?", (advisory_id,)).fetchone()
    return row[0] if row else ""


def get(store, advisory_id):
    _ensure(store)
    with store.connect() as db:
        row = db.execute("SELECT * FROM feedback WHERE advisory_id=?", (advisory_id,)).fetchone()
    return dict(row) if row else None


def entry_ids(document):
    return [s["id"] for s in document.get("sources", []) if _ENTRY.match(str(s.get("id", "")))]


def sms_code(store, advisory_id):
    """One-SMS summary, e.g. 'MF B3,F1 R UNSAFE K7Q2'. None if no decision yet."""
    advisory = store.get(advisory_id)
    if advisory["state"] == "pending":
        return None
    fb = get(store, advisory_id) or {"category": "NONE"}
    ids = ",".join(entry_ids(advisory["document"])) or "-"
    return f"MF {ids} {'A' if advisory['state'] == 'approved' else 'R'} {fb['category']} {installation_id(store)}"


def _decided_at(events, advisory_id):
    for e in events:
        if e["event"] in {"advisory_approved", "advisory_rejected"} and e["payload"].get("id") == advisory_id:
            return e["timestamp"]
    return ""


def export_file(store, district="", app_version=""):
    """Everything decided on this laptop, anonymised, as a JSON-serialisable dict."""
    _ensure(store)
    events = store.audit()                      # also proves the log is intact
    with store.connect() as db:
        ids = [r[0] for r in db.execute("SELECT id FROM advisories WHERE state != 'pending' ORDER BY rowid")]
    reviews = []
    for advisory_id in ids:
        a = store.get(advisory_id)
        doc = a["document"]
        fb = get(store, advisory_id) or {}
        reviews.append({
            "id": advisory_id,
            "decision": a["state"],
            "purpose": get_purpose(store, advisory_id) or "unknown",
            "decided_at": _decided_at(events, advisory_id),
            "category": fb.get("category", "NONE"),
            "reason": scrub(a.get("reason") or ""),
            "correction": scrub(fb.get("correction", "")),
            "missing_topic": scrub(fb.get("missing", "")),
            "question": scrub(doc.get("query", "")),
            "draft": scrub(doc.get("text", "")),
            "entries": entry_ids(doc),
            "urgent": bool(doc.get("urgent")),
            "region": doc.get("region", ""),
            "generation": doc.get("generation", ""),
            "digest": a["digest"],
        })
    return {"format": FORMAT, "installation": installation_id(store),
            "district": " ".join((district or "").split())[:80],
            "app_version": app_version, "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "audit_events": len(events), "reviews": reviews}


def export_json(store, district="", app_version=""):
    return json.dumps(export_file(store, district, app_version), ensure_ascii=False, indent=1)
