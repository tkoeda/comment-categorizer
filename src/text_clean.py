import unicodedata

from fugashi import Tagger

tagger = Tagger()


def normalize_text(text):
    """
    Normalize the text using Unicode normalization (e.g., NFKC).
    This can convert full-width characters to half-width and perform other standardizations.
    """
    return unicodedata.normalize("NFKC", text)


def clean_japanese_text(text):
    """
    Tokenizes Japanese text and keeps only tokens that are likely useful for classification.
    In this example, we keep nouns, adjectives, and verbs.
    """
    normalized = normalize_text(text)
    tokens = tagger(normalized)
    allowed_pos = {"名詞", "形容詞", "動詞"}
    filtered_tokens = [word.surface for word in tokens if word.feature.pos1 in allowed_pos]
    return " ".join(filtered_tokens)
