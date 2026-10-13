"""
Turns Murimi Fara's query log into a review report: what people asked that the
advisor could not answer, what it refused, and which entries answered what.

    python summarize_query_log.py
    python summarize_query_log.py path\\to\\query_log.jsonl another_testers_log.jsonl

With no arguments it reads %LOCALAPPDATA%\\MurimiFara\\query_log.jsonl (where the
installed app writes it). Give it several files to merge logs from testers.
It prints a summary and writes query_log_report.md.

Read the report in this order:
  1. "Asked for more detail" - questions the knowledge base couldn't cover.
     The most frequent ones are the next entries to write (with a vet or
     agronomist checking them).
  2. "Blocked by a safety guard" - check none of these was a real farming
     question that got refused by mistake. Fix the pattern in rag.py if so.
  3. "Answered" - check the entry used actually fits the question. A wrong
     match here is a wrong answer a farmer would have received.

PRIVACY: the report contains what people typed. Only collect testers' logs
with their agreement, and don't publish the report.
"""
import json
import os
import sys
from collections import Counter, defaultdict


def default_path():
    local = os.environ.get("LOCALAPPDATA")
    if local and os.path.exists(os.path.join(local, "MurimiFara", "query_log.jsonl")):
        return os.path.join(local, "MurimiFara", "query_log.jsonl")
    return "query_log.jsonl"


def load(paths):
    records, bad = [], 0
    for p in paths:
        if not os.path.exists(p):
            print(f"(not found: {p})")
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    bad += 1
    return records, bad


def main():
    paths = sys.argv[1:] or [default_path()]
    records, bad = load(paths)
    if not records:
        print("No records found. Use the app first, or pass the path to a log file.")
        return

    kinds = Counter(r.get("kind", "?") for r in records)
    text_kinds = [k for k in kinds if k != "photo"]
    answered = kinds.get("answered", 0)
    unanswered = kinds.get("needs_more_detail", 0)
    lines = []
    out = lines.append

    out("# Murimi Fara - query log report\n")
    out(f"Files: {', '.join(paths)}  |  {len(records)} records" + (f"  |  {bad} unreadable lines skipped" if bad else "") + "\n")
    out("## Overview\n")
    for k, n in kinds.most_common():
        out(f"- {k}: {n}")
    if answered + unanswered:
        out(f"\nOf the questions the knowledge base was asked to cover, it answered "
            f"{answered} and asked for more detail on {unanswered} "
            f"({100 * answered / (answered + unanswered):.0f}% answered).\n")

    # 1. Not answered
    out("## 1. Asked for more detail - candidates for new entries\n")
    groups = defaultdict(Counter)
    for r in records:
        if r.get("kind") == "needs_more_detail":
            groups[r.get("domain", "unknown")][r.get("query", "").strip().lower()] += 1
    if not groups:
        out("(none)\n")
    for domain in ("crops", "animal", "unknown"):
        if domain in groups:
            out(f"### {domain} ({sum(groups[domain].values())} messages)\n")
            for q, n in groups[domain].most_common():
                out(f"- {n}x  {q}")
            out("")

    # 2. Guards
    out("## 2. Blocked by a safety guard - check for mistakes\n")
    any_guard = False
    for kind in sorted(k for k in kinds if k.startswith("guard:")):
        any_guard = True
        out(f"### {kind[len('guard:'):]} ({kinds[kind]})\n")
        for q in sorted({r.get("query", "").strip() for r in records if r.get("kind") == kind}):
            out(f"- {q[:200]}")
        out("")
    if not any_guard:
        out("(none)\n")

    # 3. Answered
    out("## 3. Answered - check each match fits\n")
    per_entry = defaultdict(list)
    for r in records:
        if r.get("kind") == "answered":
            for e in r.get("entries", []) or ["?"]:
                per_entry[e].append(r.get("query", "").strip())
    if not per_entry:
        out("(none)\n")
    for entry in sorted(per_entry):
        out(f"### {entry} ({len(per_entry[entry])})\n")
        for q in sorted(set(per_entry[entry])):
            out(f"- {q[:200]}")
        out("")

    # photos
    photo = [r for r in records if r.get("kind") == "photo"]
    if photo:
        out("## Photo checks\n")
        for path, n in Counter(r.get("decision_path", "?") for r in photo).most_common():
            out(f"- {path}: {n}")
        out("")

    report = "\n".join(lines)
    with open("query_log_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print("\nWritten to query_log_report.md")


if __name__ == "__main__":
    main()
