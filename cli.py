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
from terramon.adapters.keyword_classifier import KeywordClassifier
from terramon.application.summon_service import SummonService
from terramon.events.agent_summoned import AgentSummoned
from terramon.events.bus import EventBus
from tools.time_tool import get_current_time


def main() -> None:
    """Parse a thought seed and print the summoned agent."""
    parser = argparse.ArgumentParser(description="Summon a Terramon agent.")
    parser.add_argument("thought_seed", help="Player input to route to an agent")
    parser.add_argument(
        "--memory",
        default="data/thought_seeds.jsonl",
        help="Path to the newline-delimited JSON memory file",
    )
    args = parser.parse_args()

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
