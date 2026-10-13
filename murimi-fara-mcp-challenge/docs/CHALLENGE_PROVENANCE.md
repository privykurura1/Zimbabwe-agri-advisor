# Existing work and new challenge development

Baseline: `privykurura1/Zimbabwe-agri-advisor` main commit
`72475229a68c66d337673865abff94ae1d9c2417` (13 October 2026).

## Existing work preserved

The entire baseline application, frontend, desktop/installer scripts, corpus,
retrieval and output guards, model/image assets, original tests, reports,
exhibition runbook, evaluation utilities and historical `submission.json` are
existing Murimi Fara work. The historical project describes an offline farming
advisor developed for the Africa Deep Tech Challenge 2026.

New challenge development must not claim those files or the prior corpus/models
as newly authored for the African Agentic AI Design Challenge. Importing existing
`rag.py` and reading the corpus is deliberate reuse, documented in the architecture.

## Newly developed for this challenge branch

- `challenge_agent/`: official MCP SDK server with four custom tools, read-only
  legacy adapter, evidence/advisory orchestration, optional local LLM drafting,
  third-party Fetch MCP integration and separate CLI.
- SQLite pending/approved/rejected advisory lifecycle, digest-bound human terminal
  review, approved-only idempotent export and transactional hash-linked audit.
- Challenge-only protocol, orchestration, approval, persistence and integrity tests.
- `docs/CHALLENGE_*.md` and `.github/workflows/challenge-agent.yml`.
- Additions to `README.md` and `.gitignore` describing and isolating the new work.

No legacy implementation file or asset is changed by the challenge patch. The old
README content is retained before the clearly labelled new section. No new Devpost
submission is created and no automated merge into main is configured.

## Workspace provenance

The cloud workspace initially had no Git checkout. Git cloning was blocked by the
configured network proxy. Text sources were fetched through the authorized GitHub
connector for inspection and tests. A local source snapshot and challenge branch
were created; that local snapshot is not presented as the remote Git history.
Binary assets and vendored browser dependencies were not needed for these tests
and were not downloaded. They remain untouched in the remote baseline.

The reviewable patch contains only challenge additions and the two documentation/
ignore edits. It is intended to apply to the real baseline checkout, preserving
all remote assets and history. GitHub branch/PR publication status is recorded in
`CHALLENGE_VALIDATION.md`; read permission alone is not evidence of write permission.
