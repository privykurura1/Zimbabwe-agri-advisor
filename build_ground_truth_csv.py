"""
Builds ground_truth.csv automatically from two folders of images, so
you never have to type out filenames and labels by hand.

SETUP:
    Put your new Roboflow images into two folders next to this script:
        roboflow_healthy/   (healthy maize leaf photos)
        roboflow_damaged/   (Fall Armyworm damaged photos)

RUN:
    python build_ground_truth_csv.py

OUTPUT:
    A new folder "roboflow_eval_set/" containing:
        - all your images, copied in
        - ground_truth.csv, correctly labeled (0 = healthy, 1 = damaged)
    Ready to upload straight to S3's test_images/ folder, replacing the
    old (compromised) evaluation set.
"""

import os
import shutil
import csv

HEALTHY_DIR = "roboflow_healthy"
DAMAGED_DIR = "roboflow_damaged"
OUTPUT_DIR = "roboflow_eval_set"

os.makedirs(OUTPUT_DIR, exist_ok=True)

rows = []

for folder, label in [(HEALTHY_DIR, 0), (DAMAGED_DIR, 1)]:
    if not os.path.isdir(folder):
        print(f"Warning: '{folder}' not found - skipping.")
        continue
    for filename in os.listdir(folder):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            shutil.copy(os.path.join(folder, filename), os.path.join(OUTPUT_DIR, filename))
            rows.append((filename, label))

csv_path = os.path.join(OUTPUT_DIR, "ground_truth.csv")
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Image_id", "Label"])
    writer.writerows(rows)

healthy_count = sum(1 for _, l in rows if l == 0)
damaged_count = sum(1 for _, l in rows if l == 1)

print(f"Done. {len(rows)} images processed ({healthy_count} healthy, {damaged_count} damaged).")
print(f"Everything is in '{OUTPUT_DIR}/', ready to upload to S3.")
