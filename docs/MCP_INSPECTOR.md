# Testing Murimi Fara's MCP server with MCP Inspector

MCP Inspector is the official tool for testing MCP servers. Use it to show that
Murimi Fara's server works with any MCP client, not only our own agent.
Checked with MCP Inspector 2.15.0 and Node.js 22.

## The 7 tools

| Tool | What it does |
|---|---|
| `search_extension_knowledge` | Searches the 55 checked knowledge entries for a farmer's question |
| `get_natural_region_context` | Facts about a Zimbabwe Natural Region (I–V) |
| `assess_extension_urgency` | Checks a question for danger signs (urgent = call a vet today) |
| `stage_extension_advisory` | Saves a draft for an officer to review. It cannot approve or send it. |
| `get_farm_records` | Reads the farm diary and open reminders (read only) |
| `add_farm_record` | Adds a diary note in two steps: preview first, saved only with the confirm code |
| `get_outbreak_summary` | Which diseases farmers asked about this week vs the 4 weeks before, by province. Counts only. |

Approving and sending advice are deliberately not tools: only a person can do them,
on the officer review page.

## Setup (once)

Install **Node.js LTS** from nodejs.org (includes `npx`). Internet is needed once to
download the Inspector; the server itself runs offline.

## Open the Inspector (from source)

In PowerShell, in the Murimi Fara folder, with the venv on:

```powershell
npx @modelcontextprotocol/inspector -e MURIMI_AGENT_DB=.challenge-data\agent.sqlite3 -e MURIMIFARA_DATA_DIR=. python -m challenge_agent.server
```

A browser page opens. Click **Connect**, then **Tools > List Tools**.

## Open the Inspector (installed app, no Python needed)

```powershell
npx @modelcontextprotocol/inspector "C:\Program Files\Murimi Fara\MurimiFara.exe" --mcp-server
```

It then uses the same farm records, question log and audit log as the installed app.
If you installed somewhere else, use that folder.

## A 2-minute demo

1. `search_extension_knowledge` with query `my cow is passing red urine and has a fever`
   → evidence entries such as B3 (redwater).
2. `assess_extension_urgency` with the same query → `urgent: true`.
3. `add_farm_record` with day `2026-11-16`, subject `Cattle (12)`, note `Dipped at the dip tank`
   → `saved: false`, a preview and a `confirm_code`. Call it again with the same values plus the
   `confirm_code` → `saved: true`. (The code only works within the same connection.)
4. `get_farm_records` → the note is there.
5. `get_outbreak_summary` → counts by condition and province (ask the advisor a few questions first,
   with a province selected, so there is something to show).
6. Show there is no `approve` tool: the AI drafts, a person decides.

## Command line (no browser)

```powershell
npx @modelcontextprotocol/inspector --cli python -m challenge_agent.server --method tools/list
npx @modelcontextprotocol/inspector --cli python -m challenge_agent.server --method tools/call --tool-name search_extension_knowledge --tool-arg "query=my cow is passing red urine"
```

Each `--cli` command starts a new server, so the two-step `add_farm_record` must be done in the
browser Inspector (one connection), not across two `--cli` commands.
