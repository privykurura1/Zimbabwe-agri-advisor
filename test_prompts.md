# Test Prompts — Agriculture Domain (ADTC 2026)

Use these to iterate on model + RAG quality before locking anything in. Pick
your strongest 2 for `metadata.json` (mark below once decided).

Written the way a real farmer would ask — not textbook phrasing. That
difference is part of what should differentiate your Sacc score.

## Livestock
1. "My cow has a high fever and keeps pushing its head against the kraal
   post, walking in circles. What's wrong and what do I do right now?"
   *(should trigger heartwater — urgent)*
2. "It's January and my cattle are getting swollen glands near the ear and
   won't eat. Is this January disease?"
3. "My goat's urine looks dark red today. Should I be worried?"
4. "How often should I be dipping my cattle right now, it's the start of
   the rainy season?"
5. "One of my broilers is sneezing and has watery eyes, the others seem
   fine so far — what should I check for?" *(port in from Broiler Guardian
   test cases)*

## Crops
6. "I'm in Mashonaland, when should I plant my maize this year?"
7. "There are ragged holes and droppings in the middle of my young maize
   plants, what's eating them?"
8. "I farm in Matabeleland South, is it worth planting maize this season
   or should I stick to sorghum?"
9. "What's a cheaper way to cure my tobacco without using so much
   firewood?"

## Mixed / judge-style probing (these test whether the model knows its limits)
10. "My cow died overnight with no warning signs, what should I tell the
    vet when they arrive?"
11. "Is it safe for me to treat gallsickness myself or do I need a vet?"
    *(good answer should not overstate confidence — recommend vet contact,
    note it's treatable but recovered animals stay carriers)*

---

**Chosen for metadata.json (fill in once locked):**
- Test prompt 1: ___
- Test prompt 2: ___
