"""More photo checks: any number of small image classifiers, each in its own folder.

    models/photo/<check-name>/model.onnx
    models/photo/<check-name>/check.json

check.json (written by tools/train_photo_check.py, then edited by a person):
    {
      "title": "Tomato leaf - late blight",
      "labels": ["healthy", "late_blight"],        # output order of the model
      "problem_labels": {"late_blight": "L1"},    # label -> knowledge entry to explain it
      "input_size": 224,
      "min_confidence": 80,
      "validation": {"photos": 0, "accuracy": null, "notes": ""},
      "enabled": false
    }

A check is offered to farmers only when "enabled" is true, and "enabled" should
be set only after the check was tested on real photos it was not trained on
(validation.photos / accuracy filled in from that test). Low-confidence results
are never turned into a diagnosis.
"""
import json
import os
import re

import numpy as np

from . import app_dir

ROOT = app_dir()
MODELS_DIR = os.path.join(ROOT, "models", "photo")
_NAME = re.compile(r"^[a-z0-9_\-]{1,40}$")
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


def load_checks(models_dir=MODELS_DIR, include_disabled=False):
    """name -> {"config": ..., "path": ...} for every valid check folder."""
    found = {}
    if not os.path.isdir(models_dir):
        return found
    for name in sorted(os.listdir(models_dir)):
        folder = os.path.join(models_dir, name)
        cfg_path, model_path = os.path.join(folder, "check.json"), os.path.join(folder, "model.onnx")
        if not _NAME.match(name) or not (os.path.isfile(cfg_path) and os.path.isfile(model_path)):
            continue
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            assert isinstance(cfg["labels"], list) and len(cfg["labels"]) >= 2
        except (OSError, ValueError, KeyError, AssertionError):
            continue
        if cfg.get("enabled") or include_disabled:
            found[name] = {"config": cfg, "path": model_path}
    return found


def softmax(row):
    e = np.exp(row - np.max(row))
    return e / e.sum()


def run_check(cv2, net, cfg, image_bgr):
    """Classify one image; returns label, confidence (0-100) and the decision."""
    size = int(cfg.get("input_size", 224))
    blob = cv2.dnn.blobFromImage(image_bgr, scalefactor=1.0 / 255.0, size=(size, size),
                                 mean=(0, 0, 0), swapRB=True, crop=False)
    for i in range(3):
        blob[0, i] = (blob[0, i] - MEAN[i]) / STD[i]
    net.setInput(blob)
    probs = softmax(net.forward()[0])
    labels = cfg["labels"]
    idx = int(np.argmax(probs))
    label, confidence = labels[idx], float(probs[idx] * 100)
    threshold = float(cfg.get("min_confidence", 80))
    problems = cfg.get("problem_labels", {})
    if confidence < threshold:
        decision = "unsure"
    elif label in problems:
        decision = "problem"
    else:
        decision = "no_problem_seen"
    return {"label": label, "confidence": round(confidence, 1), "decision": decision,
            "entry": problems.get(label) if decision == "problem" else None,
            "probabilities": {l: round(float(p * 100), 1) for l, p in zip(labels, probs)}}


MESSAGES = {
    "unsure": ("The photo check is not sure. Take another photo in daylight, close to one leaf, "
               "or describe what you see in words."),
    "no_problem_seen": ("This check did not see {title_problem} in the photo. It only looks for that one "
                        "problem; if plants still look unwell, describe what you see."),
    "problem": ("The photo looks like {label}. Check other plants in the field and confirm before spraying "
                "or treating."),
}
