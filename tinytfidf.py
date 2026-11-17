"""Small TF-IDF search, in plain Python, so Murimi Fara needs no scikit-learn,
SciPy or NumPy (together they added well over 100 MB to the app).

It reproduces scikit-learn's TfidfVectorizer(stop_words="english") defaults:
lower-case, words of 2+ letters, English stop words removed, raw term counts,
smoothed IDF  ln((1 + n) / (1 + df)) + 1, and L2-normalised vectors. Cosine
similarity is then a plain dot product. test_tinytfidf.py checks it against
scikit-learn when scikit-learn happens to be installed.
"""
import math
import re
from collections import Counter

TOKEN = re.compile(r"(?u)\b\w\w+\b")

# scikit-learn's English stop-word list (BSD licence), copied so it no longer
# has to be installed.
ENGLISH_STOP_WORDS = frozenset((
    "a", "about", "above", "across", "after", "afterwards", "again", "against", "all",
    "almost", "alone", "along", "already", "also", "although", "always", "am", "among",
    "amongst", "amoungst", "amount", "an", "and", "another", "any", "anyhow", "anyone",
    "anything", "anyway", "anywhere", "are", "around", "as", "at", "back", "be",
    "became", "because", "become", "becomes", "becoming", "been", "before",
    "beforehand", "behind", "being", "below", "beside", "besides", "between", "beyond",
    "bill", "both", "bottom", "but", "by", "call", "can", "cannot", "cant", "co", "con",
    "could", "couldnt", "cry", "de", "describe", "detail", "do", "done", "down", "due",
    "during", "each", "eg", "eight", "either", "eleven", "else", "elsewhere", "empty",
    "enough", "etc", "even", "ever", "every", "everyone", "everything", "everywhere",
    "except", "few", "fifteen", "fifty", "fill", "find", "fire", "first", "five", "for",
    "former", "formerly", "forty", "found", "four", "from", "front", "full", "further",
    "get", "give", "go", "had", "has", "hasnt", "have", "he", "hence", "her", "here",
    "hereafter", "hereby", "herein", "hereupon", "hers", "herself", "him", "himself",
    "his", "how", "however", "hundred", "i", "ie", "if", "in", "inc", "indeed",
    "interest", "into", "is", "it", "its", "itself", "keep", "last", "latter",
    "latterly", "least", "less", "ltd", "made", "many", "may", "me", "meanwhile",
    "might", "mill", "mine", "more", "moreover", "most", "mostly", "move", "much",
    "must", "my", "myself", "name", "namely", "neither", "never", "nevertheless",
    "next", "nine", "no", "nobody", "none", "noone", "nor", "not", "nothing", "now",
    "nowhere", "of", "off", "often", "on", "once", "one", "only", "onto", "or", "other",
    "others", "otherwise", "our", "ours", "ourselves", "out", "over", "own", "part",
    "per", "perhaps", "please", "put", "rather", "re", "same", "see", "seem", "seemed",
    "seeming", "seems", "serious", "several", "she", "should", "show", "side", "since",
    "sincere", "six", "sixty", "so", "some", "somehow", "someone", "something",
    "sometime", "sometimes", "somewhere", "still", "such", "system", "take", "ten",
    "than", "that", "the", "their", "them", "themselves", "then", "thence", "there",
    "thereafter", "thereby", "therefore", "therein", "thereupon", "these", "they",
    "thick", "thin", "third", "this", "those", "though", "three", "through",
    "throughout", "thru", "thus", "to", "together", "too", "top", "toward", "towards",
    "twelve", "twenty", "two", "un", "under", "until", "up", "upon", "us", "very",
    "via", "was", "we", "well", "were", "what", "whatever", "when", "whence",
    "whenever", "where", "whereafter", "whereas", "whereby", "wherein", "whereupon",
    "wherever", "whether", "which", "while", "whither", "who", "whoever", "whole",
    "whom", "whose", "why", "will", "with", "within", "without", "would", "yet", "you",
    "your", "yours", "yourself", "yourselves",
))


def tokens(text, stop_words=ENGLISH_STOP_WORDS):
    return [t for t in TOKEN.findall(text.lower()) if t not in stop_words]


def _normalise(counts):
    norm = math.sqrt(sum(v * v for v in counts.values()))
    return {t: v / norm for t, v in counts.items()} if norm else {}


class TfidfVectorizer:
    """Only what Murimi Fara uses: fit_transform(docs) and transform(docs).
    A "matrix" is a list of {term: weight} dicts, one per document."""

    def __init__(self, stop_words="english"):
        self.stop_words = ENGLISH_STOP_WORDS if stop_words == "english" else frozenset(stop_words or ())
        self.idf_ = {}

    def fit(self, docs):
        token_lists = [tokens(d, self.stop_words) for d in docs]
        n = len(token_lists)
        df = Counter(t for toks in token_lists for t in set(toks))
        self.idf_ = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
        return token_lists

    def _vector(self, toks):
        counts = Counter(t for t in toks if t in self.idf_)
        return _normalise({t: c * self.idf_[t] for t, c in counts.items()})

    def fit_transform(self, docs):
        return [self._vector(toks) for toks in self.fit(docs)]

    def transform(self, docs):
        return [self._vector(tokens(d, self.stop_words)) for d in docs]


def cosine_similarity(query_matrix, matrix):
    """Similarity of the FIRST query vector with every row: a list of floats.
    (scikit-learn returns a 2-D array; Murimi Fara always flattened it.)"""
    q = query_matrix[0]
    return [sum(w * row.get(t, 0.0) for t, w in q.items()) for row in matrix]


def top_indices(scores, k):
    """Indices of the k highest scores, highest first."""
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
