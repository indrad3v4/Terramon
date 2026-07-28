"""Text preprocessing pipeline for Terramon — NFKC, URL stripping, repeated char
normalization, emoji stripping, and stop word filtering.

Phase 5 (NLP Foundations) — Building a robust text preprocessor before
tokenization. Designed to be shared between the embedding classifier (which
needs clean, stripped input) and the LLM behavior module (which keeps emoji
and original casing for creative generation).

Pure stdlib (unicodedata, re). No external deps.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Stop words for TF-IDF filtering
# ---------------------------------------------------------------------------
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "it", "to", "and", "or", "in", "on",
    "at", "for", "of", "by", "with", "from", "as", "be", "are", "was",
    "were", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "can", "could", "shall", "should", "may", "might",
    "i", "me", "my", "myself", "we", "us", "our", "you", "your",
    "he", "she", "him", "his", "her", "they", "them", "their",
    "this", "that", "these", "those", "some", "any", "no", "not",
    "just", "so", "if", "then", "than", "too", "very", "really",
    "am", "been", "being", "has", "had", "have", "do", "does", "did",
    "about", "up", "out", "off", "over", "after", "before", "between",
    "through", "during", "because", "into", "onto", "upon",
})

_MAX_TOKEN_LENGTH = 25

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_URL_RE = re.compile(r"https?://\S+|www\.\S+")

_REPEATED_CHAR_RE = re.compile(r"(.)\1{3,}")  # 4+ repeats → 2

_EMOJI_RE: re.Pattern[str] = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
    "\U0001F680-\U0001F6FF"  # Transport and Map
    "\U0001F1E0-\U0001F1FF"  # Regional Indicator Symbols
    "\U00000270-\U0000027BF"  # Dingbats
    "\U0000FE00-\U0000FE0F"  # Variation Selectors
    "\U000024C2-\U0000F251"  # Enclosed / Supplemental
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Symbols Extended-A
    "\U00002600-\U000026FF"  # Misc symbols
    "\U00002700-\U000027BF"  # Dingbats
    "\U0000200D"            # Zero-width joiner
    "\U0000200C"            # Zero-width non-joiner
    "]",
)

# ---------------------------------------------------------------------------
# Individual pipeline stages
# ---------------------------------------------------------------------------


def normalize_unicode(text: str) -> str:
    """NFKC normalization — decomposes then composes compatible characters.

    Handles:
      - Fullwidth/halfwidth forms (Ａ -> A)
      - Ligatures (ﬁ -> fi)
      - Composites (é decomposed to e + accent then recomposed)
    """
    return unicodedata.normalize("NFKC", text)


def strip_urls(text: str) -> str:
    """Remove http/https URLs and bare www. links."""
    return _URL_RE.sub("", text)


def normalize_repeated_chars(text: str) -> str:
    """Normalize 4+ repeated characters down to 2.

    'hellooo' stays 'hellooo' (3 'o' is fine, but 'helloooo' -> 'helloo').
    'nooooooo' -> 'nooo'.
    This reduces exagerrated spelling without destroying valid doubles like
    'll' in 'hello'.
    """
    return _REPEATED_CHAR_RE.sub(r"\1\1", text)


def strip_emoji(text: str) -> str:
    """Remove emoji and variation-selector characters."""
    return _EMOJI_RE.sub("", text)


# ---------------------------------------------------------------------------
# Composed pipelines
# ---------------------------------------------------------------------------


def preprocess_for_classifier(text: str) -> str:
    """Full preprocessing pipeline for classifier input.

    Steps:
      1. Unicode NFKC normalize
      2. Strip URLs
      3. Normalize repeated chars (4+ -> 2)
      4. Strip emoji
      5. Lowercase
    """
    text = normalize_unicode(text)
    text = strip_urls(text)
    text = normalize_repeated_chars(text)
    text = strip_emoji(text)
    text = text.lower()
    return text


def preprocess_for_llm(text: str) -> str:
    """Lighter preprocessing for LLM behavior module (keeps emoji, case).

    Steps:
      1. Unicode NFKC normalize
      2. Strip URLs (URLs don't add creative value)
      3. Normalize repeated chars
    """
    text = normalize_unicode(text)
    text = strip_urls(text)
    text = normalize_repeated_chars(text)
    return text


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def is_stop_word(word: str) -> bool:
    """Check if *word* is a stop word (case-sensitive, expects lowercase)."""
    return word in _STOP_WORDS


def is_valid_token(word: str) -> bool:
    """Check if *word* passes length and content filters.

    A valid token:
      - Has length <= _MAX_TOKEN_LENGTH
      - Is not empty
      - Contains at least one letter
    """
    if not word:
        return False
    if len(word) > _MAX_TOKEN_LENGTH:
        return False
    return any(c.isalpha() for c in word)
