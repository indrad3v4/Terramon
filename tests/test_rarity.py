

def test_lightning_mint_price_minimum():
    """Lightning mint price must clear the Alby JIT floor (>= 2501 sats)."""
    from terramon.domain.rarity import lightning_mint_price, LIGHTNING_MIN_MINT_SATS
    assert LIGHTNING_MIN_MINT_SATS >= 2501
    # free tiers stay free
    assert lightning_mint_price(0) == 0
    # paid tiers lift to the minimum
    assert lightning_mint_price(15) == LIGHTNING_MIN_MINT_SATS
    assert lightning_mint_price(25) == LIGHTNING_MIN_MINT_SATS
    assert lightning_mint_price(5000) == 5000


# --------------------------------------------------------------------------- #
# M7: Russian rarity keywords (the TMA UI is Russian — Cyrillic thoughts must
# be able to deterministically reach RARE/LEGENDARY, not only by sampling luck).
# Same stem-substring mechanism and logit weights as the English terms
# (rare +1.0, legendary +2.0). Sampling is hash-seeded on the thought text,
# so these assertions are deterministic and stable.
# --------------------------------------------------------------------------- #
def test_russian_rare_keywords_classify_rare() -> None:
    from terramon.domain.rarity import classify_rarity, Rarity
    thought = ("я нашёл скрытую тайну в тени древних руин — "
               "запретное знание, потерянный секрет")
    r = classify_rarity(thought)
    # rare signals: скрыт/тайн/тени/запрет/потерян/секрет; legendary: древн
    assert r.rarity is Rarity.RARE
    assert r.price_sats == 15
    assert r.probabilities[2] >= r.probabilities[3]  # rare beats legendary


def test_russian_legendary_keywords_classify_legendary() -> None:
    from terramon.domain.rarity import classify_rarity, Rarity
    thought = ("древнее пророчество о бессмертном божестве, "
               "избранный герой легенды")
    r = classify_rarity(thought)
    # legendary signals: древн/пророчеств/бессмерт/божеств/избранн/легенд
    assert r.rarity is Rarity.LEGENDARY
    assert r.price_sats == 25
    assert r.probabilities[3] >= 0.9  # overwhelming legendary mass


def test_russian_neutral_thought_stays_free() -> None:
    from terramon.domain.rarity import classify_rarity
    thought = "тёплый ветер и тихий рассвет над рекой"
    r = classify_rarity(thought)
    # no Cyrillic keyword matches -> prior dominates, must be a free tier
    assert r.rarity.value in ("common", "uncommon")
    assert r.price_sats == 0


def test_russian_wealth_thought_not_legendary() -> None:
    """False-positive guard: 'богатство' must NOT fire the 'бог' legendary
    stem (we deliberately use 'божеств', which does not match 'богатство')."""
    from terramon.domain.rarity import classify_rarity
    for thought in ("богатство и золото", "золото и богатство",
                    "я молюсь богу каждый вечер"):
        r = classify_rarity(thought)
        assert r.price_sats == 0, f"{thought!r} must stay free, got {r.rarity}"


def test_english_thoughts_classify_identically_to_pre_m7() -> None:
    """Regression lock: English-only thoughts contain no Cyrillic substrings,
    so their logits are unchanged by the M7 Russian terms. Sampled rarity,
    price AND probabilities must equal the pre-change (git HEAD) values."""
    from terramon.domain.rarity import classify_rarity
    baseline = {
        "scan the ridge": ("common", 0, [0.5333, 0.2667, 0.1333, 0.0667]),
        "lost and alone in the shadow of a forbidden truth": (
            "rare", 15, [0.0251, 0.0046, 0.932, 0.0383]),
        "i surrender to the void": (
            "legendary", 25, [0.0464, 0.0346, 0.0575, 0.8614]),
        "I feel lost tonight": ("uncommon", 0, [0.4357, 0.1784, 0.2961, 0.0898]),
    }
    for thought, (rarity, price, probs) in baseline.items():
        r = classify_rarity(thought)
        assert r.rarity.value == rarity, thought
        assert r.price_sats == price, thought
        assert r.probabilities == probs, thought
