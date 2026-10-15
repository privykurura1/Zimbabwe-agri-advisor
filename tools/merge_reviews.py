"""Merge officers' review files (and SMS codes) into one report for the Murimi Fara team.

    python tools/merge_reviews.py reviews_folder\\*.json --sms sms_codes.txt

Writes reviews_report.md (read this) and reviews.csv (open in Excel). Files can
arrive more than once (re-sent, copied twice): each review is counted once, by
laptop code + review id.

sms_codes.txt: paste the text messages, one per line, e.g.
    MF B3,F1 R UNSAFE K7Q2

What to do with the report:
  1. "Unsafe" first - check that entry with a vet/agronomist and fix it this week.
  2. Entries with low approval - read the officers' corrected answers; they are
     drafts for a better entry, to be checked by an expert before use.
  3. Missing topics - candidates for new knowledge entries.
Officers' corrections are their opinion, not checked facts: never paste them into
the knowledge base without an expert review.
"""
import argparse
import csv
from collections import Counter, defaultdict
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from challenge_agent.feedback import CATEGORIES, FORMAT  # noqa: E402

SMS = re.compile(r"\bMF\s+([A-Z0-9,\-]+)\s+([AR])\s+([A-Z]+)\s+([A-Z0-9]{4})\b", re.I)


def load_files(patterns):
    reviews, seen, files = [], set(), 0
    for pattern in patterns:
        for path in glob.glob(pattern) or [pattern]:
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError) as exc:
                print(f"skipped {path}: {exc}")
                continue
            if data.get("format") != FORMAT:
                print(f"skipped {path}: not a Murimi Fara reviews file")
                continue
            files += 1
            for r in data.get("reviews", []):
                key = (data.get("installation"), r.get("id"))
                if key in seen:
                    continue
                seen.add(key)
                reviews.append({**r, "installation": data.get("installation", ""),
                                "district": data.get("district", ""), "source": "file"})
    return reviews, files


def load_sms(path):
    out = []
    if not path:
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = SMS.search(line)
            if m:
                ids, decision, cat, inst = m.groups()
                out.append({"entries": [i for i in ids.upper().split(",") if i != "-"],
                            "decision": "approved" if decision.upper() == "A" else "rejected",
                            "category": cat.upper(), "installation": inst.upper(), "source": "sms"})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="review JSON files (wildcards allowed)")
    ap.add_argument("--sms", help="text file with SMS codes, one per line")
    ap.add_argument("--out", default=".")
    args = ap.parse_args(argv)

    reviews, nfiles = load_files(args.files)
    sms = load_sms(args.sms)
    by_entry = defaultdict(Counter)
    for r in reviews + sms:
        for e in r.get("entries") or ["(none)"]:
            by_entry[e][r["decision"]] += 1
            by_entry[e][r["category"]] += 1
    cats = Counter(r["category"] for r in reviews + sms)
    missing = Counter(r["missing_topic"].strip().lower() for r in reviews if r.get("missing_topic", "").strip())
    laptops = {r["installation"] for r in reviews + sms}

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "reviews.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["source", "installation", "district", "decided_at", "decision", "category", "entries",
                    "urgent", "region", "question", "draft", "reason", "correction", "missing_topic"])
        for r in reviews + sms:
            w.writerow([r["source"], r["installation"], r.get("district", ""), r.get("decided_at", ""),
                        r["decision"], r["category"], " ".join(r.get("entries", [])), r.get("urgent", ""),
                        r.get("region", ""), r.get("question", ""), r.get("draft", ""), r.get("reason", ""),
                        r.get("correction", ""), r.get("missing_topic", "")])

    lines = [f"# Murimi Fara officer reviews\n",
             f"{len(reviews)} reviews from {nfiles} file(s), {len(sms)} SMS code(s), {len(laptops)} laptop(s).\n"]
    unsafe = [r for r in reviews + sms if r["category"] == "UNSAFE"]
    lines.append("## 1. Unsafe advice reported\n")
    if unsafe:
        for r in unsafe:
            lines.append(f"- **{', '.join(r.get('entries', [])) or '-'}** ({r['source']}, laptop {r['installation']}"
                         f"{', ' + r['district'] if r.get('district') else ''}): {r.get('question', '')[:160]}"
                         + (f"\n  - Officer's correction: {r['correction'][:400]}" if r.get("correction") else ""))
    else:
        lines.append("None reported.")
    lines.append("\n## 2. By knowledge entry (lowest approval first)\n")
    lines.append("| Entry | Reviews | Approved | Rejected | Approval | Main problems |\n|---|---|---|---|---|---|")
    rows = []
    for e, c in by_entry.items():
        total = c["approved"] + c["rejected"]
        rate = c["approved"] / total if total else 0
        probs = ", ".join(f"{CATEGORIES.get(k, k)} ({n})" for k, n in c.most_common()
                          if k in CATEGORIES and k != "NONE")
        rows.append((rate, e, total, c["approved"], c["rejected"], probs))
    for rate, e, total, a, rj, probs in sorted(rows):
        lines.append(f"| {e} | {total} | {a} | {rj} | {rate:.0%} | {probs or '-'} |")
    lines.append("\n## 3. Problem categories\n")
    for k, n in cats.most_common():
        lines.append(f"- {CATEGORIES.get(k, k)}: {n}")
    lines.append("\n## 4. Topics officers say are missing\n")
    lines += [f"- {t} ({n})" for t, n in missing.most_common()] or ["None reported."]
    lines.append("\n## 5. Officers' corrected answers\n")
    lines.append("Opinions to check with an expert, not facts to copy into the knowledge base.\n")
    for r in reviews:
        if r.get("correction"):
            lines.append(f"- **{', '.join(r['entries']) or '-'}** - Q: {r['question'][:160]}\n"
                         f"  - Correction: {r['correction'][:600]}")
    with open(os.path.join(args.out, "reviews_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(reviews)} reviews + {len(sms)} SMS -> reviews_report.md, reviews.csv")


if __name__ == "__main__":
    main()
