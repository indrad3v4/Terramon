

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
