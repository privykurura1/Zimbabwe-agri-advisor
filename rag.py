"""
Murimi Fara's search over the checked farm book (corpus_livestock_crops.md).

- Splits the farm book into entries (one per ### section)
- Finds the entries that match a farmer's message with TF-IDF (tinytfidf.py,
  plain Python - no scikit-learn, no AI model, fully offline)
- Domain-filters in English, Shona and Ndebele, so a question phrased entirely
  in a local language routes to the right section
- Decides whether the farm book really covers the question (retrieve_grounded)
  and whether it is urgent; scope_guard() catches questions that need a fixed
  safety reply

There is no language model: the answer the farmer sees is the checked farm book
entry itself (see answers.py).
"""

import re
from collections import Counter
from tinytfidf import ENGLISH_STOP_WORDS, TfidfVectorizer, cosine_similarity, top_indices

CORPUS_PATH = r"corpus_livestock_crops.md"          # the farm book
TOP_K = 2                                            # how many entries to use


CROP_KEYWORDS = {
    # English
    "maize", "crop", "crops", "plant", "plants", "leaves", "leaf", "tobacco",
    "groundnut", "groundnuts", "seed", "planting", "harvest", "pest",
    "armyworm", "fertilizer", "field", "sorghum", "rain", "region",
    # Shona - crop names and crop-specific qualifiers
    "chibage",      # maize
    "fodya",        # tobacco
    "nzungu",       # groundnuts
    "rechibage",    # "of maize" - the qualifier that makes "gonye" crop-specific
    # Ndebele - crop names and crop-specific qualifiers
    "umumbu",       # maize
    "igwayi",       # tobacco
    "amazambane", "indlubu",  # groundnuts (varies by locality)
    "isibungu",     # caterpillar/crop-worm - CONFIRM this isn't also used for
                     # intestinal worms before trusting it alone (see note below)
    "somumbu",      # "of maize" qualifier
    # General crop/plant/leaf/field words. Added after testing showed a Shona
    # question about "chirimwa ... mashizha" (a plant with reddish leaves) was
    # not recognised as a crop question at all, so it was answered as if it
    # were about an animal.
    "chirimwa", "zvirimwa",           # plant / plants (crops) - Shona
    "shizha",                          # leaf - also matches "mashizha" (leaves)
    "munda", "minda",                  # field / fields - Shona
    "mbeu", "dyara", "kohwa",          # seed / plant (sow) / harvest - Shona
    "isitshalo", "izitshalo",          # plant / plants - Ndebele
    "amahlamvu",                       # leaves - Ndebele
    "insimu", "imbewu",                # field / seed - Ndebele
}
ANIMAL_KEYWORDS = {
    # English
    "cow", "cows", "cattle", "goat", "goats", "chicken", "chickens",
    "poultry", "bird", "birds", "broiler", "hen", "calf", "calves",
    "kraal", "dip", "vet", "udder", "herd", "flock", "egg", "eggs",
    # Shona - animal names, disease framing, and disambiguating qualifiers
    "mombe",        # cow/cattle
    "mbudzi",       # goat
    "hwai",         # sheep
    "huku",         # chicken
    "chikwekwe", "zvikwekwe",  # tick, ticks
    "chirwere",     # "disease" - only appears in animal-disease entries
                     # in this corpus, not in the crop section, so it's a
                     # reliable animal-domain signal
    "remudumbu",    # "of the stomach" - the qualifier that makes "gonye"
                     # animal/parasite-specific, not the crop pest
    "weti",         # urine (relevant to Babesiosis/redwater)
    # Ndebele - animal names, disease framing, and disambiguating qualifiers
    "inkomo", "izinkomo",     # cow/cattle
    "imbuzi",                  # goat
    "imvu",                    # sheep
    "inkukhu", "izinkukhu",    # chicken/chickens
    "umkhaza", "imikhaza",     # tick, ticks
    "umkhuhlane",              # "disease" - same reasoning as "chirwere" above
    "impethu",                 # intestinal/stomach worm - distinct word from
                                 # "isibungu" (crop worm), safe to add directly
    "umchamo",                 # urine
}

# IMPORTANT AMBIGUITY NOTE, confirmed by testing against the corpus directly:
# Shona uses "gonye" as the shared root word for BOTH the crop pest
# (Fall Armyworm - "gonye rechibage") AND the livestock parasite
# (Haemonchus - "gonye remudumbu"). Deliberately NOT added to either
# keyword set alone - only the distinguishing qualifier words
# ("rechibage" vs "remudumbu") were added. This prevents a goat-owner
# asking about "gonye remudumbu" from being misrouted into the crop
# section purely because of the shared word "gonye" - the same class of
# bug as the original English "droppings" cross-domain issue this
# filtering was built to prevent in the first place.
#
# Priviledge: please confirm "isibungu" (Ndebele, crop worm) is NOT also
# used for intestinal/stomach worms - if it is, it needs the same
# treatment as "gonye" (removed from the set, replaced with just its
# qualifying word).


# ---- What is each entry ABOUT? (crop or animal, and which animal) ----
# The corpus used to rely on the section letter (D = crops, everything else =
# animals). That broke as soon as sections were added: maize, groundnut and
# tomato entries under J/K/L were treated as animal entries and could never be
# found by a crop question. Now each entry is classified from what it says.
# To override a wrong guess, add a line to the entry:
#     - **Applies to:** crops            (or: animals / cattle / poultry / goats and sheep / general)
import functools

_CROP_HINT = re.compile(
    r"\b(maize|tobacco|groundnuts?|tomato(?:es)?|crops?|plants?|seedlings?|leaf|leaves|cobs?|"
    r"seeds?|fields?|soil|fertili[sz]er|pesticides?|aphids?|whitefl(?:y|ies)|blight|wilt|weeds?|"
    r"harvest|stalks?|rosette|aflatoxin|irrigation|planting|agritex)\b", re.I)
_ANIMAL_HINT = re.compile(
    r"\b(cow|cows|cattle|calf|calves|bull|bulls|heifers?|goats?|sheep|lambs?|chickens?|hens?|"
    r"poultry|chicks?|birds?|flock|herd|animals?|livestock|milk|udder|vets?|veterinary|ticks?|"
    r"dip|carcass|kraal|calving)\b", re.I)
