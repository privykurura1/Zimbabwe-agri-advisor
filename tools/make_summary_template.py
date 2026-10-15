"""(Re)build data/local_summaries.json from the knowledge base.

Keeps anything already written (Shona, Ndebele, reviewed flags) and only adds
entries that are missing. The English text is a DRAFT taken from the entry's own
Action/Prevention line, for a person to shorten, check and translate.

    python tools/make_summary_template.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from rag import chunk_id, load_chunks  # noqa: E402

PATH = os.path.join(ROOT, "data", "local_summaries.json")


def draft_english(chunk):
    text = " ".join(chunk.splitlines()[1:])
    for label in ("Action", "Management", "Prevention", "What to do"):
        m = re.search(r"\*\*" + label + r":\*\*\s*(.+?)(?=\s-\s\*\*|\s\*\*[A-Z][^*]{2,30}:\*\*|$)", text)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()[:400]
    return ""


def main():
    current = {}
    if os.path.exists(PATH):
        with open(PATH, encoding="utf-8") as f:
            current = json.load(f).get("entries", {})
    entries = {}
    for chunk in load_chunks(os.path.join(ROOT, "corpus_livestock_crops.md")):
        cid = chunk_id(chunk)
        if not cid:
            continue
        title = re.sub(r"^#+\s*[A-Z]\d+\.\s*", "", chunk.splitlines()[0]).strip()
        entries[cid] = current.get(cid) or {"title": title, "en": draft_english(chunk), "sn": "", "nd": "",
                                            "reviewed": False, "reviewed_by": ""}
    doc = {"about": "One short summary per knowledge entry. Write sn (Shona) and nd (Ndebele), check en, "
                    "then set reviewed to true and reviewed_by to your name. Only reviewed entries are shown.",
           "entries": entries}
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"{len(entries)} entries; {sum(1 for e in entries.values() if e['en'])} with an English draft")


if __name__ == "__main__":
    main()
