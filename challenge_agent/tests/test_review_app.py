"""Officer review page: the human approval step in the browser."""
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from challenge_agent.review_app import create_app
from challenge_agent.store import Store

QUESTION = "my maize has ragged holes and frass in the whorl"


class ReviewPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "agent.sqlite3"
        self.client = TestClient(create_app(self.path), base_url="http://127.0.0.1")
        self.addCleanup(self.client.close)

    def make_draft(self, query=QUESTION, region=""):
        return self.client.post("/draft", data={"query": query, "region": region}, follow_redirects=False)

    def advisory_id(self, response):
        self.assertEqual(response.status_code, 303)
        return response.headers["location"].rsplit("/", 1)[-1]

    def test_full_flow_draft_review_export_audit(self):
        advisory_id = self.advisory_id(self.make_draft())
        page = self.client.get(f"/advisory/{advisory_id}").text
        self.assertIn("Fall Armyworm", page)
        self.assertIn("Your decision", page)
        digest = Store(self.path).get(advisory_id)["digest"]
        # Export before approval is refused.
        self.assertEqual(self.client.post(f"/advisory/{advisory_id}/export").status_code, 400)
        form = {"digest": digest, "name": "T. Moyo", "decision": "approve",
                "reason": "Checked against AGRITEX guidance", "confirmation": f"APPROVE {digest[:8]}"}
        self.client.post(f"/advisory/{advisory_id}/review", data=form)
        advisory = Store(self.path).get(advisory_id)
        self.assertEqual(advisory["state"], "approved")
        self.assertIn("T. Moyo (web review", advisory["reviewer"])
        exported = self.client.post(f"/advisory/{advisory_id}/export")
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.json()["id"], advisory_id)
        audit = self.client.get("/audit").text
        self.assertIn("Audit chain verified", audit)
        self.assertIn("advisory_approved", audit)

    def test_wrong_confirmation_saves_nothing(self):
        advisory_id = self.advisory_id(self.make_draft())
        digest = Store(self.path).get(advisory_id)["digest"]
        form = {"digest": digest, "name": "T. Moyo", "decision": "approve",
                "reason": "ok", "confirmation": "APPROVE"}
        page = self.client.post(f"/advisory/{advisory_id}/review", data=form).text
        self.assertIn("Confirmation did not match", page)
        self.assertEqual(Store(self.path).get(advisory_id)["state"], "pending")

    def test_tampered_digest_is_refused(self):
        advisory_id = self.advisory_id(self.make_draft())
        form = {"digest": "0" * 64, "name": "T. Moyo", "decision": "approve",
                "reason": "ok", "confirmation": "APPROVE 00000000"}
        self.client.post(f"/advisory/{advisory_id}/review", data=form)
        self.assertEqual(Store(self.path).get(advisory_id)["state"], "pending")

    def test_reject_then_no_second_decision(self):
        advisory_id = self.advisory_id(self.make_draft())
        digest = Store(self.path).get(advisory_id)["digest"]
        reject = {"digest": digest, "name": "T. Moyo", "decision": "reject",
                  "reason": "Needs a field visit", "confirmation": f"REJECT {digest[:8]}"}
        self.client.post(f"/advisory/{advisory_id}/review", data=reject)
        approve = dict(reject, decision="approve", confirmation=f"APPROVE {digest[:8]}")
        page = self.client.post(f"/advisory/{advisory_id}/review", data=approve).text
        self.assertIn("already reviewed", page)
        self.assertEqual(Store(self.path).get(advisory_id)["state"], "rejected")

    def test_planting_without_region_asks_and_stores_nothing(self):
        page = self.make_draft("when should I plant maize").text
        self.assertIn("needs more information", page)
        self.assertEqual(Store(self.path).list(), [])

    def test_only_local_requests(self):
        remote = TestClient(create_app(self.path), base_url="http://evil.example")
        self.addCleanup(remote.close)
        self.assertEqual(remote.get("/").status_code, 403)
        cross_site = self.client.post("/draft", data={"query": QUESTION},
                                      headers={"Origin": "http://evil.example"})
        self.assertEqual(cross_site.status_code, 403)
        self.assertEqual(Store(self.path).list(), [])

    def test_farmer_text_is_escaped(self):
        advisory_id = self.advisory_id(self.make_draft(QUESTION + " <script>alert(1)</script>"))
        page = self.client.get(f"/advisory/{advisory_id}").text
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)


class MountedInMainAppTests(unittest.TestCase):
    """Inside the main Murimi Fara app the page lives at /officer."""
    def setUp(self):
        from fastapi import FastAPI
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "agent.sqlite3"
        main = FastAPI()
        main.mount("/officer", create_app(self.path, prefix="/officer"))
        self.client = TestClient(main, base_url="http://127.0.0.1:8000")
        self.addCleanup(self.client.close)

    def test_links_and_redirects_use_prefix(self):
        home = self.client.get("/officer/?q=cow+red+urine").text
        self.assertIn("action='/officer/draft'", home)
        self.assertIn(">cow red urine</textarea>", home)
        r = self.client.post("/officer/draft", data={"query": QUESTION}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/officer/advisory/"))
        page = self.client.get(r.headers["location"]).text
        self.assertIn("action='/officer/advisory/", page)
        self.assertNotIn("href='/advisory/", page)

    def test_phones_on_wifi_are_refused(self):
        phone = TestClient(self.client.app, base_url="http://192.168.1.20:8000")
        self.addCleanup(phone.close)
        self.assertEqual(phone.get("/officer/").status_code, 403)


if __name__ == "__main__":
    unittest.main()