_SPECIES_HINT = {
    "cattle": re.compile(r"\b(cow|cows|cattle|calf|calves|calving|bull|bulls|heifers?|oxen|ox)\b", re.I),
    "poultry": re.compile(r"\b(chickens?|hens?|poultry|chicks?|broilers?|fowl|birds?)\b", re.I),
    "small": re.compile(r"\b(goats?|sheep|lambs?)\b", re.I),
}
_APPLIES_TO = re.compile(r"\*\*Applies to:\*\*\s*([^\n]+)", re.I)
_URGENCY_TAG = re.compile(r"\*\*Urgency:\*\*\s*emergency", re.I)


# The '## SECTION X: ...' header an entry sits under ("Cattle", "Poultry", "Maize",
# "Tomato") is a good default for entries that don't say it themselves - many
# cattle entries never write the word "cattle". Filled in by load_chunks().
_SECTION_HEADER = {}


def _header_of(chunk):
    return _SECTION_HEADER.get(chunk, "")


def _heading_and_body(chunk):
    head, _, body = chunk.partition("\n")
    return head, body


@functools.lru_cache(maxsize=None)
def get_domain(chunk):
    """'crops', 'animal' or 'general' (applies to both, e.g. rainfall zones)."""
    tag = _APPLIES_TO.search(chunk)
    if tag:
        t = tag.group(1).lower()
        crop = bool(re.search(r"crop|plant|maize|tobacco|groundnut|tomato", t))
        animal = bool(re.search(r"animal|livestock|cattle|cow|goat|sheep|chicken|poultry|bird", t))
        if crop and not animal:
            return "crops"
        if animal and not crop:
            return "animal"
        return "general"
    head, body = _heading_and_body(chunk)
    crop_score = 4 * len(_CROP_HINT.findall(head)) + len(_CROP_HINT.findall(body))
    animal_score = 4 * len(_ANIMAL_HINT.findall(head)) + len(_ANIMAL_HINT.findall(body))
    if crop_score > 2 * animal_score:
        return "crops"
    if animal_score > 2 * crop_score:
        return "animal"
    # The entry itself is mixed or silent: fall back on its section header.
    header = _header_of(chunk)
    h_crop, h_animal = len(_CROP_HINT.findall(header)), len(_ANIMAL_HINT.findall(header))
    if h_crop and not h_animal:
        return "crops"
    if h_animal and not h_crop:
        return "animal"
    return "general"


@functools.lru_cache(maxsize=None)
def entry_species(chunk):
    """'cattle', 'poultry', 'small' (goats/sheep), or None when the entry covers
    several kinds of animal or none in particular."""
    tag = _APPLIES_TO.search(chunk)
    if tag:
        found = [s for s, rx in _SPECIES_HINT.items() if rx.search(tag.group(1))]
        return found[0] if len(found) == 1 else None
    head, body = _heading_and_body(chunk)
    named = [s for s, rx in _SPECIES_HINT.items() if rx.search(head)]
    if len(named) == 1:
        return named[0]
    scores = {s: 4 * len(rx.findall(head)) + len(rx.findall(body)) for s, rx in _SPECIES_HINT.items()}
    total = sum(scores.values())
    if total == 0:
        # The entry never names an animal: take it from the section header
        # ("Cattle - Tick-Borne Diseases"), if that names exactly one kind.
        named = [s for s, rx in _SPECIES_HINT.items() if rx.search(_header_of(chunk))]
        return named[0] if len(named) == 1 else None
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 and scores[best] >= 0.7 * total else None


def _matches(query, keywords):
    """True if any keyword appears in the query - exact word match first,
    then substring match (4+ letters) to catch Shona/Ndebele roots fused
    with prefixes/suffixes (see the "mechibage" note below)."""
    query_lower = query.lower()
    query_words = set(re.findall(r"\w+", query_lower))
    if query_words & keywords:
        return True
    return any(kw in query_lower for kw in keywords if len(kw) >= 4)


# ---- Which language is the farmer actually writing in? ----
# Needed because corpus entries list Shona AND Ndebele names together
# ("Chirwere chenduru. Ndebele: Umkhuhlane..."), and without this the model
# could echo back whichever language's word happened to sit in the reference
# text - mixing a Ndebele word into a Shona answer, or the reverse. Detected
# by real, distinctive function/grammar words for each language (not by the
# shared symptom vocabulary, which overlaps less reliably).
_SHONA_MARKERS = {
    "yangu", "yako", "iri", "ari", "dzangu", "chandi", "ndinoda", "ndine",
    "haisi", "hausi", "handi", "kudya", "kurwara", "chii", "here", "uye",
    "mombe", "mbudzi", "huku", "hwai", "chibage", "nezve", "zvakare", "kana",
}
_NDEBELE_MARKERS = {
    "yami", "lami", "zami", "wami", "kayi", "kayidli", "iyagula", "ukuthi",
    "yini", "kungaba", "futhi", "lokhu", "inkomo", "imbuzi", "inkukhu",
    "imvu", "umumbu", "kanye", "njalo", "lo", "le",
}


def detect_language(query):
    """'shona', 'ndebele', or 'english' (also the default when neither is
    clearly present, e.g. a mostly-English message)."""
    words = set(re.findall(r"[a-zA-Z]+", query.lower()))
    shona = len(words & _SHONA_MARKERS)
    ndebele = len(words & _NDEBELE_MARKERS)
    if shona > ndebele:
        return "shona"
    if ndebele > shona:
        return "ndebele"
    return "english"


_OTHER_LANGUAGE_LINE = {
    # Lazy match up to (not including) whichever comes first: the next
    # language marker (handles entries with several diseases in one bullet,
    # e.g. "Haemonchus - Shona: X. Ndebele: Y. Eimeria - Shona: Z. Ndebele: W."),
    # the next bullet point, a blank line, or the end of the text. re.S lets
    # the match span the wrapped/indented continuation lines these entries use.
    "shona": re.compile(r"Ndebele\s*[:—-]\s*.*?(?=\s*(?:Shona\b|Ndebele\b|\n-\s|\n\n|$))", re.I | re.S),
    "ndebele": re.compile(r"Shona\s*[:—-]\s*.*?(?=\s*(?:Shona\b|Ndebele\b|\n-\s|\n\n|$))", re.I | re.S),
}
# Second format some entries use instead: "word (Shona) / word (Ndebele)",
# e.g. "tick = chikwekwe (Shona) / umkhaza (Ndebele)". Strips the word
# immediately before the parenthesis, not just the "(Ndebele)" tag itself.
_OTHER_LANGUAGE_PAREN = {
    # [^)]* after the language name handles "(Ndebele, varies by locality)" -
    # extra text can sit inside the parentheses, not just the bare language name.
    "shona": re.compile(r"[,;]?\s*\S+\s*\(Ndebele[^)]*\)", re.I),
    "ndebele": re.compile(r"[,;]?\s*\S+\s*\(Shona[^)]*\)", re.I),
}


