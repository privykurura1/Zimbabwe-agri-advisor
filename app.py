"""
Local API backend for the Offline AI Farming Advisor.

Wraps your existing rag.py retrieval logic (corpus loading, domain-filtered
retrieval) and talks to a running llama-server instance for inference.
Also serves the frontend itself (index.html + vendor/ libraries), which is
what lets the packaged desktop app (desktop_app.py) point one window
straight at this server and get the full working UI - not just raw API
JSON.

SETUP:
    pip install fastapi uvicorn

STEP 1 - start llama-server (in its own terminal, leave it running):
    C:\\llama.cpp\\llama-server.exe -m model\\qwen2.5-1.5b-instruct-q4_k_m.gguf -t 4 -c 4096 --port 8080

STEP 2 - start this backend (in a second terminal):
    uvicorn app:app --reload --port 8000

Then open http://localhost:8000 in a browser - this server now serves
the UI itself, so you no longer open index.html directly.
"""

import datetime
import json
import os
import socket
import threading
import urllib.request
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Reuse the retrieval logic already built and tested in rag.py.
# (We no longer use rag.py's ask_model - llama-server replaces it.)
import rag as _rag
from rag import (load_chunks, detect_language, build_index, retrieve, retrieve_grounded,
                 build_prompt, fallback_answer, scope_guard, CORPUS_PATH)

app = FastAPI(title="Offline AI Farming Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading corpus and building retrieval index...")
_chunks = load_chunks(CORPUS_PATH)
_vectorizer, _matrix = build_index(_chunks)
print(f"Ready - {len(_chunks)} entries loaded.")
if _rag.LAST_LOAD_REPORT["ignored"]:
    print(f"  ({len(_rag.LAST_LOAD_REPORT['ignored'])} non-knowledge blocks ignored: rules, tests, checklists)")

# Load the trained crop-image classifier through OpenCV's own DNN engine.
# This is a real, substantive OpenCV 5 operation - genuine preprocessing
# and genuine neural network inference, not decoration. Loaded once at
# startup, same reasoning as llama-server: load once, reuse for every
# request, instead of reloading per photo.
#
# Wrapped in try/except so a missing model file doesn't break the whole
# app - the LLM/RAG advisor still works fine even if the vision feature
# isn't set up yet.
CLASS_NAMES = ["healthy", "damaged"]
_vision_net = None
try:
    _vision_net = cv2.dnn.readNetFromONNX("faw_classifier.onnx")
    print("Vision model loaded (faw_classifier.onnx) - photo diagnosis enabled.")
except Exception as e:
    print(f"Vision model not loaded ({e}) - photo diagnosis will be unavailable.")

# Serve the frontend's local library files (react.production.min.js etc.)
# so the app works with zero internet access, and so phones on the same
# WiFi could load them too if you set up the hotspot-sharing feature later.
app.mount("/vendor", StaticFiles(directory="vendor"), name="vendor")


@app.get("/")
def serve_frontend():
    """Serves the actual app page. This is what the packaged desktop app's
    window loads, and what fixes the '{"detail":"Not Found"}' error -
    without this route, hitting the base URL had nothing to return."""
    return FileResponse("index.html")


@app.get("/murimifara.png")
def serve_logo():
    """Serves the app logo (header, answer avatar and browser tab icon).
    Without this route the page asks for /murimifara.png and gets
    'Not Found', so the UI falls back to a placeholder."""
    return FileResponse("murimifara.png", media_type="image/png")


def get_lan_ip():
    """Finds this laptop's own address on the local WiFi network - useful
    for phone access over a hotspot. The 1-second timeout is essential,
    not optional: without it, this socket call can occasionally hang for
    several seconds on a machine with unusual network state (WiFi off,
    no active connection, hotspot-only mode) - directly the kind of
    thing that caused intermittent 'backend did not become ready' errors,
    since this runs during app startup, before anything else can happen."""
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
print(f"\n{'='*60}")
print(f"  App running at: http://127.0.0.1:8000")
print(f"  (On this laptop's own WiFi: http://{_lan_ip}:8000)")
print(f"{'='*60}\n")

LLAMA_SERVER_URL = "http://localhost:8080/completion"

# ---- Query log ----
# Every message is recorded on THIS computer only (nothing is sent anywhere),
# with what the app did with it. This is how you find out what people really
# ask that the knowledge base can't answer yet - run summarize_query_log.py on
# the file. The UI tells people their questions are saved locally.
# Photos are logged as an event (result and confidence) but the image itself
# is never stored.
_DATA_DIR = os.environ.get("MURIMIFARA_DATA_DIR") or os.getcwd()
QUERY_LOG_PATH = os.path.join(_DATA_DIR, "query_log.jsonl")
_log_lock = threading.Lock()


