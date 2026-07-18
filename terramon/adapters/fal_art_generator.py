"""FAL art generator — text-to-image via fal.ai (flux/schnell).

Implements ArtPort. Uses fal_client.subscribe which handles the queue submit +
poll + result-shape correctly (raw urllib returns 422 on the result endpoint
when the app-id path differs between submit and fetch — a documented FAL gotcha).

Key handling: FAL_KEY from env only. Never commit it. Egress on some hosts
hangs foreground, so heavy calls should run in a background process.

Build-via-learn: Phase 8 (Generative Models) — the diffusion model is the tool;
this adapter is the seam between pure game state and a real generative backend.
"""

from __future__ import annotations

import os
import time
import urllib.request

from terramon.ports.art_port import ArtPort, ArtRequest, ArtResult

FAL_APP = "fal-ai/flux/schnell"


class FalArtGenerator(ArtPort):
    """Generates creature art via FAL flux/schnell.

    client: an object exposing subscribe(app, arguments) -> dict (defaults to
    fal_client). Injectable so tests run offline with a fake.
    """

    def __init__(self, client=None, out_dir: str = "data/creatures", app: str = FAL_APP) -> None:
        self._client = client
        self.out_dir = out_dir
        self.app = app

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not os.getenv("FAL_KEY"):
            raise RuntimeError("FAL not configured: set FAL_KEY")
        import fal_client  # imported lazily so the port works without the dep
        return fal_client

    def generate(self, request: ArtRequest) -> ArtResult:
        prompt = request.to_prompt()
        client = self._get_client()
        res = client.subscribe(self.app, arguments={"prompt": prompt, "num_images": 1})
        images = res.get("images") or []
        if not images:
            raise RuntimeError(f"FAL returned no images: {list(res.keys())}")
        url = images[0]["url"]
        img = urllib.request.urlopen(url, timeout=60).read()

        os.makedirs(self.out_dir, exist_ok=True)
        safe = request.archetype.lower()
        fname = f"{safe}_{request.rarity.value}_{int(time.time())}.png"
        path = os.path.join(self.out_dir, fname)
        with open(path, "wb") as f:
            f.write(img)

        return ArtResult(
            path=path,
            prompt=prompt,
            seed=res.get("seed", 0),
            bytes_len=len(img),
        )
