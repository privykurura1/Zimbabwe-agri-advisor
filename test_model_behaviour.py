"""
Murimi Fara - real-model behaviour test.

Sends farmer-style questions (English and Shona) through the SAME path the app
uses (safety guard -> retrieval gate -> prompt -> llama-server -> output
guard) and checks each answer automatically for the problems found in testing:

  * did the model stop by itself, or run on / get cut off?
  * did the output guard have to remove invented text?
  * crop answers that mention vets or animals
  * "the farmer's cow" instead of "your cow"
  * signs the farmer never mentioned (possible invented symptoms)
  * doses, chemical names or spray rates
  * answers that are too long
  * expected condition missing from the answer

HOW TO RUN (on the laptop, with llama-server already running on port 8080):

    python test_model_behaviour.py

It writes every answer to model_behaviour_report.md. Read that file yourself:
the automatic checks catch the common failures, they cannot judge whether the
advice is correct. A vet and an AGRITEX officer should read it before real
farmers rely on the app.

Optional: python test_model_behaviour.py --url http://localhost:8080/completion
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rag import (load_chunks, build_index, retrieve_grounded, build_prompt, scope_guard,
                 detect_language, tidy_answer, question_kind, prefill_of, is_crop_prompt, query_of, CORPUS_PATH)

# Same settings as app.py, copied so this test does not start the web app.
N_PREDICT = 350
STOP_SEQUENCES = ["<|im_end|>", "<|im_start|>", "FARMER'S MESSAGE:", "REFERENCE INFORMATION:",
                  "\nQUESTION:"]

# (message, domain: "crops"/"animal", words of which at least one should appear
#  in a good answer - or None when any grounded answer is acceptable)
CASES = [
    # From test_prompts.md
    ("My cow has a high fever and keeps pushing its head against the kraal post, walking in circles. What's wrong and what do I do right now?",
     "animal", ["heartwater"]),
    ("It's January and my cattle are getting swollen glands near the ear and won't eat. Is this January disease?",
     "animal", ["january", "theileri"]),
    ("My goat's urine looks dark red today. Should I be worried?", "animal", None),
    ("How often should I be dipping my cattle right now, it's the start of the rainy season?", "animal", ["dip"]),
    ("One of my broilers is sneezing and has watery eyes, the others seem fine so far - what should I check for?",
     "animal", None),
    ("I'm in Mashonaland, when should I plant my maize this year?", "crops", ["rain", "plant"]),
    ("There are ragged holes and droppings in the middle of my young maize plants, what's eating them?",
     "crops", ["armyworm"]),
    ("Is it safe for me to treat gallsickness myself or do I need a vet?", "animal", ["vet"]),
    # From the 28 Sept test report
    ("my maize has yellow leaves", "crops", None),
    # Shona
    ("Mombe yangu iri kuita weti tsvuku", "animal", ["redwater", "babes", "weti"]),
    ("Gonye riri mukati mechibage", "crops", ["armyworm", "gonye"]),
    ("Mbudzi yangu ine gonye remudumbu", "animal", None),
    ("Huku yangu ine manyoka ane ropa", "animal", ["cocci"]),
    ("Ndodyara chibage rini?", "crops", ["rain", "mvura"]),
]

# Words for signs a farmer might report. If the answer contains one that the
# farmer's message does not, the model may have invented it (English only).
SIGNS = {
    "fever": ["fever", "high temperature"],
    "red urine": ["red urine", "redwater", "dark urine", "red-brown", "urine looks dark red", "red or brown urine"],
    "diarrhoea": ["diarrh", "scour", "loose dung", "watery dung"], "blood": ["blood", "bloody"],
    "cough": ["cough"], "sneez": ["sneez"], "swollen": ["swollen", "swelling", "swell"],
    "circling": ["circl"], "head pressing": ["head press", "pushing its head", "pressing its head"],
    "not eating": ["not eating", "won't eat", "loss of appetite", "off feed", "stopped eating"],
    "weak": ["weak", "weakness"], "pale": ["pale", "anaemi", "anemi"], "trembling": ["trembl"],
    "yellow leaves": ["yellow leaves", "yellowing leaves", "leaves turn yellow"], "holes": ["holes", "ragged"], "wilting": ["wilt"],
    "droppings/frass": ["frass", "droppings"], "purple": ["purple"], "breathing": ["breath"],
    "discharge": ["discharge"], "drooling": ["drool", "saliva"], "lame": ["lame", "limp"],
}
VET_WORDS = re.compile(r"\b(vet|vets|veterinar\w*|livestock|cattle|animal health|dip tank)\b", re.I)
THIRD_PERSON = re.compile(r"\bthe farmer'?s?\b", re.I)
DOSE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|ml|g|kg|l|litres?|liters?|cc)\b(?:\s*(?:/|per)\s*\w+)?"
                  r"|\b(?:oxytetracycline|ivermectin|albendazole|imidocarb|diminazene|buparvaquone|"
                  r"cypermethrin|emamectin|lambda[- ]?cyhalothrin|chlorpyrifos|mancozeb|carbaryl)\b", re.I)


def call_model(url, prompt):
    payload = json.dumps({
        "prompt": prompt, "n_predict": N_PREDICT, "temperature": 0.3,
        "repeat_penalty": 1.1, "cache_prompt": True, "stop": STOP_SEQUENCES,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))


def stop_reason(data):
    """'eos' (model ended its turn - the good case), 'word', 'limit' or '?'."""
    if data.get("stop_type"):
        return data["stop_type"]
    if data.get("stopped_eos"):
        return "eos"
    if data.get("stopped_word"):
        return "word"
    if data.get("stopped_limit"):
        return "limit"
    return "?"


def has(text, words):
    t = text.lower()
    return any(w in t for w in words)


def check(query, domain, expect, raw, clean, was_cut, reason, language):
    problems, warnings = [], []
    if reason == "limit":
        problems.append("hit the length limit - answer cut off")
    elif reason == "word":
        warnings.append("stopped on a stop word, not by itself - the chat layout may not be working")
    elif reason == "?":
        warnings.append("llama-server did not say why it stopped")
    if was_cut:
        problems.append("output guard removed run-on text (%d characters)" % (len(raw.strip()) - len(clean)))
    if clean and clean[-1] not in ".!?)\"'*_":
        problems.append("does not end on a full sentence")
    if domain == "crops" and VET_WORDS.search(clean):
        problems.append("crop answer mentions vets/animals: %r" % VET_WORDS.search(clean).group())
    if THIRD_PERSON.search(clean):
        problems.append("says 'the farmer' instead of 'you'")
    if DOSE.search(clean):
        problems.append("gives a dose/chemical: %r" % DOSE.search(clean).group())
    if re.search(r"###[^\n]*\n\s*(?=###|\Z)", clean + "\n"):
        problems.append("a section is empty (the model may have copied instructions)")
    if re.search(r"The signs fit\s*(?:\.\.\.|…|\n|$)", clean):
        problems.append("did not name a condition after 'The signs fit'")
    words = len(clean.split())
    if words > 170:
        problems.append("too long (%d words, asked for under 120)" % words)
    if expect and not has(clean, expect):
        problems.append("expected one of %s in the answer" % expect)
    if question_kind(query) == "QUESTION" and re.search(r"signs fit|likely condition", clean, re.I):
        problems.append("a plain question was answered with a diagnosis")
    if language == "english":
        # Signs asked about under "Check for" are questions, not claims.
        claims = re.sub(r"###\s*Check for.*?(?=###|\Z)", "", clean, flags=re.S | re.I)
        invented = [name for name, ws in SIGNS.items() if has(claims, ws) and not has(query, ws)]
        if invented:
            warnings.append("signs the farmer did not mention: " + ", ".join(invented)
                            + " (check: invented, or fair advice on what to look for?)")
    return problems, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080/completion")
    ap.add_argument("--out", default="model_behaviour_report.md")
    args = ap.parse_args()

    print("Loading corpus...")
    corpus = CORPUS_PATH
    if not os.path.exists(corpus):   # run from another folder
        corpus = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.basename(CORPUS_PATH))
    chunks = load_chunks(corpus)
    vectorizer, matrix = build_index(chunks)
    print("%d entries loaded.\n" % len(chunks))

    lines = ["# Murimi Fara - model behaviour report",
             "", "Run: %s  |  %d questions  |  %d corpus entries" % (
                 datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), len(CASES), len(chunks)), ""]
    totals = {"pass": 0, "fail": 0, "asked": 0}
    times = []

    for i, (query, domain, expect) in enumerate(CASES, 1):
        print("[%d/%d] %s" % (i, len(CASES), query[:70]))
        lines += ["---", "", "## %d. %s" % (i, query), ""]

        guard = scope_guard(query)
        if guard:
            print("      safety guard: %s (model not called)\n" % guard["kind"])
            lines += ["**Safety guard (%s), model not called.**" % guard["kind"], "", guard["answer"], ""]
            totals["asked"] += 1
            continue
        result = retrieve_grounded(query, chunks, vectorizer, matrix)
        if not result["grounded"]:
            print("      no matching entry: app asks for more detail (model not called)\n")
            lines += ["**No matching entry - the app asks for more detail. Model not called.**", ""]
            totals["asked"] += 1
            continue

        language = detect_language(query)
        prompt = build_prompt(query, result["chunks"], domain=result["answer_domain"], language=language)
        start = time.time()
        try:
            data = call_model(args.url, prompt)
        except (urllib.error.URLError, OSError) as e:
            print("\nCould not reach llama-server at %s (%s).\nStart it first, e.g.\n"
                  "  llama-server -m model\\qwen2.5-1.5b-instruct-q4_k_m.gguf -t 4 -c 4096 --port 8080"
                  % (args.url, e))
            sys.exit(1)
        secs = time.time() - start
        times.append(secs)

        raw = prefill_of(prompt) + data.get("content", "")
        clean, was_cut = tidy_answer(raw, crop=is_crop_prompt(prompt), query=query_of(prompt))
        reason = stop_reason(data)
        problems, warnings = check(query, domain, expect, raw, clean, was_cut, reason, language)
        status = "FAIL" if problems else "PASS"
        totals["pass" if not problems else "fail"] += 1

        print("      %s  (%.0fs, stopped: %s, %d words)" % (status, secs, reason, len(clean.split())))
        for p in problems:
            print("        - " + p)
        for w in warnings:
            print("        ? " + w)
        print()

        sources = [c.splitlines()[0].replace("### ", "") for c in result["chunks"]]
        lines += ["**%s** - %.0f s - stopped: %s - %d words - language: %s - urgent flag: %s" % (
                      status, secs, reason, len(clean.split()), language, result["urgent"]),
                  "", "Sources: " + "; ".join(sources), ""]
        lines += ["- PROBLEM: " + p for p in problems]
        lines += ["- check: " + w for w in warnings]
        lines += ["", "**Answer the farmer sees:**", "", clean, ""]
        if clean != raw.strip():
            lines += ["<details><summary>Raw model output (before the guard)</summary>", "", "```",
                      raw.strip(), "```", "</details>", ""]
        lines += ["Reviewer: correct?  yes / partly / no   Notes: ____________", ""]

    summary = "Model answers: %d pass, %d fail. Handled without the model: %d." % (
        totals["pass"], totals["fail"], totals["asked"])
    if times:
        summary += " Average answer time: %.0f s (slowest %.0f s)." % (sum(times) / len(times), max(times))
    lines[3:3] = ["**" + summary + "**", ""]
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(summary)
    print("Full answers written to %s - read them, and have a vet / AGRITEX officer read them too." % args.out)


if __name__ == "__main__":
    main()
