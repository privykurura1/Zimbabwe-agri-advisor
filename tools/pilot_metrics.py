"""Pilot numbers from one or more query logs (counts only, no farmer text).

    python tools/pilot_metrics.py query_log.jsonl [more logs...]  -> pilot_metrics.csv + printout

Per ISO week: questions, answered from the knowledge base, asked for more
detail, blocked by a safety guard, urgent referrals, photos, provinces given.
Outcome measures (did the farmer act? did the animal recover?) cannot come from
the log - they come from the follow-up form in docs/PILOT_PLAN.md.
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime

FIELDS = ["week", "questions", "answered", "needs_more_detail", "guarded", "urgent", "photos",
          "with_province", "answered_pct"]


def week_of(t):
    y, w, _ = datetime.fromisoformat(t).isocalendar()
    return f"{y}-W{w:02d}"


def main(paths):
    rows = defaultdict(lambda: dict.fromkeys(FIELDS[1:-1], 0))
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    wk = week_of(r["time"])
                except (ValueError, KeyError):
                    continue
                kind, row = r.get("kind", ""), rows[wk]
                if kind == "photo":
                    row["photos"] += 1
                    continue
                row["questions"] += 1
                if kind == "answered":
                    row["answered"] += 1
                    row["urgent"] += bool(r.get("urgent"))
                elif kind == "needs_more_detail":
                    row["needs_more_detail"] += 1
                elif kind.startswith("guard:"):
                    row["guarded"] += 1
                row["with_province"] += bool(r.get("province"))
    with open("pilot_metrics.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        for wk in sorted(rows):
            row = rows[wk]
            row["answered_pct"] = round(100 * row["answered"] / row["questions"], 1) if row["questions"] else ""
            w.writerow({"week": wk, **row})
            print(wk, row)
    print("written pilot_metrics.csv")


if __name__ == "__main__":
    main(sys.argv[1:] or ["query_log.jsonl"])
