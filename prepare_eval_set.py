"""
Builds a genuine evaluation subset from your Zindi Train.csv + extracted
images - run this LOCALLY first, before touching AWS at all. This gives
you a small, honestly-labeled test set to actually evaluate against.

SETUP:
    Put this in the same folder as your local Train.csv, and extract
    Images.zip locally too (right-click > Extract All), then point
    IMAGES_DIR below at that extracted folder.

WHAT IT DOES:
    Randomly samples 60 labeled images (30 healthy, 30 damaged) and
    copies them into a clean "eval_set" folder alongside a
    ground_truth.csv - this is what gets uploaded to S3 next.

HONEST NOTE for your technical report: this sample comes from the same
Train.csv used for training, not a separate untouched holdout Zindi
never gave us access to (Test.csv has no labels). Say this plainly in
the report rather than overclaiming independence - it's still a
legitimate accuracy check, just not a perfectly blind one.
"""

import os
import shutil
import pandas as pd

TRAIN_CSV = "Train.csv"
IMAGES_DIR = "C:/Users/privi/Desktop/adtc-2026-submission-template/maize"  # EDIT to your actual extracted folder
OUTPUT_DIR = "eval_set"
SAMPLES_PER_CLASS = 30

df = pd.read_csv(TRAIN_CSV)
os.makedirs(OUTPUT_DIR, exist_ok=True)

healthy_sample = df[df["Label"] == 0].sample(n=SAMPLES_PER_CLASS, random_state=7)
damaged_sample = df[df["Label"] == 1].sample(n=SAMPLES_PER_CLASS, random_state=7)
eval_df = pd.concat([healthy_sample, damaged_sample]).reset_index(drop=True)

copied = 0
for _, row in eval_df.iterrows():
    for root, _, files in os.walk(IMAGES_DIR):
        if row["Image_id"] in files:
            shutil.copy(os.path.join(root, row["Image_id"]), os.path.join(OUTPUT_DIR, row["Image_id"]))
            copied += 1
            break

eval_df.to_csv(os.path.join(OUTPUT_DIR, "ground_truth.csv"), index=False)
print(f"Copied {copied}/{len(eval_df)} images into '{OUTPUT_DIR}/'")
print(f"ground_truth.csv saved alongside them - both are ready to upload to S3.")
