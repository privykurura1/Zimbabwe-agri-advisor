"""Four custom tools over the official MCP SDK's stdio transport."""
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .knowledge import needs_region, region_context, retrieve, triage, validate_query, validate_region
from .store import Store, digest

mcp = FastMCP("Murimi Fara Extension", instructions="Draft only. Human approval is outside this server.")


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


if __name__ == "__main__":
    mcp.run(transport="stdio")
