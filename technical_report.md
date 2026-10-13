# Murimi Fara — Technical Report
## OpenCV AI Competition 2026, powered by AWS

---

## 1. Problem

Cloud-hosted AI assistants require stable connectivity and ongoing costs
that don't match the reality of rural Zimbabwean farming communities.
Meanwhile, real agricultural threats — tick-borne cattle diseases,
Fall Armyworm infestations — require fast identification and action, often
in exactly the conditions (no signal, no electricity, no budget for data)
where cloud AI fails.

Murimi Fara is an offline-first agricultural advisor that runs entirely on
a single laptop, reachable by farmers' own phones over local WiFi, that:

1. Answers livestock and crop questions in English, Shona, or Ndebele,
   grounded in a curated knowledge base (not just the model's training data)
2. Diagnoses Fall Armyworm damage directly from a phone photo, using a
   trained computer vision model
3. Runs a real, meaningful AWS-hosted evaluation pipeline — while keeping
   field operation fully offline, which is the actual point of the project

---

## 2. System Architecture

```
                    ┌─────────────────────────────────────┐
                    │        Farmer's phone (browser)       │
                    │   connects via laptop's WiFi hotspot   │
                    └───────────────────┬───────────────────┘
                                         │  HTTP (local network only)
                    ┌────────────────────▼────────────────────┐
                    │         FastAPI backend (app.py)          │
                    └──┬─────────────────┬─────────────────┬───┘
                        │                 │                 │
              ┌─────────▼──────┐  ┌───────▼───────┐  ┌──────▼──────┐
              │  llama-server    │  │  RAG retrieval │  │  OpenCV 5    │
              │  Qwen2.5-1.5B    │  │  TF-IDF, EN/SN/│  │  cv2.dnn      │
              │  (text advisor)  │  │  ND corpus     │  │  (vision)     │
              └─────────────────┘  └───────────────┘  └──────────────┘
                                                                │
                                                    ┌───────────▼───────────┐
                                                    │  MobileNetV2 (ONNX)     │
                                                    │  Fall Armyworm classifier│
                                                    └────────────────────────┘

All of the above: fully offline, on one laptop. No data leaves the device
during field operation.

                    ─ ─ ─ (separate, online-only, optional) ─ ─ ─

              ┌──────────┐      ┌───────────────────┐      ┌─────────────┐
              │  Amazon S3 │ ──▶ │  SageMaker notebook │ ──▶ │  Benchmark   │
              │  (model,   │     │  OpenCV 5 + cv2.dnn  │     │  report      │
              │  test set) │     │  evaluation pipeline │     │  (S3)        │
              └──────────┘      └───────────────────┘      └─────────────┘
```

**Deployment:** packaged as a one-click Windows desktop app (PyInstaller +
pywebview) — no terminal, no visible code, no setup beyond opening a folder.

---

## 3. The Agentic Vision Pipeline (core technical contribution)

The defining requirement this submission targets directly: **vision
results must change what happens next**, not just be displayed.

```
Phone photo
    │
    ▼
PERCEPTION   OpenCV 5 (cv2.dnn.blobFromImage: resize, normalize, BGR→RGB)
    │        + MobileNetV2 inference (cv2.dnn.Net.forward)
    ▼
DECISION     Confidence-based routing:
    │          ≥80% "damaged"  → high_confidence_damaged
    │          ≥80% "healthy"  → high_confidence_healthy
    │          55-79%          → medium_confidence
    │          <55%             → low_confidence
    ▼
RETRIEVAL    Only triggered on high_confidence_damaged:
    │        RAG lookup against the Fall Armyworm corpus entry
    ▼
ADVICE       high_confidence_damaged  → full LLM-generated, RAG-grounded diagnosis
    │        high_confidence_healthy  → short reassurance, no LLM call needed
    │        medium_confidence        → asks for a clearer photo/symptoms
    │        low_confidence           → explicitly declines to diagnose,
    │                                    recommends manual/extension officer check
    ▼
HUMAN ACTION  Farmer reads an appropriately-hedged, actionable result
```

This was a deliberate design choice: **overclaiming a diagnosis from a
low-confidence result is worse than admitting uncertainty.** A blurry or
ambiguous photo is treated fundamentally differently from a clear one,
not just assigned a lower percentage on the same template.

---

## 4. Computer Vision Implementation

- **Model:** MobileNetV2, chosen specifically for its small footprint —
  consistent with the project's core "accessible hardware" philosophy
- **Training:** transfer learning on the Makerere Fall Armyworm Crop
  Challenge dataset (Zindi), 1,620 labeled field images, trained via
  Google Colab (free GPU tier), 10 epochs
- **Export:** ONNX format (`opset_version=12`)
- **Inference:** OpenCV 5's `cv2.dnn` module — genuine substantive use,
  not decoration: real preprocessing (`blobFromImage` with matched
  mean/std normalization) and real forward-pass inference
- **Model size:** 8.5 MB (ONNX file)
- **Inference latency:** 22.8 ms/image average (measured on AWS SageMaker,
  `ml.t3.medium`, CPU-only — no GPU needed for inference)

---

## 5. AWS Component

**Architecture:** S3 (test images, ground truth labels, model artifact,
reports) → SageMaker notebook instance (OpenCV 5 + cv2.dnn evaluation
script) → benchmark report written back to S3.

**Design principle:** AWS is used for evaluation, benchmarking, and
(future) approved-model distribution — never for field operation, which
remains fully offline by design. This directly satisfies the competition's
cloud requirement without compromising the project's actual purpose.

**Cost discipline:** smallest practical instance type (`ml.t3.medium`),
manually stopped immediately after each evaluation run. Total AWS spend
for this evaluation: well under $1.

### A methodological correction worth documenting directly

Our first evaluation attempt used a random sample from the same
`Train.csv` used to train the model, and returned a suspicious **100%**
across every metric. We recognized this as a data leakage problem — the
Colab training script's 80/20 train/validation split meant every row in
that file had already influenced the model in some way, leaving no
genuinely unseen data within it.

**Fix:** we rebuilt the evaluation set entirely from the Roboflow
maize-fallarmyworm dataset — a source completely independent of the
training data — and re-ran the evaluation. We also discovered and removed
9 duplicate images (some from Windows file-copy artifacts, some from
Roboflow re-export hashes of the same source photo) using content-based
(MD5) deduplication, since duplicates in either direction of a class would
have skewed the metrics.

We consider this correction itself evidence of methodological rigor: an
evaluation pipeline is only as trustworthy as the data behind it, and a
perfect score is often a sign something is wrong, not a sign of success.

---

## 6. Evaluation Results

**Test set:** 78 independently-sourced, deduplicated images (40 healthy,
38 damaged), from Roboflow — genuinely unseen by the model during training.

| Metric | Value |
|---|---|
| Accuracy | 88.5% |
| Precision | 93.5% |
| Recall | 80.6% |
| F1 Score | 86.6% |

**Confusion Matrix**

|  | Predicted Healthy | Predicted Damaged |
|---|---|---|
| **Actual Healthy** | 40 | 2 |
| **Actual Damaged** | 7 | 29 |

**Performance**

| Metric | Value |
|---|---|
| Average inference latency | 22.8 ms/image |
| Model file size | 8.5 MB |

---

## 7. Failure Case Analysis

Precision (93.5%) is notably higher than recall (80.6%) — the model is
more cautious about flagging damage than it is accurate when it does flag
it. In practical terms: **7 genuinely damaged leaves were told "healthy."**
For a farming tool, this is the more costly error direction — a missed
diagnosis risks real crop loss, whereas a false alarm only costs a
farmer a few minutes of double-checking.

We manually reviewed the two highest-confidence false negatives:

**Case 1 (84.8% confident, wrong):** an extreme macro shot directly into
the leaf whorl, with a hand pulling a leaf aside to expose the larva
itself — framed around the insect, not the leaf surface damage pattern
the model was trained to recognize.

**Case 2 (97.6% confident, wrong — the single most confidently incorrect
result in the evaluation):** a wide, whole-plant field shot showing severe,
unambiguous windowpaning and frass across the upper leaves, taken from a
distance rather than as a close-up of one leaf.

**Finding:** both of the model's most confident failures involved
**atypical photo composition**, not ambiguous or borderline damage. This
independently confirms an issue first noticed during informal testing
earlier in development, where a whole-plant photo was similarly
misclassified. The model appears highly reliable at recognizing genuine
Fall Armyworm damage *when photographed as intended* — a close-up of a
single affected leaf — and its failures cluster specifically around
framing styles absent from its training distribution (extreme macro
detail shots, whole-plant wide shots), not around genuinely difficult or
ambiguous damage cases.

**Direct product implication, already implemented:** the app's photo
upload UI explicitly instructs users to "get close to one leaf, not the
whole plant" — this finding validates that guidance was the right call,
and suggests it's worth reinforcing further (e.g. an in-app framing guide)
rather than solely trying to train around it.

---

## 8. Language Model Performance (Qwen2.5-3B vs. 1.5B)

Empirically tested head-to-head, same hardware, same questions, same
offline setup, on a development CPU predating AVX2 support (deliberately
representative of older/budget hardware common across the target region,
not the newest available machine):

| Model | Generation speed | Total response time (typical query) |
|---|---|---|
| Qwen2.5-3B | ~4.9 tokens/sec | ~159 sec |
| Qwen2.5-1.5B | ~7.9 tokens/sec | ~22 sec |

Diagnostic quality was validated as comparable across both sizes on our
test question set (e.g., correct Heartwater and Haemonchus diagnoses with
sound, corpus-grounded reasoning) — accuracy came from the RAG retrieval
layer supplying the right facts, not primarily from raw model size. This
directly informed the decision to default to the smaller, faster model:
**accessibility across the hardware people actually have was treated as
an engineering requirement, not an afterthought.**

---

## 9. Multilingual Support (Shona / Ndebele)

We tested two off-the-shelf machine translation options before building
anything custom:

- **NLLB-200** (Meta, open-source): confirmed Shona support, empirically
  tested directly against real corpus sentences. Result: unreliable on
  specialized terms — "heartwater" was translated as a literal word-by-word
  calque rather than the actual disease name, and in one case the subject
  was incorrectly switched from animal to human.
- **Google Translate**: confirmed Shona support since 2016, but its listed
  "Ndebele" is the **South African** variant, not Northern/Zimbabwean
  Ndebele — a related but distinct language. Also fundamentally a cloud
  API, incompatible with the offline requirement regardless.

**Decision:** rather than trust automated translation for
health/safety-relevant content, the app uses a **verified phrasebook** of
real farmer-facing terminology — disease names, critical action phrases,
and common symptom descriptions — personally confirmed in both Shona and
Ndebele by a fluent speaker on the development team, not machine-generated.

**Retrieval engineering challenge:** Shona's agglutinative grammar (e.g.
"mechibage" = "in the maize," fusing a locative prefix directly onto the
noun root "chibage") caused exact-word keyword matching to silently miss
valid queries. Fixed with substring-based matching for local-language
terms. Separately, the Shona word "gonye" is ambiguous between a crop pest
and a livestock parasite depending on its grammatical qualifier
("rechibage" = "of maize" vs. "remudumbu" = "of the stomach") — resolved
by keying domain classification on the distinguishing qualifier rather
than the shared ambiguous root, verified with targeted test cases in both
directions.

---

## 10. Limitations and Future Work

- Vision model recall (80.6%) would benefit from additional training data
  specifically covering whole-plant and macro-detail photo framings
- Ndebele coverage is currently limited to the verified phrasebook subset;
  broader free-form Ndebele generation remains unsolved, honestly, rather
  than approximated with an unreliable substitute
- The AWS evaluation pipeline currently runs on-demand rather than
  triggered automatically on new model versions — a natural next step
  toward the "approved model update" pattern referenced in our
  architecture
- COOL (Cloud-Optimized OpenCV Library on AWS Graviton) has not yet been
  implemented; noted as a possible future direction

---

## 11. Build & Deployment

See accompanying repository README for pinned dependencies, build
instructions (`pyinstaller --onedir --noconsole --collect-all cv2
--hidden-import multipart --hidden-import multipart.multipart`), and the
one-click desktop app produced by that process.
