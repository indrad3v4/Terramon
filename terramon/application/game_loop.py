"""GameLoop — the ONE loop the roast said didn't exist.

Build-via-learn: Chip Huyen's agent loop (REASON → ACT → OBSERVE → REFLECT →
REPEAT/terminate) applied to a game turn:

  ACT      player types a thought seed
  OBSERVE  SummonService routes it -> agent + rarity
  REWARD   PlayerProgress.award() -> xp, collection (Lens #40/#49)
  REFLECT  render juicy reveal (Lens #57/#58) + check goal (Lens #25)
  REPEAT   until goal reached or player quits

This wraps the existing SummonService WITHOUT changing it — the loop owns
progression + feedback; the service still just summons + persists.
"""

from __future__ import annotations

from dataclasses import dataclass

from terramon.application.feedback import render_reveal
from terramon.application.summon_service import SummonService
from terramon.domain.progress import PlayerProgress


@dataclass
class TurnResult:
    """Everything that happened in one loop turn — testable, not printed."""

    agent: str
    rarity: str
    xp_gained: int
    reveal: str
    goal_reached: bool


class GameLoop:
    """Drives repeated summons and advances player progress each turn."""

    def __init__(
        self,
        service: SummonService,
        progress: PlayerProgress | None = None,
    ) -> None:
        self.service = service
        self.progress = progress or PlayerProgress()

    def take_turn(self, raw_input: str, color: bool = True) -> TurnResult:
        """One full loop turn: summon -> reward -> reflect."""
        seed = self.service.summon(raw_input)
        # rarity comes back as a string on the seed; map to the enum for XP.
        from terramon.domain.rarity import Rarity

        rarity = Rarity(seed.rarity)
        xp_gained = self.progress.award(seed.summoned_agent, rarity)
        reveal = render_reveal(
            agent=seed.summoned_agent,
            rarity=rarity,
            xp_gained=xp_gained,
            progress=self.progress,
            color=color,
        )
        return TurnResult(
            agent=seed.summoned_agent,
            rarity=seed.rarity,
            xp_gained=xp_gained,
            reveal=reveal,
            goal_reached=self.progress.goal_reached,
        )
