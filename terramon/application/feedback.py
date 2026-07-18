"""Juicy feedback renderer — closes roast Lens #57 (Feedback) & #58 (Juiciness).

The roast: 'summoning a legendary creature = a print statement'. This module
turns one summon into a multi-line EVENT with anticipation, a rarity-colored
reveal, XP gain, and visible progress toward the goal.

Pure: every function returns a string (no direct print), so the loop and the
tests can assert on exact output. ANSI color is opt-in (color=False for tests).
"""

from __future__ import annotations

from terramon.domain.progress import PlayerProgress
from terramon.domain.rarity import Rarity

# ANSI colors per rarity — a channel/dimension the roast said was missing (#59).
_COLOR = {
    Rarity.COMMON: "\033[37m",      # white
    Rarity.UNCOMMON: "\033[32m",    # green
    Rarity.RARE: "\033[34m",        # blue
    Rarity.LEGENDARY: "\033[33m",   # gold
}
_RESET = "\033[0m"

_SIGIL = {
    Rarity.COMMON: "·",
    Rarity.UNCOMMON: "✦",
    Rarity.RARE: "✧",
    Rarity.LEGENDARY: "★",
}


def _c(text: str, rarity: Rarity, color: bool) -> str:
    if not color:
        return text
    return f"{_COLOR[rarity]}{text}{_RESET}"


def render_reveal(
    agent: str,
    rarity: Rarity,
    xp_gained: int,
    progress: PlayerProgress,
    color: bool = True,
) -> str:
    """Render a single summon as a juicy, multi-line reveal event."""
    sigil = _SIGIL[rarity]
    tier = rarity.value.upper()
    bar = _progress_bar(progress.xp_into_level, color)
    lines = [
        _c(f"{sigil}{sigil}{sigil}  {tier} SUMMON  {sigil}{sigil}{sigil}", rarity, color),
        _c(f"    ➜  {agent} materializes!", rarity, color),
        f"    +{xp_gained} XP   ·   Lv.{progress.level}  {bar}",
        f"    Collection: {progress.distinct_count}/{progress.goal_distinct} distinct",
    ]
    if progress.goal_reached:
        lines.append(_c("    ✸ GOAL REACHED — you are a Tamer! ✸", Rarity.LEGENDARY, color))
    return "\n".join(lines)


def _progress_bar(xp_into_level: int, color: bool, width: int = 20) -> str:
    """A 20-char XP bar toward the next level."""
    filled = int(width * xp_into_level / 100)
    bar = "█" * filled + "░" * (width - filled)
    pct = f"{xp_into_level}%"
    return f"[{bar}] {pct}"
