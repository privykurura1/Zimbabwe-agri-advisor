# Murimi Fara - Offline AI Farming Advisor for Zimbabwe

Murimi Fara ("farmer's helper" in Shona) is an offline AI advisor for Zimbabwean
smallholder farmers and the extension officers who support them. It helps with
livestock disease triage and crop problems, using a local knowledge base and a
small open-weights language model that runs on an ordinary 8 GB laptop - no
internet, no cloud, and no farmer data leaving the machine.

This repository contains two parts:

1. **The Murimi Fara app** - a desktop advisor for farmers (described first).
   It was first built for the [Africa Deep Tech Challenge 2026](https://adtc-2026.devpost.com/)
   (Agriculture domain).
2. **The Murimi Fara Extension Agent** - new work for the **African Agentic AI
   Design Challenge**: an MCP-based agent that drafts advisories for extension
   officers to approve. [Jump to the agent](#african-agentic-ai-design-challenge-murimi-fara-extension-agent).

## Two parts of one product: phone planner and laptop advisor

Murimi Fara by MPKCOMTECK Technologies comes in two parts that do different jobs:

| | Murimi Fara planner (Android) | Murimi Fara advisor (this repository) |
|---|---|---|
| Where | [Google Play](https://play.google.com/store/apps/details?id=com.fambai.goho) - on the farmer's own phone | A laptop at an AGRITEX office, with a lead farmer, or at a demo stand |
| Job | **Planning:** how long food, water and feed will last, what to buy, what to sell, and a season plan | **Problems:** what is wrong with a sick animal or a damaged crop, and what to do now |
| How | Calculations from the farmer's own numbers | A checked knowledge base and a small offline AI model |
| Internet | Not needed | Not needed; phones on the laptop's Wi‑Fi can use it too |

How they connect:

- **Now:** a farmer uses the planner on their phone every day. When an animal or crop
  has a problem, they ask the advisor on the laptop, either directly or from a phone
  on the laptop's Wi‑Fi (the address is shown at the top of the advisor page).
- **Planned, not built yet:**
  1. An "Ask the advisor" button in the phone app.
  2. The same checked contacts and short Shona/Ndebele summaries shipped inside the phone app.
  3. Farm records and reminders moved to the phone, so reminders arrive as phone notifications.
  4. Farmers sending questions from the phone to an extension officer, who approves the
     answer before it is sent back by SMS.

The AI model runs on the laptop only. Running it on phones has not been tested yet
(see [docs/ANDROID_PLAN.md](docs/ANDROID_PLAN.md)).

## What the app does

- **Livestock triage** - describe what you see (for example "my cow has a high
  fever and keeps walking in circles") and get the likely condition, other signs to
  check, and next steps. Covers common diseases of cattle, goats, sheep and
  chickens, including tick-borne diseases.
- **Crop advice** - pests and diseases of maize, groundnuts and tomatoes, and
  planting times by Natural Region (I-V).
- **Fall armyworm photo check** - an on-device image classifier (MobileNetV2,
  OpenCV DNN) flags likely fall armyworm damage on maize leaves.
- **English, Shona and Ndebele questions** - questions in all three are routed to
  the right knowledge; answers are in simple English with local disease names.
- **Safety first** - urgent cases are flagged; questions about medicine doses,
  human illness or sudden deaths (possible anthrax) get fixed safety guidance
  instead of a model answer; and when the knowledge base has no match, the app
  asks for more detail rather than guessing.

Every answer is grounded in a local knowledge base of 55 entries
(`corpus_livestock_crops.md`), retrieved for each question. Answers say "the signs
fit..." and always point to a veterinary or AGRITEX officer to confirm.

## How it works

- **Model:** Qwen2.5-1.5B-Instruct, GGUF Q4_K_M (about 1 GB), run with llama.cpp
  `llama-server` on the CPU. A typical answer takes about 30-60 seconds on a
  4-core laptop.
- **Retrieval:** TF-IDF search with a grounding gate, crop/livestock routing and
  safety guards (`rag.py`).
- **Output guard:** removes run-on text, invented entries and repeated advice
  before the farmer sees the answer.
- **App:** FastAPI backend (`app.py`) and a browser-style interface (`index.html`),
  packaged as a Windows desktop app (`desktop_app.py`, PyInstaller, Inno Setup).

## Quick start

**Windows app (easiest):** download `MurimiFara-Setup` from the
[Releases page](https://github.com/privykurura1/Zimbabwe-agri-advisor/releases),
install it and open Murimi Fara. Everything, including the model, is inside.

**From source:**

```bash
bash download_model.sh                      # downloads the Qwen2.5-1.5B model to model/
pip install fastapi uvicorn python-multipart scikit-learn numpy opencv-python-headless
llama-server -m model/qwen2.5-1.5b-instruct-q4_k_m.gguf -c 4096 --port 8080
python -m uvicorn app:app --port 8000      # in a second terminal
```

Then open http://127.0.0.1:8000/. On Windows, `start_advisor.bat` starts both.

**Tests:** `python test_rag_gate.py` (routing and safety, 104 checks),
`python test_output_guard.py` (output clean-up), and `python test_model_behaviour.py`
(asks the running model 14 farmer questions and checks each answer).

See `REPORT.md` and `technical_report.md` for design decisions and benchmarks.

**Important:** Murimi Fara gives guidance, not a diagnosis. The knowledge base
still needs review by a veterinarian and an agronomist before wide use with farmers.

## Extras for real-world use

These are optional and are loaded only if they work, so they cannot break the advisor
(`murimi_plus/`, full guide in [docs/EXTRAS.md](docs/EXTRAS.md)):

- **Outbreak watch** (`/extras/dashboard`): weekly counts of which diseases farmers
  ask about, by province, with a simple alert when one rises sharply. It shows
  counts only, never farmers' messages.
- **Find help** (`/extras/help`): vet, AGRITEX and dip-tank contacts by province,
  also shown under answers.
- **Farm records and reminders** (`/extras/farm`): dated notes and repeating
  reminders, such as weekly dipping in the hot wet season.
- **Short summaries in Shona and Ndebele, with audio:** shown only after a speaker
  and an expert have checked them.
- **Seasonal rainfall outlook** next to planting advice, copied from the official
  forecast.
- **SMS:** an officer can text an approved advisory to a farmer through an Android
  SMS gateway phone.
- **More photo checks:** add trained image classifiers in `models/photo/`, with a
  training script.
- **Low-end mode:** smaller settings on laptops with little memory.
- **Pilot kit:** an expert review sheet, a pilot plan, pilot metrics and a
  partnership letter template.

The contact list, the translations, the recordings and the rainfall outlook ship
**empty** on purpose, so that they are filled in with checked, real information
rather than guesses. Run the tests with `python -m unittest discover -s murimi_plus/tests -t .`

## African Agentic AI Design Challenge: Murimi Fara Extension Agent

> Everything in this section is new work for the African Agentic AI Design Challenge, in `challenge_agent/`.
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