"""FAL.ai adapter — generates creature portraits from thought seeds.

Pure stdlib (urllib). Uses FAL_KEY from environment.
~$0.003/image via fal-ai/flux/schnell.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def generate_portrait(thought: str, archetype: str, rarity: str,
                      out_dir: str = "data/creatures") -> str:
    """Generate a creature portrait via FAL.ai.

    Returns path to the saved image, or empty string on failure.

    The thought + archetype seed the generation for consistency:
    same thought → same portrait (deterministic seed).
    """
    api_key = os.environ.get("FAL_KEY", "")
    if not api_key:
        return ""

    seed = hash(thought + archetype) & 0x7FFFFFFF

    prompt = (
        f"A mystical creature representing the {archetype} archetype, "
        f"born from the thought: '{thought[:60]}'. "
        f"Rarity: {rarity}. Dark ethereal style, glowing sigils, "
        f"celestial fantasy art, TMA profile icon, 256x256"
    )

    # Step 1: Submit
    req = Request(
        "https://fal.run/fal-ai/flux/schnell",
        data=json.dumps({
            "prompt": prompt,
            "image_size": "square",
            "num_images": 1,
            "seed": seed,
        }).encode(),
        headers={
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        resp = json.loads(urlopen(req, timeout=30).read().decode())
        image_url = resp.get("images", [{}])[0].get("url", "") if isinstance(resp.get("images"), list) else ""
        if not image_url:
            return ""
    except (URLError, json.JSONDecodeError, KeyError, IndexError):
        return ""

    # Step 2: Download
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    local_path = str(out_path / f"portrait_{uuid.uuid4().hex[:8]}.png")
    try:
        img_req = Request(image_url, headers={"User-Agent": "Terramon/1.0"})
        img_data = urlopen(img_req, timeout=30).read()
        Path(local_path).write_bytes(img_data)
        return local_path
    except (URLError, OSError):
        return ""
