"""SMS goes out only after human approval, once per number, and is audited."""
import json
from pathlib import Path
import tempfile
import unittest

try:
    import httpx
    from challenge_agent.store import Store
    from murimi_plus import sms
except ImportError as missing:  # the SMS feature needs the challenge agent folder
    SKIP = f"SMS tests need challenge_agent and httpx in this folder ({missing})"
else:
    SKIP = None

DOC = {"query": "cow red urine", "urgent": True,
       "text": "### Likely condition\nThe signs fit **Redwater**.\n- Call the vet today."}


@unittest.skipIf(SKIP, SKIP or "")
class SmsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "agent.sqlite3")
        staged = self.store.stage(DOC)
        self.id, self.digest = staged["id"], staged["digest"]
        self.sent = []

        def handler(request):
            self.sent.append((request.url.path, request.headers.get("authorization"), json.loads(request.content)))
            return httpx.Response(202, json={"id": "abc123", "state": "Pending"})
        self.client = httpx.Client(transport=httpx.MockTransport(handler))
        self.gateway = {"url": "http://phone:8080", "user": "u", "password": "p"}

    def approve(self):
        self.store.review(self.id, self.digest, "T. Moyo (web review)", True, "checked")

    def test_pending_advisory_cannot_be_sent(self):
        with self.assertRaises(ValueError):
            sms.send(self.store, self.id, "0771234567", gateway=self.gateway, client=self.client)
        self.assertEqual(self.sent, [])

    def test_approved_advisory_sent_once_and_audited(self):
        self.approve()
        result = sms.send(self.store, self.id, "077 123 4567", gateway=self.gateway, client=self.client, actor="op")
        path, auth, body = self.sent[0]
        self.assertEqual(path, "/message")
        self.assertTrue(auth.startswith("Basic "))
        self.assertEqual(body["phoneNumbers"], ["+263771234567"])
        text = body["textMessage"]["text"]
        self.assertTrue(text.startswith("URGENT: Likely condition"))
        self.assertNotIn("**", text)
        self.assertIn("checked by T. Moyo.", text)
        self.assertEqual(result["gateway_id"], "abc123")
        events = self.store.audit()
        sent = [e for e in events if e["event"] == "sms_sent"][0]["payload"]
        self.assertEqual(sent["phone_last3"], "567")
        self.assertNotIn("771234567", json.dumps(events))
        self.assertIn("advisory_exported", [e["event"] for e in events])
        with self.assertRaises(ValueError):
            sms.send(self.store, self.id, "+263771234567", gateway=self.gateway, client=self.client)
        self.assertEqual(len(self.sent), 1)

    def test_long_text_needs_officer_version(self):
        doc = dict(DOC, text="Long advice. " * 60)
        staged = self.store.stage(doc)
        self.store.review(staged["id"], staged["digest"], "T. Moyo", True, "ok")
        with self.assertRaises(ValueError):
            sms.build_message(self.store.get(staged["id"]))
        msg = sms.build_message(self.store.get(staged["id"]), "Likely redwater. Call the vet today.")
        self.assertTrue(msg.startswith("URGENT: Likely redwater"))

    def test_dry_run_without_gateway(self):
        self.approve()
        result = sms.send(self.store, self.id, "0771234567", gateway=None)
        self.assertTrue(result["dry_run"])
        self.assertNotIn("sms_sent", [e["event"] for e in self.store.audit()])

    def test_bad_numbers_refused(self):
        for bad in ["12345", "+27821234567", "0771234"]:
            with self.assertRaises(ValueError):
                sms.normalise_phone(bad)

    def test_gateway_error_is_logged_not_marked_sent(self):
        self.approve()
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401)))
        with self.assertRaises(ValueError):
            sms.send(self.store, self.id, "0771234567", gateway=self.gateway, client=client)
        events = [e["event"] for e in self.store.audit()]
        self.assertIn("sms_failed", events)
        self.assertNotIn("sms_sent", events)


if __name__ == "__main__":
    unittest.main()