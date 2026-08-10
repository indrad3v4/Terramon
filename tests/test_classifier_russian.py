"""Cyrillic (Russian) tokenization + classification regression tests.

Measured prod bug (2026-08-10): the classifier tokenizer used
``re.findall(r"[a-z']+", text)``, which DROPS ALL CYRILLIC. A Russian thought
like 'Я хочу защитить слабых, встать между опасностью и невинными...' produced
empty token lists and all-0.0 scores, so bayes_forward stayed at the uniform
prior (~0.083) and a Russian player needed ~12 summons of the SAME archetype to
unlock the mint gate, while an English player reached it in 1-5 summons. The
TMA audience is Russian-speaking (UI strings are Russian), so this structurally
capped real-world MintRate.

Fix: the tokenizer regex now also captures Cyrillic (``[a-zа-яё']+``), each of
the 12 Jungian archetypes gained 3 Russian example phrases (bright + shadow
essence), and a curated Russian stopword subset was added for TF-IDF hygiene.
These tests pin the regression: Russian thoughts must tokenize, score, and
reach the mint gate within a handful of summons.
"""

import re

import pytest

from terramon.adapters.embedding_classifier import EmbeddingClassifier, _tokens
from terramon.adapters.text_preprocessing import is_stop_word
from terramon.application.bayes_router import (
    _ARCHETYPE_NAMES,
    bayes_forward,
    should_gate_payment,
    update_belief,
)

RU_THOUGHT = (
    "я хочу защитить слабых и быть храбрым, "
    "встать между опасностью и невинными"
)
EN_THOUGHT = (
    "Courage! I will stand between danger and the innocent, shield the weak."
)

# The exact English unigrams extracted by the tokenizer — must not drift now
# that the regex also accepts Cyrillic (English tokens are byte-identical).
EXPECTED_EN_UNIGRAMS = [
    "courage", "i", "will", "stand", "between", "danger",
    "and", "the", "innocent", "shield", "the", "weak",
]

CYRILLIC_RE = re.compile(r"[а-яё]")


def _unigrams(text: str) -> list[str]:
    return [t for t in _tokens(text) if "_" not in t]


def test_russian_thought_produces_non_empty_tokens():
    """(a) A Cyrillic thought must tokenize into real content tokens."""
    toks = _tokens(RU_THOUGHT)
    assert toks, "Russian thought produced empty token list"
    unigrams = _unigrams(RU_THOUGHT)
    # The heroism content words must survive tokenization + stopword removal
    # (these are not Russian stopwords).
    for word in ("храбрым", "опасностью", "невинными", "слабых"):
        assert word in unigrams, f"missing content token: {word}"


def test_russian_heroism_thought_scores_hero():
    """(b) Russian heroism thought: non-zero scores, Hero in top-3 (and #1)."""
    clf = EmbeddingClassifier()
    s = clf.scores(RU_THOUGHT)
    assert max(s.values()) > 0.0, "all scores zero for Russian thought"
    top3 = sorted(s.items(), key=lambda kv: -kv[1])[:3]
    assert "Hero" in {name for name, _ in top3}, f"Hero not in top-3: {top3}"
    # Direct cosine path: Hero is the confident winner (>= MIN_CONFIDENCE),
    # no NB fallback, no defaulting to Innocent.
    assert clf.classify(RU_THOUGHT) == "Hero"


def test_russian_player_reaches_mint_gate_within_six_summons():
    """(c) Bayesian mint gate: a Russian player mints within <=6 summons.

    prior=[1.0]*12 (Dirichlet uniform), then bayes_forward + update_belief per
    summon. Pre-fix this took ~12 summons; post-fix it must be <=6.
    """
    prior = [1.0] * len(_ARCHETYPE_NAMES)
    for summon in range(1, 7):
        winner, posterior, _ = bayes_forward(RU_THOUGHT, prior)
        if should_gate_payment(posterior, 0.5):
            return  # gate opened within 6 summons
        prior = update_belief(prior, winner)
    pytest.fail("Russian player did not reach the mint gate within 6 summons")


def test_english_regression_tokens_and_scores_unchanged():
    """(d) English pipeline must not regress with the Cyrillic changes.

    - Tokens: identical English word list (regex is a superset, no drift).
    - Scores: still non-zero; Hero cosine exactly 0.0 both before and after
      (the EN thought shares no hashed buckets with any Hero example — the
      regression guarantee is that this value does not move).
    - Mint path: English still unlocks within 6 summons (prod: 1-5).
    """
    clf = EmbeddingClassifier()
    assert _unigrams(EN_THOUGHT) == EXPECTED_EN_UNIGRAMS, (
        "English tokenization changed after adding Cyrillic support"
    )
    s = clf.scores(EN_THOUGHT)
    assert max(s.values()) > 0.0, "English thought lost all scores"
    # Hero cosine: byte-identical to the pre-Cyrillic baseline (0.0).
    assert s["Hero"] == 0.0, "English Hero score drifted from baseline"

    prior = [1.0] * len(_ARCHETYPE_NAMES)
    for summon in range(1, 7):
        winner, posterior, _ = bayes_forward(EN_THOUGHT, prior)
        if should_gate_payment(posterior, 0.5):
            return
        prior = update_belief(prior, winner)
    pytest.fail("English thought no longer reaches the mint gate within 6 summons")


def test_every_archetype_has_russian_examples():
    """Rubric: all 12 archetypes carry >=3 Russian example phrases."""
    clf = EmbeddingClassifier()
    assert len(clf.ARCHETYPES) == 12
    for name, phrases in clf.ARCHETYPES.items():
        ru = [p for p in phrases if CYRILLIC_RE.search(p)]
        assert len(ru) >= 3, f"{name} has only {len(ru)} Russian phrases"


def test_russian_stopwords_are_filtered_but_content_words_kept():
    """Russian function words land in the stopword set; content words do not."""
    for w in ("и", "в", "не", "на", "я", "что", "с", "по", "для", "между",
              "будет", "чтобы", "когда", "потому", "этот"):
        assert is_stop_word(w), f"expected Russian stopword: {w}"
    # English stopword behavior is untouched
    assert is_stop_word("the") and is_stop_word("between")
    # Heroism content words must NOT be treated as stopwords
    for w in ("храбрым", "опасностью", "невинными", "слабых", "отвага"):
        assert not is_stop_word(w), f"content word wrongly stopworded: {w}"
