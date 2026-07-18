"""Eval tests for the art pipeline — offline, deterministic.

Each test = one failure mode:
  - prompt loses game state -> to_prompt must carry archetype+rarity+element
  - adapter hits network in tests -> fake client, no egress
  - empty FAL response -> raises, not silent
"""

import os
import tempfile

from terramon.adapters.fal_art_generator import FalArtGenerator
from terramon.domain.rarity import Rarity
from terramon.ports.art_port import ArtRequest


def test_prompt_carries_game_state():
    req = ArtRequest(thought="i am the storm lord", archetype="Strategist", rarity=Rarity.LEGENDARY)
    p = req.to_prompt()
    assert "air" in p                     # Strategist element
    assert "golden aura" in p             # legendary aura
    assert "tactician" in p               # archetype motif
    assert "no text" in p                 # card-safe


def test_prompt_rarity_changes_aura():
    common = ArtRequest("x", "Ranger", Rarity.COMMON).to_prompt()
    legendary = ArtRequest("x", "Ranger", Rarity.LEGENDARY).to_prompt()
    assert "grey aura" in common
    assert "golden aura" in legendary
    assert common != legendary


def test_unknown_archetype_falls_back():
    p = ArtRequest("x", "Nonexistent", Rarity.RARE).to_prompt()
    assert "mysterious creature" in p
    assert "blue aura" in p


class _FakeClient:
    def __init__(self, url):
        self._url = url
        self.calls = []

    def subscribe(self, app, arguments):
        self.calls.append((app, arguments))
        return {"images": [{"url": self._url}], "seed": 42}


def test_adapter_offline_with_fake_client(monkeypatch):
    # serve image bytes from a local file:// URL — no network
    with tempfile.TemporaryDirectory() as d:
        img_path = os.path.join(d, "fake.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
        fake = _FakeClient("file://" + img_path)
        gen = FalArtGenerator(client=fake, out_dir=os.path.join(d, "out"))
        req = ArtRequest("calm morning", "Wanderer", Rarity.COMMON)
        res = gen.generate(req)
        assert res.bytes_len > 100
        assert res.seed == 42
        assert os.path.exists(res.path)
        assert "wanderer_common" in res.path
        assert fake.calls[0][0] == "fal-ai/flux/schnell"


def test_empty_response_raises(monkeypatch):
    class Empty:
        def subscribe(self, app, arguments):
            return {"images": []}

    gen = FalArtGenerator(client=Empty())
    import pytest

    with pytest.raises(RuntimeError):
        gen.generate(ArtRequest("x", "Ranger", Rarity.COMMON))


def test_missing_key_raises():
    import pytest

    gen = FalArtGenerator(client=None)
    # ensure no key
    old = os.environ.pop("FAL_KEY", None)
    try:
        with pytest.raises(RuntimeError):
            gen.generate(ArtRequest("x", "Ranger", Rarity.COMMON))
    finally:
        if old:
            os.environ["FAL_KEY"] = old
