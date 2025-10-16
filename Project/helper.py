import re
from itertools import islice



URL_RE = re.compile(r"http\S+|www\S+|https\S+")
EMAIL_RE = re.compile(r"\S+@\S+")
HTML_RE = re.compile(r"<.*?>")
EMOJI_RE = re.compile(r"[^\x00-\x7F]+")
MULTISPACE_RE = re.compile(r"\s+")

STOPWORDS = set([
    # Articles / Determiners
    "a", "an", "the", "this", "that", "these", "those",

    # Conjunctions
    "and", "or", "but", "so", "because", "as", "if", "while", "though", "although",

    # Prepositions
    "in", "on", "at", "to", "from", "for", "of", "with", "by", "about", "against",
    "between", "into", "through", "during", "before", "after", "above", "below",
    "under", "over", "around", "near",

    # Pronouns
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",

    # Auxiliary & linking verbs
    "am", "is", "are", "was", "were", "be", "been", "being", "do", "does", "did",
    "doing", "have", "has", "had", "having", "can", "could", "shall", "should",
    "will", "would", "may", "might", "must",

    # Question / filler words
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",

    # Others (common short fillers)
    "there", "then", "than", "too", "very", "just", "not", "no", "nor", "only",
    "own", "same", "such", "s", "t", "re", "ll", "d", "m", "ve"
])


def clean_text(text):
    text = URL_RE.sub(" ", str(text))
    text = EMAIL_RE.sub(" ", text)
    text = HTML_RE.sub(" ", text)
    text = EMOJI_RE.sub(" ", text)
    text = MULTISPACE_RE.sub(" ", text)
    return text.strip()


def important_words_from_texts(texts, max_words=200):

    results = []

    for text in texts:
            words = [w.lower() for w in re.findall(r"\w+", clean_text(text))
                     if w.lower() not in STOPWORDS and len(w) > 2]
            seen, out = set(), []
            for w in words:
                if w not in seen:
                    out.append(w)
                    seen.add(w)
                if len(out) >= max_words:
                    break
            results.append(" ".join(out))
        

    return results


def generate_ngrams(words, n=1, append_label=None, limit=200):
    if not words:
        return []
    res, L = [], len(words)
    for i in range(L - n + 1):
        gram = " ".join(words[i:i+n])
        if append_label:
            res.append(f"{gram} {append_label}")
        else:
            res.append(gram)
    return list(islice(res, limit))






def generate_podcast_strings_for_keywordplanner(one_word, two_word, red_one_word, red_two_word):
    # Filter valid words
    valid_one_word = [w for w in one_word if w not in red_one_word]
    valid_two_word = [w for w in two_word if w not in red_two_word]

    # Build podcast variations
    def make_phrases(words):
        result = []
        for w in words:
            result.append(f"{w} podcast")
            result.append(f"{w} podcasts")
        return ", ".join(result)

    one_word_text = make_phrases(valid_one_word)
    two_word_text = make_phrases(valid_two_word)

    return one_word_text, two_word_text

