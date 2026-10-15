"""Transactional drafts, human decisions, approved exports and hash-linked audit."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS advisories (
                    id TEXT PRIMARY KEY, document TEXT NOT NULL, digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('pending','approved','rejected')),
                    reviewer TEXT, reason TEXT);
                CREATE TABLE IF NOT EXISTS audit (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                    event TEXT NOT NULL, actor TEXT NOT NULL, payload TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outbox (
                    advisory_id TEXT PRIMARY KEY REFERENCES advisories(id),
                    document TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS immutable_document
                    BEFORE UPDATE OF document,digest ON advisories
                    BEGIN SELECT RAISE(ABORT,'advisory content is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS append_only_audit_update BEFORE UPDATE ON audit
                    BEGIN SELECT RAISE(ABORT,'audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS append_only_audit_delete BEFORE DELETE ON audit
                    BEGIN SELECT RAISE(ABORT,'audit is append-only'); END;
            """)
        self.path.chmod(0o600)

    def _open(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def connect(self):
        """Commit on success and ALWAYS close. sqlite3's own `with` only commits;
        a connection left open keeps the file locked on Windows (WinError 32)."""
        db = self._open()
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        db = self._open()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _audit(self, db, event, actor, payload):
        previous = db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        previous_hash = previous[0] if previous else "0" * 64
        timestamp = datetime.now(timezone.utc).isoformat()
        fields = {"timestamp": timestamp, "event": event, "actor": actor,
                  "payload": payload, "previous_hash": previous_hash}
        db.execute("INSERT INTO audit(timestamp,event,actor,payload,previous_hash,hash) VALUES (?,?,?,?,?,?)",
                   (timestamp, event, actor, canonical(payload), previous_hash, digest(fields)))

    def log(self, event, actor, payload):
        with self.transaction() as db:
            self._audit(db, event, actor, payload)

    def stage(self, document):
        advisory_id = str(uuid.uuid4())
        content_hash = digest(document)
        with self.transaction() as db:
            db.execute("INSERT INTO advisories(id,document,digest,state) VALUES (?,?,?,'pending')",
                       (advisory_id, canonical(document), content_hash))
            self._audit(db, "advisory_staged", "agent", {"id": advisory_id, "digest": content_hash})
        return {"id": advisory_id, "digest": content_hash, "state": "pending"}

    def get(self, advisory_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM advisories WHERE id=?", (advisory_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown advisory")
        result = dict(row)
        result["document"] = json.loads(result["document"])
        if digest(result["document"]) != result["digest"]:
            raise ValueError("Advisory integrity check failed")
        return result

    def list(self, limit=50):
        """Newest first, for the officer review page."""
        with self.connect() as db:
            rows = db.execute("SELECT a.id, a.document, a.state, a.reviewer, "
                              "(SELECT timestamp FROM audit WHERE event='advisory_staged' "
                              " AND json_extract(payload,'$.id')=a.id) AS staged_at, "
                              "EXISTS(SELECT 1 FROM outbox o WHERE o.advisory_id=a.id) AS exported "
                              "FROM advisories a ORDER BY a.rowid DESC LIMIT ?", (limit,)).fetchall()
        result = []
        for row in rows:
            document = json.loads(row["document"])
            result.append({"id": row["id"], "state": row["state"], "reviewer": row["reviewer"],
                           "staged_at": row["staged_at"], "exported": bool(row["exported"]),
                           "query": document.get("query", ""), "urgent": document.get("urgent", False)})
        return result

    def review(self, advisory_id, content_hash, reviewer, approve, reason):
        # This method is used ONLY by the trusted operator CLI, never an MCP tool.
        if not reviewer.strip() or not reason.strip() or len(reason) > 2000:
            raise ValueError("Reviewer identity and a reason (1–2000 characters) are required")
        with self.transaction() as db:
            row = db.execute("SELECT * FROM advisories WHERE id=?", (advisory_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown advisory")
            if row["state"] != "pending":
                raise ValueError("Advisory already reviewed; create a new draft for revisions")
            if row["digest"] != content_hash or digest(json.loads(row["document"])) != content_hash:
                raise ValueError("Review digest does not match the immutable draft")
            state = "approved" if approve else "rejected"
            db.execute("UPDATE advisories SET state=?,reviewer=?,reason=? WHERE id=?",
                       (state, reviewer, reason, advisory_id))
            self._audit(db, "advisory_" + state, reviewer,
                        {"id": advisory_id, "digest": content_hash, "reason": reason})
        return self.get(advisory_id)

    def export(self, advisory_id, actor):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM advisories WHERE id=?", (advisory_id,)).fetchone()
            if row is None or row["state"] != "approved":
                raise ValueError("Only a human-approved advisory can be exported")
            document = json.loads(row["document"])
            if digest(document) != row["digest"]:
                raise ValueError("Advisory integrity check failed")
            exists = db.execute("SELECT 1 FROM outbox WHERE advisory_id=?", (advisory_id,)).fetchone()
            if not exists:
                db.execute("INSERT INTO outbox VALUES (?,?)", (advisory_id, row["document"]))
                self._audit(db, "advisory_exported", actor, {"id": advisory_id, "digest": row["digest"]})
        return {"id": advisory_id, "approved_by": row["reviewer"],
                "digest": row["digest"], "document": document}

    def audit(self):
        with self.connect() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM audit ORDER BY seq")]
        previous_hash = "0" * 64
        for expected_seq, row in enumerate(rows, 1):
            payload = json.loads(row["payload"])
            fields = {k: row[k] for k in ("timestamp", "event", "actor", "previous_hash")}
            fields["payload"] = payload
            if row["seq"] != expected_seq or row["previous_hash"] != previous_hash or row["hash"] != digest(fields):
                raise ValueError("Audit integrity check failed")
            previous_hash = row["hash"]
            row["payload"] = payload
        return rows
