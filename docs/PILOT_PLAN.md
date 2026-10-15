# Pilot plan: Murimi Fara with real farmers

**Purpose:** find out whether farmers who use Murimi Fara act sooner and more correctly
on sick animals and damaged crops, and where the advisor gets things wrong. The
pilot does not try to prove a yield or mortality effect, because a small pilot is
too small for that.

Everything in [square brackets] is for you to fill in. The numbers here are
suggestions for a first pilot, not results.

## 1. Set-up

| Item | Plan |
|---|---|
| Where | [1–2 wards, ideally one in NR II and one in NR IV] |
| Partner | [AGRITEX district office / Department of Veterinary Services officer] who reviews answers and takes referrals |
| Who | [about 30–60] farmers who keep cattle, goats or chickens, or grow maize |
| How they use it | At an AGRITEX office or lead-farmer laptop; phones on the same Wi‑Fi open the laptop address |
| Length | [8 weeks] in the rainy season, when tick-borne disease and fall armyworm peak |
| Consent | Read the consent text below aloud in Shona or Ndebele, then record the answer. Nobody is required to take part. |

Before the pilot starts:
1. The expert review is done: every entry has a reviewer's sign-off (`review/expert_review_sheet.csv`).
2. The contacts in `data/help_directory.json` are real and were checked by phone.
3. A partner officer has agreed to check the outbreak watch page weekly.

## 2. What is measured

**From the app, automatically (counts only):** `python tools/pilot_metrics.py <logs>`
- questions per week; % answered from the knowledge base; % "needs more detail"
- urgent referrals given
- photo checks and their results
- outbreak-watch alerts, and whether the officer found a real problem behind each one

**From people (follow-up form, 1–2 weeks after a question):**

| Question | Answer |
|---|---|
| Did you understand the advice? | yes / partly / no |
| What did you do? | called vet / went to dip tank / treated / sprayed / nothing / other |
| How many days after the problem started? | number |
| What happened to the animal or crop? | recovered / still sick / died / sold / don't know |
| Was the advice wrong or harmful in any way? | free text |
| Would you use it again? | yes / no, why |

**Expert check of answers:** each week the partner officer reads [20] random answers
from the log (with the farmers' agreement) and marks each one *correct*, *incomplete*
or *wrong/unsafe*. Any *wrong/unsafe* answer is fixed in the knowledge base that
week, and a test is added for it.

## 3. Stop rule

The pilot pauses if an answer is marked *unsafe* and a farmer acted on it, until the
cause is fixed and re-tested.

## 4. Consent text (translate and have the translation checked)

> This laptop program gives farm advice. Your question and the app's answer are saved
> on this computer so that [partner] can check the advice is right. Your name and phone
> number are not saved with the question. You can stop at any time. The advice does
> not replace a vet or extension officer.

## 5. What to report at the end

Weekly table from `pilot_metrics.csv`; follow-up form results; the expert check
(correct / incomplete / wrong); every alert and what the officer found; the
corrections made to the knowledge base; what farmers asked for that was not covered.
