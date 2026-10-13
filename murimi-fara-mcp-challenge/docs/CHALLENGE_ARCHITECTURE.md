# Murimi Fara MCP Agricultural Extension Agent

This is new African Agentic AI Design Challenge development. It is an additive
companion to the existing Murimi Fara application, not a replacement or a change
to the historical Africa Deep Tech Challenge submission.

## Existing system

`app.py` serves the browser UI in `index.html` and connects to a local llama-server.
`desktop_app.py`, launch scripts and installer support the existing desktop app.
`rag.py` uses TF-IDF over 55 agricultural reference entries, routes English/Shona/
Ndebele questions, limits unsupported diagnoses and includes urgent/scope gates.
The image classifier and model assets remain part of that existing application.

None of those execution paths imports the challenge agent. The new package only
reads the original corpus and calls the existing retrieval functions through
`knowledge.py`. The legacy web API is not silently routed through the new approval
workflow; that workflow applies to new challenge advisories only.

## New orchestration (LangGraph)

```text
Officer question (review page or CLI) + Natural Region when planting
          |
          v
LangGraph StateGraph (challenge_agent/orchestrator.py)
  gather_evidence --MCP stdio--> custom server: search_extension_knowledge,
          |                      assess_extension_urgency, get_natural_region_context
          |                      -> existing rag.py + corpus (read-only)
          +--> clarify (no evidence / blocked) ------------------------> END, nothing stored
          +--> urgent_referral (time-critical) --+
          +--> fetch_reference (armyworm, online) --MCP--> third-party mcp-server-fetch (FAO page)
          +--> skip_reference (online, not relevant)
          v
  write_draft -> local llama-server (Qwen2.5-1.5B) via rag.build_prompt, or evidence template
          v
  stage_for_review --MCP--> stage_extension_advisory -> immutable PENDING draft + audit
          v
Human: officer review page (127.0.0.1) or CLI -> approve/reject exact digest -> export
```

## Tool contracts

| Custom tool | Input | Result / guard |
| --- | --- | --- |
| `search_extension_knowledge` | 3–2000-character query | Grounding, cited corpus entries, clarification/referral; original scope gates |
| `get_natural_region_context` | I, II, III, IV or V | Original A1 reference, selected region, no forecast claim |
| `assess_extension_urgency` | Query | Original urgency/scope status and officer referral |
| `stage_extension_advisory` | Query, draft, source IDs, optional region/mode/external text | Server re-retrieves evidence; rejects unsupported questions, forged IDs, missing planting region, oversized text; writes pending only |

The official MCP SDK handles initialize, tools/list, tools/call, schema validation,
error results and newline-delimited JSON-RPC over stdio. `mcp.json` demonstrates
the two server configurations; the orchestrator launches both explicitly rather
than assuming that an MCP config file performs orchestration on its own.

The Fetch adapter calls the actual third-party `mcp_server_fetch` process and its
`fetch` tool with a fixed FAO URL and 3000-character limit. It records success/failure
and a content hash. Successful text is stored as explicitly untrusted supplementary
review material. It is excluded from the local model prompt and cannot authorize
new tools or override grounded evidence. Offline is the default. `--online` reports
unavailability and continues with local evidence; `--require-external` fails before
staging. A missing module or network failure is not reported as successful Fetch use.

## Approval and state transitions

```text
pending --human approve exact digest--> approved --export--> outbox (once)
pending --human reject exact digest---> rejected
```

`Store.review` is called only from the trusted local CLI. It requires an interactive
terminal, displays the full draft, and demands a typed `APPROVE <digest>` or
`REJECT <digest>`. The reviewer is the current OS user, not a model-supplied name.
The decision includes a reason and timestamp in the audit. MCP exposes neither
review nor export. It cannot set the draft state to approved. No SMTP, SMS, WhatsApp
or other external distribution is implemented: export is an approved local JSON
handoff for an officer. This is sufficient to demonstrate the human approval gate
without claiming farmer delivery.

Draft content is immutable via a SQLite trigger and verified against its digest
when read, reviewed and exported. A decision can be made once. Revised content
must become a new advisory with a new approval. `BEGIN IMMEDIATE` serializes
decisions and export writes, preventing concurrent duplicate reviews. Export is
idempotent by advisory ID.

## Audit, data and trust boundary

Every tool and orchestration outcome records an audit event. Query text is hashed
in audit events; the complete question and evidence are stored in the local draft
because the reviewer needs them. Draft creation, decision and export each commit
their audit entry in the same transaction. Events link the previous SHA-256 hash;
`audit` checks sequence and chain integrity. Triggers reject ordinary audit updates
and deletes. The database is created with owner-only file permissions on POSIX and
excluded from Git; operators must control their OS account and filesystem access.

The hash chain is an integrity aid, not an independently anchored tamper-proof
ledger. A privileged database owner can remove triggers, rewrite the chain or
truncate history. This local prototype does not implement remote authenticated
reviewer roles, separation between multiple OS accounts, signed audit checkpoints,
encrypted storage or backups. Anyone able to run arbitrary Python against the
database is inside the trusted operator boundary. Model prompts do not grant that
access. Do not expose this local process as a public review service without adding
authentication and role authorization.

Human reviewers must verify agronomic suitability and model claims. The system
checks source identity and grounding, not entailment of every model sentence.
AI output remains unverified until review; a citation alone is not proof of a
correct diagnosis. The local model endpoint is restricted to loopback HTTP and
uses no environment proxy. The existing language retrieval is reused; new drafting
does not claim validated Shona/Ndebele fluency. No new diagnostic model is trained.

## Verification

Run the unchanged legacy retrieval and output-guard scripts plus the new unittest
suite. The challenge suite uses real SDK client/server stdio round trips and tests
approval persistence, invalid inputs, concurrency, audit integrity, terminal review,
and model/Fetch adapters. Live local-model and third-party network tests are separate
and must be reported separately from mocked integration checks.
