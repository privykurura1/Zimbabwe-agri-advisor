# Murimi Fara extras (branch `feature/outstanding`)

All of this is in `murimi_plus/`. app.py loads it only if it imports cleanly, so a
fault in the extras can never stop the advisor from answering. Nothing in the extras
asks the language model to write anything. Everything a farmer sees here was written
or checked by a person.

## What was added, and its status

| Feature | Where | Status |
|---|---|---|
| Outbreak watch | `/extras/dashboard`, `murimi_plus/outbreak.py` | Works; tested on made-up logs. The alert thresholds are a starting guess for a vet to adjust. |
| Province on questions | Selector at the top of the app; saved in the log | Works. Optional for the farmer. |
| Short summaries in Shona / Ndebele | `data/local_summaries.json` | Framework works. **The Shona and Ndebele text is blank on purpose**: you write it, and a speaker checks it. |
| Audio ("listen") | `audio/<ENTRY>_sn.mp3` etc. | Plays any recording you add. **No recordings are included.** |
| Find help | `/extras/help`, `data/help_directory.json` | Works. **All contacts are blank** until you add real, checked numbers. |
| Seasonal outlook in planting answers | `data/seasonal_outlook.json` | Works. **Blank** until you copy in the official outlook. It only shows when the farmer names a region ("region 4"). |
| Farm records and reminders | `/extras/farm` | Works. The only built-in suggestion is weekly dipping, from knowledge entry B5. |
| SMS of approved advice | `python -m murimi_plus.sms send ...` | Tested only against a simulated gateway; **not yet with a real phone and SIM**. |
| More photo checks | `/extras/photo`, `models/photo/`, `tools/train_photo_check.py` | Framework tested with a tiny test model. **No new trained checks are included**: they need labelled photos. The training script was **not run here** because PyTorch is not available in this environment. |
| Low-end hardware mode | `murimi_plus/hardware.py`, used by `desktop_app.py` | Works. It uses fewer threads and a smaller context on computers with less than 6 GB RAM, plus an optional `model/lite.gguf`. |
| Expert review sheet | `tools/export_review_sheet.py` → `review/expert_review_sheet.csv` | Ready to send. |
| Pilot plan + metrics | `docs/PILOT_PLAN.md`, `tools/pilot_metrics.py` | Ready. |
| Partnership letter | `docs/PARTNERSHIP_LETTER.md` | Template to fill in. |
| Android | `docs/ANDROID_PLAN.md` | Plan only. Phones can already use the laptop over Wi‑Fi. |

Tests: `python -m unittest discover -s murimi_plus/tests -t .` runs 37 tests.

## How to fill in the content

**Summaries** (`data/local_summaries.json`): each entry has `en` (an English draft
taken from the entry's own *Action* line; shorten it to 1–2 sentences), `sn`, `nd`,
`reviewed` and `reviewed_by`. Set `reviewed` to `true` only after a Shona/Ndebele
speaker and someone who knows the subject have both checked the text. Unreviewed
entries are never shown. To add entries after the corpus grows, run
`python tools/make_summary_template.py`; it keeps what you already wrote.

**Audio:** record the reviewed summary on a phone and save it as `audio/B3_sn.mp3`
(entry id, underscore, `sn`/`nd`/`en`). A play button appears automatically.

**Contacts** (`data/help_directory.json`): replace each `FILL IN` with the real
office name and phone number, and put the date you checked it in `checked_on`.
`type` is `vet`, `animal_health`, `dip_tank` or `agritex`. Animal questions show vet,
animal health and dip-tank contacts; crop questions show AGRITEX contacts.

**Seasonal outlook** (`data/seasonal_outlook.json`): copy the official seasonal
rainfall outlook for each Natural Region (`below normal`, `normal` or `above normal`),
with `source` and `issued` date. Leave a region blank if the outlook does not cover it.

In the installed app these files are in the install folder, under Program Files.
Edit them before building the installer, or edit them as administrator.

## SMS set-up

1. On an Android phone with a local SIM, install *SMS Gateway for Android*
   (github.com/capcom6/android-sms-gateway). Turn on **Local Server** and note the
   address, username and password it shows.
2. On the officer's computer:
   ```
   set MURIMIFARA_SMS_URL=http://<phone-ip>:8080
   set MURIMIFARA_SMS_USER=<username>
   set MURIMIFARA_SMS_PASS=<password>
   python -m murimi_plus.sms --db .challenge-data\agent.sqlite3 send <advisory-id> --to 0771234567
   ```
   Only approved advisories can be sent. If the approved text is longer than 3 SMS
   (459 characters), add `--text "short version"`. The officer types `SEND` to confirm.
   The audit log keeps the exact text and the last 3 digits of the number.
   Without the three settings above, the command does a dry run and sends nothing.

## Outbreak watch rule

A condition is flagged when it had at least 3 matched questions in the last 7 days,
and that is at least twice its weekly average over the 4 weeks before (or it had none
before). More questions is a reason for an officer to look, not proof of an outbreak.
The page shows counts only, never what farmers typed. Change the numbers at the top of
`murimi_plus/outbreak.py` with your partner vet.
