"""Tests for the small, model-free Murimi Fara (version 2).

    python -m unittest test_core -v

Covers the plain-Python search (tinytfidf), our own trainable model (matcher),
the answer pipeline (advisor), training (tools/train_model.py) and the web app.
No AI model, no internet.
"""
import json
import os
import shutil
import tempfile
import unittest

import advisor
import matcher
import rag
import tinytfidf

ROOT = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(ROOT, rag.CORPUS_PATH)
MODEL = os.path.join(ROOT, "models", "murimi_model.json")


class TinyTfidfTests(unittest.TestCase):
    def test_same_scores_as_scikit_learn(self):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            self.skipTest("scikit-learn not installed (it is no longer needed by the app)")
        docs = rag.load_chunks(CORPUS)
        ours = tinytfidf.TfidfVectorizer("english")
        mine = ours.fit_transform(docs)
        theirs = TfidfVectorizer(stop_words="english")
        ref = theirs.fit_transform(docs)
        for q in ["my cow passes red urine", "ragged holes in maize leaves", "huku dzine manyoka"]:
            a = tinytfidf.cosine_similarity(ours.transform([q]), mine)
            b = cosine_similarity(theirs.transform([q]), ref).flatten()
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, float(y), places=9)


class MatcherTests(unittest.TestCase):
    def test_learns_a_new_phrasing_from_one_checked_example(self):
        examples = [{"text": "Babesiosis redwater", "entry": "B3"}, {"text": "Newcastle disease", "entry": "C1"}]
        before = matcher.Model(examples).predict("mombe yangu irikuchama ropa")
        self.assertNotEqual(before["level"], "strong")
        after = matcher.Model(examples + [{"text": "mombe irikuchama ropa", "entry": "B3"}])
        p = after.predict("mombe yangu irikuchama ropa")
        self.assertEqual((p["entry"], p["level"]), ("B3", "strong"))

    def test_spelling_mistakes_still_match(self):
        m = matcher.Model([{"text": "red urine", "entry": "B3"}, {"text": "twisted neck", "entry": "C1"}])
        self.assertEqual(m.predict("red urin")["entry"], "B3")

    def test_save_and_load(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        path = os.path.join(folder, "m.json")
        matcher.save(matcher.Model([{"text": "red urine", "entry": "B3"}], info={"version": 7}), path)
        loaded = matcher.load(path)
        self.assertEqual(loaded.info["version"], 7)
        self.assertEqual(loaded.predict("red urine")["entry"], "B3")
        self.assertIsNone(matcher.load(os.path.join(folder, "missing.json")))


class AdvisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adv = advisor.Advisor(CORPUS, MODEL)

    def test_shipped_model_passes_every_retrieval_check(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("train_model", os.path.join(ROOT, "tools", "train_model.py"))
        tm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tm)
        score = tm.evaluate(self.adv)
        self.assertEqual(score["failures"], [], score["failures"][:5])

    def test_answer_is_the_farm_book_entry(self):
        found = self.adv.ask("Mombe yangu iri kuita weti tsvuku")
        self.assertEqual(found["kind"], "answer")
        self.assertIn("B3", found["entries"])
        self.assertTrue(found["urgent"])
        self.assertIn("Babesiosis", found["text"])
        self.assertIn("From the Murimi Fara farm book", found["text"])
        # A Shona question never shows the Ndebele text, and the reverse.
        self.assertNotIn("Ndebele", found["text"])
        # Search-only text is not shown to farmers.
        self.assertNotIn("Farmer phrases", self.adv.ask("my cow is passing red urine")["text"])

    def test_urgent_line_only_when_asked(self):
        self.assertNotIn("URGENT", self.adv.ask("Mombe yangu iri kuita weti tsvuku")["text"])
        self.assertIn("URGENT", self.adv.ask("Mombe yangu iri kuita weti tsvuku", urgent_line=True)["text"])

    def test_safety_replies_and_unknowns(self):
        self.assertEqual(self.adv.ask("how many ml of ivermectin for a 300kg cow")["kind"], "guard")
        unknown = self.adv.ask("my pig has a cough")
        self.assertEqual(unknown["kind"], "need_detail")
        self.assertEqual(unknown["entries"], [])

    def test_model_cannot_answer_outside_the_right_animal_or_crop(self):
        model = matcher.Model([{"text": "coughing", "entry": "G8"}], {"strong": 0.1, "weak": 0.1})
        adv = advisor.Advisor(CORPUS)
        adv.model = model
        self.assertEqual(adv.find("my pig is coughing")["kind"], "need_detail")


class TrainingTests(unittest.TestCase):
    def test_training_saves_only_when_not_worse(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("train_model", os.path.join(ROOT, "tools", "train_model.py"))
        tm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tm)
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        out = os.path.join(folder, "model.json")
        self.assertEqual(tm.main(["--out", out]), 0)
        self.assertEqual(matcher.load(out).info["version"], 1)
        # A wrong label that sends a vague message to an answer must be refused.
        reviews = os.path.join(folder, "reviews.json")
        with open(reviews, "w", encoding="utf-8") as f:
            json.dump({"installation": "TEST", "reviews": [
                {"id": "1", "question": "my chickens are dying", "decision": "rejected", "category": "WRONG",
                 "correct_entry": "C1", "entries": []}]}, f)
        self.assertEqual(tm.main(["--out", out, "--reviews", reviews, "--weak", "0.3"]), 2)
        self.assertEqual(matcher.load(out).info["version"], 1)

    def test_review_files_become_examples(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("train_model", os.path.join(ROOT, "tools", "train_model.py"))
        tm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tm)
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        path = os.path.join(folder, "r.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"installation": "AB12", "reviews": [
                {"id": "1", "question": "q one", "decision": "approved", "category": "NONE", "entries": ["B3"]},
                {"id": "2", "question": "q two", "decision": "rejected", "category": "WRONG", "correct_entry": "C1",
                 "entries": ["B3"]},
                {"id": "3", "question": "q three", "decision": "rejected", "category": "UNSAFE", "entries": ["B3"]}]}, f)
        rows = tm.review_examples([path, path])            # the same file twice counts once
        self.assertEqual([(r["text"], r["entry"], r["source"]) for r in rows],
                         [("q one", "B3", "officer_approved"), ("q two", "C1", "officer_correction")])


