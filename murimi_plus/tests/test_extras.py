"""Extras: outbreak counts, checked content only, farm records, pages."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import rag
from murimi_plus import content, outbreak
from murimi_plus.farm import Farm
from murimi_plus.router import condition_titles, create_router

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
CHUNKS = rag.load_chunks(rag.CORPUS_PATH)
TITLES = condition_titles(CHUNKS, rag)


def rec(days_ago, entries, province=""):
    r = {"time": (NOW - timedelta(days=days_ago)).isoformat(), "kind": "answered", "entries": entries}
    if province:
        r["province"] = province
    return r


class OutbreakTests(unittest.TestCase):
    def test_titles_are_conditions_only(self):
        self.assertIn("B3", TITLES)
        self.assertIn("D1", TITLES)
        self.assertNotIn("A1", TITLES)        # natural regions is not a disease
        self.assertNotIn("F1", TITLES)        # symptom pattern, not a condition

    def test_new_spike_is_flagged(self):
        r = outbreak.summarise([rec(1, ["G1"], "Masvingo")] * 4, TITLES, now=NOW)
        self.assertEqual([a["entry"] for a in r["alerts"]], ["G1"])
        self.assertEqual(r["alerts"][0]["provinces"], {"Masvingo": 4})

    def test_steady_level_is_not_flagged(self):
        records = [rec(d, ["B3"]) for d in (1, 2, 3)] + [rec(8 + 7 * w + i, ["B3"]) for w in range(4) for i in range(3)]
        r = outbreak.summarise(records, TITLES, now=NOW)
        self.assertEqual(r["alerts"], [])
        self.assertEqual(r["table"][0]["previous_4_weeks"], 12)

    def test_below_minimum_is_not_flagged(self):
        r = outbreak.summarise([rec(1, ["G1"])] * 2, TITLES, now=NOW)
        self.assertEqual(r["alerts"], [])

    def test_non_conditions_and_bad_lines_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "log.jsonl"
            path.write_text("not json\n" + json.dumps({"kind": "needs_more_detail", "query": "x"}) + "\n"
                            + json.dumps(rec(1, ["A1", "D1"])) + "\n", encoding="utf-8")
            r = outbreak.summarise(outbreak.read_log(path), TITLES, now=NOW)
        self.assertEqual(r["total_matches"], 1)


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(content, "DATA_DIR", self.tmp.name)
        p.start(); self.addCleanup(p.stop)
        a = mock.patch.object(content, "AUDIO_DIR", self.tmp.name)
        a.start(); self.addCleanup(a.stop)

    def write(self, name, data):
        Path(self.tmp.name, name).write_text(json.dumps(data), encoding="utf-8")

    def test_unreviewed_summary_never_shown(self):
        self.write("local_summaries.json", {"entries": {"B3": {"en": "Call the vet.", "sn": "x", "reviewed": False}}})
        self.assertIsNone(content.summary_for(["B3"], "shona"))

    def test_english_shown_once(self):
        self.write("local_summaries.json", {"entries": {"B3": {"en": "Call the vet.", "reviewed": True}}})
        self.assertEqual(len(content.summary_for(["B3"], "english")["texts"]), 1)

    def test_reviewed_summary_in_farmers_language_first(self):
        self.write("local_summaries.json", {"entries": {"B3": {"title": "Redwater", "en": "Call the vet.",
                                                               "sn": "SHONA TEXT", "reviewed": True}}})
        Path(self.tmp.name, "B3_sn.mp3").write_bytes(b"x")
        s = content.summary_for(["B3"], "shona")
        self.assertEqual([t["lang"] for t in s["texts"]], ["sn", "en"])
        self.assertEqual(s["texts"][0]["audio"], "/audio/B3_sn.mp3")

    def test_placeholder_contacts_hidden(self):
        self.write("help_directory.json", {"contacts": {"Masvingo": [
            {"type": "vet", "name": "FILL IN: office name", "phone": "FILL IN"},
            {"type": "vet", "name": "Masvingo vet office", "phone": "+263 000"}]}})
        found = content.contacts_for("Masvingo", "animal")
        self.assertEqual([c["name"] for c in found], ["Masvingo vet office"])

    def test_blank_outlook_not_shown(self):
        self.write("seasonal_outlook.json", {"regions": {"II": {"outlook": ""}, "IV": {"outlook": "below normal"}}})
        self.assertIsNone(content.outlook_for("II"))
        self.assertEqual(content.outlook_for("IV")["outlook"], "below normal")

    def test_outlook_only_with_planting_advice(self):
        self.write("seasonal_outlook.json", {"season": "2026/27", "regions": {"IV": {"outlook": "below normal"}}})
        self.assertIsNotNone(content.extras_for_answer(["D2"], region="IV")["outlook"])
        self.assertIsNone(content.extras_for_answer(["B3"], region="IV")["outlook"])
        self.assertEqual(content.region_in("plant maize in region 4"), "IV")
        self.assertEqual(content.region_in("regional office"), "")

    def test_audio_name_cannot_escape(self):
        self.assertIsNone(content.audio_for("../app", "sn"))

    def test_shipped_templates_show_nothing_unchecked(self):
        mock.patch.stopall()
        for cid in TITLES:
            self.assertIsNone(content.summary_for([cid]), cid)
        for p in outbreak.PROVINCES:
            self.assertEqual(content.contacts_for(p, "all"), [], p)
        for r in ["I", "II", "III", "IV", "V"]:
            self.assertIsNone(content.outlook_for(r))


class FarmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.farm = Farm(Path(self.tmp.name) / "farm.sqlite3")

    def test_repeating_reminder_moves_forward(self):
        rid = self.farm.add_suggested("dipping", "2026-11-02")
        self.assertTrue(self.farm.complete(rid, on=date(2026, 11, 3)))
        self.assertEqual(self.farm.reminders(today=date(2026, 11, 3))[0]["due"], "2026-11-09")
        self.assertEqual(self.farm.records()[0]["subject"], "Reminder done")

    def test_one_off_reminder_closes(self):
        rid = self.farm.add_reminder("2026-10-01", "Vaccinate chickens", 0)
        self.assertTrue(self.farm.reminders(today=date(2026, 10, 15))[0]["overdue"])
        self.farm.complete(rid)
        self.assertEqual(self.farm.reminders(), [])

    def test_bad_input_refused(self):
        with self.assertRaises(ValueError):
            self.farm.add_record("not a date", "Cattle", "dipped")
        with self.assertRaises(ValueError):
            self.farm.add_record("2026-10-01", "  ", "dipped")
        with self.assertRaises(ValueError):
            self.farm.add_reminder("2026-10-01", "x", 999)


class PageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "query_log.jsonl"
        now = datetime.now(timezone.utc)
        self.log.write_text("".join(json.dumps({"time": now.isoformat(), "kind": "answered", "entries": ["G1"],
                                                "province": "Masvingo", "query": "SECRET FARMER TEXT"}) + "\n"
                                    for _ in range(3)), encoding="utf-8")
        app = FastAPI()
        app.include_router(create_router(CHUNKS, rag, str(self.log), Path(self.tmp.name) / "farm.sqlite3"))
        self.client = TestClient(app, base_url="http://127.0.0.1:8000")
        self.addCleanup(self.client.close)

    def test_dashboard_shows_counts_not_messages(self):
        page = self.client.get("/extras/dashboard").text
        self.assertIn("Look into: Lumpy Skin Disease", page)
        self.assertIn("Masvingo: 3", page)
        self.assertNotIn("SECRET", page)
        self.assertNotIn("SECRET", self.client.get("/api/extras/outbreak").text)

    def test_farm_form_flow_and_escaping(self):
        r = self.client.post("/extras/farm/record", data={"day": "2026-10-15", "subject": "<b>Cattle</b>",
                                                          "note": "dipped"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        page = self.client.get("/extras/farm").text
        self.assertIn("&lt;b&gt;Cattle&lt;/b&gt;", page)
        bad = self.client.post("/extras/farm/record", data={"day": "x", "subject": "a", "note": "b"})
        self.assertIn("Invalid isoformat", bad.text)

    def test_cross_site_post_refused(self):
        r = self.client.post("/extras/farm/record", data={"day": "2026-10-15", "subject": "a", "note": "b"},
                             headers={"Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 403)

    def test_audio_route_rejects_other_files(self):
        self.assertEqual(self.client.get("/audio/app.py").status_code, 404)

    def test_answer_extras_ignores_bad_ids(self):
        r = self.client.get("/api/extras/answer", params={"ids": "B3,../x", "province": "Masvingo"}).json()
        self.assertEqual(set(r), {"summary", "contacts", "outlook"})


if __name__ == "__main__":
    unittest.main()
