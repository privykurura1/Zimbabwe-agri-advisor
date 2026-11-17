"""
Murimi Fara backend - small, offline, no AI language model.

Answers come from the checked farm book (corpus_livestock_crops.md), chosen by
the farm book search (rag.py) and our own small trained model (matcher.py,
models/murimi_model.json). See advisor.py for how they are combined.

It also serves the app page itself (index.html + vendor/), so the same server is
  * the desktop app   - desktop_app.py opens a window on it, and
  * the web app       - any phone or computer opens http://<this computer>:8000
                        in a browser (on the same Wi-Fi/hotspot, or on a server).

Run it from source:
    pip install fastapi uvicorn python-multipart
    uvicorn app:app --port 8000          (add --host 0.0.0.0 for phones/other computers)
"""

import datetime
import json
import os
import socket
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import rag as _rag
from advisor import Advisor, default_model_path
from rag import CORPUS_PATH

APP_VERSION = "2.0"

app = FastAPI(title="Murimi Fara")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Where this computer keeps its own files (logs, feedback, records). The packaged
# app sets MURIMIFARA_DATA_DIR to a writable folder; from source it is this folder.
_DATA_DIR = os.environ.get("MURIMIFARA_DATA_DIR") or os.getcwd()
QUERY_LOG_PATH = os.path.join(_DATA_DIR, "query_log.jsonl")
FEEDBACK_PATH = os.path.join(_DATA_DIR, "farmer_feedback.jsonl")
MODEL_PATH = default_model_path(os.getcwd())
_log_lock = threading.Lock()

print("Loading the farm book and Murimi Fara's model...")
_advisor = Advisor(CORPUS_PATH, MODEL_PATH)
_chunks = _advisor.chunks
_model_info = _advisor.model.info if _advisor.model else {}
print(f"Ready - {len(_chunks)} farm book entries; model version {_model_info.get('version', 'none')}.")

app.mount("/vendor", StaticFiles(directory="vendor"), name="vendor")


@app.get("/")
def serve_frontend():
    return FileResponse("index.html")


@app.get("/murimifara.png")
def serve_logo():
    return FileResponse("murimifara.png", media_type="image/png")


def get_lan_ip():
    """This computer's address on the local Wi-Fi, for phones on its hotspot. The
    1-second timeout matters: without it this can hang at startup."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


_lan_ip = get_lan_ip()
print(f"\n{'=' * 60}\n  App running at: http://127.0.0.1:8000\n"
      f"  (Phones on this computer's Wi-Fi: http://{_lan_ip}:8000)\n{'=' * 60}\n")


def log_problem(context, exc):
    """The packaged app has no console, so write problems to a file the user can send."""
    try:
        import traceback
        with open(os.path.join(_DATA_DIR, "murimifara_error.log"), "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.datetime.now().isoformat(timespec='seconds')} {context} ---\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except OSError:
        pass


def _append(path, record):
    """Append one JSON line. Never raises - logging must not break answering."""
    try:
        record = {"time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), **record}
        with _log_lock, open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---- Query log ----
# Every message is recorded on THIS computer only (nothing is sent anywhere), with
# what the app did with it. It feeds the outbreak counts and shows what people ask
# that the farm book cannot answer yet (summarize_query_log.py).
def log_query(kind: str, query: str = "", **extra):
    _append(QUERY_LOG_PATH, {"kind": kind, "query": query[:600], **extra})


def _province_of(payload):
    try:
        from murimi_plus.outbreak import PROVINCES
    except Exception:
        return {}
    return {"province": payload.province} if payload.province in PROVINCES else {}


def _region_of(query):
    try:
        from murimi_plus.content import region_in
        return region_in(query)
    except Exception:
        return ""


class Question(BaseModel):
    question: str
    # Optional, chosen by the farmer; used only for outbreak counts and nearby contacts.
    province: str = ""


def answer(payload: Question):
    """Run the farmer's message through the advisor and log what happened."""
    query = payload.question
    try:
        found = _advisor.ask(query)
    except Exception as e:  # noqa: BLE001
        log_problem("answer", e)
        return {"kind": "error", "text": "Something went wrong. Please ask again.", "entries": [],
                "titles": [], "urgent": False, "matched_by": None, "domain": "unknown", "language": "english"}
    if found["kind"] == "guard":
        log_query("guard:" + found["guard"], query)
    elif found["kind"] == "answer":
        log_query("answered", query, domain=found["domain"], entries=found["entries"], urgent=found["urgent"],
                  matched_by=found["matched_by"], **_province_of(payload))
    else:
        log_query("needs_more_detail", query, domain=found["domain"])
    return found


