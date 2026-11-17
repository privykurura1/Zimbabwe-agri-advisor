# Murimi Fara - small, offline farm advisor for Zimbabwe

Murimi Fara ("farmer's helper" in Shona) helps smallholder farmers and the
extension officers who support them with sick animals and damaged crops. It works
with **no internet**, on **old computers**, and is **small enough to download on a
phone or share by WhatsApp** (target: under 50 MB).

**Version 2.0 has no AI language model.** Version 1 shipped a 1 GB AI model
(Qwen2.5-1.5B). Farmers in Zimbabwe often have no internet to download it, and
many have no laptop. The answers never needed it: they always came from the farm
book, and the AI model only rewrote them (and sometimes added mistakes). So 2.0
shows the checked farm book entry itself and uses **our own small model** (a few
KB) to recognise which entry a farmer's message is about. It learns from
officers' and vets' corrections.

## Who can use it

| Who | How |
|---|---|
| Anyone with a Windows computer | Install the small desktop app (`MurimiFara-Setup-2.0.exe`) |
| Farmers with a phone, near that computer | Join the computer's Wi‑Fi/hotspot and open the address shown at the top of the app, in the phone's browser. No app to install, no data bundle |
| A farmer group, ZFU office or extension office | One shared computer runs `MurimiFara.exe --server`; every phone and computer on its Wi‑Fi uses it |
| Anyone with internet | The same server can run online (any small server); people open it in a browser |
| Farmers with no phone | A trained lead farmer or officer asks for them and reads (or plays) the answer |