def log_query(kind: str, query: str = "", **extra):
    """Append one line to the query log. Never raises - logging must not be able
    to break answering a farmer."""
    try:
        record = {
            "time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "kind": kind,
            "query": query[:600],
            **extra,
        }
        with _log_lock, open(QUERY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


class Question(BaseModel):
    question: str


# Real bug this fixes, found during Shona generation testing: with no stop
# sequence at all, the model sometimes kept generating past its actual answer,
# inventing entirely fake disease entries (a fabricated "Bacterial Blight"
# entry, with a fake cause and fake Shona name, that does not exist anywhere
# in the real corpus) and even fake follow-up farmer messages - because the
# prompt's own repeating structure ("REFERENCE INFORMATION:", "FARMER'S
# MESSAGE:", "ANSWER:") gives the model a template to keep pattern-matching
# into once its real answer is done. These stop sequences match that
# structure, so generation halts the instant the model tries to start a new
# fake turn, instead of continuing until n_predict runs out.
STOP_SEQUENCES = [
    # The prompt now uses Qwen's own chat layout (rag.build_prompt), so the
    # model normally ends with its end-of-turn token and stops by itself.
    # These catch the cases where it doesn't.
    "<|im_end|>",
    "<|im_start|>",
    "FARMER'S MESSAGE:",
    "REFERENCE INFORMATION:",
    "\nQUESTION:",
]
# "\n###" and "\n---" were removed on purpose: they also cut legitimate
# headed answers. Fake entries are caught by rag.OutputGuard instead.


def ask_model_server(prompt: str, n_predict: int = 350) -> str:
    """
    Calls the already-running llama-server instead of spawning a new
    llama-cli process. This is what makes repeated questions fast -
    the model stays loaded in memory between requests.
    """
    payload = json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0.3,
        "repeat_penalty": 1.1,
        "cache_prompt": True,   # reuse the identical opening of the prompt between questions
        "stop": STOP_SEQUENCES,
    }).encode("utf-8")

    req = urllib.request.Request(
        LLAMA_SERVER_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # The /completion endpoint returns only the generated continuation,
        # not the echoed prompt - no cleanup/parsing needed, unlike llama-cli.
        # The answer was started inside the prompt (rag.PREFILL); put that start back.
        return _rag.tidy_answer(_rag.prefill_of(prompt) + data.get("content", ""),
                                crop=_rag.is_crop_prompt(prompt), query=_rag.query_of(prompt))[0]
    except urllib.error.URLError:
        raise ConnectionError(
            "Could not reach llama-server on port 8080. "
            "Make sure llama-server.exe is running first."
        )


# Sent as the last thing in the stream when the answer was cut off before it
# finished. The old limit (250 tokens) cut most three-part answers off
# mid-sentence, and nothing told the farmer. The UI removes this marker,
# trims back to the last complete sentence, and adds a short note.
TRUNCATION_MARKER = "\n\n[[TRUNCATED]]"


def stream_llama_server(prompt: str, n_predict: int = 350):
    """
    Streams the answer token-by-token from llama-server as it's generated,
    instead of waiting for the full answer to finish. This is what makes
    the app feel responsive like a chat assistant - text starts appearing
    within a couple seconds instead of a long silent wait. Total generation
    speed is unchanged (still bounded by the CPU), but perceived speed is
    much better since the person sees continuous progress.
    """
    payload = json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0.3,
        "repeat_penalty": 1.1,
        "cache_prompt": True,   # reuse the identical opening of the prompt between questions
        "stream": True,
        "stop": STOP_SEQUENCES,
    }).encode("utf-8")

    req = urllib.request.Request(
        LLAMA_SERVER_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    guard = _rag.OutputGuard(crop=_rag.is_crop_prompt(prompt), query=_rag.query_of(prompt))
    # The answer was started inside the prompt (rag.PREFILL); show that start first.
    out = guard.feed(_rag.prefill_of(prompt))
    if out:
        yield out
    hit_limit = False
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            data_str = line[len("data:"):].strip()
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            content = data.get("content", "")
            if content:
                out = guard.feed(content)
                if out:
                    yield out
                if guard.stopped:
                    break   # model went off-script: stop reading, closing the request ends generation
            if data.get("stop"):
                # llama-server reports why it stopped; the field name differs
                # between builds, so accept either form.
                hit_limit = bool(data.get("stopped_limit")) or data.get("stop_type") == "limit"
                break

    tail = guard.flush()
    if tail:
        yield tail

    # A runaway cut is a finished answer plus junk removed - not a truncation.
    # Otherwise, an answer that hit the limit or doesn't end on sentence
    # punctuation was cut off.
    text = guard.text.rstrip()
    if not guard.was_cut and (hit_limit or (text and text[-1] not in ".!?)\"'*_")):
        yield TRUNCATION_MARKER


@app.post("/api/ask/stream")
def ask_stream(payload: Question):
    """
    Streaming version of /api/ask. Sends the retrieved source titles first
    (as a special first line), then streams the answer text as it's
    generated. The frontend reads this incrementally instead of waiting
    for one big JSON response.
    """
    query = payload.question

    guard = scope_guard(query)
    if guard:
        log_query("guard:" + guard["kind"], query)
        # Fixed reply, model never called (see scope_guard in rag.py).
        def guarded():
            yield "META:::" + json.dumps({"sources": [], "urgent": guard["urgent"], "grounded": False}) + "\n"
            yield guard["answer"]
        return StreamingResponse(guarded(), media_type="text/plain")

    result = retrieve_grounded(query, _chunks, _vectorizer, _matrix)
    retrieved_titles = [c.splitlines()[0].replace("### ", "") for c in result["chunks"]]
    meta = {
        "sources": retrieved_titles,
        # Decided by which corpus entry matched, not by words in the model's
        # answer (the old text-scanning flag could tag "not urgent" as urgent).
        "urgent": result["urgent"],
        "grounded": result["grounded"],
    }
    if result["grounded"]:
        log_query("answered", query, domain=result["domain"], entries=sorted(result["matched"]), urgent=result["urgent"])
    else:
        log_query("needs_more_detail", query, domain=result["domain"])

    def generate():
        yield f"META:::{json.dumps(meta)}\n"

        if not result["grounded"]:
            # Nothing in the knowledge base matches what the farmer described.
            # Do NOT ask the model to answer anyway - that is what produced
            # invented symptoms and wrong diagnoses in testing. Ask for detail.
            yield fallback_answer(result["domain"])
            return

        prompt = build_prompt(query, result["chunks"], domain=result["answer_domain"], language=detect_language(query))
        try:
            for chunk in stream_llama_server(prompt):
                yield chunk
        except (ConnectionError, urllib.error.URLError, OSError) as e:
            yield f"\n\nError: could not reach the language model ({e}). Make sure the advisor is fully started."

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/api/ask")
def ask(payload: Question):
    query = payload.question

    guard = scope_guard(query)
    if guard:
        log_query("guard:" + guard["kind"], query)
        return {"question": query, "retrieved_sources": [], "urgent": guard["urgent"],
                "grounded": False, "answer": guard["answer"]}

    result = retrieve_grounded(query, _chunks, _vectorizer, _matrix)
    retrieved_titles = [c.splitlines()[0].replace("### ", "") for c in result["chunks"]]

    if result["grounded"]:
        log_query("answered", query, domain=result["domain"], entries=sorted(result["matched"]), urgent=result["urgent"])
    else:
        log_query("needs_more_detail", query, domain=result["domain"])

    if not result["grounded"]:
        return {
            "question": query,
            "retrieved_sources": [],
            "urgent": False,
            "grounded": False,
            "answer": fallback_answer(result["domain"]),
        }

    prompt = build_prompt(query, result["chunks"], domain=result["answer_domain"], language=detect_language(query))
    try:
        answer = ask_model_server(prompt)
    except ConnectionError as e:
        return {"question": query, "retrieved_sources": [], "urgent": False, "grounded": True, "answer": f"Error: {e}"}

    return {
        "question": query,
        "retrieved_sources": retrieved_titles,
        "urgent": result["urgent"],
        "grounded": True,
        "answer": answer,
    }


@app.get("/api/health")
def health():
    """Quick check the frontend can use to confirm the backend is running.
    Also includes the LAN address, so the app's own UI can display it -
    since the packaged app runs with --noconsole, the printed version at
    startup is invisible, and this is the only way to actually see and
    share the address with a farmer's phone."""
    return {"status": "ok", "chunks_loaded": len(_chunks), "ignored_blocks": len(_rag.LAST_LOAD_REPORT["ignored"]), "lan_address": f"http://{_lan_ip}:8000"}


@app.post("/api/classify_image")
async def classify_image(file: UploadFile = File(...)):
    """
    The Agentic Vision pipeline: the OpenCV classification result actively
    changes what happens next, rather than just being displayed on its own.

        PERCEPTION  -> OpenCV 5 preprocessing + MobileNetV2 inference (cv2.dnn)
        DECISION    -> confidence-based routing (see thresholds below)
        RETRIEVAL   -> RAG lookup, only triggered on a confident "damaged" result
        ADVICE      -> grounded LLM generation, or a safe templated response
                        when confidence is too low to responsibly diagnose
        HUMAN ACTION -> the farmer reads a clear, appropriately-hedged next step

    This is deliberately NOT "photo in, label out" - a low-confidence result
    is treated differently from a high-confidence one, and only a confident
    "damaged" result triggers a full RAG+LLM explanation. This is what
    "vision results changing what happens next" actually means in practice.
    """
    if _vision_net is None:
        return {"error": "Vision model not available on this installation."}

    image_bytes = await file.read()
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img is None:
        return {"error": "Could not read the uploaded image."}

    # ---- PERCEPTION: real OpenCV 5 preprocessing + inference ----
    mean = (0.485, 0.456, 0.406)
    std = (0.229, 0.224, 0.225)

    blob = cv2.dnn.blobFromImage(
        img,
        scalefactor=1.0 / 255.0,
        size=(224, 224),
        mean=(0, 0, 0),
        swapRB=True,
        crop=False,
    )
    for i in range(3):
        blob[0, i, :, :] = (blob[0, i, :, :] - mean[i]) / std[i]

    _vision_net.setInput(blob)
    output = _vision_net.forward()

    exp_scores = np.exp(output - np.max(output))
    probabilities = exp_scores / exp_scores.sum()

    predicted_idx = int(np.argmax(probabilities))
    predicted_class = CLASS_NAMES[predicted_idx]
    confidence = float(probabilities[0][predicted_idx] * 100)

    vision_result = {
        "prediction": predicted_class,
        "confidence": round(confidence, 1),
        "probabilities": {
            name: round(float(probabilities[0][i] * 100), 1)
            for i, name in enumerate(CLASS_NAMES)
        },
    }

    # ---- DECISION: confidence-based routing ----
    # Thresholds are deliberately conservative - overclaiming a diagnosis
    # from a low-confidence result is worse than admitting uncertainty.
    HIGH_CONFIDENCE = 80.0
    LOW_CONFIDENCE = 55.0

    if confidence >= HIGH_CONFIDENCE and predicted_class == "damaged":
        decision_path = "high_confidence_damaged"
    elif confidence >= HIGH_CONFIDENCE and predicted_class == "healthy":
        decision_path = "high_confidence_healthy"
    elif confidence >= LOW_CONFIDENCE:
        decision_path = "medium_confidence"
    else:
        decision_path = "low_confidence"

    result = {"vision": vision_result, "decision_path": decision_path}
    log_query("photo", "", decision_path=decision_path,
              prediction=predicted_class, confidence=round(confidence, 1))

    # ---- RETRIEVAL + ADVICE: only a confident "damaged" result earns a
    # full grounded diagnosis. Every other path gets an honest, safe
    # response instead of a guess dressed up as a diagnosis. ----
    if decision_path == "high_confidence_damaged":
        retrieved_chunks = retrieve(
            "fall armyworm maize damage holes windowpaning frass",
            _chunks, _vectorizer, _matrix,
        )
        retrieved_titles = [c.splitlines()[0].replace("### ", "") for c in retrieved_chunks]

        vision_note = (
            f"A photo analysis (OpenCV 5 image classifier) detected Fall Armyworm "
            f"damage on this maize leaf with {confidence:.0f}% confidence. Using the "
            f"reference information below, confirm this and give the farmer clear, "
            f"immediate next steps."
        )
        # No farmer-written text exists for a photo upload - vision_note is machine-
        # generated, not something to detect a language from - so this always stays in
        # English, consistent with the rest of the photo-check UI.
        prompt = build_prompt(vision_note, retrieved_chunks, domain="crops", photo=True, language="english")
        result["sources"] = retrieved_titles
        result["advice"] = ask_model_server(prompt)

    elif decision_path == "high_confidence_healthy":
        result["sources"] = []
        result["advice"] = (
            "Good news — this leaf looks healthy, with no signs of Fall Armyworm "
            "damage detected. Keep scouting your field regularly, especially during "
            "the wet season when risk is highest."
        )

    elif decision_path == "medium_confidence":
        result["sources"] = []
        result["advice"] = (
            "This photo isn't clear enough for a confident result. Please take "
            "another close-up photo of a single leaf in good light, or describe "
            "what you're seeing (holes, discoloration, droppings) so I can help "
            "further."
        )

    else:  # low_confidence
        result["sources"] = []
        result["advice"] = (
            "I can't give a reliable assessment from this photo. Please inspect "
            "the plant closely yourself, or contact your local extension officer "
            "for an in-person check rather than relying on this result."
        )

    return result