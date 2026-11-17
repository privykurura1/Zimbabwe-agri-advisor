"""Officer review drafts: evidence -> route -> draft -> staged for a human decision.

No AI language model: the draft is the matched farm book entry, laid out the
same way the farmer's app shows it (advisor.compose). Everything runs on this
computer. Every route taken is written to the tamper-evident audit log, and the
draft can only be stored as PENDING - approving is the officer's job.
"""
from pathlib import Path
import sys

from advisor import compose
from rag import detect_language

from . import tools
from .knowledge import needs_region, validate_query, validate_region
from .store import Store, digest

# Folder holding corpus_livestock_crops.md, murimifara.png and data/: beside the
# exe when packaged (PyInstaller puts this package inside _internal), else the
# project folder.
ROOT = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[1])

GENERATION = "farm_book"
FOOTER = "\n\nDraft for officer review - not yet approved."


def gather_evidence(store, query, region):
    """Read-only lookups, each one logged by the tool itself."""
    evidence = tools.search_extension_knowledge(store, query)
    urgency = tools.assess_extension_urgency(store, query)
    context = tools.get_natural_region_context(store, region) if region else None
    return {"evidence": evidence, "urgency": urgency, "region": context}


def write_draft(query, facts):
    """The farmer-facing answer built from the matched entries, plus the referral."""
    evidence = facts["evidence"]
    chunks = [s["text"] for s in evidence["sources"]]
    text = compose(chunks, urgent=evidence["urgent"], language=detect_language(query),
                   unsure=evidence.get("matched_by") == "model_unsure")
    if facts.get("region"):
        text += f"\n\nFarm location: Natural Region {facts['region']['region']}. {facts['region']['note']}"
    text += "\n\n" + facts["urgency"]["referral"] + "." + FOOTER
    return text[:6000]


async def draft(query, db_path, region=""):
    query = validate_query(query)
    region = validate_region(region) if region else ""
    store = Store(db_path)
    store.log("run_started", "orchestrator", {"query_hash": digest(query), "generation": GENERATION})

    def route(name, **detail):
        store.log("route_selected", "orchestrator", {"route": name, **detail})

    if needs_region(query) and not region:
        store.log("clarification_requested", "orchestrator", {"field": "natural_region"})
        return {"state": "needs_information", "message": "Which Natural Region (I–V) is your farm in?"}
    try:
        facts = gather_evidence(store, query, region)
        evidence = facts["evidence"]
        if not evidence["grounded"] or evidence["blocked"]:
            route("clarify", grounded=evidence["grounded"], blocked=evidence["blocked"])
            store.log("clarification_requested", "orchestrator", {"grounded": False})
            return {"state": "needs_information", "message": evidence["clarification"]}
        if evidence["urgent"]:
            route("urgent_referral", matched_by=evidence.get("matched_by"))
            store.log("urgent_case_escalated", "orchestrator",
                      {"source_ids": [s["id"] for s in evidence["sources"]]})
        else:
            route("write_draft", matched_by=evidence.get("matched_by"))
        text = write_draft(query, facts)
        result = tools.stage_extension_advisory(store, query, text, [s["id"] for s in evidence["sources"]],
                                                region=region, generation=GENERATION)
        store.log("run_completed", "orchestrator", {"id": result["id"]})
        return {**result, "urgent": bool(evidence["urgent"]),
                "message": "Draft stored for human review; no farmer delivery has occurred."}
    except Exception as exc:
        store.log("run_failed", "orchestrator", {"error_type": type(exc).__name__})
        raise
