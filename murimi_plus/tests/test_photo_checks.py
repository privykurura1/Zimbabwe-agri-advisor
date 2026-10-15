"""Extra photo checks: loading, confidence gate, enabled flag (tiny test model)."""
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

import rag
from murimi_plus import photo_checks
from murimi_plus.router import create_router

try:
    import onnx
    from onnx import TensorProto, helper
except ImportError:  # pragma: no cover
    onnx = None


def tiny_model(path, weights):
    """Mean colour of the image -> 2 scores. Stands in for a trained network."""
    w = helper.make_tensor("W", TensorProto.FLOAT, [3, 2], np.asarray(weights, np.float32).flatten().tolist())
    b = helper.make_tensor("B", TensorProto.FLOAT, [2], [0.0, 0.0])
    graph = helper.make_graph(
        [helper.make_node("GlobalAveragePool", ["input"], ["p"]),
         helper.make_node("Flatten", ["p"], ["f"]),
         helper.make_node("Gemm", ["f", "W", "B"], ["logits"])],
        "tiny", [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 224, 224])],
        [helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, 2])], [w, b])
    onnx.save(helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)]), path)


def jpeg(bgr):
    img = np.zeros((300, 300, 3), np.uint8)
    img[:] = bgr
    return cv2.imencode(".jpg", img)[1].tobytes()


@unittest.skipIf(onnx is None, "onnx not installed")
class PhotoCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.models = Path(self.tmp.name) / "photo"
        folder = self.models / "tomato_test"
        folder.mkdir(parents=True)
        # Red-heavy image -> "late_blight"; green-heavy -> "healthy" (channels are RGB after swapRB).
        tiny_model(str(folder / "model.onnx"), [[-4, 4], [4, -4], [0, 0]])
        self.cfg = {"title": "Tomato test", "labels": ["healthy", "late_blight"],
                    "problem_labels": {"late_blight": "L1"}, "min_confidence": 80,
                    "validation": {"photos": 40, "accuracy": 90}, "enabled": True}
        (folder / "check.json").write_text(json.dumps(self.cfg))
        app = FastAPI()
        app.include_router(create_router(rag.load_chunks(rag.CORPUS_PATH), rag, str(Path(self.tmp.name) / "log"),
                                         Path(self.tmp.name) / "farm.db", models_dir=str(self.models)))
        self.client = TestClient(app, base_url="http://127.0.0.1:8000")
        self.addCleanup(self.client.close)

    def post(self, data):
        return self.client.post("/api/extras/photo/tomato_test", files={"file": ("p.jpg", data, "image/jpeg")})

    def test_problem_found_points_to_entry(self):
        r = self.post(jpeg((0, 0, 255))).json()          # BGR red
        self.assertEqual((r["label"], r["decision"], r["entry"]), ("late_blight", "problem", "L1"))
        self.assertIn("Tomato late blight", r["entry_title"])

    def test_healthy(self):
        r = self.post(jpeg((0, 255, 0))).json()
        self.assertEqual(r["decision"], "no_problem_seen")
        self.assertIsNone(r["entry"])

    def test_unsure_below_threshold(self):
        r = self.post(jpeg((128, 128, 128))).json()       # equal colours -> 50/50
        self.assertEqual(r["decision"], "unsure")

    def test_disabled_check_not_offered(self):
        (self.models / "tomato_test" / "check.json").write_text(json.dumps(dict(self.cfg, enabled=False)))
        self.assertEqual(self.client.get("/api/extras/photo_checks").json(), [])
        self.assertEqual(self.post(jpeg((0, 0, 255))).status_code, 404)

    def test_not_an_image(self):
        self.assertEqual(self.post(b"hello").status_code, 400)

    def test_page_form(self):
        self.assertIn("Tomato test", self.client.get("/extras/photo").text)
        page = self.client.post("/extras/photo", data={"name": "tomato_test"},
                                files={"file": ("p.jpg", jpeg((0, 0, 255)), "image/jpeg")}).text
        self.assertIn("late blight", page)
        self.assertIn("Tested on 40 photos", page)


if __name__ == "__main__":
    unittest.main()
