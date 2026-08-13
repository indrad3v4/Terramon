"""Ritual monetisation tests (owner directive 2026-08-13).

The ACTUAL WIN — a complete release (final words + real geo) — is the
PAID sacred moment («монета в фонтан»). Words reach the world only when
the ritual settles (Lightning sacred rail / Stars), so complete_releases
counts PAID wins by construction: the free path releases the creature
but never persists words, hence never counts toward the depth win.
"""

from __future__ import annotations

from pathlib import Path

from terramon.domain.rarity import (
    LIGHTNING_MIN_MINT_SATS,
    RITUAL_RELEASE_SATS,
    RITUAL_RELEASE_STARS,
    ritual_release_price,
)

_TMA = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"
_TMA_SRC = _TMA.read_text(encoding="utf-8")


# ── Rarity: ritual prices ─────────────────────────────────────────────

def test_ritual_price_above_jit_floor() -> None:
    """The sacred rail must clear the Alby JIT channel floor (2501 sats)."""
    assert RITUAL_RELEASE_SATS >= LIGHTNING_MIN_MINT_SATS
    assert RITUAL_RELEASE_STARS > 0


def test_ritual_release_price_contract() -> None:
    assert ritual_release_price(0) == 0
    assert ritual_release_price(5) == RITUAL_RELEASE_SATS
    assert ritual_release_price(1) >= LIGHTNING_MIN_MINT_SATS


# ── TMA source guards: the release flow is ritual-gated ───────────────

def test_tma_has_ritual_state() -> None:
    for var in (
        "show_ritual_payment",
        "release_ritual_paid",
        "release_ritual_invoice",
        "release_ritual_ref",
        "release_ritual_auto_verify",
        "pending_words",
    ):
        assert var in _TMA_SRC


def test_tma_free_path_never_counts_depth() -> None:
    """The legacy path calls _do_release with complete=False and persists
    status ONLY (no final_words) — so it can never count toward
    complete_releases."""
    assert '_do_release("", complete=False)' in _TMA_SRC
    # legacy persist: status only, no words
    assert (
        '_MEMORY.update_seed(self.agent, self.thought, status="released")'
        in _TMA_SRC
    )
    assert "if complete:" in _TMA_SRC


def test_tma_ritual_path_persists_words() -> None:
    """The paid ritual persists final words → the depth win survives a
    restart (the /health seed scan counts it)."""
    assert (
        '_MEMORY.update_seed(\n'
        "                    self.agent, self.thought, status=\"released\", final_words=words\n"
        "                )"
    ) in _TMA_SRC


def test_tma_ritual_handlers_present() -> None:
    for handler in (
        "def create_ritual_invoice",
        "def verify_release_ritual",
        "def pay_ritual_stars",
        "def release_without_ritual",
        "def _complete_ritual_release",
        "def _do_release",
    ):
        assert handler in _TMA_SRC


def test_tma_ritual_kpi_marker() -> None:
    """The KPI probe parses this marker to prove the monetised win-path
    is live (invoice creation) without settling a real payment."""
    assert "⚡ Ритуал отпускания:" in _TMA_SRC


def test_tma_ritual_panel_mounted() -> None:
    assert "ritual_payment_panel()," in _TMA_SRC
    assert "Ритуал Отпускания" in _TMA_SRC
    assert "Отпустить без ритуала" in _TMA_SRC
    assert "RITUAL_RELEASE_SATS" in _TMA_SRC
    assert "RITUAL_RELEASE_STARS" in _TMA_SRC


def test_tma_depth_win_contract_preserved() -> None:
    """The depth win still requires words + geo (record_complete_release
    is only called in the complete branch)."""
    assert "record_complete_release(" in _TMA_SRC
    assert "self.complete_releases = int(_LOOP.progress.complete_releases)" in _TMA_SRC


def test_release_receipt_has_share_cta() -> None:
    """The release receipt (the released_just_now cond) carries a share
    CTA wired to share_creature — the M6 share loop reaches the just-
    released player right at the peak emotional moment. The KPI probe's
    receipt marker («отпустил свою мысль») must survive, and the
    released_just_now gate must stay intact."""
    assert "📤 Поделиться отпусканием" in _TMA_SRC
    assert "on_click=TerramonState.share_creature" in _TMA_SRC
    assert "отпустил свою мысль" in _TMA_SRC
    assert "released_just_now" in _TMA_SRC
