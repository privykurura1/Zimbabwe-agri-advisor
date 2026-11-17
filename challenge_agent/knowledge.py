"""Read-only adapter to Murimi Fara's answer pipeline (advisor.py): the same
farm book search, trained model and safety checks the farmer's app uses."""
from functools import lru_cache
import re
from pathlib import Path
import sys

from advisor import Advisor, default_model_path
from rag import chunk_id

# Folder holding corpus_livestock_crops.md, murimifara.png, data/ and models/:
# beside the exe when packaged (PyInstaller puts this package inside _internal),
# else the project folder.
ROOT = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[1])
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
def advisor():
    return Advisor(str(ROOT / "corpus_livestock_crops.md"), default_model_path(str(ROOT)))


def index():
    return advisor().chunks


def retrieve(query: str) -> dict:
    query = validate_query(query)
    found = advisor().find(query)
    if found["kind"] == "guard":
        return {"grounded": False, "sources": [], "domain": "unknown", "matched_by": None,
                "urgent": found["urgent"], "clarification": found["text"], "blocked": True}
    if found["kind"] == "need_detail":
        return {"grounded": False, "sources": [], "domain": found["domain"], "matched_by": None,
                "urgent": False, "clarification": found["text"], "blocked": False}
    return {"grounded": True, "domain": found["answer_domain"], "urgent": found["urgent"], "blocked": False,
            "clarification": None, "matched_by": found["matched_by"],
            "sources": [{"id": chunk_id(c), "title": c.splitlines()[0],
                         "text": c, "origin": "corpus_livestock_crops.md"}
                        for c in found["chunks"]]}


def region_context(region: str) -> dict:
    region = validate_region(region)
    reference = advisor().by_id["A1"]
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