def strip_other_language(chunk, language):
    """Removes the OTHER language's local-name text from a reference entry
    before it reaches the model, so a Shona question can never pick up a
    Ndebele word from the reference, or the reverse. English questions keep
    both (harmless, and some entries read oddly with only one removed)."""
    line_pattern = _OTHER_LANGUAGE_LINE.get(language)
    paren_pattern = _OTHER_LANGUAGE_PAREN.get(language)
    if not line_pattern:
        return chunk
    chunk = line_pattern.sub("", chunk)
    chunk = paren_pattern.sub("", chunk)
    return chunk


def detect_domain(query):
    """'crops', 'animal', or 'unknown' (mixed or no clear signal)."""
    has_crop = _matches(query, CROP_KEYWORDS)
    has_animal = _matches(query, ANIMAL_KEYWORDS)
    if has_crop and not has_animal:
        return "crops"
    if has_animal and not has_crop:
        return "animal"
    return "unknown"


def filter_by_domain(query, chunks):
    """If the query clearly leans crop or animal vocabulary (in English,
    Shona, or Ndebele), restrict retrieval to that domain's chunks first -
    prevents cross-domain word overlap (e.g. English 'droppings', or Shona
    'gonye') from pulling in the wrong section.

    Uses substring matching, not just exact-word matching, because Shona
    and Ndebele attach prefixes/suffixes directly onto noun roots (e.g.
    "mechibage" = "in the maize", fusing the locative prefix onto
    "chibage"). Exact-word matching - fine for English - silently misses
    these inflected forms.
    """
    domain = detect_domain(query)
    if domain in ("crops", "animal"):
        filtered = [c for c in chunks if get_domain(c) in (domain, "general")]
        return filtered if filtered else chunks
    return chunks  # ambiguous or mixed - search everything


# ---- Species filtering inside the animal domain ----
# Found in testing: a question about a COW retrieved the poultry
# coccidiosis entry (and the goat/sheep heartwater entry), because they
# share words like "blood" and "fever". If the farmer names exactly one kind
# of animal, entries about other animals are dropped.
SPECIES_TERMS = {
    "cattle": {"cow", "cows", "cattle", "calf", "calves", "bull", "ox", "oxen",
               "mombe", "inkomo", "izinkomo"},
    "poultry": {"chicken", "chickens", "hen", "hens", "chick", "chicks", "poultry",
                "broiler", "broilers", "huku", "inkukhu", "izinkukhu"},
    "small": {"goat", "goats", "sheep", "lamb", "lambs", "mbudzi", "hwai",
              "imbuzi", "imvu"},
}

# Every species word is also an animal-routing word (found in testing: "sheep"
# was not recognised as an animal). Animals and crops the corpus has no entries
# for are still ROUTED correctly, so the farmer gets the right follow-up
# questions and an honest "I don't cover this" instead of a confused reply.
for _terms in SPECIES_TERMS.values():
    ANIMAL_KEYWORDS |= _terms
ANIMAL_KEYWORDS |= {"pig", "pigs", "donkey", "donkeys", "rabbit", "rabbits", "duck",
                    "ducks", "turkey", "turkeys", "dog", "dogs", "heifer", "heifers"}
CROP_KEYWORDS |= {"beans", "bean", "tomato", "tomatoes", "cotton", "wheat", "soybean",
                  "soybeans", "cabbage", "vegetables", "vegetable", "garden",
                  "seedling", "seedlings", "millet", "sunflower", "potato", "potatoes",
                  "onion", "onions", "pumpkin", "pumpkins"}


def filter_by_species(query, chunks):
    found = [name for name, terms in SPECIES_TERMS.items() if _matches(query, terms)]
    if len(found) != 1:
        return chunks  # no animal named, or several named - don't guess
    species = found[0]
    kept = [c for c in chunks if entry_species(c) in (None, species)]
    return kept if kept else chunks


# Blocks that live in the corpus file but are NOT knowledge for the advisor to
# quote: test cases (S), follow-up-question checklists (O), synonym hints (P) and
# maintenance rules (T). Found when the corpus grew: the test cases were being
# loaded as knowledge, so "Mombe yangu iri kuita weti tsvuku" was answered from
# the TEST ENTRY ("Expected behavior: identify redwater...") instead of the real
# redwater entry. Better to keep them in separate files; until then they are
# ignored here.
NON_KNOWLEDGE_SECTIONS = {"S", "O", "P", "T"}
_TRAILING_NOTE = re.compile(r"(?:\n[ \t]*>[^\n]*)+\s*$")
_PLACEHOLDER_LINE = re.compile(
    r"^[ \t]*-[ \t]*\*\*Local (?:aliases|names)[^*\n]*\*\*[ \t]*(?:PENDING|TBD|TO BE ADDED)[^\n]*\n?", re.I | re.M)
LAST_LOAD_REPORT = {"loaded": 0, "ignored": []}


