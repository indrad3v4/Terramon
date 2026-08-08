"""Light Concordia-style GameMaster for Terramon + geo proximity helper.

Deterministic world rules run first (no LLM budget spent); the LLM is
consulted only for ambiguous actions — bounded to max 1 call per validate,
with a safe fallback of allowed=True and a neutral outcome. Pure stdlib.

Context keys (all optional, rules skip gracefully when missing):
  - release state:  already_released / released (bool)
  - talking target: target_released (bool, default True)
  - geo:            anchor_lat/anchor_lon (fallback: lat/lon) — the
                    creature's home; action_lat/action_lon (fallback:
                    target_lat/target_lon) — where the action happens.
"""

from __future__ import annotations

import math
from typing import Any, Callable

ANCHOR_MAX_KM = 100.0  # creatures cannot act farther than this from home

_SYSTEM = (
    "Ты — Мир Terramon. Отвечай ровно одним словом 'allow' или 'deny', "
    "затем короткая фраза на русском."
)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km between two WGS84 points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _ctx_coord(context: dict, *keys: str) -> float | None:
    """First usable float among *keys* in context, else None."""
    for key in keys:
        value = context.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


class GameMaster:
    """Validates creature actions: deterministic rules, LLM as a last resort."""

    def __init__(self,
                 llm_call: Callable | None = None,
                 max_llm_calls: int = 1,
                 anchor_max_km: float = ANCHOR_MAX_KM) -> None:
        self.llm_call = llm_call
        self.anchor_max_km = anchor_max_km
        self._budget = max(int(max_llm_calls), 0)

    def validate(self, proposed_action: str, context: dict) -> tuple[bool, str]:
        """(allowed, outcome) for *proposed_action* given *context*.

        Deterministic rules first; the LLM is consulted only when no rule
        matches, spending at most 1 call (fallback: allowed, neutral).
        """
        rule = self._check_rules(proposed_action, context)
        if rule is not None:
            return rule

        if callable(self.llm_call) and self._budget > 0:
            self._budget -= 1
            try:
                raw = self.llm_call(
                    f"Действие: {proposed_action}. Контекст: {context}. Разрешено ли?",
                    _SYSTEM,
                )
                answer = (raw or "").strip().lower()
                if answer.startswith("allow") or "можно" in answer:
                    return True, "Мир согласен. Действие допустимо."
                if answer.startswith("deny") or "нельзя" in answer or "запрещ" in answer:
                    return False, "Мир возражает. Действие отклонено."
            except Exception:
                pass  # fall through to the neutral default

        return True, "Мир спокоен. Действие допустимо."

    def _check_rules(self, proposed_action: str, context: dict) -> tuple[bool, str] | None:
        """Return a verdict when a deterministic rule matches, else None."""
        action = (proposed_action or "").lower()
        released = bool(context.get("already_released") or context.get("released"))

        # 1. A release is irreversible — it cannot be done twice or undone.
        if "release" in action or "отпустить" in action or "освободить" in action:
            if released:
                return False, "Нельзя отпустить дважды — это уже сделано, и обратного пути нет."
            return True, "Существо отпущено на свободу. Вернуть его нельзя."
        if "reverse" in action or "вернуть" in action or "отменить" in action:
            if released:
                return False, "Выпуск нельзя отменить — решение уже принято."

        # 2. You cannot talk to a creature that isn't released.
        if any(word in action for word in ("talk", "говорить", "поговорить", "разговор")):
            if not context.get("target_released", True):
                return False, "С этим существом нельзя говорить — оно ещё не выпущено."
            return True, "Разговор состоялся. Существо слушало."

        # 3. No acting farther than anchor_max_km from the creature's anchor.
        lat = _ctx_coord(context, "action_lat", "target_lat")
        lon = _ctx_coord(context, "action_lon", "target_lon")
        anchor_lat = _ctx_coord(context, "anchor_lat", "lat")
        anchor_lon = _ctx_coord(context, "anchor_lon", "lon")
        if (lat is not None and lon is not None
                and anchor_lat is not None and anchor_lon is not None):
            dist = _haversine_km(anchor_lat, anchor_lon, lat, lon)
            if dist > self.anchor_max_km:
                return False, f"Это в {dist:.0f} км от дома — слишком далеко. Существо не пойдёт туда."
        return None


def _get_coord(item: Any, key: str) -> float | None:
    """Read a coordinate from a dict (item[key]) or an object (item.key)."""
    if isinstance(item, dict):
        value = item.get(key)
    else:
        value = getattr(item, key, None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def nearby_creatures(anchor_lat: float,
                     anchor_lon: float,
                     all_creatures: list,
                     radius_km: float = 50.0) -> list:
    """Creatures within *radius_km* of the anchor, closest first.

    Each creature is a dict with 'lat'/'lon' keys or an object with
    .lat/.lon attributes; entries without usable coordinates are skipped.
    The original items are returned (not copies), sorted by distance.
    """
    near: list[tuple[float, Any]] = []
    for creature in all_creatures:
        lat = _get_coord(creature, "lat")
        lon = _get_coord(creature, "lon")
        if lat is None or lon is None:
            continue
        dist = _haversine_km(anchor_lat, anchor_lon, lat, lon)
        if dist <= radius_km:
            near.append((dist, creature))
    near.sort(key=lambda pair: pair[0])
    return [creature for _, creature in near]
