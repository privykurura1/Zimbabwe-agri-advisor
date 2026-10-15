# Android plan

Three steps, cheapest first. Only step 1 works today.

## Step 1: phones use the laptop (works now)

The laptop app shows its Wi‑Fi address at the top of the page (for example
`http://192.168.1.5:8000`). Any phone on the same Wi‑Fi or laptop hotspot opens
that address in its browser and uses the full advisor, photo check, farm records
and find-help pages. The phone needs no data bundle and no install, because the
model runs on the laptop.

Limits: the laptop must be on and nearby. The farm records are on the laptop, so
they are shared by everyone using it.

## Step 2: SMS for phones without Wi‑Fi (built, needs a real test)

An officer approves an advisory, and `python -m murimi_plus.sms send <id> --to 07...`
sends it through an Android phone running the open-source *SMS Gateway for Android*
app (Apache-2.0). See `murimi_plus/sms.py`. This has only been tested against a
simulated gateway, not a real phone and SIM. Questions still reach the officer by
SMS or a phone call, and the officer types them in.

## Step 3: the advisor on the phone itself (not built)

What would be needed:
- **Model:** llama.cpp builds for Android (arm64). The current 1.5B Q4_K_M model
  file is about 1 GB. My expectation is that it is usable on phones with 4 GB RAM
  or more, but I have **not** tested this. A 0.5B model would fit smaller phones
  but must pass `test_model_behaviour.py` before it is used.
- **App:** the retrieval (`rag.py`) and answer clean-up are Python. They could be
  ported to Kotlin, or run with an embedded Python such as Chaquopy. Both options
  need checking before choosing.
- **Knowledge base:** the same Markdown file, shipped with the app.
- **Test:** the same 104 retrieval checks and the 14 behaviour checks must pass on
  the phone build.

Suggested order: (a) measure llama.cpp speed with the current model on 2–3 phones
farmers actually own; (b) decide on 1.5B or 0.5B from that measurement plus the
behaviour tests; (c) port the retrieval; (d) build the UI by reusing `index.html`
in a WebView.
