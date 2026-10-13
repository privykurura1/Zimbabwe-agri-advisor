"""Read-only adapter to the existing Murimi Fara retrieval and safety gates."""
from functools import lru_cache
from pathlib import Path
import re

from rag import (build_index, chunk_id, fallback_answer, load_chunks,
                 retrieve_grounded, scope_guard)

ROOT = Path(__file__).resolve().parents[1]
REGIONS = {"I", "II", "III", "IV", "V"}


def validate_query(query: str) -> str:
    if not isinstance(query, str) or not 3 <= len(query.strip()) <= 2000:
        raise ValueError("Question must contain 3–2000 characters")
    return query.strip()


def validate_region(region: str) -> str:
    region = region.strip().upper()
    if region not in REGIONS:
        raise ValueError("Natural Region must be I, II, III, IV or V")
    return region


@lru_cache(maxsize=1)
def index():
    chunks = load_chunks(str(ROOT / "corpus_livestock_crops.md"))
    vectorizer, matrix = build_index(chunks)
    return chunks, vectorizer, matrix


def retrieve(query: str) -> dict:
    query = validate_query(query)
    guard = scope_guard(query)
    if guard:
        return {"grounded": False, "sources": [], "domain": "unknown",
                "urgent": guard["urgent"], "clarification": guard["answer"], "blocked": True}
    chunks, vectorizer, matrix = index()
    result = retrieve_grounded(query, chunks, vectorizer, matrix)
    return {"grounded": result["grounded"], "domain": result["answer_domain"],
            "urgent": result["urgent"], "blocked": False,
            "clarification": None if result["grounded"] else fallback_answer(result["domain"]),
            "sources": [{"id": chunk_id(c), "title": c.splitlines()[0],
                         "text": c, "origin": "existing/corpus_livestock_crops.md"}
                        for c in result["chunks"]]}


def region_context(region: str) -> dict:
    region = validate_region(region)
    chunks, _, _ = index()
    reference = next(c for c in chunks if chunk_id(c) == "A1")
    return {"region": region, "source_id": "A1", "text": reference,
            "note": "Confirm district and current rainfall with AGRITEX; this is not a weather forecast."}


def triage(query: str) -> dict:
    result = retrieve(query)
    return {"urgent": result["urgent"], "blocked": result["blocked"],
            "grounded": result["grounded"],
            "referral": "Contact a veterinary officer immediately" if result["urgent"]
            else "Ask your local AGRITEX or veterinary officer to review this advice"}


# Planting-time and crop-choice questions need the farm's Natural Region. Only
# those: "my maize plant is wilting" must not be held back for a region.
_PLANTING_QUESTION = re.compile(
    r"\b(when|what time|which month|best time|right time|too early|too late)\b.{0,40}\b(plant|sow)\w*"
    r"|\w*dyara\w*\b.{0,25}\brini\b|\brini\b.{0,25}\b\w*dyara\w*"
    r"|\bwhat (crop|crops|should i plant|to plant|should i grow)\b|\bwhich (crop|crops|variety|varieties)\b"
    r"|\bcrop choice\b", re.I)


def needs_region(query: str) -> bool:
    return bool(_PLANTING_QUESTION.search(query))


def fetch_is_relevant(evidence: dict) -> bool:
    """The only third-party reference is FAO's fall armyworm page."""
    return any(s["id"] == "D1" for s in evidence.get("sources", []))
