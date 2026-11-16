"""Murimi Fara's MCP server: seven tools over the official MCP SDK's stdio transport.

Advisory tools (the officer-review agent):
  search_extension_knowledge, get_natural_region_context, assess_extension_urgency,
  stage_extension_advisory  - drafts only; approving and sending are not tools.
Farm tools (the same data the desktop app's Farm records and Outbreak watch use):
  get_farm_records, add_farm_record (two-step: nothing is saved until confirmed),
  get_outbreak_summary (counts only, never farmers' messages).
"""
import hashlib
import hmac
import os
from pathlib import Path
import secrets

from mcp.server.fastmcp import FastMCP

from .knowledge import index, needs_region, region_context, retrieve, triage, validate_query, validate_region
from .store import Store, digest

mcp = FastMCP("Murimi Fara Extension", instructions=(
    "Offline farm advisory tools for Zimbabwe. Advisories are drafts only: human approval is outside this "
    "server. add_farm_record saves nothing until the person has seen the preview and agreed."))

# Per-run secret for add_farm_record confirmation codes: a code from one run of
# the server cannot be replayed in another.
_CONFIRM_SECRET = secrets.token_bytes(16)


def store():
    return Store(os.environ.get("MURIMI_AGENT_DB", str(Path(".challenge-data") / "agent.sqlite3")))


@mcp.tool()
async def search_extension_knowledge(query: str) -> dict:
    """Retrieve grounded crop/livestock evidence using the unchanged legacy RAG gates."""
    result = retrieve(query)
    store().log("knowledge_searched", "evidence_agent", {"query_hash": digest(query),
                "source_ids": [s["id"] for s in result["sources"]], "grounded": result["grounded"]})
    return result


@mcp.tool()
async def get_natural_region_context(region: str) -> dict:
    """Read Zimbabwe Natural Region I–V context from the existing A1 reference."""
    result = region_context(region)
    store().log("region_checked", "evidence_agent", {"region": result["region"]})
    return result


@mcp.tool()
async def assess_extension_urgency(query: str) -> dict:
    """Apply existing urgent-entry and scope guards; this is triage, not diagnosis."""
    result = triage(query)
    store().log("urgency_assessed", "evidence_agent", result)
    return result


@mcp.tool()
async def stage_extension_advisory(query: str, text: str, source_ids: list[str],
                             region: str = "", generation: str = "grounded_template",
                             external_text: str = "") -> dict:
    """Stage an immutable draft for human review. Cannot approve or publish it."""
    query = validate_query(query)
    if region:
        region = validate_region(region)
    if needs_region(query) and not region:
        raise ValueError("Confirm a Natural Region before staging planting/crop-choice advice")
    result = retrieve(query)
    if not result["grounded"] or result["blocked"]:
        raise ValueError("No supported evidence; ask for clarification or refer to an officer")
    available = {s["id"] for s in result["sources"]}
    if not source_ids or len(set(source_ids)) != len(source_ids) or not set(source_ids) <= available:
        raise ValueError("Citations must be unique IDs from this question's retrieved evidence")
    if not 20 <= len(text.strip()) <= 6000:
        raise ValueError("Draft text must contain 20–6000 characters")
    if generation not in {"grounded_template", "local_llm"}:
        raise ValueError("Unknown generation mode")
    if len(external_text) > 3000:
        raise ValueError("Supplementary external reference is limited to 3000 characters")
    # Re-retrieve evidence server-side; do not trust agent-provided source bodies.
    document = {"query": query, "region": region, "text": text.strip(),
                "sources": [s for s in result["sources"] if s["id"] in source_ids],
                "urgent": result["urgent"], "generation": generation,
                "notice": "Unverified draft; AGRITEX/veterinary human review required. No definitive diagnosis or doses."}
    if region:
        document["region_context"] = region_context(region)
    if external_text:
        document["supplementary_reference"] = {
            "url": "https://www.fao.org/fall-armyworm/en/", "text": external_text,
            "notice": "Untrusted third-party page text for human review, not diagnostic evidence."}
    return store().stage(document)


