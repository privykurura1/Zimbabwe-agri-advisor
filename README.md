# Offline AI Farming Advisor for Zimbabwe

An offline, on-device AI advisor that helps Zimbabwean farmers diagnose
livestock diseases and get crop guidance by Natural Region — no internet, no
cloud, running entirely on an 8GB laptop.

Built for the [Africa Deep Tech Challenge 2026](https://adtc-2026.devpost.com/)
— Agriculture domain.

## What it does

- **Livestock disease triage** — describe symptoms, get a likely diagnosis,
  reasoning, and clear next steps (cattle tick-borne diseases, poultry disease)
- **Crop advisory** — pest identification and planting-window guidance tuned
  to Zimbabwe's Natural Regions (I–V)

Every answer is grounded in a locally-stored knowledge base
(`corpus_livestock_crops.md`), retrieved at inference time — not just the
model's general training data.

## How it works

- **Model:** Qwen2.5-3B-Instruct, GGUF Q4_K_M quantization
- **Runtime:** llama.cpp, CPU-only
- **Retrieval:** TF-IDF-based RAG over the local corpus (`rag.py`)

## Quick start

```bash
bash download_model.sh
python rag.py "your farming question here"
```

See `REPORT.md` for full technical details, design decisions, and benchmarks.
