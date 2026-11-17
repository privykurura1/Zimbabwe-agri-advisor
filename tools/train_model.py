"""Train Murimi Fara's own model, check it, and save it only if it is not worse.

    python tools/train_model.py                       # train from data/training_phrases.csv
    python tools/train_model.py --reviews reviews\\*.json   # also learn from officers' review files
    python tools/train_model.py --seed                # first time: add phrases from the farm book

Where the examples come from (data/training_phrases.csv, one example per row):
  text, entry, language, source, checked_by
  * source "farm_book": taken from the farm book itself (titles, symptom lines,
    the farmer phrasings already written in it). Added by --seed.
  * add your own rows: how farmers really describe each problem, in English,
    Shona and Ndebele. Put who checked it in checked_by.
  * --reviews: officers' review files (the "reviews file" from the officer page).
    A review teaches the model when the officer APPROVED the answer (the entry was
    right) or picked the CORRECT ENTRY for a wrong one.

The check (nothing is saved if it gets worse):
  * every case in test_rag_gate.py (real messages from testing) is run through
    the whole app pipeline: must it answer or ask for detail, which entry, is it
    urgent - plus data/test_phrases.csv if you add one (text, entry; leave entry
    empty for "should ask for more detail");
  * test cases are NEVER used for training, so the score is honest.
"""
import argparse
import ast
import csv
import datetime
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import advisor  # noqa: E402
import matcher  # noqa: E402
import rag  # noqa: E402

PHRASES = os.path.join(ROOT, "data", "training_phrases.csv")
TEST_PHRASES = os.path.join(ROOT, "data", "test_phrases.csv")
MODEL = os.path.join(ROOT, "models", "murimi_model.json")
CORPUS = os.path.join(ROOT, rag.CORPUS_PATH)
FIELDS = ["text", "entry", "language", "source", "checked_by"]
_QUOTED = re.compile(r'"([^"\n]{3,120})"')
_PHRASE_BLOCK = re.compile(r"\*\*(?:Farmer phrases|Local names|Local aliases|Local terms):\*\*(.*?)(?=\n[ \t]*-[ \t]*\*\*|\n[ \t]*\n|\Z)",
                           re.S)
_SIGNS = re.compile(r"\*\*(?:Symptoms|Signs|Typical signs[^:]*|Possible signs|Danger signs):\*\*(.*?)(?=\n[ \t]*-[ \t]*\*\*|\n[ \t]*\n|\Z)",
                    re.S)


# ---------------------------------------------------------------- examples
def farm_book_examples(chunks):
    """Examples already written in the farm book - nothing invented."""
    rows = []
    for chunk in chunks:
        cid = rag.chunk_id(chunk)
        found = [advisor.title_of(chunk)]
        local = []
        for block in _PHRASE_BLOCK.findall(chunk):
            block = " ".join(block.split())
            found += _QUOTED.findall(block)
            local += local_names(block)
        for block in _SIGNS.findall(chunk):
            found.append(" ".join(block.split()))
        for text in found:
            text = " ".join(text.split()).strip(" .")
            if len(text) >= 3:
                rows.append({"text": text, "entry": cid, "language": rag.detect_language(text),
                             "source": "farm_book", "checked_by": ""})
        for text, language in local:
            rows.append({"text": text, "entry": cid, "language": language,
                         "source": "farm_book", "checked_by": ""})
    return rows


_LOCAL_SEGMENT = re.compile(r"\b(Shona|Ndebele)\s*[—–-]\s*(.*?)(?=\b(?:Shona|Ndebele)\s*[—–-]|$)")


def local_names(block):
    """Shona and Ndebele names written in a "Local names: Shona — ..., ...
    Ndebele — ..." line, as (name, language). Notes in brackets are dropped."""
    text = re.sub(r"\([^)]*\)", " ", block)
    out = []
    for language, names in _LOCAL_SEGMENT.findall(text):
        for name in re.split(r"[,;.]", names):
            name = " ".join(name.split()).strip(" .—-")
            if len(name) >= 6 and "PENDING" not in name.upper():
                out.append((name, language.lower()))
    return out


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def review_examples(patterns):
    """Labelled examples from officers' review files (feedback.export_file)."""
    rows, seen = [], set()
    for pattern in patterns:
        for path in glob.glob(pattern) or [pattern]:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for r in data.get("reviews", []):
                key = (data.get("installation"), r.get("id"))
                if key in seen or not r.get("question"):
                    continue
                seen.add(key)
                if r.get("correct_entry"):
                    entry, source = r["correct_entry"], "officer_correction"
                elif r.get("decision") == "approved" and r.get("category", "NONE") == "NONE" and r.get("entries"):
                    entry, source = r["entries"][0], "officer_approved"
                else:
                    continue
                rows.append({"text": r["question"], "entry": entry, "language": rag.detect_language(r["question"]),
                             "source": source, "checked_by": "officer " + str(data.get("installation", ""))})
    return rows


