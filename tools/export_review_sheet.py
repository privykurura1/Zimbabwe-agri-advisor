"""Write the expert review sheet: one row per knowledge entry, ready for a vet or
agronomist to fill in (opens in Excel / LibreOffice / Google Sheets).

    python tools/export_review_sheet.py            -> review/expert_review_sheet.csv
"""
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import rag  # noqa: E402

# Questions already found in testing that only an expert can settle.
KNOWN_QUESTIONS = {
    "B3": "A goat question was answered from this cattle entry (it has no species tag). Does redwater "
          "advice apply to goats/sheep as written, or should the entry say cattle only?",
    "E1": "The model wrote 'Deworm your goat'. Is that acceptable advice without a faecal test / FAMACHA "
          "check, given resistance concerns?",
}

COLUMNS = ["id", "title", "urgent_flag", "text", "known_question",
           "facts_correct (yes/no/partly)", "safe_for_farmers (yes/no)", "what_to_change",
           "missing_for_zimbabwe", "species_or_crops_it_applies_to", "reviewer_name", "qualification",
           "date"]


def main():
    out_dir = os.path.join(ROOT, "review")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "expert_review_sheet.csv")
    chunks = rag.load_chunks(rag.CORPUS_PATH)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for c in chunks:
            cid = rag.chunk_id(c) or ""
            title = re.sub(r"^#+\s*", "", c.splitlines()[0])
            w.writerow([cid, title, "yes" if rag.is_urgent_entry(c) else "",
                        "\n".join(c.splitlines()[1:]).strip(), KNOWN_QUESTIONS.get(cid, "")]
                       + [""] * (len(COLUMNS) - 5))
    print(f"{len(chunks)} entries -> {path}")


if __name__ == "__main__":
    main()
