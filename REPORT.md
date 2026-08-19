# Technical Report — Offline AI Farming Advisor for Zimbabwe

**Team ID:** 
**Domain:** agriculture
**Model:** Qwen2.5-3B-Instruct-Q4_K_M

---

## Problem

Cloud-hosted LLMs require stable connectivity, sustained electricity, and
ongoing API fees — none of which are guaranteed for a smallholder farmer,
extension officer, or agri-dealer in rural Zimbabwe. Meanwhile, tick-borne
cattle diseases alone account for roughly 20-30% of recorded cattle deaths
annually in the country, and farmers often lack fast access to a vet when
symptoms first appear.

The target user is a Zimbabwean smallholder farmer or extension worker with
access to a low-cost laptop but unreliable or no internet connectivity. This
model gives them immediate, locally-grounded triage for livestock disease
symptoms and crop pest/planting guidance — without requiring a live network
connection, a subscription, or specialist training to use.

Running this fully on-device matters because the moments this advice is
needed most — a sick animal at night, a pest outbreak during planting season —
are exactly the moments connectivity and expert access are least reliable in
these communities.

---

## Design Decisions

**Base model:** Qwen2.5-3B-Instruct, quantized to GGUF Q4_K_M.

We chose a 3B parameter model as a balance point: small enough to run
comfortably within the ADTC Standard Laptop's 8GB RAM budget (observed peak
~2GB, well under the 7GB Seff ceiling), while still strong enough to follow
multi-part structured instructions (diagnosis → reasoning → action steps)
reliably. We considered smaller models (Qwen2.5-1.5B) for additional speed
headroom, but did not have reliable bandwidth during development to test this
tradeoff directly; this remains a documented open alternative rather than a
tested rejection.

**Runtime:** llama.cpp (CPU-only build), matching the ADTC Standard Laptop's
integrated-graphics-only hardware profile — no discrete GPU acceleration.

**Grounding strategy — RAG over general model knowledge:** Rather than relying
on the base model's general training data, we built a hand-curated, Zimbabwe-
specific knowledge corpus (Natural Region agro-ecological data, tick-borne
cattle disease profiles, fall armyworm identification, poultry disease
patterns) and retrieve relevant entries via TF-IDF at query time before the
model answers.

This was a direct, evidence-based decision: in an ungrounded test, the model
guessed BVD, foot-and-mouth disease, and rabies for a textbook heartwater
symptom set (fever + circling + head-pressing). After wiring in RAG retrieval
over our corpus, the same query correctly and consistently identified
heartwater across multiple repeated runs, with reasoning that explicitly
referenced the retrieved reference material rather than generic guessing.
This comparison is the core evidence behind choosing RAG over a larger base
model or fine-tuning as our primary accuracy lever.

We chose TF-IDF (scikit-learn) over a dense embedding model for retrieval to
avoid an additional model download and dependency, given real bandwidth
constraints during development — a deliberate tradeoff of retrieval
sophistication for reliability and offline-first simplicity, appropriate at
our current corpus size (dozens, not thousands, of chunks).

**Prompt structure:** We require the model to answer in three explicit parts —
likely condition, reasoning tied to symptoms, and action steps — rather than
a free-form answer. This both improves answer usability for a non-technical
farmer and reduces hallucination by forcing the model to justify its
conclusion against the retrieved context rather than stating one outright.

**Thread tuning:** Development was done on an Ivy Bridge-era CPU (pre-AVX2),
below the ADTC reference spec (Intel i5 10th-12th gen or Ryzen 5 3000-5000,
both AVX2-capable). We benchmarked thread count (`-t 4` was optimal on our
4-core development machine, `-t 8` was measurably worse due to oversubscription)
and flash attention (`-fa 1`, no measurable gain on this hardware, likely
because flash attention's benefits are more pronounced on newer vectorized
CPU instruction sets) to optimize within our constraints. We expect
meaningfully higher throughput on the actual AVX2-capable reference hardware
used for judging, since our development numbers represent a conservative
floor rather than the model's true ceiling.

---

## Constraints

- Target: 8 GB RAM, integrated GPU only, Ubuntu 22.04 (ADTC Standard Laptop
  reference profile)
- No GPU acceleration — pure CPU inference via llama.cpp
- Development machine was below the reference CPU generation (pre-AVX2),
  meaning our self-reported throughput numbers are a conservative estimate,
  not a ceiling
- Real-world bandwidth constraints during development (mirroring our actual
  target users' connectivity situation) limited how many alternative model
  sizes and embedding approaches we could directly benchmark; decisions here
  are documented as reasoned tradeoffs rather than exhaustively tested against
  every alternative
- Zero external network calls required at inference time — verified by
  running with network access disabled

---

## Benchmarks

| Metric | Value |
|---|---|
| Machine | Windows laptop, Intel CPU (Ivy Bridge generation, pre-AVX2), 15.8 GB RAM |
| RAM at peak | ~2.05 GB (well under the 7 GB Seff budget) |
| Generation speed | 5.71 t/s (llama-bench, `-t 4`, best configuration found) |
| Prompt processing speed | ~7.5 t/s |
| Thermal throttling | None observed (CPU peaked at ~95-100% utilization, no throttle flagged) |

These are self-reported development benchmarks, measured on hardware below
the ADTC reference spec. Official scores are measured by the ADTC profiler on
the standard evaluation machine, which we expect to show improved throughput
given its newer, AVX2-capable CPU architecture.

**Qualitative accuracy check (informal, not self-reported to Sacc):** the
model was tested with and without RAG retrieval on the same symptom-based
query. Without retrieval, it produced plausible-sounding but incorrect
guesses (BVD, foot-and-mouth, rabies). With retrieval, it correctly and
consistently identified heartwater across repeated runs, with reasoning
explicitly grounded in the retrieved reference material.