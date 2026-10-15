"""Officer feedback, the offline reviews file, SMS codes and the team's merge tool."""
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from challenge_agent import feedback
from challenge_agent.review_app import create_app
from challenge_agent.store import Store
from tools import merge_reviews

DOC = {"query": "My cow has red urine, call me on 0771234567", "text": "### Likely condition\nRedwater.",
       "sources": [{"id": "B3", "title": "B3", "text": "x"}, {"id": "F1", "title": "F1", "text": "y"}],
       "urgent": True, "region": ""}


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "agent.sqlite3")
        s = self.store.stage(DOC)
        self.id, self.digest = s["id"], s["digest"]

    def decide(self, approve, category="NONE", correction="", missing=""):
        self.store.review(self.id, self.digest, "T. Moyo (web review)", approve, "checked")
        feedback.record(self.store, self.id, category, correction, missing)

    def test_sms_code_and_installation_id_are_stable(self):
        self.assertIsNone(feedback.sms_code(self.store, self.id))          # pending
        self.decide(False, "UNSAFE")
        code = feedback.sms_code(self.store, self.id)
        inst = feedback.installation_id(self.store)
        self.assertEqual(code, f"MF B3,F1 R UNSAFE {inst}")
        self.assertEqual(len(code), len(code.encode()))                    # plain ASCII
        self.assertLessEqual(len(code), 160)
        self.assertEqual(feedback.installation_id(self.store), inst)

    def test_export_is_anonymised(self):
        self.decide(False, "WRONG", "Tell them to call 0712 345 678 and the vet", "goat foot rot")
        data = json.loads(feedback.export_json(self.store, "Masvingo"))
        r = data["reviews"][0]
        self.assertEqual(data["format"], feedback.FORMAT)
        self.assertNotIn("Moyo", json.dumps(data))
        self.assertNotIn("0771234567", r["question"])
        self.assertNotIn("345", r["correction"])
        self.assertEqual(r["entries"], ["B3", "F1"])
        self.assertEqual((r["decision"], r["category"], r["missing_topic"]), ("rejected", "WRONG", "goat foot rot"))
        self.assertTrue(r["decided_at"])

    def test_dates_are_not_scrubbed(self):
        self.assertEqual(feedback.scrub("dip on 2026-10-15"), "dip on 2026-10-15")

    def test_feedback_is_audited_and_once_only(self):
        self.decide(True)
        self.assertIn("feedback_recorded", [e["event"] for e in self.store.audit()])
        with self.assertRaises(ValueError):
            feedback.record(self.store, self.id, "NONE")
        with self.assertRaises(ValueError):
            feedback.record(self.store, self.id, "MADE_UP")

    def test_merge_counts_each_review_once_and_reads_sms(self):
        self.decide(False, "UNSAFE", "Call the vet first")
        out = Path(self.tmp.name)
        f1 = out / "a.json"
        f1.write_text(feedback.export_json(self.store), encoding="utf-8")
        f2 = out / "a_copy.json"
        f2.write_text(f1.read_text(encoding="utf-8"), encoding="utf-8")
        sms = out / "sms.txt"
        sms.write_text("from 0771: MF E1 R WRONG AB12\nhello\n", encoding="utf-8")
        merge_reviews.main([str(f1), str(f2), "--sms", str(sms), "--out", str(out)])
        report = (out / "reviews_report.md").read_text(encoding="utf-8")
        self.assertIn("1 reviews from 2 file(s), 1 SMS code(s)", report)
        self.assertIn("Unsafe advice reported", report)
        self.assertIn("| E1 | 1 | 0 | 1 | 0% |", report)


class ReviewPageFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "agent.sqlite3"
        self.client = TestClient(create_app(self.path), base_url="http://127.0.0.1")
        self.addCleanup(self.client.close)
        r = self.client.post("/draft", data={"query": "my maize has ragged holes and frass in the whorl"},
                             follow_redirects=False)
        self.id = r.headers["location"].rsplit("/", 1)[-1]
        self.digest = Store(self.path).get(self.id)["digest"]

    def test_reject_with_correction_then_export(self):
        form = {"digest": self.digest, "name": "T. Moyo", "decision": "reject", "reason": "Missing scouting advice",
                "confirmation": f"REJECT {self.digest[:8]}", "category": "MISSING",
                "correction": "Scout 20 plants in a W pattern first", "missing": ""}
        page = self.client.post(f"/advisory/{self.id}/review", data=form).text
        self.assertIn("Feedback for the Murimi Fara team", page)
        self.assertIn(" R MISSING ", page)
        self.assertIn("Scout 20 plants", page)
        self.assertEqual(self.client.post("/export", data={"district": "Gutu"}).status_code, 400)   # no consent
        r = self.client.post("/export", data={"district": "Gutu", "consent": "1"})
        self.assertIn("attachment; filename=murimi-fara-reviews-", r.headers["content-disposition"])
        data = r.json()
        self.assertEqual(data["district"], "Gutu")
        self.assertEqual(data["reviews"][0]["category"], "MISSING")

    def test_reject_without_category_counts_as_other(self):
        form = {"digest": self.digest, "name": "T. Moyo", "decision": "reject", "reason": "no",
                "confirmation": f"REJECT {self.digest[:8]}"}
        self.client.post(f"/advisory/{self.id}/review", data=form)
        self.assertEqual(feedback.get(Store(self.path), self.id)["category"], "OTHER")


if __name__ == "__main__":
    unittest.main()
