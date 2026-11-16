"""Farm MCP tools over the real stdio protocol: records, two-step add, outbreak counts."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import StdioServerParameters

from challenge_agent.orchestrator import ROOT, call, session
from challenge_agent.store import Store


class FarmToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 60   # quiet "took N seconds" debug noise
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.agent_db, self.farm_db, self.log = d / "agent.sqlite3", d / "farm.sqlite3", d / "query_log.jsonl"
        now = datetime.now(timezone.utc)
        lines = [{"time": (now - timedelta(days=1)).isoformat(), "kind": "answered", "entries": ["G1"],
                  "province": "Masvingo", "query": "SECRET FARMER TEXT"}] * 4
        lines.append({"time": now.isoformat(), "kind": "answered", "entries": ["B3"], "province": "Midlands"})
        self.log.write_text("".join(json.dumps(l) + "\n" for l in lines), encoding="utf-8")

    def parameters(self):
        env = dict(os.environ, MURIMI_AGENT_DB=str(self.agent_db), MURIMI_FARM_DB=str(self.farm_db),
                   MURIMI_QUERY_LOG=str(self.log))
        return StdioServerParameters(command=sys.executable, args=["-m", "challenge_agent.server"],
                                     cwd=str(ROOT), env=env)

    async def test_add_record_needs_confirmation(self):
        record = {"day": "2026-11-16", "subject": "Cattle (12)", "note": "Dipped at the communal dip tank"}
        async with session(self.parameters()) as client:
            first = await call(client, "add_farm_record", record)
            self.assertFalse(first["saved"])
            self.assertEqual(first["preview"]["subject"], "Cattle (12)")
            self.assertEqual((await call(client, "get_farm_records", {}))["records"], [])     # nothing saved yet
            wrong = await client.call_tool("add_farm_record", dict(record, confirm_code="00000000"))
            self.assertTrue(wrong.isError)
            changed = await client.call_tool("add_farm_record", dict(record, note="Something else",
                                                                      confirm_code=first["confirm_code"]))
            self.assertTrue(changed.isError)                         # code is tied to the exact record
            saved = await call(client, "add_farm_record", dict(record, confirm_code=first["confirm_code"]))
            self.assertTrue(saved["saved"])
            records = (await call(client, "get_farm_records", {"limit": 5}))["records"]
            self.assertEqual([r["note"] for r in records], ["Dipped at the communal dip tank"])
            bad_date = await client.call_tool("add_farm_record", {"day": "yesterday", "subject": "x", "note": "y"})
            self.assertTrue(bad_date.isError)
        events = [e["event"] for e in Store(self.agent_db).audit()]
        self.assertIn("farm_record_proposed", events)
        self.assertIn("farm_record_added", events)

    async def test_outbreak_summary_counts_only(self):
        async with session(self.parameters()) as client:
            report = await call(client, "get_outbreak_summary", {})
            self.assertEqual([a["entry"] for a in report["alerts"]], ["G1"])
            self.assertNotIn("SECRET", json.dumps(report))
            midlands = await call(client, "get_outbreak_summary", {"province": "Midlands"})
            self.assertEqual(midlands["alerts"], [])
            self.assertEqual([t["entry"] for t in midlands["table"]], ["B3"])
            bad = await client.call_tool("get_outbreak_summary", {"province": "Nairobi"})
            self.assertTrue(bad.isError)


if __name__ == "__main__":
    unittest.main()