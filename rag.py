"""
Minimal offline RAG pipeline for the ADTC Agri Advisor.

- Loads your corpus markdown file, splits it into chunks (one per ### section)
- Uses TF-IDF (scikit-learn) for retrieval — no extra embedding model to
  download, fully offline, fast enough for a corpus of this size
- Retrieves the top-k most relevant chunks for a farmer's question
- Builds an augmented prompt and calls llama-cli.exe as a subprocess

Usage:
    python rag.py "My cow has a high fever and keeps pushing its head against the kraal post"

Before running, edit the three CONFIG paths below to match your setup.
"""

import re
import subprocess
import sys
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------- CONFIG — edit these three paths ----------------
CORPUS_PATH = r"corpus_livestock_crops.md"          # your corpus file
LLAMA_CLI_PATH = r"C:\llama.cpp\llama-cli.exe"      # path to llama-cli.exe
MODEL_PATH = r"model\qwen2.5-3b-instruct-q4_k_m.gguf"  # your GGUF model
TOP_K = 3                                            # how many chunks to retrieve
# -------------------------------------------------------------------


def load_chunks(path):
    """Split the corpus markdown into chunks, one per ### section heading."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # Split on '### ' headings, keep the heading with its content
    raw_chunks = re.split(r"\n(?=### )", text)
    chunks = [c.strip() for c in raw_chunks if c.strip().startswith("###")]
    return chunks


def build_index(chunks):
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(chunks)
    return vectorizer, matrix


def retrieve(query, chunks, vectorizer, matrix, k=TOP_K):
    query_vec = vectorizer.transform([query])
    sims = cosine_similarity(query_vec, matrix).flatten()
    top_indices = sims.argsort()[::-1][:k]
    return [chunks[i] for i in top_indices if sims[i] > 0]


def build_prompt(query, retrieved_chunks):
    context = "\n\n".join(retrieved_chunks)
    prompt = f"""You are an offline farming advisor for Zimbabwean farmers. Use the reference information below to answer accurately. If the reference information doesn't cover the question, say so honestly rather than guessing, and recommend contacting a vet or extension officer.

Structure your answer in three parts:
1. LIKELY CONDITION: name the most likely condition based on the symptoms described.
2. WHY: briefly explain which symptoms pointed to this condition, referencing the reference information.
3. WHAT TO DO: clear, immediate action steps, including whether this is urgent enough to need a vet right away.

REFERENCE INFORMATION:
{context}

FARMER'S QUESTION:
{query}

ANSWER:"""
    return prompt


def ask_model(prompt, n_predict=250):
    process = subprocess.Popen(
        [
            LLAMA_CLI_PATH,
            "-m", MODEL_PATH,
            "-p", prompt,
            "-n", str(n_predict),
            "--temp", "0.3",   # lower temperature = more grounded, less creative drift
            "-no-cnv",         # single-turn completion, don't drop into interactive chat mode
            "-t", "4",         # optimal thread count found via llama-bench testing (4 physical cores)
        ],
        stdin=subprocess.DEVNULL,   # prevent hanging if it ever waits for further input
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # merge stderr so you see errors inline too
        text=True,
        encoding="utf-8",
        errors="replace",           # avoid crashes on box-drawing/banner characters on Windows
        bufsize=1,
    )

    output_lines = []
    print("(streaming output live — this can take 30-90s on CPU)\n")
    try:
        for line in process.stdout:
            print(line, end="", flush=True)
            output_lines.append(line)
            # llama-cli prints this summary line once generation is fully done.
            # This build drops into an interactive REPL afterward and waits
            # forever for more input, so we detect completion here and force
            # exit immediately instead of waiting or relying on Ctrl+C.
            if "Generation:" in line and "t/s" in line:
                process.kill()
                break
    except KeyboardInterrupt:
        process.kill()
        print("\n(stopped)")

    return "".join(output_lines)


def main():
    if len(sys.argv) < 2:
        print('Usage: python rag.py "your question here"')
        sys.exit(1)

    query = sys.argv[1]

    print("Loading corpus...")
    chunks = load_chunks(CORPUS_PATH)
    print(f"Loaded {len(chunks)} chunks.")

    vectorizer, matrix = build_index(chunks)

    print("Retrieving relevant context...")
    retrieved = retrieve(query, chunks, vectorizer, matrix)
    print(f"Retrieved {len(retrieved)} relevant chunk(s):")
    for r in retrieved:
        print(" -", r.splitlines()[0])  # print just the heading

    prompt = build_prompt(query, retrieved)

    print("\nQuerying model...\n")
    output = ask_model(prompt)
    print(output)


if __name__ == "__main__":
    main()