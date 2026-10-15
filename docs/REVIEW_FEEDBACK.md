# Getting officers' reviews back to the Murimi Fara team (no internet needed)

Every laptop keeps working offline. Reviews travel back to you in two ways.

## 1. The reviews file (full details)

On the officer review page: **Prepare the reviews file** → optional district → tick consent →
**Save the reviews file**. It saves `murimi-fara-reviews-<CODE>-<date>.json`.

- Contains: questions, drafts, decisions, reasons, the officer's problem category,
  corrected answer and missing topic, knowledge entry IDs, region, urgency.
- Does **not** contain officer names. Phone numbers and ID-like numbers are removed
  from all text. The laptop is identified only by a random 4-character code.
- Officers carry it on a flash drive, or send it to their phone by Bluetooth/USB and
  forward it by WhatsApp or email when they have signal. Collect files when you visit
  to deliver app updates.

## 2. SMS codes (fast warnings)

After each decision the page shows a one-SMS code, e.g. `MF B3,F1 R UNSAFE K7Q2`:
entries used, A(pproved)/R(ejected), problem category, laptop code. Officers text it to
the number in `data/team_contact.json` (fill in `sms_number`; until then the page says
"the Murimi Fara team's number"). Each SMS costs airtime; no data needed.

Categories: NONE, WRONG (wrong condition), MISSING (advice missing), UNSAFE, UNCLEAR,
LANG (language/translation), SCOPE (topic not covered), OTHER.

## 3. Your side: merge everything

    python tools/merge_reviews.py reviews\*.json --sms sms_codes.txt

Paste received SMS messages into `sms_codes.txt`, one per line. The tool writes
`reviews_report.md` (unsafe reports first, approval per entry, problem categories,
missing topics, officers' corrections) and `reviews.csv`. Files sent twice are counted once.

Officers' corrections are their opinion, not checked facts: have a vet or agronomist
check them before anything goes into the knowledge base.

## Before collecting at scale

Get the partner office's agreement on how review data is used, and check data-protection
law in each country (in Zimbabwe, as far as I know, the Cyber and Data Protection Act -
verify the current requirements).
