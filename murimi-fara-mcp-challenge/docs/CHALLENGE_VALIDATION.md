# Challenge validation

Re-validated on 13 October 2026 against `privykurura1/Zimbabwe-agri-advisor` main
commit `72475229a68c66d337673865abff94ae1d9c2417`, on Linux with Python 3.13 and
the pinned `challenge_agent/requirements.txt` (mcp 1.29.0, mcp-server-fetch
2026.10.10). No runtime shim was needed.

## Results

| Check | Result |
| --- | --- |
| `python test_rag_gate.py` (existing) | 104/104 passed |
| `python test_output_guard.py` (existing) | 18/18 passed |
| `python -m unittest discover -s challenge_agent/tests -v` | 32/32 passed (also with ResourceWarnings as errors) |
| LangGraph routes | clarify, urgent_referral, fetch_reference, skip_reference, write_draft each tested; route decisions audited |
| Officer review page | Draft, show, approve/reject with typed confirmation, export, audit page tested; non-local hosts and cross-site posts refused; farmer text escaped |
| Real stdio MCP: initialize, tools/list, tools/call | Passed (4 custom tools; invalid region, missing argument, unknown tool and forged citation rejected) |
| CLI draft -> show -> audit, template mode | Passed; audit hash chain verified |
| CLI draft in AI mode against a stand-in llama-server | Passed; prompt uses the app's chat layout, run-on text removed, sources appended |
| Planting question without region | Asks for the Natural Region; nothing staged |
| Planting question with region (AI mode) | Answered as a question (no diagnosis), region in prompt |
| Third-party Fetch MCP server, live | Server started and fetched a public page over real MCP. The FAO page itself could not be reached from the test machine (network allow-list), so the FAO fetch must be confirmed on a connected machine |
| Fetch for a non-armyworm question | Skipped and logged as `not_relevant_to_question` |

## Not yet verified

- AI mode with the real Qwen2.5-1.5B weights on the target laptop (the stand-in
  server checks the plumbing, not answer quality).
- The live FAO fetch (`--require-external`) on an internet-connected machine; the
  Fetch server checks robots.txt by default.
- The interactive CLI review on Windows (the automated PTY test runs only on POSIX); the web review page is covered by tests.
- Agricultural correctness: an AGRITEX/veterinary officer must review drafts.
