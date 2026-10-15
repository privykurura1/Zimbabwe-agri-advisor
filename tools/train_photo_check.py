"""Train a new photo check (MobileNetV2, transfer learning) and export it for Murimi Fara.

NOT run in the build environment (no PyTorch there) - test it on your own machine
first with a small dataset. Needs:  pip install torch torchvision

Photos go in one folder per label, e.g.
    dataset/healthy/*.jpg
    dataset/late_blight/*.jpg
Use photos from Zimbabwean fields where you can, and keep some fields/farms
completely out of training for the real test (see check.json "validation").

    python tools/train_photo_check.py --data dataset --name tomato_late_blight \
        --title "Tomato leaf - late blight" --problem late_blight=L1

Writes models/photo/<name>/model.onnx and check.json with "enabled": false.
Switch it on only after testing on photos the model never saw.
"""
import argparse
import json
import os
import random

import torch
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, models, transforms

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--name", required=True, help="folder name: lowercase letters, digits, _ or -")
    ap.add_argument("--title", required=True)
    ap.add_argument("--problem", action="append", default=[], help="label=ENTRY, e.g. late_blight=L1")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    train_tf = transforms.Compose([transforms.RandomResizedCrop(224, scale=(0.6, 1.0)), transforms.RandomHorizontalFlip(),
                                   transforms.ColorJitter(0.3, 0.3, 0.3), transforms.ToTensor(),
                                   transforms.Normalize(MEAN, STD)])
    test_tf = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(), transforms.Normalize(MEAN, STD)])
    full_train = datasets.ImageFolder(args.data, transform=train_tf)
    full_test = datasets.ImageFolder(args.data, transform=test_tf)
    labels = full_train.classes
    idx = list(range(len(full_train)))
    random.shuffle(idx)
    cut = int(len(idx) * args.holdout)
    train_set, test_set = Subset(full_train, idx[cut:]), Subset(full_test, idx[:cut])
    print(f"labels {labels}; {len(train_set)} training photos, {len(test_set)} held out")

    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    for p in model.features.parameters():
        p.requires_grad = False
    model.classifier[1] = nn.Linear(model.last_channel, len(labels))
    opt = torch.optim.Adam(model.classifier.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    for epoch in range(args.epochs):
        model.train()
        for x, y in DataLoader(train_set, batch_size=32, shuffle=True):
            opt.zero_grad()
            loss_fn(model(x), y).backward()
            opt.step()
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for x, y in DataLoader(test_set, batch_size=64):
                correct += (model(x).argmax(1) == y).sum().item()
                total += len(y)
        acc = 100 * correct / max(total, 1)
        print(f"epoch {epoch + 1}: held-out accuracy {acc:.1f}% ({total} photos)")

    out = os.path.join(ROOT, "models", "photo", args.name)
    os.makedirs(out, exist_ok=True)
    model.eval()
    torch.onnx.export(model, torch.randn(1, 3, 224, 224), os.path.join(out, "model.onnx"),
                      input_names=["input"], output_names=["logits"], opset_version=13)
    problems = dict(p.split("=", 1) for p in args.problem)
    unknown = set(problems) - set(labels)
    if unknown:
        raise SystemExit(f"--problem labels not in dataset: {sorted(unknown)}")
    cfg = {"title": args.title, "labels": labels, "problem_labels": problems, "input_size": 224,
           "min_confidence": 80,
           "training": {"photos": len(train_set), "random_holdout_photos": total,
                        "random_holdout_accuracy": round(acc, 1),
                        "note": "Random split of the same dataset; usually higher than real-field accuracy."},
           "validation": {"photos": 0, "accuracy": None,
                          "notes": "Fill in after testing on photos from fields not used in training."},
           "enabled": False}
    with open(os.path.join(out, "check.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"Saved to {out}. Test on new field photos, fill in validation, then set enabled to true.")


if __name__ == "__main__":
    main()
