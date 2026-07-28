"""BPE (Byte-Pair Encoding) tokenizer — learns subword merge rules from a corpus.

Phase 5 (NLP Foundations): Subword tokenization makes the classifier more robust
to rare words and misspellings. BPE iteratively merges the most frequent adjacent
character pairs, building a vocabulary of subword units.

How it works:
  1. Start with character-level tokens (each word split into individual characters
     plus a special end-of-word marker '</w>').
  2. Count all adjacent character pairs across the corpus.
  3. Merge the most frequent pair into a new subword unit.
  4. Repeat until the desired vocabulary size is reached.
  5. To tokenize: apply the learned merges greedily from longest to shortest.

Pure stdlib (defaultdict). No external deps.

Reference: Sennrich et al., "Neural Machine Translation of Rare Words with
Subword Units" (ACL 2016).
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Optional


class BPETokenizer:
    """Learns and applies BPE merge rules from a text corpus.

    Attributes:
        vocab_size: Target vocabulary size (includes individual characters).
        merges: Dict mapping (left, right) -> merged_token, ordered by merge step.
        vocab: Set of all known tokens (characters + merged subwords).
        max_merge_len: Length of the longest merged token (for greedy matching).
    """

    def __init__(self, vocab_size: int = 200):
        self.vocab_size = max(vocab_size, 30)  # at least enough for all chars
        self.merges: list[tuple[tuple[str, str], str]] = []
        self.vocab: set[str] = set()
        self.max_merge_len: int = 1
        self._merge_map: dict[str, tuple[str, str]] = {}  # merged -> (left, right) for detokenization

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------

    def learn(self, corpus: list[str], verbose: bool = False) -> None:
        """Learn BPE merge rules from *corpus*.

        Args:
            corpus: List of text strings to learn from.
            verbose: Print merge progress if True.
        """
        # Preprocess: lowercase and split into words
        words = self._preprocess_corpus(corpus)

        # Initialize character vocab from all individual characters in the corpus
        char_vocab: set[str] = set()
        for char_tuple in words:
            for char in char_tuple:
                if char:
                    char_vocab.add(char)

        self.vocab = set(char_vocab)
        # Add a special end-of-word marker (will be tracked inside word representations)
        self.vocab.add("</w>")

        # Count character pair frequencies
        pair_counts = self._count_pairs(words)

        n_initial = len(self.vocab)
        target = self.vocab_size - n_initial

        for step in range(target):
            if not pair_counts:
                break

            # Find the most frequent pair
            best_pair = max(pair_counts, key=pair_counts.get)
            best_count = pair_counts[best_pair]

            if best_count < 1:
                break

            # Merge: e.g. ('h', 'e') -> 'he'
            merged = best_pair[0] + best_pair[1]
            self.merges.append((best_pair, merged))
            self.vocab.add(merged)
            self._merge_map[merged] = best_pair

            # Update word representations and pair counts
            words, pair_counts = self._apply_merge(words, best_pair, merged, pair_counts)

            if verbose and (step + 1) % 100 == 0:
                print(f"  BPE merge {step + 1}/{target}: '{merged}' (freq={best_count})")

        self.max_merge_len = max(len(t) for t in self.vocab) if self.vocab else 1

        if verbose:
            n_final = len(self.vocab)
            print(f"  BPE vocab: {n_initial} chars -> {n_final} subwords ({n_final - n_initial} merges)")

    def _preprocess_corpus(self, corpus: list[str]) -> dict[tuple[str, ...], int]:
        """Lowercase, tokenize, and count word frequencies.

        Returns dict mapping word-as-char-tuple -> frequency.
        Each word is a tuple of characters (with </w> appended to mark end).
        """
        word_freq: dict[tuple[str, ...], int] = defaultdict(int)
        for text in corpus:
            # Lowercase, split into words
            for word in re.findall(r"[a-z']+", text.lower()):
                if not word:
                    continue
                # Represent as characters + end-of-word marker
                chars = list(word) + ["</w>"]
                char_tuple = tuple(chars)
                word_freq[char_tuple] += 1
        return word_freq

    def _count_pairs(
        self, words: dict[tuple[str, ...], int]
    ) -> dict[tuple[str, str], int]:
        """Count all adjacent character pairs across the corpus."""
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        for char_tuple, freq in words.items():
            for i in range(len(char_tuple) - 1):
                pair = (char_tuple[i], char_tuple[i + 1])
                pair_counts[pair] += freq
        return pair_counts

    def _apply_merge(
        self,
        words: dict[tuple[str, ...], int],
        pair: tuple[str, str],
        merged: str,
        pair_counts: dict[tuple[str, str], int],
    ) -> tuple[dict[tuple[str, ...], int], dict[tuple[str, str], int]]:
        """Apply a single merge operation to all word representations.

        Replaces all occurrences of *pair* with *merged* across the corpus,
        then recomputes pair counts.
        """
        new_words: dict[tuple[str, ...], int] = {}
        new_counts: dict[tuple[str, str], int] = defaultdict(int)

        for char_tuple, freq in words.items():
            new_tuple = self._merge_in_tuple(char_tuple, pair, merged)
            new_words[new_tuple] = freq

            # Count pairs in the new representation
            for i in range(len(new_tuple) - 1):
                p = (new_tuple[i], new_tuple[i + 1])
                new_counts[p] += freq

        return new_words, new_counts

    @staticmethod
    def _merge_in_tuple(
        t: tuple[str, ...],
        pair: tuple[str, str],
        merged: str,
    ) -> tuple[str, ...]:
        """Merge adjacent elements matching *pair* into *merged*.

        E.g. ('h', 'e', 'l', 'l', 'o') with pair=('l', 'l'), merged='ll'
        -> ('h', 'e', 'll', 'o')
        """
        result: list[str] = []
        i = 0
        while i < len(t):
            if i < len(t) - 1 and t[i] == pair[0] and t[i + 1] == pair[1]:
                result.append(merged)
                i += 2
            else:
                result.append(t[i])
                i += 1
        return tuple(result)

    # ------------------------------------------------------------------
    # Tokenization
    # ------------------------------------------------------------------

    def tokenize(self, text: str) -> list[str]:
        """Split *text* into subword tokens using learned BPE merges.

        For each word (after basic tokenization), applies merges greedily
        from longest to shortest. If no merge matches, falls back to
        character-level tokens.

        Returns list of subword tokens (without </w> markers — the end-of-word
        boundary is implicit in the token boundary).
        """
        if not self.merges:
            # No merges learned yet — just return characters
            return [c for c in text.lower() if c.isalpha()]

        words = re.findall(r"[a-z']+", text.lower())
        tokens: list[str] = []

        for word in words:
            # Start with character-level + </w>
            char_list: list[str] = list(word) + ["</w>"]

            # Apply merges greedily by iterating through sorted merge list
            # We apply from the most recently learned (longest) merge first
            for pair, merged in reversed(self.merges):
                char_list = self._merge_in_list(char_list, pair, merged)

            # Remove </w> marker and add tokens
            for tok in char_list:
                cleaned = tok.replace("</w>", "")
                if cleaned:
                    tokens.append(cleaned)

        return tokens

    @staticmethod
    def _merge_in_list(
        tokens: list[str],
        pair: tuple[str, str],
        merged: str,
    ) -> list[str]:
        """Merge adjacent elements matching *pair* into *merged* (list version)."""
        result: list[str] = []
        i = 0
        while i < len(tokens):
            if i < len(tokens) - 1 and tokens[i] == pair[0] and tokens[i + 1] == pair[1]:
                result.append(merged)
                i += 2
            else:
                result.append(tokens[i])
                i += 1
        return result

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def detokenize(self, tokens: list[str]) -> str:
        """Reconstruct a readable string from BPE tokens (best effort)."""
        return "".join(tokens)

    @property
    def num_merges(self) -> int:
        return len(self.merges)

    def save(self, path: str) -> None:
        """Save merge rules and vocab to a text file (one merge per line).

        Format: "left right -> merged"
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# BPE tokenizer — {self.num_merges} merges, {len(self.vocab)} vocab\n")
            for (left, right), merged in self.merges:
                f.write(f"{left} {right} -> {merged}\n")
            # Also write the full vocab
            f.write("# VOCAB\n")
            for token in sorted(self.vocab, key=lambda t: (-len(t), t)):
                f.write(f"{token}\n")

    @classmethod
    def load(cls, path: str) -> BPETokenizer:
        """Load merge rules from a saved file."""
        tokenizer = cls(vocab_size=10000)
        with open(path, "r", encoding="utf-8") as f:
            in_vocab = False
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    if line.startswith("# VOCAB"):
                        in_vocab = True
                        continue
                    elif line.startswith("# BPE"):
                        continue
                    continue
                if in_vocab:
                    tokenizer.vocab.add(line)
                else:
                    parts = line.split(" -> ")
                    if len(parts) == 2:
                        left_right = parts[0].split(" ")
                        if len(left_right) == 2:
                            pair = (left_right[0], left_right[1])
                            merged = parts[1]
                            tokenizer.merges.append((pair, merged))
                            tokenizer._merge_map[merged] = pair
                            tokenizer.vocab.add(merged)
        tokenizer.max_merge_len = max(len(t) for t in tokenizer.vocab) if tokenizer.vocab else 1
        return tokenizer


def build_default_bpe(corpus: list[str] | None = None, vocab_size: int = 200) -> BPETokenizer:
    """Build and return a BPE tokenizer from the embedding classifier's archetype corpus.

    This is the recommended way to create a BPE tokenizer for Terramon's text
    processing pipeline.

    Args:
        corpus: List of training phrases. If None, uses the archetype examples
                from the embedding classifier.
        vocab_size: Target subword vocabulary size (default: 200).

    Returns:
        A trained BPETokenizer instance.
    """
    if corpus is None:
        from terramon.adapters.embedding_classifier import EmbeddingClassifier

        clf = EmbeddingClassifier()
        corpus = []
        for examples in clf.ARCHETYPES.values():
            corpus.extend(examples)

    tokenizer = BPETokenizer(vocab_size=vocab_size)
    tokenizer.learn(corpus, verbose=False)
    return tokenizer
