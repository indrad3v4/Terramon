"""Embedding-lite classifier — a real vector-space model, no API, no deps.

Build-via-learn: Phase 5/10 (NLP / LLMs) of the course, scaled down honestly.
This is a *bi-encoder in miniature*:

  1. ENCODE text -> a sparse term-frequency-inverse-document-frequency vector
     in a hashed feature space (the "hashing trick": token -> hash % DIM, so
     vocab is unbounded but the vector is fixed-width). Word unigrams +
     bigrams + trigrams capture local context. IDF weighting makes rare /
     discriminative tokens more important.
  2. NORMALIZE (L2) so length doesn't bias similarity.
  3. Each ARCHETYPE has a prototype = the L2-normalized mean (centroid) of its
     example phrases' vectors — exactly how a nearest-centroid / prototype
     classifier works.
  4. CLASSIFY = argmax cosine(query, prototype). Cosine of L2-normed vectors
     is just their dot product.
  5. LOW-CONFIDENCE FALLBACK: if cosine similarity is below MIN_CONFIDENCE for
     ALL archetypes, a simple Naive Bayes classifier (per-word likelihood model
     with Laplace smoothing) is used as second pass before defaulting to
     Innocent. This catches inputs that are semantically distant from all
     centroids but lexically similar to one archetype.
  6. KNN SCORING: the scores() method computes average cosine to the TOP-K
     nearest prototype examples per archetype, giving a smoother score
     distribution than single-centroid comparison.

Phase 5 enhancements (NLP Foundations):
  - Better tokenization: split hyphenated compound words, max token length
    filtering, punctuation-aware splitting, stop word filtering for TF-IDF.
  - TF-IDF++: smooth IDF (add 1 to avoid zero weights), sublinear TF scaling
    (1 + log(tf) reduces the impact of very frequent terms), and L2-normalized
    TF-IDF vectors.
  - BPE subword tokenizer available as a separate module for rare-word and
    misspelling robustness.

Pure stdlib (math, hashlib) to honor the repo's stdlib-first rule. Deterministic:
hashing uses blake2b with a fixed key, not Python's salted hash().
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict

from terramon.adapters.text_preprocessing import (
    is_stop_word,
    is_valid_token,
    preprocess_for_classifier,
)
from terramon.domain.insight import GeoContext
from terramon.ports.classifier_port import ClassifierPort

DIM = 512  # hashed feature space width
TOP_K = 3  # default K for KNN-style scoring


def _tokens(text: str, remove_stop_words: bool = False) -> list[str]:
    """Tokenize *text* into unigrams + adjacent bigrams + trigrams.

    Improvements over Phase 2 (Phase 5 NLP Foundations):
      - Uses preprocess_for_classifier() for NFKC, URL stripping, emoji removal,
        repeated char normalization, and lowercasing.
      - Splits hyphenated compound words (e.g. 'well-known' -> 'well', 'known').
      - Max token length filtering (tokens > 25 chars are dropped).
      - Optional stop word removal (used for TF-IDF weight computation).

    When *remove_stop_words* is True, common stop words are filtered out
    before generating n-grams. This is used during TF-IDF encoding so that
    high-frequency stop words don't distort the vector space. The NB fallback
    keeps all tokens for maximum evidence.
    """
    text = preprocess_for_classifier(text)
    # Split compound words joined by hyphens, em-dashes, or slashes
    text = text.replace("-", " ").replace("—", " ").replace("/", " ").replace("'", " ' ")
    words = re.findall(r"[a-z']+", text)

    # Filter tokens: max length, stop word removal
    filtered: list[str] = []
    for w in words:
        if not is_valid_token(w):
            continue
        if remove_stop_words and is_stop_word(w):
            continue
        filtered.append(w)

    grams: list[str] = list(filtered)
    grams += [f"{a}_{b}" for a, b in zip(filtered, filtered[1:])]
    grams += [f"{a}_{b}_{c}" for a, b, c in zip(filtered, filtered[1:], filtered[2:])]
    return grams


def _hash(token: str) -> int:
    """Deterministic token -> bucket in [0, DIM). blake2b avoids hash() salting."""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % DIM


def _encode(text: str,
            idf: dict[int, float] | None = None,
            geo: GeoContext | None = None) -> dict[int, float]:
    """Text -> L2-normalized sparse TF-IDF vector (dict bucket->weight).

    When *idf* is provided, tokens are encoded with sublinear TF scaling
    (1 + log(tf)) × smooth IDF (log(N/df) + 1). Stop words are removed
    during TF-IDF encoding to reduce noise. Without *idf*, behaves as plain
    TF with all tokens (backward-compatible for non-TF-IDF encoding).

    When *geo* is provided and non-zero (lat != 0 or lon != 0), geo-derived
    features are encoded as additional dimensions in the same hashed space:
    climate zone, continent, urban/rural flag, and place_name tokens. These
    are added to the vector BEFORE L2 normalization, so they shift the
    direction. When no geo is available (geo=None or lat=0,lon=0), the
    encoding is unchanged (backward compatible).

    Phase 5 enhancements (TF-IDF++):
      - Sublinear TF: 1 + log(raw_tf) reduces the impact of very frequent terms.
      - Smooth IDF: log(N / df) + 1 avoids zero IDF for tokens in every document.
      - L2 normalization (cosine normalization).
    """
    tokens = _tokens(text, remove_stop_words=idf is not None)

    if idf:
        # Phase 5 TF-IDF++: count raw frequencies, then apply sublinear TF + smooth IDF
        token_counts: dict[str, int] = {}
        for tok in tokens:
            token_counts[tok] = token_counts.get(tok, 0) + 1

        vec: dict[int, float] = defaultdict(float)
        for tok, tf in token_counts.items():
            h = _hash(tok)
            idf_w = idf.get(h, 0.0)
            # Sublinear TF: 1 + log(tf)
            sublinear_tf = 1.0 + math.log(max(tf, 1))
            vec[h] += sublinear_tf * idf_w
    else:
        # Plain TF (backward-compatible: no IDF, no sublinear, no stop word removal)
        vec = defaultdict(float)
        for tok in tokens:
            h = _hash(tok)
            vec[h] += 1.0

    # --- GEO MODIFIER: add geo-derived features to the vector ---
    # Only apply when geo is present and has meaningful coordinates
    if geo is not None and (geo.lat != 0.0 or geo.lon != 0.0):
        geo_tokens: list[str] = []

        # 1. Climate zone — derived from absolute latitude
        abs_lat = abs(geo.lat)
        if abs_lat >= 66.5:
            climate = "polar"
        elif abs_lat >= 55.0:
            climate = "subpolar"
        elif abs_lat >= 35.0:
            climate = "temperate"
        elif abs_lat >= 23.5:
            climate = "subtropical"
        else:
            climate = "tropical"
        geo_tokens.append(f"geo_climate_{climate}")

        # 2. Continent — derived from lat/lon bounding boxes
        lat, lon = geo.lat, geo.lon
        if lat < -60:
            continent = "antarctica"
        elif -35 <= lat <= 37 and -20 <= lon <= 55:
            continent = "africa"
        elif 36 <= lat <= 70 and -10 <= lon <= 40:
            continent = "europe"
        elif 25 <= lat <= 72 and -170 <= lon <= -50:
            continent = "north_america"
        elif -55 <= lat <= 12 and -80 <= lon <= -35:
            continent = "south_america"
        elif -40 <= lat <= 40 and 55 <= lon <= 150:
            continent = "asia"
        elif -40 <= lat <= -20 and 110 <= lon <= 180:
            continent = "australia_oceania"
        else:
            continent = "unknown"
        geo_tokens.append(f"geo_continent_{continent}")

        # 3. Urban/rural heuristic — presence of city-like structure in place_name
        is_urban = 0
        if geo.place_name:
            pn_lower = geo.place_name.lower()
            # Comma-separated "City, Region/Country" indicates urban location
            if "," in pn_lower or "city" in pn_lower or "town" in pn_lower:
                is_urban = 1
            elif len(geo.place_name.split()) >= 2:
                is_urban = 1
        geo_tokens.append(f"geo_urban_{is_urban}")

        # 4. Place_name words encoded through the same hashing trick
        if geo.place_name:
            place_tokens = _tokens(geo.place_name, remove_stop_words=True)
            for tok in place_tokens:
                geo_tokens.append(f"geo_place_{tok}")

        # Add all geo feature tokens to the vector (same hashing trick)
        for tok in geo_tokens:
            h = _hash(tok)
            vec[h] += 1.0

    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: v / norm for k, v in vec.items()}


def _centroid(vectors: list[dict[int, float]]) -> dict[int, float]:
    """Mean of vectors, then L2-normalized -> an archetype prototype."""
    acc: dict[int, float] = defaultdict(float)
    for vec in vectors:
        for k, v in vec.items():
            acc[k] += v
    n = len(vectors) or 1
    acc = {k: v / n for k, v in acc.items()}
    norm = math.sqrt(sum(v * v for v in acc.values()))
    if norm == 0:
        return {}
    return {k: v / norm for k, v in acc.items()}


def _cosine(a: dict[int, float], b: dict[int, float]) -> float:
    """Cosine of two L2-normed sparse vectors = dot product over shared keys."""
    if not a or not b:
        return 0.0
    small, big = (a, b) if len(a) < len(b) else (b, a)
    return sum(w * big.get(k, 0.0) for k, w in small.items())


def _compute_idf(archetypes: dict[str, list[str]]) -> dict[int, float]:
    """Compute smooth IDF weights from all prototype training phrases.

    Phase 5 smooth IDF: IDF(t) = log(N / df(t)) + 1.0
    Adding 1.0 ensures every token (even those appearing in every document)
    gets a nonzero weight. Tokens appearing in few documents get higher IDF,
    making them more discriminative. Stop words are removed before computing
    IDF to prevent high-frequency common words from dominating.

    Returns dict mapping hashed bucket -> smooth IDF weight.
    """
    all_phrases = []
    for examples in archetypes.values():
        all_phrases.extend(examples)
    n = len(all_phrases)
    if n == 0:
        return {}

    doc_freq: dict[int, int] = defaultdict(int)
    for phrase in all_phrases:
        seen: set[int] = set()
        for tok in _tokens(phrase, remove_stop_words=True):
            h = _hash(tok)
            if h not in seen:
                doc_freq[h] += 1
                seen.add(h)

    idf: dict[int, float] = {}
    for h, df in doc_freq.items():
        # Smooth IDF: log(N / df) + 1 — every token gets at least 1.0
        idf[h] = math.log(n / max(df, 1)) + 1.0
    return idf


def _build_naive_bayes(
    archetypes: dict[str, list[str]],
    idf: dict[int, float] | None = None,
) -> tuple[dict[int, list[float]], list[float]]:
    """Build a Naive Bayes model: P(token | archetype) and P(archetype).

    Uses Laplace smoothing: P(token | arch) = (count + 1) / (total + V)
    where V = total unique hashes across all archetypes. This prevents
    zero-probability issues for unseen tokens.

    When *idf* is provided, token counts are weighted by IDF so rare
    discriminative tokens contribute more to the likelihood.

    Returns:
        word_likelihoods: dict[hash -> [P(hash|a0), P(hash|a1), ...]]
        priors: list[float] of length N_ARCHETYPES (uniform)
    """
    names = list(archetypes.keys())
    n = len(names)

    # Count tokens per archetype
    token_counts: list[dict[int, float]] = [defaultdict(float) for _ in range(n)]
    total_tokens: list[float] = [0.0] * n

    for i, name in enumerate(names):
        for phrase in archetypes[name]:
            for tok in _tokens(phrase, remove_stop_words=False):
                h = _hash(tok)
                w = idf.get(h, 1.0) if idf else 1.0
                token_counts[i][h] += w
                total_tokens[i] += w

    # All unique hashes across all archetypes
    all_hashes: set[int] = set()
    for i in range(n):
        all_hashes.update(token_counts[i].keys())
    V = len(all_hashes) or 1  # avoid division by zero

    # Laplace-smoothed: P(h | arch_i) = (count_i(h) + 1) / (total_i + V)
    word_likelihoods: dict[int, list[float]] = {}
    for h in all_hashes:
        probs: list[float] = []
        for i in range(n):
            probs.append((token_counts[i].get(h, 0.0) + 1.0) / (total_tokens[i] + V))
        word_likelihoods[h] = probs

    # Uniform prior P(archetype)
    priors = [1.0 / n] * n

    return word_likelihoods, priors


def _naive_bayes_predict(
    text: str,
    word_likelihoods: dict[int, list[float]],
    priors: list[float],
    names: list[str],
) -> str:
    """Classify text using Naive Bayes with log-space computation.

    log P(arch | text) ∝ sum(log P(token | arch)) + log P(arch)

    Tokens not in the vocabulary are silently skipped (they contribute
    nothing to any archetype's score).
    """
    n = len(names)
    # Start with log-prior
    log_scores = [math.log(max(p, 1e-15)) for p in priors]

    for tok in _tokens(text, remove_stop_words=False):
        h = _hash(tok)
        if h in word_likelihoods:
            probs = word_likelihoods[h]
            for i in range(n):
                log_scores[i] += math.log(max(probs[i], 1e-15))

    best_idx = max(range(n), key=lambda i: log_scores[i])
    return names[best_idx]


class EmbeddingClassifier(ClassifierPort):
    """Nearest-centroid classifier over hashed TF-IDF vectors with NB fallback."""

    DEFAULT_AGENT = "Innocent"

    # Each archetype defined by example thought seeds (its "training set").
    # v3: Jung's 12 archetypes (replaces 24 made-up names).
    # Grounded in Jungian psychology — every creature is a real psychological
    # pattern, not shower thoughts. The 512-dim embedding space still captures
    # unique nuance within each archetype (C option: start with Jung, expand
    # with continuous embedding).
    #
    # v4 (Lens #44 Character): expanded from 5 → 10 example sentences per
    # archetype, including a SHADOW trait (the dark side of each archetype).
    # Real characters have contradictions: the Innocent is also naive, the
    # Hero is also arrogant. Including shadow phrases in the training set
    # means the classifier captures the FULL character, not just the bright
    # side. This makes creatures feel like real personalities, not labels.
    ARCHETYPES: dict[str, list[str]] = {
        "Innocent": [
            "i just want to be safe",
            "everything will be okay",
            "i trust that this is right",
            "keep me from harm",
            "i believe in the good of people",
            # Shadow: naive, dependent, in denial
            "i don't want to know the ugly truth",
            "just tell me it's fine even if it isn't",
            "i can't handle this on my own",
            "please make the scary thing go away",
            "i pretend everything is fine because reality hurts",
        ],
        "Orphan": [
            "i don't belong anywhere",
            "nobody understands me",
            "we are all in this together",
            "i just want to fit in",
            "why am i always left out",
            # Shadow: resentful, self-pitying, envious
            "everyone else has what i don't",
            "fine i'll do it alone like always",
            "you don't really care you're just pretending",
            "i hate how happy they look without me",
            "nobody ever stays so why start now",
        ],
        "Hero": [
            "i will overcome this",
            "nothing can stop me now",
            "i have to be strong",
            "face the challenge head on",
            "this is my trial to overcome",
            # Shadow: arrogant, reckless, can't ask for help
            "i don't need anyone i've got this",
            "if i can't do it nobody can",
            "weakness is not an option",
            "i'll prove them all wrong no matter the cost",
            "asking for help is for people who aren't me",
        ],
        "Caregiver": [
            "let me help you",
            "i need to take care of them",
            "your pain matters to me",
            "i give because i care",
            "protect the vulnerable",
            # Shadow: martyr, controlling, burnt out
            "if i stop giving who am i even",
            "i give so much and nobody gives back",
            "you need me whether you know it or not",
            "i can't say no even when i'm empty",
            "i'll fix you even if you didn't ask",
        ],
        "Explorer": [
            "i want to see what's out there",
            "don't fence me in",
            "the road is calling me",
            "i need to find my own path",
            "freedom is everything",
            # Shadow: restless, commitment-phobic, rootless
            "the moment it gets familiar i want to leave",
            "staying in one place feels like dying",
            "i left because i was scared of staying",
            "every door i walk through i'm already eyeing the exit",
            "roots feel like chains to me",
        ],
        "Rebel": [
            "rules are meant to be broken",
            "i won't follow their system",
            "tear it all down",
            "they can't tell me what to do",
            "revolution starts now",
            # Shadow: destructive, contrarian, burns bridges
            "i'll destroy everything before they can take it from me",
            "i say no just to see them squirm",
            "burn it all there's nothing worth saving",
            "if you're not angry you're not paying attention",
            "i broke it because it deserved to break",
        ],
        "Lover": [
            "i want to be close to you",
            "love is all that matters",
            "i give you my whole heart",
            "being with you is enough",
            "i crave connection and intimacy",
            # Shadow: codependent, jealous, loses self in others
            "if you leave i will fall apart",
            "i need you to need me back",
            "who am i when you're not here",
            "i saw you with them and it ruined my whole day",
            "i love you so much it scares me and you",
        ],
        "Creator": [
            "i will build something new",
            "make something from nothing",
            "my imagination is limitless",
            "create what has never been seen",
            "art is how i breathe",
            # Shadow: perfectionist, never satisfied, burns out
            "it's not good enough it's never good enough",
            "i started ten projects and finished zero",
            "if i can't make it perfect why bother",
            "i poured everything into this and nobody noticed",
            "the blank page terrifies me more than anything",
        ],
        "Jester": [
            "life is a joke enjoy it",
            "make them laugh",
            "don't take it so seriously",
            "joy in every moment",
            "laughter is the best medicine",
            # Shadow: hides pain behind humor, avoids seriousness
            "if i stop joking i'll have to feel it",
            "laugh so you don't cry that's the motto",
            "why be real when you can be funny",
            "the moment gets heavy and i crack a joke to break it",
            "they think i'm happy but i'm just loud",
        ],
        "Sage": [
            "the truth will set me free",
            "i seek wisdom and understanding",
            "knowledge is power",
            "let me understand why",
            "enlighten me with your wisdom",
            # Shadow: know-it-all, detached, paralyzed by analysis
            "i've read enough to know you're wrong",
            "let me explain why your experience isn't valid",
            "i understand everything and connect with nothing",
            "analysis paralysis is my default state",
            "knowing the answer is easier than living it",
        ],
        "Magician": [
            "transform this situation",
            "i can make things happen",
            "believe and it will come",
            "the universe is on my side",
            "turn lead into gold",
            # Shadow: manipulative, delusional, bypasses reality
            "i can make them see what i want them to see",
            "visualization is enough why would i actually do it",
            "i don't need a plan i have faith",
            "i'll bend the truth until it fits my narrative",
            "spiritual bypass is my favorite avoidance strategy",
        ],
        "Ruler": [
            "take charge of this situation",
            "i must be in control",
            "lead the people",
            "order from chaos",
            "power and responsibility",
            # Shadow: authoritarian, micromanaging, isolates in leadership
            "if i don't control it it will fall apart",
            "my way is the right way",
            "trust is earned through obedience",
            "i carry everything because nobody else can",
            "leadership means nobody gets close enough to see me falter",
        ],
    }

    # Below this cosine, the input is too far from every archetype -> NB fallback.
    # v2 (Lens #23 Emergence): raised from 0.05 to 0.15 so the Naive Bayes
    # fallback actually fires for truly ambiguous inputs. This creates
    # emergence: the same input classified differently by two different
    # models (centroid cosine vs NB token likelihood), producing unexpected
    # but valid archetype assignments that broaden the creature spectrum.
    MIN_CONFIDENCE = 0.15

    def __init__(self) -> None:
        """Precompute IDF weights, prototypes, per-example vectors, and NB model."""
        # IDF weights — rare/discriminative tokens get higher weight
        self._idf = _compute_idf(self.ARCHETYPES)

        # Prototype centroids (IDF-weighted)
        self._prototypes: dict[str, dict[int, float]] = {
            name: _centroid([_encode(ex, self._idf) for ex in examples])
            for name, examples in self.ARCHETYPES.items()
        }

        # Per-example vectors for KNN scoring
        self._example_vectors: dict[str, list[dict[int, float]]] = {
            name: [_encode(ex, self._idf) for ex in examples]
            for name, examples in self.ARCHETYPES.items()
        }

        # Naive Bayes model for low-confidence fallback
        self._nb_word_likelihoods, self._nb_priors = _build_naive_bayes(
            self.ARCHETYPES, self._idf
        )
        self._nb_names = list(self.ARCHETYPES.keys())

    def classify(self, thought_seed: str, geo: GeoContext | None = None) -> str:
        """Return the archetype whose prototype is closest to the input.

        1. Compute cosine similarity to each archetype prototype.
        2. If the best score >= MIN_CONFIDENCE, return that archetype.
        3. If ALL scores are below MIN_CONFIDENCE, use Naive Bayes as a
           second pass before defaulting to Innocent. This catches inputs
           that are semantically distant from all centroids but lexically
           similar to one archetype.

        When *geo* is provided, the input is encoded with geo-derived
        features, so the same thought at different locations can produce
        a different archetype.
        """
        query = _encode(thought_seed, self._idf, geo=geo)
        if not query:
            return self.DEFAULT_AGENT

        best_name = self.DEFAULT_AGENT
        best_score = -1.0
        for name, proto in self._prototypes.items():
            score = _cosine(query, proto)
            if score > best_score:
                best_name, best_score = name, score

        # Confident prediction — return the best archetype
        if best_score >= self.MIN_CONFIDENCE:
            return best_name

        # Low-confidence fallback: try Naive Bayes before defaulting
        return _naive_bayes_predict(
            thought_seed,
            self._nb_word_likelihoods,
            self._nb_priors,
            self._nb_names,
        )

    def scores(
        self, thought_seed: str, k: int = TOP_K, geo: GeoContext | None = None
    ) -> dict[str, float]:
        """Expose per-archetype similarity scores (for eval/debug/transparency).

        Uses KNN-style scoring: for each archetype, computes cosine similarity
        to every per-example vector, takes the top-k nearest, and returns the
        average. This gives a smoother score distribution than single-centroid
        comparison.

        When k=1, falls back to single nearest-centroid (classic behavior).

        When *geo* is provided, the input is encoded with geo-derived
        features, so the same thought at different locations produces
        different score distributions.
        """
        query = _encode(thought_seed, self._idf, geo=geo)
        if not query:
            return {name: 0.0 for name in self._prototypes}

        scores: dict[str, float] = {}
        for name, examples in self._example_vectors.items():
            # Cosine to every example vector for this archetype
            cosines = sorted(
                [_cosine(query, ex) for ex in examples], reverse=True
            )
            # Average of top-k
            top = cosines[:k]
            avg = sum(top) / len(top) if top else 0.0
            scores[name] = round(avg, 4)

        return scores
