"""
Local API backend for the Offline AI Farming Advisor.

Wraps your existing rag.py retrieval logic (corpus loading, domain-filtered
retrieval) and talks to a running llama-server instance for inference.

WHY llama-server INSTEAD OF llama-cli:
llama-cli reloads the entire model from disk into RAM on every single call,
which is most of what made this feel slow. llama-server loads the model
ONCE and keeps it in memory, answering each question almost instantly
after that. You need to start it separately, once, before this backend.

SETUP:
    pip install fastapi uvicorn

STEP 1 — start llama-server (in its own terminal, leave it running):
    C:\\llama.cpp\\llama-server.exe -m model\\qwen2.5-3b-instruct-q4_k_m.gguf -t 4 -c 4096 --port 8080

STEP 2 — start this backend (in a second terminal):
    uvicorn app:app --reload --port 8000

Then open frontend/index.html in a browser.
"""

import json
import urllib.request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Reuse the retrieval logic already built and tested in rag.py.
# (We no longer use rag.py's ask_model — llama-server replaces it.)
from rag import load_chunks, build_index, retrieve, build_prompt, CORPUS_PATH

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
print(f"Ready — {len(_chunks)} chunks loaded.")

LLAMA_SERVER_URL = "http://localhost:8080/completion"


class Question(BaseModel):
    question: str


def ask_model_server(prompt: str, n_predict: int = 250) -> str:
    """
    Calls the already-running llama-server instead of spawning a new
    llama-cli process. This is what makes repeated questions fast —
    the model stays loaded in memory between requests.
    """
    payload = json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0.3,
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
        # not the echoed prompt — no cleanup/parsing needed, unlike llama-cli.
        return data.get("content", "").strip()
    except urllib.error.URLError:
        raise ConnectionError(
            "Could not reach llama-server on port 8080. "
            "Make sure llama-server.exe is running first."
        )


def stream_llama_server(prompt: str, n_predict: int = 250):
    """
    Streams the answer token-by-token from llama-server as it's generated,
    instead of waiting for the full answer to finish. This is what makes
    the app feel responsive like a chat assistant — text starts appearing
    within a couple seconds instead of a long silent wait. Total generation
    speed is unchanged (still bounded by the CPU), but perceived speed is
    much better since the person sees continuous progress.
    """
    payload = json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0.3,
        "stream": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        LLAMA_SERVER_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

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
                yield content
            if data.get("stop"):
                break


@app.post("/api/ask/stream")
def ask_stream(payload: Question):
    """
    Streaming version of /api/ask. Sends the retrieved source titles first
    (as a special first line), then streams the answer text as it's
    generated. The frontend reads this incrementally instead of waiting
    for one big JSON response.
    """
    query = payload.question
    retrieved_chunks = retrieve(query, _chunks, _vectorizer, _matrix)
    retrieved_titles = [c.splitlines()[0].replace("### ", "") for c in retrieved_chunks]
    prompt = build_prompt(query, retrieved_chunks)

    def generate():
        yield f"SOURCES:::{json.dumps(retrieved_titles)}\n"
        try:
            for chunk in stream_llama_server(prompt):
                yield chunk
        except ConnectionError as e:
            yield f"\n\nError: {e}"

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/api/ask")
def ask(payload: Question):
    query = payload.question

    retrieved_chunks = retrieve(query, _chunks, _vectorizer, _matrix)
    retrieved_titles = [c.splitlines()[0].replace("### ", "") for c in retrieved_chunks]

    prompt = build_prompt(query, retrieved_chunks)

    try:
        answer = ask_model_server(prompt)
    except ConnectionError as e:
        return {"question": query, "retrieved_sources": [], "answer": f"Error: {e}"}

    return {
        "question": query,
        "retrieved_sources": retrieved_titles,
        "answer": answer,
    }


@app.get("/api/health")
def health():
    """Quick check the frontend can use to confirm the backend is running."""
    return {"status": "ok", "chunks_loaded": len(_chunks)}