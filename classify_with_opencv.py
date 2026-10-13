"""
Runs your trained Fall Armyworm classifier through OpenCV 5's own DNN
module (cv2.dnn) - this is what makes OpenCV do genuine, substantive
work: real image preprocessing AND real neural network inference,
not just a color-threshold guess like our earlier experiment.

SETUP:
    Put faw_classifier.onnx (from the Colab training script) in the
    same folder as this script.

USAGE:
    python classify_with_opencv.py test1.jpg
"""

import sys
import cv2
import numpy as np

# Confirmed directly by inspecting real sample images from the dataset:
# label 0 = healthy leaf (little/no damage), label 1 = Fall Armyworm
# damage (holes, window-pane patches, torn sections). This order must
# match exactly, since it maps to the model's output indices 0 and 1.
CLASS_NAMES = ["healthy", "damaged"]

MODEL_PATH = "faw_classifier.onnx"

if len(sys.argv) < 2:
    print("Usage: python classify_with_opencv.py path\\to\\photo.jpg")
    sys.exit(1)

image_path = sys.argv[1]
img = cv2.imread(image_path)
if img is None:
    print(f"Could not open '{image_path}'")
    sys.exit(1)

# Load the trained model through OpenCV's own DNN engine - this is the
# real substantive OpenCV work: OpenCV is running the actual neural
# network forward pass, not just displaying an image.
net = cv2.dnn.readNetFromONNX(MODEL_PATH)

# Preprocess exactly the way the model was trained to expect:
# resize to 224x224, scale pixel values, convert BGR->RGB, and
# normalize using the same mean/std used during training in Colab.
# blobFromImage does the resize + scaling + channel reordering in one
# genuine OpenCV operation.
mean = (0.485, 0.456, 0.406)
std = (0.229, 0.224, 0.225)

blob = cv2.dnn.blobFromImage(
    img,
    scalefactor=1.0 / 255.0,
    size=(224, 224),
    mean=(0, 0, 0),  # we'll normalize manually below for accuracy
    swapRB=True,
    crop=False,
)

# Manual per-channel normalization to match training exactly
for i in range(3):
    blob[0, i, :, :] = (blob[0, i, :, :] - mean[i]) / std[i]

net.setInput(blob)
output = net.forward()

# Convert raw output scores to probabilities
exp_scores = np.exp(output - np.max(output))
probabilities = exp_scores / exp_scores.sum()

predicted_idx = np.argmax(probabilities)
predicted_class = CLASS_NAMES[predicted_idx]
confidence = probabilities[0][predicted_idx] * 100

print(f"Image: {image_path}")
print(f"Prediction: {predicted_class}")
print(f"Confidence: {confidence:.1f}%")
print(f"\nAll class probabilities:")
for i, name in enumerate(CLASS_NAMES):
    print(f"  {name}: {probabilities[0][i]*100:.1f}%")
