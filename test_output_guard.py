"""
Regression test for the output guard in rag.py (cut_runaway / OutputGuard).
Runs in a second; needs no model.

    python test_output_guard.py

The "runaway" samples are real model outputs from test_shona_generation.py
(Oct 2026), shortened. Each must be cut back to the real answer. The "good"
samples must come through unchanged.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rag import cut_runaway, OutputGuard, speak_to_you, tidy_answer

RUNAWAY = [
    ("fake Q&A entry + fake farmer turn",
     "Likely condition: Babesiosis (\"Redwater\"). What to do: Contact the Department of Veterinary "
     "Services or a local animal-health worker for confirmation.\n\n### MAIZE Q&A:\n- **Local name:** "
     "Shona - Chirwe\n\nFARMER'S MESSAGE: Mombe yangu iri kuita weti chirwe\n\nANSWER: Likely",
     "for confirmation."),
    ("invented corpus entry after ---",
     "What to do: Scout fields regularly from emergence. Ask AGRITEX which products are registered and "
     "follow the label.\n\n---\n\n### D2. Maize \u2014 Bacterial Blight\n- **Cause:** Pseudomonas",
     "follow the label."),
    ("whole answer restated a second time",
     "What to do: Regularly check inner eyelid/gum color for anemia as a simple\nscreening tool. "
     "Keep animals off heavily grazed, wet pasture to reduce reinfection risk.\n\n**Action:**\n"
     "1. Regularly check inner eyelid/gum color for anemia as a simple screening tool (pale = concern).",
     "reinfection risk."),
    ("chat token leaked as text",
     "### What to do\n1. Keep your cow in the shade.<|im_end|>\n<|im_start|>user\nmore",
     "Keep your cow in the shade."),
]

GOOD = [
    "### LIKELY CONDITION\nThe most likely condition is **Babesiosis** (\"Redwater\").\n\n### WHY\n"
    "Your cow is passing red urine.\n\n### WHAT TO DO\nContact a veterinarian today.",
    "### Likely condition\nThe signs fit fall armyworm.\n### Why\nRagged holes and droppings.\n"
    "### What to do\n1. Scout early.\n2. Ask AGRITEX which products are registered.\n---\nThat is all.",
    "1. LIKELY CONDITION: Heartwater.\n2. WHY: Fever and circling.\n3. WHAT TO DO: Contact a vet. "
    "Keep the cow calm. Contact a vet.",
]


SPEAK_TO_YOU = [
    ("The farmer's cow is passing red urine.", "Your cow is passing red urine."),
    ("Keep the farmer's chickens apart.", "Keep your chickens apart."),
    ("The farmer should contact a vet today.", "You should contact a vet today."),
    ("Then the farmer can scout early.", "Then you can scout early."),
    ("Advise the farmer to confirm with AGRITEX.", "Confirm with AGRITEX."),
    # copied instruction lines (real output, 10 Oct 2026) are removed
    ("### What to do\n2-4 short numbered steps.\n1. Scout fields regularly.",
     "### What to do\n1. Scout fields regularly."),
    ("### Check for\n2-3 other signs from the reference, written as short questions.\n- Is it trembling?",
     "### Check for\n- Is it trembling?"),
]


# Real answers from 11 Oct 2026: (answer, crop?, farmer's message, expected clean answer)
FINISH = [
    ("### What to do\n1. Monitor.\n\n**Action:** Avoid recommending pesticides when symptoms fit nutrient, "
     "moisture, or soil constraints better than a pest/disease.", True, "my maize has yellow leaves",
     "### What to do\n1. Monitor."),
    ("### What to do\n1. Keep an eye on soil moisture.\n\nYour maize.", True, "when should I plant",
     "### What to do\n1. Keep an eye on soil moisture."),
    ("### What to do\n1. Plant after the first reliable rain.\n\nNdodyara chibage rini? (When should I plant maize?)",
     True, "Ndodyara chibage rini?", "### What to do\n1. Plant after the first reliable rain."),
    ("### What to do\n1. Treat with approved pesticides if necessary.", True, "gonye in maize",
     "### What to do\n1. Treat with approved pesticides if necessary.\n\n"
     "Ask AGRITEX which products are registered and follow the label."),
]


def stream(text, size=3):
    g, out = OutputGuard(), ""
    for i in range(0, len(text), size):
        out += g.feed(text[i:i + size])
        if g.stopped:
            break
    return out + g.flush(), g.was_cut


def main():
    failures = 0
    for label, text, must_end in RUNAWAY:
        clean, cut = cut_runaway(text)
        streamed, s_cut = stream(text)
        ok = cut and s_cut and clean.endswith(must_end) and streamed == clean
        failures += not ok
        print("%s  runaway: %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            print("      got: %r" % clean[-120:])
    for text in GOOD:
        clean, cut = cut_runaway(text)
        streamed, _ = stream(text)
        ok = not cut and clean == text and streamed == text
        failures += not ok
        print("%s  good answer unchanged: %s..." % ("PASS" if ok else "FAIL", text[:40].replace("\n", " ")))
    for before, after in SPEAK_TO_YOU:
        streamed, _ = stream(before)
        batch = speak_to_you(before + "\n").rstrip("\n")
        ok = batch == after and streamed == after
        failures += not ok
        print("%s  'the farmer' -> 'you': %s" % ("PASS" if ok else "FAIL", before))
        if not ok:
            print("      got: %r / streamed %r" % (batch, streamed))
    for text, crop, query, after in FINISH:
        batch = tidy_answer(text, crop=crop, query=query)[0]
        g, streamed = OutputGuard(crop=crop, query=query), ""
        for i in range(0, len(text), 3):
            streamed += g.feed(text[i:i + 3])
        streamed += g.flush()
        ok = batch == after and streamed.strip() == after
        failures += not ok
        print("%s  final clean-up: %s" % ("PASS" if ok else "FAIL", text.splitlines()[-1][:60]))
        if not ok:
            print("      got: %r / streamed %r" % (batch, streamed))
    total = len(RUNAWAY) + len(GOOD) + len(SPEAK_TO_YOU) + len(FINISH)
    print("\n%d/%d passed" % (total - failures, total))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
