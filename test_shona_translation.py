"""
Test script - NOT wired into the real app yet. Just for trying NLLB-200's
Shona translation quality on real Murimi Fara text before we commit to
using it for real.

SETUP:
    pip install transformers torch sentencepiece

Heads up on sizes, given your bandwidth situation:
    - torch (CPU version): a few hundred MB
    - transformers + sentencepiece: small, a few MB
    - The NLLB model itself downloads automatically the first time you
      run this script: ~2.4 GB (the smallest "distilled" version, still
      the full multilingual model since it covers 200 languages at once)

This will take a while to download and to run on your CPU (no AVX2,
same hardware constraint as your main model) - run it and be patient,
this is just a quality test, not the final integration.
"""

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

MODEL_NAME = "facebook/nllb-200-distilled-600M"
SHONA_CODE = "sna_Latn"

print("Loading NLLB-200 (this downloads ~2.4GB the first time you run it)...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, src_lang="eng_Latn")
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
print("Loaded. Translating test sentences...\n")


def get_lang_token_id(tokenizer, lang_code):
    """Handles both older and newer versions of the NLLB tokenizer, which
    expose the language-code-to-token-id mapping slightly differently."""
    if hasattr(tokenizer, "lang_code_to_id"):
        return tokenizer.lang_code_to_id[lang_code]
    return tokenizer.convert_tokens_to_ids(lang_code)


def translate_to_shona(text):
    inputs = tokenizer(text, return_tensors="pt")
    translated_tokens = model.generate(
        **inputs,
        forced_bos_token_id=get_lang_token_id(tokenizer, SHONA_CODE),
        max_length=200,
    )
    return tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]


# Real sentences from your actual corpus/answers - testing on the exact
# kind of text the app would need to translate, not generic examples.
test_sentences = [
    "This is an emergency. Seek veterinary help immediately.",
    "Isolate the animal from the rest of the herd.",
    "The symptoms of high fever and circling are strong indicators of heartwater.",
    "Contact a veterinary officer or dip tank attendant as soon as possible.",
    "There are ragged holes and droppings in the middle of the maize plants.",
]

for sentence in test_sentences:
    shona_text = translate_to_shona(sentence)
    print(f"EN: {sentence}")
    print(f"SN: {shona_text}")
    print()

print("Done. Read through these carefully (or have a Shona speaker check)")
print("before deciding whether this is accurate enough to actually use.")