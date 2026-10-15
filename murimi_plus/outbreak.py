"""Outbreak early warning from the app's own query log.

Counts how often each condition was matched, by province and ISO week, and
flags a condition when this week's count is clearly above its recent level.
Only counts leave this module: never the farmer's message.

Rule (simple on purpose, so a vet can understand and question it):
    alert if   count in the last 7 days >= MIN_CASES
    and        count >= SPIKE_FACTOR x the average weekly count of the 4 weeks before
               (or there were no cases at all in those 4 weeks).
A spike in questions is a reason to look, not proof of an outbreak.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
import os

MIN_CASES = 3
SPIKE_FACTOR = 2.0
BASELINE_WEEKS = 4

PROVINCES = ["Bulawayo", "Harare", "Manicaland", "Mashonaland Central", "Mashonaland East",
             "Mashonaland West", "Masvingo", "Matabeleland North", "Matabeleland South", "Midlands"]


def read_log(path):
    """Yield the 'answered' records of a query_log.jsonl file; skip bad lines."""
    if not path or not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("kind") == "answered" and record.get("entries"):
                yield record


def _when(record):
    try:
        return datetime.fromisoformat(record["time"])
    except (KeyError, ValueError):
        return None


def summarise(records, titles, now=None):
    """Counts and alerts. `titles` maps entry id -> condition name; entries not in
    it (regions, planting times, general advice) are not diseases and are skipped."""
    now = now or datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    base_start = week_start - timedelta(weeks=BASELINE_WEEKS)
    recent, baseline = Counter(), Counter()
    by_province = defaultdict(Counter)
    weekly = defaultdict(Counter)            # entry -> {iso week label: count}
    total = 0
    for record in records:
        when = _when(record)
        if when is None:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        for entry in record["entries"]:
            if entry not in titles:
                continue
            total += 1
            year, week, _ = when.isocalendar()
            weekly[entry][f"{year}-W{week:02d}"] += 1
            province = record.get("province") or "Not given"
            if when >= week_start:
                recent[entry] += 1
                by_province[entry][province] += 1
            elif when >= base_start:
                baseline[entry] += 1
    alerts = []
    for entry, count in recent.items():
        average = baseline[entry] / BASELINE_WEEKS
        if count >= MIN_CASES and (average == 0 or count >= SPIKE_FACTOR * average):
            alerts.append({"entry": entry, "condition": titles[entry], "last_7_days": count,
                           "weekly_average_before": round(average, 1),
                           "provinces": dict(by_province[entry].most_common())})
    alerts.sort(key=lambda a: a["last_7_days"], reverse=True)
    table = sorted(({"entry": e, "condition": titles[e], "last_7_days": recent[e],
                     "previous_4_weeks": baseline[e], "provinces": dict(by_province[e].most_common())}
                    for e in set(recent) | set(baseline)),
                   key=lambda r: (r["last_7_days"], r["previous_4_weeks"]), reverse=True)
    return {"generated": now.isoformat(timespec="minutes"), "total_matches": total,
            "alerts": alerts, "table": table, "weekly": {e: dict(w) for e, w in weekly.items()},
            "rule": {"min_cases": MIN_CASES, "spike_factor": SPIKE_FACTOR, "baseline_weeks": BASELINE_WEEKS}}
