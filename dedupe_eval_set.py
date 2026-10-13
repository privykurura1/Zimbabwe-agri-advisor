"""
Removes duplicate images from your evaluation set, based on actual file
content (not just filename) - this catches both:
    - Windows "... - Copy.jpg" duplicates
    - Roboflow re-export duplicates (same source photo, different
      export hash in the filename)

RUN THIS from inside your project folder, where roboflow_eval_set/
already exists (from build_ground_truth_csv.py).

OUTPUT:
    A new "roboflow_eval_set_clean/" folder with duplicates removed,
    and a correspondingly filtered ground_truth.csv - THIS is what you
    upload to S3 to replace what's there now.
"""

import os
import shutil
import hashlib
import csv

INPUT_DIR = "roboflow_eval_set"
OUTPUT_DIR = "roboflow_eval_set_clean"
CSV_PATH = os.path.join(INPUT_DIR, "ground_truth.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def file_hash(path):
    """MD5 of the actual file bytes - identical content = identical hash,
    regardless of what the file is named."""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

seen_hashes = {}  # hash -> first filename that had it
duplicates_found = []
kept_rows = []

with open(CSV_PATH, "r", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        image_path = os.path.join(INPUT_DIR, row["Image_id"])
        if not os.path.exists(image_path):
            continue
        h = file_hash(image_path)
        if h in seen_hashes:
            duplicates_found.append((row["Image_id"], seen_hashes[h]))
            continue  # skip - this is a duplicate of an already-kept image
        seen_hashes[h] = row["Image_id"]
        shutil.copy(image_path, os.path.join(OUTPUT_DIR, row["Image_id"]))
        kept_rows.append(row)

with open(os.path.join(OUTPUT_DIR, "ground_truth.csv"), "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["Image_id", "Label"])
    writer.writeheader()
    writer.writerows(kept_rows)

healthy_count = sum(1 for r in kept_rows if r["Label"] == "0")
damaged_count = sum(1 for r in kept_rows if r["Label"] == "1")

print(f"Kept {len(kept_rows)} unique images ({healthy_count} healthy, {damaged_count} damaged)")
print(f"Removed {len(duplicates_found)} duplicate(s):")
for dup, original in duplicates_found:
    print(f"  - {dup}  (duplicate of {original})")

print(f"\nClean set saved to '{OUTPUT_DIR}/' - upload this to S3 instead,")
print("replacing everything currently in test_images/.")
