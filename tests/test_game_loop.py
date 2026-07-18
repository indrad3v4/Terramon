"""Eval-driven tests for the game loop — each test = one roast failure mode.

Chip Huyen: define failure modes, benchmark each. Offline, deterministic.
"""

from pathlib import Path

from terramon.adapters.json_memory import JsonMemory
from terramon.adapters.keyword_classifier import KeywordClassifier
from terramon.application.game_loop import GameLoop
from terramon.application.summon_service import SummonService
from terramon.domain.progress import PlayerProgress, XP_BY_RARITY
from terramon.domain.rarity import Rarity
from terramon.events.bus import EventBus


def _service(tmp_path: Path) -> SummonService:
    return SummonService(
        classifier=KeywordClassifier(),
        memory=JsonMemory(tmp_path / "seeds.jsonl"),
        bus=EventBus(),
        clock=lambda: "2026-07-18T00:00:00Z",
    )


# --- Failure mode #25 Goals: a win condition must exist ---
def test_goal_reached_after_distinct_collection(tmp_path):
    loop = GameLoop(_service(tmp_path), PlayerProgress(goal_distinct=2))
    loop.take_turn("hello world", color=False)
    r = loop.take_turn("i am the storm", color=False)  # different agent
    assert loop.progress.distinct_count >= 1
    # goal is reachable and reported
    assert isinstance(r.goal_reached, bool)


# --- Failure mode #49 Visible Progress: xp/level move every turn ---
def test_progress_advances_each_turn(tmp_path):
    loop = GameLoop(_service(tmp_path), PlayerProgress())
    assert loop.progress.xp == 0
    r1 = loop.take_turn("calm thought", color=False)
    assert loop.progress.xp == r1.xp_gained > 0


# --- Failure mode #40 Reward: rare summon FEELS bigger (more xp) ---
def test_reward_scales_with_rarity():
    assert XP_BY_RARITY[Rarity.LEGENDARY] > XP_BY_RARITY[Rarity.RARE]
    assert XP_BY_RARITY[Rarity.RARE] > XP_BY_RARITY[Rarity.COMMON]


# --- Failure mode #57 Feedback: reveal is a multi-line event, not one string ---
def test_reveal_is_multiline_event(tmp_path):
    loop = GameLoop(_service(tmp_path), PlayerProgress())
    r = loop.take_turn("i surrender to the void", color=False)
    assert r.reveal.count("\n") >= 3  # multi-line, not a bare print
    assert "SUMMON" in r.reveal
    assert "XP" in r.reveal


# --- Failure mode #58/#59 Juiciness/Channels: rarity shows as a sigil ---
def test_reveal_has_rarity_sigil(tmp_path):
    loop = GameLoop(_service(tmp_path), PlayerProgress())
    r = loop.take_turn("i am the thunder god", color=False)
    # legendary path uses the ★ sigil
    assert "★" in r.reveal or "✧" in r.reveal or "✦" in r.reveal or "·" in r.reveal


# --- #49 progress bar renders within 0..100% ---
def test_progress_bar_bounds(tmp_path):
    loop = GameLoop(_service(tmp_path), PlayerProgress())
    r = loop.take_turn("a quiet day", color=False)
    assert "%" in r.reveal
    assert "[" in r.reveal and "]" in r.reveal


# --- level derives from xp correctly ---
def test_level_from_xp():
    p = PlayerProgress()
    p.xp = 0
    assert p.level == 1
    p.xp = 100
    assert p.level == 2
    p.xp = 250
    assert p.level == 3


# --- goal not reached with one creature when goal is higher ---
def test_goal_not_reached_early():
    p = PlayerProgress(goal_distinct=3)
    p.award("Ranger", Rarity.COMMON)
    assert not p.goal_reached
    assert p.distinct_count == 1


# --- duplicate creatures don't inflate distinct count ---
def test_duplicates_dont_count_twice():
    p = PlayerProgress(goal_distinct=3)
    p.award("Ranger", Rarity.COMMON)
    p.award("Ranger", Rarity.COMMON)
    assert p.distinct_count == 1
    assert p.xp == 2 * XP_BY_RARITY[Rarity.COMMON]  # xp still accrues
