# Offline AI Farming Advisor for Zimbabwe

An offline, on-device AI advisor that helps Zimbabwean farmers diagnose
livestock diseases and get crop guidance by Natural Region — no internet, no
cloud, running entirely on an 8GB laptop.

Built for the [Africa Deep Tech Challenge 2026](https://adtc-2026.devpost.com/)
— Agriculture domain.

## What it does

- **Livestock disease triage** — describe symptoms, get a likely diagnosis,
  reasoning, and clear next steps (cattle tick-borne diseases, poultry disease)
- **Crop advisory** — pest identification and planting-window guidance tuned
  to Zimbabwe's Natural Regions (I–V)

Every answer is grounded in a locally-stored knowledge base
(`corpus_livestock_crops.md`), retrieved at inference time — not just the
model's general training data.

## How it works

- **Model:** Qwen2.5-1.5B-Instruct, GGUF Q4_K_M quantization
- **Runtime:** llama.cpp, CPU-only
- **Retrieval:** TF-IDF-based RAG over the local corpus (`rag.py`)

## Quick start

```bash
bash download_model.sh
python rag.py "your farming question here"
```

See `REPORT.md` for full technical details, design decisions, and benchmarks.

## African Agentic AI Design Challenge: Murimi Fara Extension Agent

> Everything in this section is new work for the challenge, in `challenge_agent/`.
> The existing Murimi Fara app above (desktop app, knowledge base, retrieval and
> safety gates, photo classifier) is reused, not rewritten. See
> [development provenance](docs/CHALLENGE_PROVENANCE.md).

### Problem

Smallholder farmers in Zimbabwe wait days for an extension officer or vet, and
officers cover very large areas. Officers need help turning a farmer's message
into checked, evidence-based advice quickly, without an AI sending unchecked
advice to farmers.

### Solution and users

An **AGRITEX extension officer or animal-health worker** types in a farmer's
message (English, Shona or Ndebele). An agent gathers evidence through MCP tools,
spots urgent cases, drafts an advisory with a local open-weights model, and stages
it for the officer. **Nothing reaches a farmer until the officer approves it.**
Every step is written to a tamper-evident audit log. It runs offline on a laptop.

### Agent architecture

The workflow is a **LangGraph** state machine (`challenge_agent/orchestrator.py`):

```text
officer question (+ Natural Region for planting questions)
  -> gather_evidence ........ MCP: search_extension_knowledge, assess_extension_urgency,
  |                           get_natural_region_context  (custom MCP server, stdio)
  +-> clarify ............... no matching evidence / blocked by safety guard -> ask for detail, store nothing
  +-> urgent_referral ....... time-critical disease -> draft opens with "contact a vet TODAY"
  +-> fetch_reference ....... fall armyworm -> third-party Fetch MCP server, FAO page (optional, online)
  +-> skip_reference ........ online requested but the FAO page is not relevant
  -> write_draft ............ Qwen2.5-1.5B-Instruct (GGUF) on local llama-server, or evidence-only template
  -> stage_for_review ....... MCP: stage_extension_advisory -> immutable PENDING draft
  -> HUMAN: officer review page or CLI -> approve / reject -> export approved advice
```

Every route the graph takes is logged (`route_selected`), so the reviewer can see
why the agent did what it did.

| Component | Technology |
| --- | --- |
| Orchestration | LangGraph 1.2 (open source) |
| MCP | Official MCP Python SDK 1.29 (FastMCP server, stdio client) |
| Custom MCP server | `challenge_agent/server.py`, 4 tools (below) |
| Third-party MCP server | Official `mcp-server-fetch` (modelcontextprotocol/servers) |
| LLM | Qwen2.5-1.5B-Instruct Q4_K_M via llama.cpp `llama-server`, CPU, offline |
| Retrieval | Existing TF-IDF retrieval + safety gates over 55 knowledge entries (`rag.py`) |
| Storage / audit | SQLite: immutable drafts, decisions, outbox, hash-chained audit log |
| Officer UI | FastAPI page on 127.0.0.1 (`challenge_agent/review_app.py`) + CLI |

### MCP tools

| Tool (custom server) | What it does | Guards |
| --- | --- | --- |
| `search_extension_knowledge` | Finds matching knowledge entries for the farmer's message | Existing scope/safety gates; no match -> clarification, not a guess |
| `assess_extension_urgency` | Flags time-critical cases and the referral to give | Triage only, not a diagnosis |
| `get_natural_region_context` | Zimbabwe Natural Region I-V context | Only I-V accepted; not a weather forecast |
| `stage_extension_advisory` | Stores the draft for human review | Server re-checks evidence itself; rejects invented citations, unsupported questions, planting advice without a region; can only create **pending** drafts |

**Third-party:** `mcp-server-fetch`, called with one fixed public FAO fall-armyworm
URL. No farmer text is sent to it, and the fetched page is shown to the officer as
untrusted background; it is never given to the model as instructions.

There is deliberately **no MCP tool to approve or export**. Those exist only in the
human interfaces.

### Human-in-the-loop

- The officer reads the draft and **all its evidence**, then types
  `APPROVE <code>` or `REJECT <code>` (the code is the first 8 characters of the
  draft's content digest), with their name and a reason.
- The decision is bound to the exact draft content (SHA-256 digest). Drafts cannot
  be edited after staging, and each draft can be decided once. Changes need a new draft.
- Only approved drafts can be exported (a local JSON hand-off). There is no
  automatic SMS/WhatsApp/email to farmers.

### Audit log

Every tool call, route decision, draft, decision and export is logged with a
timestamp. Each entry contains the hash of the previous one; `audit` (CLI) or the
Audit page re-checks the whole chain. The log is append-only (SQLite triggers).

### Setup (Windows, PowerShell)

```powershell
python -m venv .venv-challenge
.venv-challenge\Scripts\Activate.ps1
python -m pip install -r challenge_agent\requirements.txt
```
(Linux/macOS: `source .venv-challenge/bin/activate`.) Python 3.12+.
For AI drafting, start the existing model server first:
`llama-server -m model\qwen2.5-1.5b-instruct-q4_k_m.gguf -c 4096 --port 8080`.

### Usage

**Officer review page (recommended for the demo):**
```powershell
python -m challenge_agent web --model-url http://127.0.0.1:8080/completion --online
```
Open http://127.0.0.1:8765/, enter a farmer's message, read the draft and its
evidence, approve or reject, export, and view the audit log. Without `--model-url`
drafts are evidence-only templates (no AI); without `--online` the FAO fetch is off.

**Command line:**
```powershell
python -m challenge_agent draft --query "My maize has ragged holes and frass in the whorl" --model-url http://127.0.0.1:8080/completion --online
python -m challenge_agent show ADVISORY_ID
python -m challenge_agent review ADVISORY_ID --digest FULL_DIGEST --decision approve --reason "Checked against AGRITEX guidance"
python -m challenge_agent export ADVISORY_ID
python -m challenge_agent audit
```
`--require-external` fails instead of continuing when the FAO fetch is unavailable.
Drafts and the audit log are stored in `.challenge-data/` (not committed).

### Tests

```powershell
python test_rag_gate.py
python test_output_guard.py
python -m unittest discover -s challenge_agent/tests -v
```
The challenge tests make real MCP calls over stdio and cover the LangGraph routes,
approval rules, the review page, concurrency and audit tamper detection.
Results and what is still unverified: [validation](docs/CHALLENGE_VALIDATION.md).

### Changes from the design in our submission form

The form described the plan at the start of the build. What was built differs:

- Custom tools are the four above, not `get_plot_history` / `get_pest_signals` /
  `save_advisory_draft`. Plot-history and rainfall records were not built.
- The third-party MCP server is **Fetch**, not Filesystem (Fetch needs no Node.js
  on farm laptops).
- The officer interface is a local web page plus a CLI.
- LangGraph orchestration, local open-weights model, SQLite and human approval are
  as described.

### Limitations

- The 1.5B model writes the advice text only; which tools run is decided by the
  graph, not by the model (a deliberate safety choice for a small model).
- Knowledge covers 55 entries (common cattle, goat, sheep and poultry diseases;
  maize, groundnut and tomato problems; planting times). Anything else gets a
  request for detail.
- Answers are in English even for Shona/Ndebele questions; local names are added.
- Single-user, local prototype: no login or roles; anyone with access to the
  laptop account can use the review page. Not for use on a shared network.
- Drafts must be checked by a vet or AGRITEX officer; the knowledge base itself
  still needs expert review.

### Future improvements

- Plot history and seasonal rainfall data as further MCP tools.
- SMS/WhatsApp delivery of approved advice, sent only after approval.
- Officer accounts and roles; a shared server for an AGRITEX district office.
- Shona/Ndebele answers written and checked by fluent speakers.