# ---------------------------------------------------------------- the check
def gate_cases():
    """CASES and URGENT_CASES from test_rag_gate.py, read without running it."""
    tree = ast.parse(open(os.path.join(ROOT, "test_rag_gate.py"), encoding="utf-8").read())
    names = {"ANSWER": True, "ASK": False}
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"CASES", "URGENT_CASES"}:
                found[name] = eval(compile(ast.Expression(node.value), "test_rag_gate.py", "eval"), {}, names)
    cases = [(msg, should, must) for _label, msg, should, must in found.get("CASES", [])]
    for row in read_csv(TEST_PHRASES):
        cases.append((row["text"], bool(row.get("entry")), {row["entry"]} if row.get("entry") else None))
    return cases, found.get("URGENT_CASES", [])


def evaluate(adv):
    """Run every test case through the full pipeline. Returns the score and the failures."""
    cases, urgent_cases = gate_cases()
    failures = []
    for msg, should_answer, must_use in cases:
        found = adv.find(msg)
        answered = found["kind"] == "answer"
        ok = answered == should_answer and (not must_use or must_use <= set(found["entries"]))
        if not ok:
            failures.append({"message": msg, "wanted": sorted(must_use) if must_use else ("answer" if should_answer else "ask"),
                             "got": found["entries"] or found["kind"], "by": found["matched_by"]})
    for msg, expect in urgent_cases:
        if adv.find(msg)["urgent"] != expect:
            failures.append({"message": msg, "wanted": f"urgent={expect}", "got": f"urgent={not expect}", "by": None})
    total = len(cases) + len(urgent_cases)
    return {"passed": total - len(failures), "total": total, "failures": failures}


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", action="store_true", help="add the farm book's own phrases to training_phrases.csv")
    ap.add_argument("--reviews", nargs="*", default=[], help="officers' review files (JSON)")
    ap.add_argument("--strong", type=float, default=0.80, help="score to trust the model over the search")
    ap.add_argument("--weak", type=float, default=0.65, help="lowest score the model may answer with (marked 'not sure')")
    ap.add_argument("--force", action="store_true", help="save even if the check got worse")
    ap.add_argument("--out", default=MODEL)
    args = ap.parse_args(argv)

    chunks = rag.load_chunks(CORPUS)
    known = {rag.chunk_id(c) for c in chunks}
    rows = read_csv(PHRASES)
    if args.seed:
        have = {(r["text"].lower(), r["entry"]) for r in rows}
        new = [r for r in farm_book_examples(chunks) if (r["text"].lower(), r["entry"]) not in have]
        rows += new
        write_csv(PHRASES, rows)
        print(f"Added {len(new)} farm book phrases to {os.path.relpath(PHRASES, ROOT)}")

    examples = rows + review_examples(args.reviews)
    test_texts = {msg.lower() for msg, _s, _m in gate_cases()[0]}
    bad = [e for e in examples if e["entry"] not in known]
    leaked = [e for e in examples if e["text"].lower() in test_texts]
    for e in bad:
        print(f"SKIPPED (no entry {e['entry']} in the farm book): {e['text'][:60]}")
    if leaked:
        print(f"SKIPPED {len(leaked)} example(s) that are also test cases (kept out so the check stays honest)")
    examples = [e for e in examples if e not in bad and e not in leaked]
    if not examples:
        print("No training examples. Run with --seed first.")
        return 1

    previous = matcher.load(args.out) if os.path.exists(args.out) else None
    sources = {}
    for e in examples:
        sources[e.get("source") or "unknown"] = sources.get(e.get("source") or "unknown", 0) + 1
    model = matcher.Model([{k: e.get(k, "") for k in ("text", "entry", "source")} for e in examples],
                          {"strong": args.strong, "weak": args.weak})

    adv = advisor.Advisor(CORPUS)
    adv.model = model
    score = evaluate(adv)
    adv.model = None
    baseline = evaluate(adv)
    print(f"\nCheck: {score['passed']}/{score['total']} with the new model "
          f"(farm book search alone: {baseline['passed']}/{baseline['total']})")
    for f in score["failures"]:
        print(f"  FAIL  {f['message'][:60]!r}: wanted {f['wanted']}, got {f['got']} ({f['by']})")

    prev_passed = previous.info.get("check", {}).get("passed", -1) if previous else -1
    if score["passed"] < max(prev_passed, baseline["passed"]) and not args.force:
        print(f"\nNOT SAVED: the new model passes fewer checks than "
              f"{'the current model' if prev_passed >= baseline['passed'] else 'the search alone'}. "
              "Fix the examples, or use --force if you are sure.")
        return 2
    version = (previous.info.get("version", 0) if previous else 0) + 1
    model.info = {"version": version,
                  "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  "examples": len(examples), "sources": sources,
                  "check": {"passed": score["passed"], "total": score["total"]},
                  "search_alone": {"passed": baseline["passed"], "total": baseline["total"]}}
    matcher.save(model, args.out)
    size = os.path.getsize(args.out) / 1024
    print(f"\nSaved model version {version} to {os.path.relpath(args.out, ROOT)} ({size:.0f} KB, {len(examples)} examples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
