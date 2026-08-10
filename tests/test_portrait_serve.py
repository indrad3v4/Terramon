"""Lesson 13 artifact tests — portrait serving + TMA wiring guards.

Root cause of «no creature images»: the FAL portrait pipeline
(fal_art.py → data/creatures/ registry) existed, but the TMA never
rendered it — agent_portrait was set but had no rx.image, refresh_portrait
was never called, and there was no route to serve the PNGs. These guards
lock the fix. Offline: the Reflex module is read as TEXT (see
test_iter6_regression.py for the convention).
"""

from __future__ import annotations

from pathlib import Path

from terramon.adapters.portrait_serve import (
    creature_art_url,
    portrait_file_path,
)

_VALID = "portrait_5aa12483775bc51319dc4ebd9ea5c71b.png"
_VALID_THUMB = "thumb_5aa12483775bc51319dc4ebd9ea5c71b.png"


def test_url_accepts_portrait_and_thumb() -> None:
    assert creature_art_url(_VALID) == "/creature-art?name=" + _VALID
    assert (
        creature_art_url("data/creatures/" + _VALID)
        == "/creature-art?name=" + _VALID
    )
    assert creature_art_url(_VALID_THUMB) == "/creature-art?name=" + _VALID_THUMB


def test_url_rejects_traversal_and_garbage() -> None:
    assert creature_art_url("../../etc/passwd") == ""
    assert creature_art_url("portrait_evil.sh") == ""
    assert creature_art_url("") == ""
    assert creature_art_url("portrait_xyz.png") == ""  # not 32-hex


def test_path_resolves_only_inside_creatures_dir(tmp_path: Path) -> None:
    creatures = tmp_path / "creatures"
    creatures.mkdir()
    f = creatures / _VALID
    f.write_bytes(b"\x89PNG fake")
    assert portrait_file_path(_VALID, str(tmp_path)) == f.resolve()
    assert portrait_file_path("../secret.png", str(tmp_path)) is None
    assert portrait_file_path("..%2Fsecret.png", str(tmp_path)) is None


def test_path_rejects_missing_file(tmp_path: Path) -> None:
    assert portrait_file_path(_VALID, str(tmp_path)) is None


_TMA = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"
_TMA_SRC = _TMA.read_text(encoding="utf-8")


def test_tma_renders_portrait_on_main_card() -> None:
    assert "src=TerramonState.agent_portrait" in _TMA_SRC
    assert "portrait_pending: bool" in _TMA_SRC
    assert "on_change=TerramonState.poll_portrait" in _TMA_SRC


def test_tma_seed_cards_carry_portrait() -> None:
    assert '"portrait": _portrait_url_for(seed)' in _TMA_SRC
    assert 'item["portrait"] != ""' in _TMA_SRC


def test_tma_registers_creature_art_route() -> None:
    assert "def creature_art(request):" in _TMA_SRC
    assert 'add_route("/creature-art", creature_art' in _TMA_SRC


def test_tma_calls_refresh_portrait_on_load() -> None:
    assert "self.refresh_portrait()" in _TMA_SRC
    assert "self.portrait_pending = True" in _TMA_SRC