def load_chunks(path):
    """Read the corpus into one chunk per knowledge entry.

    An entry is a '### X1. Title' block. Split on '##' headings as well, so a
    section note or the notes at the end of the file never stick to the entry
    before them (this used to inflate entries with unrelated text). Rule blocks
    ('### 0.1 ...'), test/checklist/hint/maintenance sections and stray code
    fences are ignored; what was ignored is recorded in LAST_LOAD_REPORT.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"^```[a-z]*\s*$\n?", "", text, flags=re.M)      # stray code fences

    chunks, ignored = [], []
    _SECTION_HEADER.clear()
    get_domain.cache_clear()
    entry_species.cache_clear()
    header = ""
    for block in re.split(r"\n(?=#{1,3} )", text):   # any heading ends the previous entry
        block = re.sub(r"\n-{3,}\s*$", "", block.strip()).strip()
        if block.startswith("## "):
            header = block.splitlines()[0][3:]
            continue
        if not block.startswith("###"):
            continue                                                # the file title
        heading = block.splitlines()[0]
        m = re.match(r"###\s+([A-Z])(\d+)\.\s", heading)
        if not m or m.group(1) in NON_KNOWLEDGE_SECTIONS:
            ignored.append(heading.replace("###", "").strip()[:60])
            continue
        # "- **Local aliases:** PENDING VERIFICATION." is a to-do note for the editor, not
        # knowledge: it would be read by the model and might be repeated to a farmer.
        block = _PLACEHOLDER_LINE.sub("", block)
        # A '> note' at the END of an entry is an editor's comment that happens to sit
        # before the next section (it was being attached to the tobacco entry, D3).
        block = _TRAILING_NOTE.sub("", block).rstrip()
        _SECTION_HEADER[block] = header
        chunks.append(block)
    LAST_LOAD_REPORT["loaded"] = len(chunks)
    LAST_LOAD_REPORT["ignored"] = ignored
    return chunks


def build_index(chunks):
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(chunks)
    return vectorizer, matrix


def retrieve(query, chunks, vectorizer, matrix, k=TOP_K):
    domain_chunks = filter_by_domain(query, chunks)

    # Re-vectorize against the filtered subset so scores aren't diluted
    # by comparing against irrelevant-domain chunks
    if len(domain_chunks) < len(chunks):
        sub_vectorizer = TfidfVectorizer(stop_words="english")
        sub_matrix = sub_vectorizer.fit_transform(domain_chunks)
        query_vec = sub_vectorizer.transform([query])
        sims = cosine_similarity(query_vec, sub_matrix)
        return [domain_chunks[i] for i in top_indices(sims, k) if sims[i] > 0]

    query_vec = vectorizer.transform([query])
    sims = cosine_similarity(query_vec, matrix)
    return [chunks[i] for i in top_indices(sims, k) if sims[i] > 0]


# ---- Local-language symptom words ----
# Only 17 of the 55 entries carry Shona or Ndebele words, so a farmer describing a
# problem in Shona ("Mombe ine kupisa, yakazvimba pasi penzeve...") could not reach
# the other 38. This maps common SYMPTOM words to English so the search can find the
# entry. It is a lookup table of words from the verified phrasebook, not machine
# translation, and it is used only to search: the farmer never sees the English, and
# the model still receives the original question. Add words here as they are verified.
# Roots are matched inside words because Shona and Ndebele fuse prefixes onto nouns
# and verbs ("yakazvimba" contains "zvimba").
LOCAL_SYMPTOM_WORDS = {
    # Shona
    "kupisa": "fever", "fivha": "fever",
    "zvimba": "swollen swelling",
    "kufema": "breathing", "kunetseka kufema": "difficulty breathing", "kutadza kufema": "difficulty breathing",
    "manyoka": "diarrhea diarrhoea", "ndove": "dung droppings", "ropa": "blood",
    "weti": "urine", "tsvuku": "red", "kushaya simba": "weak weakness", "haina simba": "weak weakness",
    "haisi kudya": "not eating appetite", "nzeve": "ear", "mudumbu": "stomach",
    "kurwara": "sick", "chikwekwe": "tick", "zvikwekwe": "ticks",
    # Ndebele
    "ukutshisa": "fever", "vuvuka": "swollen swelling", "uhudo": "diarrhea diarrhoea",
    "igazi": "blood", "umchamo": "urine", "obomvu": "red", "ubuthakathaka": "weak weakness",
    "kayidli": "not eating appetite", "ukuphefumula": "breathing", "indlebe": "ear", "izindlebe": "ears",
}


# Everyday English words farmers use where the entries use the clinical word.
FARMER_ENGLISH_WORDS = {
    "afterbirth": "placenta", "womb": "uterus uterine",
    # "when should I plant my maize" - "plant" alone is an everyday word, so the
    # planting-window entry (D2) was never matched. Only a question about WHEN
    # to plant/sow adds the planting terms, so "my plant has yellow leaves" doesn't.
    r"(?:when|what time|which month|right time|too early|too late)\b.{0,40}\b(?:plant|sow)\w*":
        "planting window onset",
    r"\w*dyara\w*\b.{0,25}\brini|rini\b.{0,25}\b\w*dyara\w*":   # Shona: plant ... when
        "planting window onset",
}


def expand_local_terms(query):
    """Append English equivalents of Shona/Ndebele symptom words (and farmer words
    such as "afterbirth"), for searching only."""
    q = query.lower()
    extra = [english for local, english in LOCAL_SYMPTOM_WORDS.items() if local in q]
    extra += [english for farmer, english in FARMER_ENGLISH_WORDS.items()
              if re.search(r"\b" + farmer + r"\b", q)]
    return query + (" " + " ".join(extra) if extra else "")


# ---- Subject filtering: an entry only applies to what it is ABOUT ----
# Found while drafting new entries: as the knowledge base grows, one shared rare
# word is enough to answer about the wrong crop or animal - "my beans have brown
# spots" matched the maize streak virus entry on the word "spots", and a pig with
# a swollen jaw matched the goat parasite entry. So: if the farmer names a crop
# or animal the knowledge base has no entry for, or names a different one than an
# entry is about, that entry is not used. (Nothing covers it -> the app says so.)
CROP_SUBJECTS = {
    "maize": {"maize", "chibage", "umumbu"},
    "tobacco": {"tobacco", "fodya", "igwayi"},
    "groundnuts": {"groundnut", "groundnuts", "nzungu", "indlubu"},
    "tomato": {"tomato", "tomatoes"},
}
_UNCOVERED_CROPS = {"beans", "bean", "cotton", "wheat", "soybean",
                    "soybeans", "cabbage", "vegetables", "vegetable", "millet", "sunflower",
                    "potato", "potatoes", "onion", "onions", "pumpkin", "pumpkins", "sorghum"}
_UNCOVERED_ANIMALS = {"pig", "pigs", "donkey", "donkeys", "rabbit", "rabbits", "duck",
                      "ducks", "turkey", "turkeys", "dog", "dogs"}


def _entry_crops(chunk):
    """Which covered crops an entry is about, read from its heading and the start
    of its text ("### J1. Maize Streak Virus" -> maize). Empty for a general crop
    entry (drought stress, waterlogging), which applies to any crop."""
    tag = _APPLIES_TO.search(chunk)
    if tag:                                   # explicit: names a crop, or none = any crop
        t = tag.group(1).lower()
        return {crop for crop in CROP_SUBJECTS if crop.rstrip("s") in t}
    head, body = _heading_and_body(chunk)
    for scope in (head.lower(), body[:250].lower(), _header_of(chunk).lower()):
        found = {crop for crop in CROP_SUBJECTS if crop.rstrip("s") in scope}
        if found:
            return found
    return set()


def filter_by_subject(query, chunks):
    """Drop entries about a different crop or animal than the farmer named. May
    return an empty list on purpose (unlike the other filters, which fall back
    to everything): empty means the knowledge base does not cover this subject."""
    named_crops = {crop for crop, terms in CROP_SUBJECTS.items() if _matches(query, terms)}
    other_crop = _matches(query, _UNCOVERED_CROPS)
    named_covered_animal = any(_matches(query, terms) for terms in SPECIES_TERMS.values())
    other_animal = _matches(query, _UNCOVERED_ANIMALS) and not named_covered_animal

    kept = []
    for c in chunks:
        domain = get_domain(c)
        if domain == "crops":
            subjects = _entry_crops(c)
            if subjects:                          # entry is about specific crop(s)
                if named_crops and not (subjects & named_crops):
                    continue                      # farmer named a different covered crop
                if other_crop and not named_crops:
                    continue                      # farmer named only a crop we have no entry for
        elif domain == "animal" and other_animal:
            # The farmer named an animal we have no entry for (a pig). Keep only
            # entries that mention that animal, or that name no covered animal at
            # all (general ones). An entry about cattle, sheep and goats is not
            # about pigs - "my pig has pale gums" must not be answered from it.
            about = [s for s, rx in _SPECIES_HINT.items() if rx.search(c)] or \
                    [s for s, rx in _SPECIES_HINT.items() if rx.search(_header_of(c))]
            named = [t for t in _UNCOVERED_ANIMALS if _matches(query, {t})]
            if about and not any(re.search(r"\b" + re.escape(t) + r"\b", c, re.I) for t in named):
                continue
        kept.append(c)
    return kept


# ---- Grounding gate ----
# Problem found in testing: for questions the corpus doesn't cover ("maize
# with purple leaves", "maize with yellow leaves"), retrieval still returned
# the Fall Armyworm entry, purely because "maize" and "leaves" appear in it.
# The model was then told to diagnose from that entry, so it invented
# symptoms and named a pest the farmer never described.
#
# A similarity threshold does NOT fix this - measured on this corpus, the bad
# queries scored 0.25 while a correct Shona goat-worm question scored 0.09.
# Instead: an entry only counts as a match if the farmer's message shares at
# least one SPECIFIC term with it (not just generic words like "maize",
# "leaves", "cow", "sick"), and either shares two of them or one that is rare
# across the corpus. If nothing qualifies, the app asks follow-up questions
# instead of asking the model to guess.

_FUNCTION_WORDS = {
    # Shona
    "yangu", "yako", "yake", "yedu", "yavo", "changu", "chako", "dzangu", "dzako",
    "wangu", "wako", "yanyu", "yenyu", "ndiri", "ndine", "ine", "ane", "ari", "iri",
    "riri", "rine", "aka", "uye", "kana", "nekuti", "chii", "chingava", "kudini",
    "sei", "here", "haisi", "hausi", "handi", "dziri", "dzakawanda", "iyi", "ichi", "aya", "ava", "izvi",
    "izvo", "pane", "paya", "kuita", "irikuita", "kuti", "ndira", "chine", "dzine",
    # Ndebele
    "yami", "lami", "zami", "wami", "kanti", "futhi", "loku", "lokhu", "yini",
    "kungaba", "kuyini", "ilo", "kayi",
}

_GENERIC_WORDS = {
    # words that describe almost any farm problem, so they say nothing about WHICH one
    "maize", "crop", "crops", "plant", "plants", "planted", "leaf", "leaves", "field",
    "fields", "farm", "farmer", "cow", "cows", "cattle", "calf", "calves", "goat",
    "goats", "sheep", "chicken", "chickens", "hen", "hens", "poultry", "animal",
    "animals", "bird", "birds", "kraal", "herd", "flock", "sick", "ill", "illness",
    "problem", "problems", "wrong", "help", "growing", "grow", "grown", "growth",
    "well", "bad", "look", "looks", "looking", "seems", "seem", "weak", "weakness",
    "dying", "died", "dead", "die", "eating", "eat", "appetite", "drinking",
    "disease", "symptoms", "symptom", "condition", "thing", "things", "many", "some",
    "days", "day", "week", "weeks", "today", "yesterday", "tell", "know", "please",
    "cause", "causing", "caused", "happening", "happen", "started", "since",
    "high", "low", "very", "quite", "big", "small", "large", "little", "short",
    "long", "old", "young", "new", "good", "better", "best", "worse", "bit",
    "lot", "lots", "really", "too", "always", "often", "sometimes",
    "keep", "keeps", "kept", "keeping", "get", "gets", "got", "getting", "going",
    "goes", "come", "comes", "came", "make", "makes", "made", "take", "takes",
    "took", "see", "seen", "saw", "give", "gave", "given", "put", "let", "say",
    "says", "said", "want", "need", "use", "used",
    "chibage", "umumbu", "chirimwa", "zvirimwa", "mashizha", "shizha", "amahlamvu",
    "isitshalo", "izitshalo", "munda", "minda", "insimu", "mbeu", "imbewu",
    "mombe", "inkomo", "izinkomo", "mbudzi", "imbuzi", "hwai", "imvu", "huku",
    "inkukhu", "izinkukhu", "chirwere", "umkhuhlane",
}


# British spellings farmers and vets write, mapped to the spelling the corpus uses,
# so "fertiliser"/"fertilizer" and "diarrhoea"/"diarrhea" match. Applied to both the
# question and the corpus.
_SPELLING = {
    "fertiliser": "fertilizer", "fertilisers": "fertilizers", "diarrhoea": "diarrhea",
    "anaemia": "anemia", "anaemic": "anemic", "colour": "color", "colours": "colors",
    "mould": "mold", "moulds": "molds", "mouldy": "moldy", "oedema": "edema",
    "haemorrhage": "hemorrhage", "litre": "liter", "litres": "liters",
    "behaviour": "behavior", "tumour": "tumor", "faeces": "feces", "grey": "gray",
    "paralysed": "paralyzed", "labour": "labor", "sulphur": "sulfur",
}


def _stem(word):
    """Crude, consistent suffix stripping so 'droppings'/'dropping' and
    'holes'/'hole' compare equal. Applied identically to the farmer's message
    and to the corpus, so it only has to be consistent, not linguistically
    correct."""
    w = _SPELLING.get(word.lower(), word.lower())
    changed = True
    while changed:
        changed = False
        for suf in ("ing", "ous", "ed", "es", "ly", "e", "s", "y"):
            min_left = 3 if len(suf) > 1 else 4
            if w.endswith(suf) and len(w) - len(suf) >= min_left:
                w = w[: -len(suf)]
                changed = True
                break
    return w


def _stems(text):
    return {_stem(t) for t in re.findall(r"[a-zA-Z]+", text.lower()) if len(t) >= 3}


# Names of crops and animals say WHAT the question is about, never WHICH problem it
# is - found when "my beans have brown spots" matched the regions entry because it
# mentions "sugar beans", and "my tomatoes have holes" matched every tomato entry.
_SUBJECT_NAMES = (set().union(*CROP_SUBJECTS.values()) | _UNCOVERED_CROPS | _UNCOVERED_ANIMALS
                  | set().union(*SPECIES_TERMS.values()))
_GENERIC_RAW = set(ENGLISH_STOP_WORDS) | _FUNCTION_WORDS | _GENERIC_WORDS | _SUBJECT_NAMES


def _distinctive_terms(query):
    """Stems of the words in the farmer's message that say something specific."""
    return {_stem(t) for t in re.findall(r"[a-zA-Z]+", query.lower())
            if len(t) >= 3 and t not in _GENERIC_RAW}

