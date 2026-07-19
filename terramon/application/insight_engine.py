"""Insight Engine — what actually drives the agent (FIX 2, PLAYER_JOURNEY_MAP).

The surface text a player types is only a *symptom*. Behind it lives an INSIGHT,
the hidden behavioral mechanism that MOVES the creature (per
docs/dvizhok/phase1-strategy.md §3 INSIGHT ENGINE):

    DRIVER  = what the player WANTS
    BARRIER = what BLOCKS it (keyword/embedding signal)
    THEREFORE = the creature's behavior directive — this is what the agent
                actually DOES, not the rarity label.

Pure stdlib (no API, no deps). Deterministic keyword/embedding-lite heuristics
map cues in the text to DRIVER/BARRIER themes, then a THEREFORE template turns
the barrier into a meet-don't-control directive for the Scout/agent.
"""

from __future__ import annotations

from terramon.domain.insight import Insight


# --- cue tables (keyword heuristics) ----------------------------------------

# Each barrier cue maps a surface word to the thing that blocks the player.
_BARRIER_CUES: dict[str, str] = {
    "money": "money", "rent": "money", "broke": "money", "pay": "money",
    "payment": "money", "debt": "money", "bills": "money", "poor": "money",
    "work": "work", "job": "work", "boss": "work", "burnout": "work",
    "deadline": "work", "tired": "work", "exhausted": "work",
    "afraid": "fear", "fear": "fear", "scared": "fear", "anxious": "fear",
    "anxiety": "fear", "terrified": "fear", "worried": "fear",
    "alone": "loneliness", "lonely": "loneliness", "isolated": "loneliness",
    "nobody": "loneliness", "no one": "loneliness", "abandoned": "loneliness",
    "lost": "direction", "stuck": "direction", "confused": "direction",
    "purpose": "direction", "meaning": "direction", "which way": "direction",
}

# Each driver cue maps a surface word to what the player wants (the pull).
_DRIVER_CUES: dict[str, str] = {
    "money": "to be safe and free of scarcity",
    "rent": "to be safe and free of scarcity",
    "broke": "to be safe and free of scarcity",
    "work": "rest and a life outside the grind",
    "job": "rest and a life outside the grind",
    "boss": "rest and a life outside the grind",
    "burnout": "rest and a life outside the grind",
    "afraid": "to be unafraid of what comes next",
    "fear": "to be unafraid of what comes next",
    "scared": "to be unafraid of what comes next",
    "anxious": "to be unafraid of what comes next",
    "alone": "to be met and held",
    "lonely": "to be met and held",
    "isolated": "to be met and held",
    "lost": "to know which way to turn",
    "stuck": "to know which way to turn",
    "confused": "to know which way to turn",
    "interview": "to be ready and unafraid",
    "tomorrow": "to be ready and unafraid",
    "love": "to be close to someone",
    "friend": "to be close to someone",
    "family": "to be close to someone",
    "calm": "quiet and stillness",
    "peace": "quiet and stillness",
    "rest": "quiet and stillness",
}

# Barrier -> the behavior directive the creature performs (MEET, don't control).
_THEREFORE_BY_BARRIER: dict[str, str] = {
    "money": "It sits with you in the scarcity and does not look away.",
    "work": "It clears a small space so you can breathe.",
    "fear": "It waits by the door so you are not facing it alone.",
    "loneliness": "It stays close, a warm weight at your side.",
    "direction": "It walks a little ahead, showing the next step only.",
}

_NEUTRAL_THEREFORE = (
    "It settles beside you and listens to what the quiet is saying."
)


def _detect(text: str, cues: dict[str, str]) -> tuple[str, str] | None:
    """Return (keyword, theme) for the first matching cue, else None.

    Longer multi-word cues are checked before single tokens so 'no one'
    wins over 'one'.
    """
    lowered = text.lower()
    for cue in sorted(cues, key=len, reverse=True):
        if cue in lowered:
            return cue, cues[cue]
    return None


def extract_insight(raw_input: str) -> Insight:
    """Derive the INSIGHT (DRIVER + BARRIER -> THEREFORE) from raw player text.

    Keyword/embedding-lite heuristics: scan for barrier cues first (what blocks
    the player), then driver cues (what they want). The THEREFORE template turns
    the detected barrier into the creature's hidden behavior directive.

    Empty / cue-less input yields a neutral, still-centred insight — the
    creature simply listens. This keeps the agent driven by an insight even
    when no strong signal is present, rather than by a rarity label.
    """
    text = (raw_input or "").strip()

    barrier_hit = _detect(text, _BARRIER_CUES)
    driver_hit = _detect(text, _DRIVER_CUES)

    barrier = barrier_hit[1] if barrier_hit else "the quiet ordinary"
    driver = driver_hit[1] if driver_hit else "to be met where you are"

    therefore = _THEREFORE_BY_BARRIER.get(barrier, _NEUTRAL_THEREFORE)

    return Insight(driver=driver, barrier=barrier, therefore=therefore)
