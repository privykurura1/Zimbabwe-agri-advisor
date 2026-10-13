"""
Tests whether Qwen2.5 can generate a FULL answer directly in Shona - not
translation, genuine generation. This is a real experiment: Qwen2.5 is not on
its own list of officially supported languages, so there's no guarantee here.

Run this with llama-server already running (same as always), then READ the
output yourself and judge it - that's the actual test. I can't verify Shona
quality myself.

    python test_shona_generation.py

For each answer, note:
  - Is it genuinely Shona, or does it drift into English mid-answer?
  - Is the grammar natural, or does it read like a word-for-word translation?
  - Are the disease names/facts actually correct, or just fluent-sounding?
  - Does it ever invent a Shona word that isn't real?
"""
import sys
sys.path.insert(0, ".")
from rag import load_chunks, build_index, retrieve_grounded, build_prompt, CORPUS_PATH
from app import ask_model_server  # reuses your actual app's model-calling code

TEST_QUESTIONS = [
    "Mombe yangu iri kuita weti tsvuku",
    "Mombe yangu ine kupisa uye iri kuzvimba pasi penzeve",
    "Gonye riri mukati mechibage",
    "Mbudzi yangu ine gonye remudumbu",
    "Huku yangu ine manyoka ane ropa",
]

print("Loading corpus...")
chunks = load_chunks(CORPUS_PATH)
vectorizer, matrix = build_index(chunks)

for q in TEST_QUESTIONS:
    print("\n" + "=" * 70)
    print(f"QUESTION: {q}")
    result = retrieve_grounded(q, chunks, vectorizer, matrix)
    if not result["grounded"]:
        print("(no entry matched - skipping)")
        continue
    prompt = build_prompt(
        q, result["chunks"], domain=result["answer_domain"], language="shona"
    )
    print("(generating - this takes a while on CPU)")
    answer = ask_model_server(prompt)
    print(f"\nANSWER:\n{answer}")

print("\n" + "=" * 70)
print("Done. Read each answer above and judge it yourself - that's the real test.")
