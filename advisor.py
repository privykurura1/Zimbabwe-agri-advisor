"""Murimi Fara's answer pipeline - no AI language model anywhere.

    farmer's message
      -> safety check (rag.scope_guard): fixed safety replies (dose questions,
         sudden deaths/anthrax, human illness, tricks)
      -> which farm book entry? Two independent ways, combined:
           * farm book search (rag.retrieve_grounded) - tested rules
           * our own trained model (matcher.py) - learns from checked examples
      -> the answer IS that farm book entry, laid out for the farmer, with the
         urgent warning when the entry is time-critical
      -> nothing matches: ask for more detail (rag.fallback_answer), never guess

The app, the officer review page and the tests all use this one function, so
they can never disagree.
"""
import os
import re

import matcher
import rag

# How the entry was chosen - shown to officers and saved for the outbreak log.
FARM_BOOK = "farm_book_search"
MODEL = "model"
MODEL_UNSURE = "model_unsure"

_HEADING = re.compile(r"^#+\s*[A-Z]\d+\.\s*")
# Lines meant for the search or for editors, not for farmers.
_INTERNAL_LINE = re.compile(r"^[ \t]*(?:-[ \t]*)?\*\*(?:Applies to|Urgency|Type|Status):\*\*[^\n]*\n?", re.I | re.M)
_FARMER_PHRASES = re.compile(r"^\*\*Farmer phrases:\*\*.*?(?:\n[ \t]*\n|\Z)", re.S | re.M)

URGENT_LINE = ("**URGENT - this can kill quickly. Contact a veterinary officer or animal-health "
               "worker TODAY. Do not wait to see if it gets better.**")
UNSURE_LINE = ("*I am not fully sure this is the right match. If it does not fit, send a new "
               "message with more detail, or ask your AGRITEX or veterinary officer.*")


def title_of(chunk):
    return _HEADING.sub("", chunk.splitlines()[0]).strip()


_NEW_BLOCK = re.compile(r"^(?:[-*•]\s|#|\d+[.)]\s|\*\*|>|\|)")


def unwrap(text):
    """Join the farm book's wrapped lines back into whole sentences, so every
    bullet or paragraph is one line (the app shows each line separately)."""
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append("")
        elif out and out[-1] and not _NEW_BLOCK.match(stripped):
            out[-1] += " " + stripped
        else:
            out.append(stripped)
    return "\n".join(out)


def body_of(chunk, language="english"):
    text = rag.strip_other_language(chunk, language)
    text = "\n".join(text.splitlines()[1:])            # the "### B3. ..." heading
    text = _FARMER_PHRASES.sub("", text)
    text = _INTERNAL_LINE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", unwrap(text)).strip()


def compose(chunks, urgent=False, language="english", unsure=False):
    """The farmer's answer: the matched farm book entry (and a second one to
    check, if there is one), with the urgent warning on top."""
    parts = []
    if urgent:
        parts.append(URGENT_LINE)
    if unsure:
        parts.append(UNSURE_LINE)
    for i, chunk in enumerate(chunks[:2]):
        heading = "### This may be: " if i == 0 else "### Also check: "
        parts.append(heading + title_of(chunk) + "\n\n" + body_of(chunk, language))
    ids = ", ".join(rag.chunk_id(c) for c in chunks[:2])
    parts.append(f"*From the Murimi Fara farm book (entry {ids}). This is guidance, not a "
                 "diagnosis: if you are not sure, ask your AGRITEX officer or vet.*")
    return "\n\n".join(parts)


class Advisor:
    def __init__(self, corpus_path, model_path=None):
        self.chunks = rag.load_chunks(corpus_path)
        self.vectorizer, self.matrix = rag.build_index(self.chunks)
        self.by_id = {rag.chunk_id(c): c for c in self.chunks}
        self.model_path = model_path
        self.model = matcher.load(model_path) if model_path else None

    def reload_model(self):
        self.model = matcher.load(self.model_path) if self.model_path else None

    def _pool(self, query):
        """Entries the farm book search would even consider for this message
        (right crop/animal and domain). The model must stay inside it, so it can
        never answer a pig question with a cattle entry."""
        q = rag.expand_local_terms(query)
        pool = rag.filter_by_subject(q, rag.filter_by_species(q, rag.filter_by_domain(q, self.chunks)))
        return {rag.chunk_id(c) for c in pool}

    def find(self, query):
        """Which entries answer this message, without writing the answer.
        Returns {"kind": "guard"|"answer"|"need_detail", ...}."""
        guard = rag.scope_guard(query)
        if guard:
            return {"kind": "guard", "guard": guard["kind"], "text": guard["answer"],
                    "urgent": guard["urgent"], "entries": [], "matched_by": None,
                    "domain": "unknown", "model": None}
        result = rag.retrieve_grounded(query, self.chunks, self.vectorizer, self.matrix)
        search_ids = [rag.chunk_id(c) for c in result["chunks"]]
        prediction = self.model.predict(query) if self.model else None
        if prediction and prediction["entry"] not in self._pool(query):
            prediction = {**prediction, "level": "none"}

        if prediction and prediction["level"] == "strong" and prediction["entry"] in self.by_id:
            # A near-copy of a checked example: trust what officers/vets taught it.
            ids = [prediction["entry"]] + [i for i in search_ids if i != prediction["entry"]][:1]
            matched_by = MODEL
        elif result["grounded"]:
            ids, matched_by = search_ids, FARM_BOOK
        elif prediction and prediction["level"] == "weak" and prediction["entry"] in self.by_id:
            ids, matched_by = [prediction["entry"]], MODEL_UNSURE
        else:
            return {"kind": "need_detail", "entries": [], "matched_by": None, "urgent": False,
                    "domain": result["domain"], "model": prediction,
                    "text": rag.fallback_answer(result["domain"])}

        chunks = [self.by_id[i] for i in ids]
        if matched_by == FARM_BOOK:
            urgent = result["urgent"]
        else:
            urgent = rag.is_urgent_entry(chunks[0]) and not rag._INFO_QUESTION.match(query)
        kinds = {rag.get_domain(c) for c in chunks}
        answer_domain = "animal" if "animal" in kinds else "crops" if "crops" in kinds else (
            "crops" if result["domain"] == "crops" else "animal")
        return {"kind": "answer", "entries": ids, "chunks": chunks, "matched_by": matched_by,
                "urgent": bool(urgent), "domain": result["domain"], "answer_domain": answer_domain,
                "model": prediction}

    def ask(self, query, urgent_line=False):
        """find() plus the answer text for the farmer."""
        found = self.find(query)
        if found["kind"] == "answer":
            # The app shows its own urgent banner from found["urgent"], so the
            # warning line is only written into the text when asked for.
            found["text"] = compose(found["chunks"], found["urgent"] and urgent_line, rag.detect_language(query),
                                    unsure=found["matched_by"] == MODEL_UNSURE)
        found["titles"] = [title_of(c) for c in found.get("chunks", [])]
        found["language"] = rag.detect_language(query)
        return found


def default_model_path(base_dir):
    return os.path.join(base_dir, "models", "murimi_model.json")
