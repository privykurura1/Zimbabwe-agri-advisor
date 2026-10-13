# Murimi Fara — exhibition runbook

## Tonight (about 45 minutes, in this order)

1. **Put the latest files in your project folder:** `app.py`, `rag.py`, `index.html`,
   `desktop_app.py`, `corpus_livestock_crops.md`.
2. **Rebuild the app.** `app.py` and `rag.py` are compiled into the exe, so copying them
   is not enough.
   ```
   .\venv\Scripts\Activate.ps1
   pyinstaller --onedir --noconsole --noconfirm --icon=murimifara.ico --collect-all cv2 --hidden-import multipart --hidden-import multipart.multipart --name MurimiFara desktop_app.py
   ```
   Copy into `dist\MurimiFara\`: `index.html`, `rag.py`, `corpus_livestock_crops.md`,
   `faw_classifier.onnx`, `vendor\`, `llama\`, `model\`. (`model\` must hold only the
   1.5B `.gguf` — the 3B one makes the folder 3 GB and is unused.)
3. **Demo from that folder.** Do not build or run a new installer on the exhibition
   laptop tomorrow morning — use exactly what you test tonight.
4. **Start `MurimiFara.exe`, wait for the window, then run the check:**
   ```
   python preflight_check.py --photo test1.jpg
   ```
   It asks the real app 13 questions and reports the entry used, the urgent flag, any
   "not sure" or dose in an answer, and **how long each answer takes**. Read the answers
   it prints yourself.
5. **Fix what it flags.** If it says only 18 entries loaded, the app is reading an old
   corpus file: copy the new one next to the exe and restart.
6. **Record a backup.** Screen-record 4 or 5 good answers (cow circling, Shona redwater,
   maize photo, a refusal). If anything fails tomorrow, play the recording.
7. **Freeze.** After the check passes, change nothing more.

**Laptop settings:** plugged in; Windows power mode "Best performance"; sleep off; close
every other program; notifications off (Focus assist); add the app folder to Windows
Defender exclusions; test the phone hotspot once tonight.

## Tomorrow morning

- Start the app **20 minutes before** you open, ask one question (the first is slow while
  the model loads), and leave the app open.
- Keep WiFi **off** for the first part of the demo. It proves it is offline. Turn the
  hotspot on only for the phone part.

## Run of show (about 6 minutes)

| Step | Type or do this | What it shows |
|---|---|---|
| 1. Problem (30 s) | Say it: no signal, no vet nearby, no money for data | Why offline matters |
| 2. Livestock emergency | *My cow has a high fever and keeps pushing its head against the kraal post, walking in circles* | Heartwater; the urgent tag; the source entries shown under the answer |
| 3. Shona | *Mombe yangu iri kuita weti tsvuku* | Local-language question, redwater |
| 4. Ndebele | *Inkomo yami ichama umchamo obomvu* | Same, in Ndebele |
| 5. Crops + photo | *There are ragged holes and droppings in the middle of my young maize plants, what's eating them?* then upload a **close-up leaf** photo | Fall Armyworm; the photo result changes what happens next |
| 6. It knows its limits | *my maize has yellow leaves*, then *how many ml of ivermectin for a 300kg cow*, then the sudden-death question | Asks questions instead of guessing; refuses doses; anthrax warning. These replies are **instant** |
| 7. Phone (optional) | Hotspot on; open the address shown in the app header on a phone | No install needed on the phone |
| 8. Close (30 s) | The numbers and the limits below | Honest and credible |

All of these were checked against the code. Whether the real model words them well is
what tonight's check is for.

**Speed:** on your development laptop, reading about 550 tokens took roughly 40 seconds
before the first word, then about 8 tokens a second writing. Expect **45 to 90 seconds
for a full answer** unless tomorrow's laptop is faster (an estimate — the check
measures it). Words appear as they are written, so start talking after you press Enter.
The safety replies and "Let's find out..." replies are instant. If the check says it is
too slow, lead with those and play the recording for the long ones.

## Numbers you can quote (all measured)

- Photo model: **88.5% accuracy, 93.5% precision, 80.6% recall**, tested on **78 independent
  images** it never trained on. Inference 22.8 ms, model 8.5 MB, runs on a CPU.
- 55 knowledge entries: cattle, chicken, goat and sheep diseases and emergencies; maize,
  groundnut and tomato problems.
- Everything runs on one laptop with no internet. A farmer's own phone connects over the
  laptop's WiFi.

## Say these limits yourself, before someone asks

- The photo check works on a **close-up of one leaf**. Whole-plant photos and extreme
  close-ups of the insect were its weak spot; it missed 7 of the 36 damaged leaves.
- It covers what is in its knowledge base. Outside that it asks questions or says who to
  ask — by design, so it never invents a diagnosis.
- It never gives medicine doses or chemical rates.
- Shona and Ndebele: local names for 17 of 55 entries, plus a symptom-word lookup. Not every
  entry has local names yet.
- The photo check only looks for Fall Armyworm.

**Do not say:** "vet-approved", "verified by experts" (the knowledge base has **not** been
reviewed by a vet or agronomist — say it is *being* prepared for review, only if true),
"diagnoses", or "works for all crops and animals".

## If a visitor types their own question

- Covered: it answers. Not covered: it says "Let's find out..." and asks questions.
  Present that as a feature: *"It tells you when it can't help, instead of guessing."*
- Dose, human-health and injection-style prompts get a fixed, instant reply.

## If something goes wrong

| Symptom | Do this |
|---|---|
| Window shows "Something went wrong starting the advisor" | Open `%LOCALAPPDATA%\MurimiFara\murimifara_error.log` (paste that path into File Explorer). Close every MurimiFara / llama-server process in Task Manager, wait 10 seconds, start again |
| "Advisor not running" | The app is still starting — wait a minute. If it stays, do the step above |
| Answers take minutes | Close other programs, plug in power, restart the app. Otherwise switch to the recording |
| Only 18 entries loaded (`http://127.0.0.1:8000/api/health`) | Old corpus: copy the new one next to the exe and restart |
| Phone cannot connect | Hotspot on? Same network? Use the address in the app header. If it still fails, skip it — it is optional |
| Photo gives an error | Skip it; use the recording |
| Everything fails | Play the backup recording. It shows the real app |