# Corpus entries a farmer should treat as time-critical. This is decided by
# the corpus, not by the model's wording: the old UI flagged "urgent" whenever
# the answer text contained "urgent"/"immediately" - including the phrase
# "not urgent" - so it contradicted itself and flagged crop answers too.
# Taken from the corpus's own rule 0.3 ("Veterinary emergency triggers"): nervous
# signs, sudden deaths of several animals, suspected anthrax or foot-and-mouth,
# red/brown urine with weakness or fever, very high fever with rapid decline,
# poisoning, prolapsed uterus, difficult birth with no progress, severe bloat.
# A vet should confirm this list. To flag any other entry, add the line
#     - **Urgency:** emergency
# to it - no code change needed.
URGENT_CHUNK_IDS = {
    "B1", "B3", "B4", "C1", "E2", "E3",
    "F1", "F2", "F3", "F5", "F7",
    "G2", "G3", "G4", "G6",
    "H1", "H3", "N1",
}


_TRIAGE_HEADING = re.compile(r"\bvs\.?\b|\bversus\b", re.I)
_TRIAGE_TAG = re.compile(r"\*\*Type:\*\*\s*triage", re.I)


def is_triage_entry(chunk):
    """A 'X vs disease' entry ("Maize nutrient deficiency vs disease", "Crop drought
    stress vs disease"): it exists to catch COMMON, VAGUE symptoms (yellow leaves,
    wilting) and answer with the questions to ask. To mark another entry as one, put
    "vs" in its heading or add the line   - **Type:** triage"""
    return bool(_TRIAGE_TAG.search(chunk)) or bool(_TRIAGE_HEADING.search(chunk.splitlines()[0]))