def _meta(found, query):
    return {
        "sources": found.get("titles", []),
        "urgent": found["urgent"],
        "grounded": found["kind"] == "answer",
        "entry_ids": found["entries"],
        "matched_by": found.get("matched_by"),
        "domain": found.get("answer_domain") or found.get("domain"),
        "language": found.get("language", "english"),
        "region": _region_of(query),
    }


@app.post("/api/ask/stream")
def ask_stream(payload: Question):
    """Same answer as /api/ask, in the page's streaming format: one 'META:::{json}'
    line, then the answer text. Kept so older pages and phones keep working."""
    found = answer(payload)

    def generate():
        yield "META:::" + json.dumps(_meta(found, payload.question)) + "\n"
        yield found["text"]
    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/api/ask")
def ask(payload: Question):
    found = answer(payload)
    return {"question": payload.question, "answer": found["text"], **_meta(found, payload.question)}


class Feedback(BaseModel):
    question: str
    entry_ids: list = []
    helpful: bool
    note: str = ""


@app.post("/api/feedback")
def feedback(payload: Feedback):
    """The farmer's thumbs up / "not right". Saved on this computer only; officers
    see the "not right" ones on the officer page and say which entry was right.
    That is how the model learns (tools/train_model.py)."""
    try:
        from challenge_agent.feedback import scrub
    except Exception:  # noqa: BLE001
        scrub = lambda t: t  # noqa: E731
    _append(FEEDBACK_PATH, {"question": scrub(payload.question)[:600],
                            "entries": [str(e)[:4] for e in payload.entry_ids][:2],
                            "helpful": bool(payload.helpful), "note": scrub(payload.note)[:300]})
    return {"saved": True}


# ---- Extras (outbreak watch, farm records, find help, summaries) ----
# Included only if they load; a fault there must never stop the advisor.
try:
    from murimi_plus.router import create_router as _extras_router
    app.include_router(_extras_router(_chunks, _rag, QUERY_LOG_PATH,
                                      os.path.join(_DATA_DIR, "farm_records.sqlite3")))
    from murimi_plus.views import DESIGN_VERSION as _extras_design
    print(f"Extras loaded (design v{_extras_design}): /extras/dashboard, /extras/farm, /extras/help")
except Exception as _e:  # noqa: BLE001
    print(f"Extras not loaded ({_e}) - the advisor works without them.")


# ---- Officer review, at /officer (this computer only) ----
OFFICER_DB_PATH = os.path.join(_DATA_DIR, "officer_review.sqlite3")
try:
    from challenge_agent.review_app import create_app as _officer_app
    app.mount("/officer", _officer_app(OFFICER_DB_PATH, prefix="/officer", farmer_feedback_path=FEEDBACK_PATH))
    print("Officer review loaded: http://127.0.0.1:8000/officer/  (this computer only)")
except Exception as _e:  # noqa: BLE001
    print(f"Officer review not loaded ({_e}) - the advisor works without it.")


@app.get("/api/health")
def health():
    """For the page: is the backend up, and the address phones can use."""
    return {"status": "ok", "version": APP_VERSION, "chunks_loaded": len(_chunks),
            "model": {"version": _model_info.get("version"), "examples": _model_info.get("examples"),
                      "check": _model_info.get("check")},
            "ignored_blocks": len(_rag.LAST_LOAD_REPORT["ignored"]), "lan_address": f"http://{_lan_ip}:8000"}