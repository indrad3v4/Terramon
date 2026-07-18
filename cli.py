"""Minimal CLI for summoning a Terramon agent from a thought seed.

PR workflow reminder:
1. Run: python -m pytest tests/
2. Open a PR
3. Comment: @askserge please review
4. Fix Serge's notes
5. Ask a human for final merge review
"""

import argparse
from pathlib import Path

from terramon.adapters.json_memory import JsonMemory
from terramon.adapters.embedding_classifier import EmbeddingClassifier
from terramon.adapters.keyword_classifier import KeywordClassifier
from terramon.application.game_loop import GameLoop
from terramon.application.summon_service import SummonService
from terramon.domain.progress import PlayerProgress
from terramon.events.agent_summoned import AgentSummoned
from terramon.events.bus import EventBus
from tools.time_tool import get_current_time


def _build_service(memory_path: str, quiet: bool = False) -> SummonService:
    bus = EventBus()
    if not quiet:
        bus.subscribe(AgentSummoned, lambda event: None)  # signal handled by loop UI
    return SummonService(
        classifier=EmbeddingClassifier(),
        memory=JsonMemory(Path(memory_path)),
        bus=bus,
        clock=get_current_time,
    )


def _play(args) -> None:
    """Interactive game loop: summon -> reward -> reflect -> repeat (Lens #25/#49/#57)."""
    service = _build_service(args.memory, quiet=True)
    loop = GameLoop(service, PlayerProgress(goal_distinct=args.goal))
    print("🌍 TERRAMON — type a thought to summon. 'quit' to leave.\n")
    while True:
        try:
            raw = input("💭 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 The tamer rests.")
            break
        if raw.lower() in {"quit", "exit", "q"}:
            print("👋 The tamer rests.")
            break
        if not raw:
            continue
        result = loop.take_turn(raw, color=not args.no_color)
        print(result.reveal + "\n")
        if result.goal_reached:
            print("🏆 Session complete — goal reached!\n")
            break


def main() -> None:
    """Summon one agent (legacy) or play the interactive loop."""
    parser = argparse.ArgumentParser(description="Summon a Terramon agent.")
    parser.add_argument("thought_seed", nargs="?", help="One-shot thought seed (legacy mode)")
    parser.add_argument("--play", action="store_true", help="Interactive game loop")
    parser.add_argument("--goal", type=int, default=3, help="Distinct creatures to win")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color")
    parser.add_argument(
        "--memory",
        default="data/thought_seeds.jsonl",
        help="Path to the newline-delimited JSON memory file",
    )
    args = parser.parse_args()

    if args.play or not args.thought_seed:
        _play(args)
        return

    # Legacy one-shot mode (unchanged behavior for existing users).
    bus = EventBus()
    bus.subscribe(AgentSummoned, lambda event: print(
        f"📡 Signal emitted: {event.agent_name} summoned at {event.timestamp}"
    ))
    service = SummonService(
        classifier=KeywordClassifier(),
        memory=JsonMemory(Path(args.memory)),
        bus=bus,
        clock=get_current_time,
    )
    seed = service.summon(args.thought_seed)
    print(f"🌱 Thought seed: {seed.raw_input}")
    print(f"🧙 Summoned agent: {seed.summoned_agent}")
    print(f"🕒 Timestamp: {seed.timestamp}")
    print(f"💾 Memory saved to: {args.memory}")


if __name__ == "__main__":
    main()