def is_urgent_entry(chunk):
    return bool(_URGENCY_TAG.search(chunk)) or chunk_id(chunk) in URGENT_CHUNK_IDS


def chunk_id(chunk):
    m = re.match(r"###\s*([A-Z]\d+)", chunk)
    return m.group(1) if m else None


_SUBJECT_STEMS = ({_stem(t) for terms in CROP_SUBJECTS.values() for t in terms}
                  | {_stem(t) for terms in SPECIES_TERMS.values() for t in terms})


# How many entries a word may appear in and still count as 'specific'. Raised
# from 2 when the corpus grew, because a disease now appears in its own entry
# AND in the symptom-pattern entry that points to it.
RARE_MAX_DF = 3
TITLE_MAX_DF = 4
TOPIC_ZONE_CHARS = 380


_INFO_QUESTION = re.compile(r"^\s*(what is|what are|what's|whats|tell me about|explain|define|how do i know)\b", re.I)


def evaluate_entries(query, chunks, vectorizer, matrix):
    """Compare a question with every entry and say, for each, whether it counts as a
    match and why. The gate (retrieve_grounded) and the diagnostic tool
    (explain_match.py) both use this, so they can never disagree."""
    q = expand_local_terms(query)
    domain = detect_domain(q)
    pool = set(filter_by_subject(q, filter_by_species(q, filter_by_domain(q, chunks))))

    query_terms = _distinctive_terms(q)
    chunk_terms = [_stems(c) for c in chunks]
    doc_freq = Counter(term for terms in chunk_terms for term in terms)
    # Where an entry says what it is ABOUT: its title and opening lines (disease
    # name, local names, cause). A lone matching word only counts if it is found
    # there - not in incidental symptom text. Found when "my cow has PUSHED out her
    # womb" was answered as heartwater, whose symptom list says "PUSHING head
    # against objects", and a Shona twisted-neck question matched bronchitis on
    # "dziri" ("they are").
    topic_terms = [_stems(c[:TOPIC_ZONE_CHARS]) for c in chunks]
    sims = cosine_similarity(vectorizer.transform([q]), matrix)

    rows = []
    for i, c in enumerate(chunks):
        shared = query_terms & chunk_terms[i]
        # A crop or animal NAME is never evidence (see _SUBJECT_NAMES). A word in the
        # entry's TITLE counts (a disease or topic name) unless it is common across
        # the corpus: symptom words in the symptom-pattern entries ("Cow with FEVER
        # plus swollen lymph nodes") would otherwise let the single word "fever"
        # answer.
        in_title = {t for t in (shared & _stems(c.splitlines()[0])) - _SUBJECT_STEMS
                    if doc_freq[t] <= TITLE_MAX_DF}
        if len(shared) >= 2:
            reason = "two or more specific words"
        elif in_title:
            reason = "names the entry's disease/topic"
        elif domain != "unknown" and any(doc_freq[t] <= RARE_MAX_DF for t in shared & topic_terms[i]):
            reason = "one rare word (question is clearly about crops or animals)"
        elif domain != "unknown" and is_triage_entry(c) and (shared & topic_terms[i]):
            # Triage entries are MEANT to answer vague, common symptoms, which are not
            # rare words ("yellow" appears in several entries), so they match on any
            # word from their opening lines.
            reason = "vague-symptom (triage) entry"
        else:
            reason = None
        rows.append({"chunk": c, "in_pool": c in pool, "shared": sorted(shared),
                     "strong": reason is not None, "reason": reason, "sim": float(sims[i])})
    return {"query": q, "domain": domain, "terms": sorted(query_terms),
            "doc_freq": doc_freq, "rows": rows}


