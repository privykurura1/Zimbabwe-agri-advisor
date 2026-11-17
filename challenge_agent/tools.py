"""The officer-review agent's tools, as plain Python functions on this laptop.

  search_extension_knowledge, get_natural_region_context, assess_extension_urgency
      read-only lookups in the Murimi Fara knowledge base
  stage_extension_advisory
      saves a draft as PENDING for an officer to review

There is deliberately no function here to approve, reject or export a draft.
Only the officer review page and the operator command line can do that, and
both need a person to confirm.
"""
from .knowledge import needs_region, region_context, retrieve, triage, validate_query, validate_region
from .store import digest


def search_extension_knowledge(store, query: str) -> dict:
    """Retrieve grounded crop/livestock evidence using the unchanged legacy RAG gates."""
    result = retrieve(query)
    store.log("knowledge_searched", "evidence_agent", {"query_hash": digest(query),
              "source_ids": [s["id"] for s in result["sources"]], "grounded": result["grounded"],
              "matched_by": result.get("matched_by")})
    return result


def get_natural_region_context(store, region: str) -> dict:
    """Read Zimbabwe Natural Region I-V context from the existing A1 reference."""
    result = region_context(region)
    store.log("region_checked", "evidence_agent", {"region": result["region"]})
    return result


def assess_extension_urgency(store, query: str) -> dict:
    """Apply existing urgent-entry and scope guards; this is triage, not diagnosis."""
    result = triage(query)
    store.log("urgency_assessed", "evidence_agent", result)
    return result


def stage_extension_advisory(store, query: str, text: str, source_ids: list,
                             region: str = "", generation: str = "farm_book") -> dict:
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
    if generation != "farm_book":
        raise ValueError("Unknown generation mode")
    # Re-retrieve evidence here; do not trust source bodies passed in by the agent.
    document = {"query": query, "region": region, "text": text.strip(),
                "sources": [s for s in result["sources"] if s["id"] in source_ids],
                "urgent": result["urgent"], "generation": generation,
                "notice": "Unverified draft; AGRITEX/veterinary human review required. No definitive diagnosis or doses."}
    if region:
        document["region_context"] = region_context(region)
    return store.stage(document)