The **Murimi Fara Planner** Android app ([Google Play](https://play.google.com/store/apps/details?id=com.fambai.goho))
is separate: it does planning (feed, water, what to buy and sell). Planned: the
same farm book inside the Planner, so phones work with no computer at all.

## What it does

- **Livestock and crop problems:** describe what you see in English, Shona or
  Ndebele ("Mombe yangu iri kuita weti tsvuku"). Murimi Fara shows the matching
  farm book entry: what it may be, the signs, what to do now, and when to call
  the vet. Cattle, goats, sheep and chickens; maize, groundnuts, tomatoes;
  planting times by Natural Region.
- **Urgent warning** when the matched entry is time-critical (decided by the
  entry, not by wording).
- **Safety replies** for medicine-dose questions, human illness and sudden deaths
  (possible anthrax), and **"tell me more"** instead of a guess when nothing matches.
- **"Was this answer right?"** buttons. "Not right" answers go to the officer page.
- **Officer review** (`/officer`, on the computer itself): drafts, approval,
  tamper-evident audit log, feedback to the Murimi Fara team by file or SMS code.
- **Extras:** outbreak watch, find help (contacts by province), farm records and
  reminders, checked Shona/Ndebele summaries with audio, rainfall outlook.

Murimi Fara gives guidance, not a diagnosis. The farm book still needs review by a
veterinarian and an agronomist before wide use with farmers.

## How it works

```text
farmer's message
  -> safety check (rag.scope_guard)            fixed safety replies
  -> which farm book entry?
       farm book search (rag.py, tinytfidf.py) tested rules, plain Python
       our own model (matcher.py)               learns from checked examples
  -> the answer IS that entry (advisor.py)      nothing is generated
  -> no match: ask for more detail              never guess
```

How the two are combined (`advisor.py`):

1. The model is **very sure** (the message is almost the same as a checked
   example): use its entry.
2. Otherwise the **farm book search** decides, if it finds a match.
3. Otherwise the model may answer if it is **fairly sure**, marked "I am not fully
   sure this is the right match".
4. Otherwise ask for more detail.

The model can only choose entries the search would allow for that animal or crop,
so a pig question can never get a cattle answer.

| File | What it is |
|---|---|
| `corpus_livestock_crops.md` | The farm book: 55 checked entries |
| `rag.py`, `tinytfidf.py` | Farm book search and safety rules (no scikit-learn) |
| `matcher.py` | Murimi Fara's own model: a nearest-example classifier on words and letter pieces (copes with spelling and Shona/Ndebele word forms) |
| `models/murimi_model.json` | The trained model (examples + settings, about 12 KB) |
| `data/training_phrases.csv` | Training examples: how farmers describe each problem |
| `advisor.py` | The answer pipeline, used by the app, the officer page and the tests |
| `app.py`, `index.html` | Web app (FastAPI + page) |
| `desktop_app.py` | Desktop window (pywebview), or `--server` for web only |
| `challenge_agent/` | Officer review, audit log, feedback export |
| `murimi_plus/` | Extras (outbreak watch, farm records, help, summaries, SMS) |

## Teaching the model (the feedback loop)

```text
farmer taps "Not right"  ->  officer page "Farmer feedback"  ->  officer checks the question
  ->  picks the RIGHT farm book entry  ->  "Prepare the reviews file"  ->  sent to the team
  ->  python tools/train_model.py --reviews reviews\*.json  ->  new model, only if not worse
```

- **Add your own examples** to `data/training_phrases.csv`: how farmers really
  describe each problem, in English, Shona and Ndebele (`text, entry, language,
  source, checked_by`). Ask a vet or officer to check them.
- **Train:** `python tools/train_model.py` (first time: `--seed` adds the phrases
  already in the farm book). Approved officer reviews and "correct entry" choices
  from review files are added with `--reviews`.
- **The check:** every case in `test_rag_gate.py` (real messages from testing),
  plus `data/test_phrases.csv` if you add one, runs through the whole app. The
  new model is saved **only if it passes at least as many as before**. Test cases
  are never used for training, so the score stays honest.
- Ship the new `models/murimi_model.json` as an update: a few KB.

Officers' corrections are their opinion, not checked facts: check new examples
with an expert, and never change farm book text without expert review.

## Run it

**Windows app:** download `MurimiFara-Setup` from the
[Releases page](https://github.com/privykurura1/Zimbabwe-agri-advisor/releases),
install and open. Phones on the same Wi‑Fi can open the address shown at the top.

**From source (Windows, Linux or Mac, Python 3.12+):**

```bash
pip install -r challenge_agent/requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000/ (phones: `http://<this computer's address>:8000`).
`--host 0.0.0.0` lets other devices connect; leave it out for this computer only.

**Build the Windows app:** `.\build_exe.ps1` (runs the tests, builds
`dist\MurimiFara`, self-tests it, reports the size), then compile
`murimifara_installer.iss` with Inno Setup.

## Tests

```bash
python test_rag_gate.py                                 # farm book search and safety (104 checks)
python -m unittest test_core                            # model, pipeline, training, web app
python -m unittest discover -s challenge_agent/tests -t .   # officer review, audit, feedback
python -m unittest discover -s murimi_plus/tests -t .       # extras
```

## Limits (honest)

- The model only knows problems that are **in the farm book**. A new disease needs
  a new entry, written and checked with a vet.
- At first the model knows only the phrases written in the farm book, so today it
  mostly agrees with the search. It gets better as checked farmer phrasings and
  officer corrections are added.
- Some farm book entries are written for advisers ("advise the farmer to..."),
  not for farmers. They should be rewritten in plain words, with Shona and
  Ndebele versions by fluent speakers (`data/local_summaries.json`).
- Answers are shown in English with local names; Shona/Ndebele summaries appear
  only once a speaker and an expert have checked them.
- Phones need the computer (same Wi‑Fi) or an online server; a fully offline phone
  version is planned in the Planner app.
- Officer review is single-computer and has no logins.

## History

Version 1 (2026) used Qwen2.5-1.5B with llama.cpp, an OpenCV fall-armyworm photo
check, LangGraph and MCP, built for the Africa Deep Tech Challenge, the OpenCV AI
Competition and the African Agentic AI Design Challenge. Version 2.0 removed all of
them to make Murimi Fara small and reachable.

By MPKCOMTECK Technologies (Private) Limited.