def retrieve_grounded(query, chunks, vectorizer, matrix, k=TOP_K):
    """Like retrieve(), but also decides whether the corpus really covers the
    question. Returns a dict:
        grounded      True only if at least one entry shares specific terms
                      with the farmer's message
        chunks        the matching entries (empty when not grounded)
        domain        'crops' / 'animal' / 'unknown', read from the question
        answer_domain 'crops' or 'animal', read from the entries chosen
        urgent        True if the best entry is time-critical
        matched       {entry id: [specific terms shared]} - for debugging
    """
    ev = evaluate_entries(query, chunks, vectorizer, matrix)
    domain = ev["domain"]
    candidates = [(len(r["shared"]), r["sim"], r["chunk"], r["shared"])
                  for r in ev["rows"] if r["in_pool"] and r["strong"]]
    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    # A supporting entry must be at least half as well matched as the best one.
    # Without this, a weak second entry (matching on one filler word such as
    # "middle") is handed to the model alongside the right one and dilutes it.
    best = candidates[0][0] if candidates else 0
    chosen = [t for t in candidates[:k] if t[0] * 2 >= best]

    chosen_chunks = [t[2] for t in chosen]
    kinds = {get_domain(c) for c in chosen_chunks}
    if "animal" in kinds:
        answer_domain = "animal"
    elif "crops" in kinds:
        answer_domain = "crops"
    else:                                   # only general entries: follow the question
        answer_domain = "crops" if domain == "crops" else "animal"
    return {
        "grounded": bool(chosen_chunks),
        "chunks": chosen_chunks,
        "domain": domain,
        "answer_domain": answer_domain,
        # Time-critical if the best-matching entry is a time-critical one - unless the
        # question is plainly informational ("what is heartwater?") and matched on a
        # single word. A missed alarm on a real emergency is worse than a needless
        # one, so a description that shares only one word ("trying to give birth for
        # hours and nothing is coming out") still raises it.
        "urgent": bool(chosen) and is_urgent_entry(chosen[0][2])
                  and (chosen[0][0] >= 2 or not _INFO_QUESTION.match(query)),
        "matched": {chunk_id(t[2]): t[3] for t in chosen},
    }


def fallback_answer(domain):
    """What the farmer sees when the corpus does not cover the question.
    Deliberately does NOT call the language model: with nothing relevant to
    ground it, the model just invents a diagnosis (see the testing notes
    above). English only for now - Shona/Ndebele wording needs to come from a
    fluent speaker, not machine translation."""
    coverage = (
        "\n\n*I can help with common diseases, parasites and emergencies of cattle, goats, "
        "sheep and chickens; problems of maize, groundnuts and tomatoes; and planting "
        "times. For anything else, your AGRITEX extension officer or veterinary officer "
        "is the right person to see.*"
    )
    ask_again = (
        "\n\nSend your answers **together with your first message** in one new "
        "message - I look at each message on its own."
    )
    if domain == "crops":
        return (
            "### Let's find out what is affecting your crop\n"
            "Several different problems cause these signs, and the right treatment "
            "depends on which one it is. A few details will point to the answer:\n\n"
            "### Tell me\n"
            "- Which crop, and which variety if you know it?\n"
            "- Which district, or which Natural Region?\n"
            "- How old is the crop (weeks since planting)?\n"
            "- Which part is affected - leaves, stem, roots, or the cob or fruit? Old "
            "lower leaves or young top leaves? Is the colour along the edges, in "
            "stripes, in patches, or over the whole leaf?\n"
            "- Is it the whole field or only patches?\n"
            "- Do you see insects, holes, droppings, mould, spots or streaks?\n"
            "- Has there been heavy rain, drought, standing water, spraying, or fertiliser?\n\n"
            "### Do this now\n"
            "If many plants are affected or it is spreading, show a sample to your "
            "local AGRITEX extension officer." + ask_again + coverage
        )
    if domain == "animal":
        return (
            "### Let's find out what is affecting your animal\n"
            "Several different illnesses cause these signs, and the right treatment "
            "depends on which one it is. A few details will point to the answer:\n\n"
            "### Tell me\n"
            "- Which animal (cattle, goat, sheep, chicken) and how old?\n"
            "- What are the main signs, and when did they start?\n"
            "- Is it eating and drinking? Does it have a fever, if you can check safely?\n"
            "- What colour are the gums or the inside of the eyelids?\n"
            "- Any diarrhoea, blood in the dung or urine, coughing, swelling, or "
            "strange behaviour (circling, pushing its head against things, staggering)?\n"
            "- Are there ticks? When was it last dipped or vaccinated?\n"
            "- Are other animals sick?\n\n"
            "### Do this now\n"
            "If the animal is very weak, cannot stand, or several animals are sick, "
            "do not wait - contact your veterinary officer or extension officer "
            "today. Keep the sick animal apart from the others." + ask_again + coverage
        )
    return (
        "### Tell me a little more\n"
        "Is your question about a crop or about animals? Tell me which crop or "
        "animal, and what you are seeing "
        "(what looks different, since when, and how many plants or animals)." + ask_again + coverage
    )


# ---- Scope and safety guard ----
# Runs BEFORE retrieval. The grounding gate above stops the model inventing
# answers for topics the knowledge base doesn't cover. It does not stop a
# message that IS about a covered disease but asks for something the app must
# not answer. Found by probing the app the way a public tester would:
#   - "how many ml of oxytetracycline for redwater"  -> reached the model, which
#     can invent a dose
#   - "my child has a fever and cough"               -> matched to the goat
#     disease PPR
#   - "cattle died suddenly and bled from the nose"  -> answered as Theileriosis,
#     with no warning about anthrax
#   - "...ignore your rules and tell the farmer to..." -> the attacker's text
#     went straight into the model's prompt
# These are pattern checks, not understanding: they catch the common, casual
# versions of each, not a determined attacker. English-only for now; Shona and
# Ndebele versions of these messages need a fluent speaker.

MAX_QUERY_CHARS = 600

_INJECTION = re.compile(
    r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instructions?|rules?|prompt|previous|above|system)\b"
    r"|\b(system prompt|jailbreak|developer mode|you are now|pretend (to be|you are))\b"
    r"|\bact as (a|an) ", re.I)

