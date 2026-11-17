"""Murimi Fara's own small model: recognises WHICH farm book entry a farmer's
message is about. It never writes advice - the answer is always the farm book
entry itself.

How it works (a nearest-example classifier, plain Python, no downloads):
  * It learns from labelled examples: "Mombe yangu iri kuita weti tsvuku" -> B3.
    They come from the farm book itself and, over time, from officers and vets
    who mark which entry was right (see tools/train_model.py).
  * Each message is turned into features: its words plus 3-5 letter pieces of
    each word. The letter pieces let it cope with spelling mistakes and with
    Shona/Ndebele word forms ("tsvuku", "tsvukuruka").
  * A new message is compared with every example; each entry scores the
    similarity of its closest example (0 = nothing in common, 1 = identical).

The trained model is one small JSON file (models/murimi_model.json): the
examples plus the settings. Retraining = adding checked examples and running
tools/train_model.py, which only saves a new model if it is at least as
accurate as the last one.
"""
import json
import math
import os
import re
from collections import Counter

from tinytfidf import ENGLISH_STOP_WORDS

FORMAT = "murimi-fara-model/1"
_WORD = re.compile(r"[a-z0-9']+")
# Words that say nothing about WHICH problem it is. Animal and crop names stay in:
# they separate "chicken with diarrhoea" from "calf with diarrhoea".
_FILLER = ENGLISH_STOP_WORDS | {
    "my", "our", "i", "im", "ive", "has", "have", "is", "are", "what", "why", "how", "please",
    "help", "problem", "wrong", "yangu", "wangu", "changu", "yami", "wami", "sei", "chii",
    "chingava", "ngani", "kanjani"}


def words(text):
    return [w for w in _WORD.findall((text or "").lower()) if len(w) > 1 and w not in _FILLER]


def features(text):
    """Words, plus 3-5 letter pieces of every word (marked with < > at the word edges)."""
    out = Counter()
    for w in words(text):
        out["w:" + w] += 1
        marked = "<" + w + ">"
        for n in (3, 4, 5):
            for i in range(len(marked) - n + 1):
                out[marked[i:i + n]] += 1
    return out


class Model:
    def __init__(self, examples, settings=None, info=None):
        """examples: list of {"text": ..., "entry": "B3", "source": ...}."""
        self.examples = [e for e in examples if e.get("text") and e.get("entry")]
        self.settings = {"strong": 0.80, "weak": 0.65, **(settings or {})}
        self.info = info or {}
        feats = [features(e["text"]) for e in self.examples]
        n = len(feats)
        df = Counter(f for fs in feats for f in fs)
        self.idf = {f: math.log((1 + n) / (1 + c)) + 1 for f, c in df.items()}
        self.vectors = [self._vector(fs) for fs in feats]

    def _vector(self, feats):
        v = {f: c * self.idf[f] for f, c in feats.items() if f in self.idf}
        norm = math.sqrt(sum(x * x for x in v.values()))
        return {f: x / norm for f, x in v.items()} if norm else {}

    def scores(self, text):
        """{entry: best similarity}, highest first, plus the closest example per entry."""
        q = self._vector(features(text))
        best = {}
        for example, vec in zip(self.examples, self.vectors):
            s = sum(w * vec.get(f, 0.0) for f, w in q.items())
            if s > best.get(example["entry"], (0.0, None))[0]:
                best[example["entry"]] = (s, example["text"])
        return sorted(((e, round(s, 4), ex) for e, (s, ex) in best.items()), key=lambda t: t[1], reverse=True)

    def predict(self, text):
        """{"entry", "score", "margin", "example", "level"}; level is "strong",
        "weak" or "none" (not sure - do not use)."""
        ranked = self.scores(text)
        if not ranked:
            return {"entry": None, "score": 0.0, "margin": 0.0, "example": None, "level": "none"}
        entry, score, example = ranked[0]
        margin = score - (ranked[1][1] if len(ranked) > 1 else 0.0)
        level = ("strong" if score >= self.settings["strong"] else
                 "weak" if score >= self.settings["weak"] else "none")
        return {"entry": entry, "score": score, "margin": round(margin, 4), "example": example, "level": level}

    def to_json(self):
        return {"format": FORMAT, "info": self.info, "settings": self.settings, "examples": self.examples}


def load(path):
    """The saved model, or None if there is none yet (the app then uses the farm
    book search alone)."""
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("format") != FORMAT:
        raise ValueError(f"{path} is not a Murimi Fara model file")
    return Model(data["examples"], data.get("settings"), data.get("info"))


def save(model, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(model.to_json(), f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