# ---------------------------------------------------------------- farm tools
def _farm():
    from murimi_plus.farm import Farm, default_path
    return Farm(os.environ.get("MURIMI_FARM_DB") or default_path())


def _query_log():
    base = os.environ.get("MURIMIFARA_DATA_DIR") or os.getcwd()
    return os.environ.get("MURIMI_QUERY_LOG") or os.path.join(base, "query_log.jsonl")


def _confirm_code(day, subject, note):
    message = f"{day}|{subject}|{note}".encode("utf-8")
    return hmac.new(_CONFIRM_SECRET, message, hashlib.sha256).hexdigest()[:8]


@mcp.tool()
async def get_farm_records(limit: int = 20) -> dict:
    """Read this laptop's farm diary (newest first) and the open reminders, with
    overdue / due-soon flags. Read only."""
    if not 1 <= limit <= 200:
        raise ValueError("limit must be 1-200")
    farm = _farm()
    records = farm.records(limit=limit)
    reminders = farm.reminders()
    store().log("farm_records_read", "farm_agent", {"records": len(records), "reminders": len(reminders)})
    return {"records": records, "reminders": reminders,
            "note": "Records typed by people on this laptop; not checked by an expert."}


@mcp.tool()
async def add_farm_record(day: str, subject: str, note: str, confirm_code: str = "") -> dict:
    """Add a dated note to the farm diary, e.g. day='2026-11-16', subject='Cattle (12)',
    note='Dipped at the communal dip tank'. Two steps: call without confirm_code to get
    a preview and a code; show the preview to the person; only if they agree, call again
    with the same values and confirm_code. Nothing is saved on the first call."""
    from murimi_plus.farm import MAX_TEXT, _day, _text
    day, subject, note = _day(day), _text(subject, "subject")[:MAX_TEXT], _text(note, "note")[:MAX_TEXT]
    code = _confirm_code(day, subject, note)
    if not confirm_code:
        store().log("farm_record_proposed", "farm_agent", {"day": day, "subject_hash": digest(subject)})
        return {"saved": False, "preview": {"day": day, "subject": subject, "note": note},
                "confirm_code": code,
                "next_step": "Show this preview to the person. Only if they agree, call add_farm_record again "
                             "with the same day, subject and note and this confirm_code."}
    if not hmac.compare_digest(confirm_code.strip().lower(), code):
        raise ValueError("Confirmation code does not match this record; ask for a new preview")
    record_id = _farm().add_record(day, subject, note)
    store().log("farm_record_added", "farm_agent", {"record_id": record_id, "day": day})
    return {"saved": True, "record_id": record_id, "day": day, "subject": subject, "note": note}


@mcp.tool()
async def get_outbreak_summary(province: str = "") -> dict:
    """Which diseases and pests farmers asked this laptop's advisor about in the last
    7 days compared with the 4 weeks before, and which are rising sharply. Counts only,
    never farmers' messages. Optionally filter to one Zimbabwe province.
    A rise in questions is a reason to check with a vet or AGRITEX, not proof of an outbreak."""
    import rag
    from murimi_plus import outbreak
    if province and province not in outbreak.PROVINCES:
        raise ValueError("Province must be one of: " + ", ".join(outbreak.PROVINCES))
    chunks = index()[0]
    titles = {}
    for chunk in chunks:
        cid = rag.chunk_id(chunk)
        name = rag.condition_name([chunk]) if cid else None
        if cid and name:
            titles[cid] = name
    report = outbreak.summarise(outbreak.read_log(_query_log()), titles)
    if province:
        keep = lambda row: province in row["provinces"]
        report["alerts"] = [a for a in report["alerts"] if keep(a)]
        report["table"] = [t for t in report["table"] if keep(t)]
    report.pop("weekly", None)
    report["province"] = province or "all"
    report["note"] = "A rise in questions is a reason to check with a vet or AGRITEX, not proof of an outbreak."
    store().log("outbreak_summary_read", "farm_agent", {"province": province or "all",
                                                         "alerts": len(report["alerts"])})
    return report


if __name__ == "__main__":
    mcp.run(transport="stdio")