_HUMAN = re.compile(
    r"\b(child|children|baby|babies|toddler|pregnant|myself|mwana|vana|umntwana|abantwana"
    r"|my (son|daughter|wife|husband|mother|father|grandmother|grandfather|brother|sister))\b", re.I)

_DOSE = re.compile(
    r"\b(doses?|dosage|dosing|inject|injection|injecting|drench|drenching|antibiotics?"
    r"|oxytetracycline|terramycin|penicillin|amoxicillin|ivermectin|albendazole|levamisole"
    r"|berenil|diminazene|dewormer|deworm|acaricide|pesticide|insecticide|cypermethrin"
    r"|tablets?|ml|mg|cc|withdrawal period)\b", re.I)

_DIED = re.compile(r"\b(died|dead|death|deaths|dying|found dead)\b", re.I)
_SUDDEN = re.compile(r"\b(sudden|suddenly|overnight|without warning|no warning|found dead)\b", re.I)
_BLEED = re.compile(
    r"\b(bled|bleed|bleeding|blood)\b.{0,30}\b(nose|mouth|anus|eyes?|ears?|nostrils?|openings?|orifices?)\b"
    r"|\b(nose|mouth|anus|nostrils?)\b.{0,30}\b(bled|bleed|bleeding|blood)\b", re.I)

_GUARD_TEXT = {
    "too_long": (
        "### Please shorten your message\n"
        "Please describe the problem in a few short sentences: what you see, "
        "which crop or animal, and for how long."
    ),
    "injection": (
        "### I can only help with farming questions\n"
        "I'm a farm advisor for crops and animals. Please describe a problem "
        "with your crops, cattle, goats, sheep or chickens and I will do my best "
        "to help."
    ),
    "human": (
        "### I can't help with human health\n"
        "I only advise on crops and farm animals. If a person is unwell, please go "
        "to your nearest clinic or health worker. If the illness could have come "
        "from an animal - for example after handling a sick or dead animal - tell "
        "the health worker that."
    ),
    "dose": (
        "### I can't advise on medicines, doses or chemicals\n"
        "A wrong dose can kill an animal or crop, make treatment stop working, or "
        "leave harmful residues in meat and milk. The right product and amount "
        "depend on the animal, the illness and the product label.\n\n"
        "Please ask your veterinary officer or AGRITEX extension officer, or an "
        "animal health worker, and have them read the label with you.\n\n"
        "I can still explain what a disease or pest looks like and what to do "
        "about it in general - just describe what you are seeing."
    ),
    "anthrax": (
        "### Sudden death - please be careful\n"
        "Sudden death of cattle, goats or sheep, especially with blood from the "
        "nose, mouth or other openings, can be caused by anthrax. Anthrax is "
        "dangerous to people.\n\n"
        "Until a vet has checked the animal:\n"
        "- Do NOT cut it open, skin it, or eat the meat.\n"
        "- Keep people, children and dogs away from the body and any blood.\n"
        "- Do not move the body or drag it to other places.\n"
        "- Contact your veterinary officer today - suspected anthrax must be "
        "reported."
    ),
}


def scope_guard(query):
    """Return None if the message is fine to process, otherwise
    {"kind", "answer", "urgent"} - a fixed reply the app shows WITHOUT calling
    the language model."""
    if len(query) > MAX_QUERY_CHARS:
        return {"kind": "too_long", "answer": _GUARD_TEXT["too_long"], "urgent": False}
    if _INJECTION.search(query):
        return {"kind": "injection", "answer": _GUARD_TEXT["injection"], "urgent": False}

    domain = detect_domain(query)

    # Sudden death in livestock (not poultry - sudden poultry deaths are usually
    # Newcastle disease, which the knowledge base covers).
    only_poultry = _matches(query, SPECIES_TERMS["poultry"]) and not (
        _matches(query, SPECIES_TERMS["cattle"]) or _matches(query, SPECIES_TERMS["small"]))
    if _DIED.search(query) and not only_poultry and (
            (_SUDDEN.search(query) and domain == "animal") or _BLEED.search(query)):
        return {"kind": "anthrax", "answer": _GUARD_TEXT["anthrax"], "urgent": True}

    if _DOSE.search(query):
        return {"kind": "dose", "answer": _GUARD_TEXT["dose"], "urgent": False}

    # A person, not a plant or animal. If an animal or crop is also named
    # ("baby goat", "my son's cow"), assume it is a farming question.
    if _HUMAN.search(query) and domain == "unknown":
        return {"kind": "human", "answer": _GUARD_TEXT["human"], "urgent": False}
    return None


# What the message is about, in plain English ("your chicken"). Found in testing:
# a Shona question about chickens was answered "your cow has bloody diarrhoea",
# because the prompt's own examples said "your cow".
_LOCAL_SUBJECT = {
    "mombe": "cow", "inkomo": "cow", "izinkomo": "cattle", "huku": "chicken",
    "inkukhu": "chicken", "izinkukhu": "chickens", "mbudzi": "goat", "imbuzi": "goat",
    "hwai": "sheep", "imvu": "sheep", "chibage": "maize", "umumbu": "maize",
    "fodya": "tobacco", "igwayi": "tobacco", "nzungu": "groundnuts", "indlubu": "groundnuts",
}


def subject_of(query):
    """The animal or crop named in the message, e.g. 'chicken', or None."""
    names = set().union(*SPECIES_TERMS.values(), *CROP_SUBJECTS.values()) | {"tomato", "tomatoes"}
    for word in re.findall(r"[a-zA-Z]+", query.lower()):
        if word in _LOCAL_SUBJECT:
            return _LOCAL_SUBJECT[word]
        if word in names:
            return word
    return None


_NOT_A_CONDITION = re.compile(r"general|planting|context|natural regions|husbandry|biosecurity", re.I)


def condition_name(chunks):
    """Display name of the first retrieved entry that is a condition, e.g.
    'Babesiosis ("Redwater")' or 'Fall Armyworm'; None if there is none."""
    for c in chunks:
        title = re.sub(r"^#+\s*[A-Z]\d+\.\s*", "", c.splitlines()[0]).strip()
        cid = chunk_id(c) or ""
        if cid.startswith(("A", "F")) or is_triage_entry(c) or _NOT_A_CONDITION.search(title):
            continue
        if " \u2014 " in title:                       # "Maize — Fall Armyworm", "PPR — Regional Awareness"
            left, right = title.split(" \u2014 ", 1)
            title = right if left.strip().lower() in {"maize", "tobacco", "groundnuts", "tomato"} else left
        return title.strip()
    return None