class CorrectEntryTests(unittest.TestCase):
    def test_officer_correct_entry_is_saved_and_exported(self):
        import asyncio
        from challenge_agent import feedback
        from challenge_agent.orchestrator import draft
        from challenge_agent.store import Store
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        db = os.path.join(folder, "r.sqlite3")
        result = asyncio.run(draft("my maize leaves have ragged holes and droppings in the middle", db))
        store = Store(db)
        store.review(result["id"], result["digest"], "officer", False, "It was stalk borer")
        with self.assertRaises(ValueError):
            feedback.record(store, result["id"], "WRONG", correct_entry="not an id")
        feedback.record(store, result["id"], "WRONG", correct_entry="j3")
        exported = feedback.export_file(store)["reviews"][0]
        self.assertEqual(exported["correct_entry"], "J3")
        self.assertEqual(exported["generation"], "farm_book")


class WebAppTests(unittest.TestCase):
    def test_ask_feedback_and_health(self):
        try:
            from fastapi.testclient import TestClient
        except Exception:  # noqa: BLE001 - needs httpx, a test-only library
            self.skipTest("fastapi TestClient (httpx) not installed")
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        old = os.environ.get("MURIMIFARA_DATA_DIR")
        os.environ["MURIMIFARA_DATA_DIR"] = folder
        self.addCleanup(lambda: os.environ.__setitem__("MURIMIFARA_DATA_DIR", old) if old is not None
                        else os.environ.pop("MURIMIFARA_DATA_DIR", None))
        import importlib
        import app as app_module
        app_module = importlib.reload(app_module)
        client = TestClient(app_module.app, base_url="http://127.0.0.1")
        self.assertEqual(client.get("/api/health").json()["status"], "ok")
        r = client.post("/api/ask", json={"question": "Inkomo yami ichama umchamo obomvu"}).json()
        self.assertIn("B3", r["entry_ids"])
        self.assertTrue(r["urgent"])
        stream = client.post("/api/ask/stream", json={"question": "Inkomo yami ichama umchamo obomvu"}).text
        self.assertTrue(stream.startswith("META:::"))
        self.assertEqual(client.post("/api/feedback", json={"question": "call me on 0771234567 my cow",
                                                            "entry_ids": ["B3"], "helpful": False}).json(),
                         {"saved": True})
        with open(os.path.join(folder, "farmer_feedback.jsonl"), encoding="utf-8") as f:
            saved = json.loads(f.readline())
        self.assertNotIn("0771234567", saved["question"])
        self.assertFalse(saved["helpful"])
        self.assertIn("my cow", client.get("/officer/farmer-feedback").text)
        self.assertEqual(client.post("/api/classify_image").status_code, 404)     # photo checks removed


if __name__ == "__main__":
    unittest.main()
