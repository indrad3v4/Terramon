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
from terramon.application.geo_tournament import GeoTournamentService
from terramon.application.summon_service import SummonService
from terramon.domain.progress import PlayerProgress, XP_BY_RARITY


@dataclass
class TurnResult:
    """Everything that happened in one loop turn — testable, not printed."""

    agent: str
    rarity: str
    xp_gained: int
    reveal: str
    goal_reached: bool
    price_sats: int = 0  # P1 T07: uniqueness-adjusted MINT price
    tournament_id: str = ""  # M02: geo-tournament offer battle_id, if created
    tournament_archetype: str = ""  # M02: archetype matched for tournament


class GameLoop:
    """Drives repeated summons and advances player progress each turn."""

    def __init__(
        self,
        service: SummonService,
        progress: PlayerProgress | None = None,
        tournament_service: GeoTournamentService | None = None,
    ) -> None:
        self.service = service
        self.progress = progress or PlayerProgress()
        self.tournament_service = tournament_service or GeoTournamentService()

    def take_turn(self, raw_input: str, color: bool = True, today: str | None = None) -> TurnResult:
        """One full loop turn: summon -> reward -> reflect.

        Args:
            raw_input: The thought seed text.
            color: Whether to use ANSI colors in the reveal.
            today: Date string "YYYY-MM-DD" for streak tracking.
                Defaults to today's date if None.
        """
        if today is None:
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
        from terramon.domain.rarity import Rarity

        # I09: Update summon streak before summoning
        self.progress.update_streak(today)

        # I09: Pass rare probability boost from streak to the summon
        rare_boost = self.progress.rare_probability_boost
        seed = self.service.summon(raw_input, rare_boost=rare_boost)

        # rarity comes back as a string on the seed; map to the enum for XP.
        rarity = Rarity(seed.rarity)
        xp_gained = self.progress.award(seed.summoned_agent, rarity)

        # I09: Apply streak XP multiplier
        xp_gained = int(xp_gained * self.progress.streak_xp_multiplier)
        self.progress.xp += xp_gained - XP_BY_RARITY[rarity]  # adjust for the bonus

        # Lens #39 fix: read goal_reached BEFORE render_reveal (which also
        # reads it, and goal_reached is a mutable-access property that
        # advances the tier on first read). Reading it first ensures the
        # TurnResult gets the correct value.
        goal_reached = self.progress.goal_reached
        reveal = render_reveal(
            agent=seed.summoned_agent,
            rarity=rarity,
            xp_gained=xp_gained,
            progress=self.progress,
            color=color,
        )

        # M02: Check for same-archetype proximity match
        tournament_id = ""
        tournament_archetype = ""
        try:
            battle = self.tournament_service.check_and_offer(
                memory=self.service.memory,
                archetype=seed.summoned_agent,
                lat=seed.lat,
                lon=seed.lon,
                player_id="player_default",
                bond_level=0,
                evolution_stage=0,
            )
            if battle is not None:
                tournament_id = battle.battle_id
                tournament_archetype = battle.archetype
        except Exception:
            pass  # tournament offer is best-effort

        return TurnResult(
            agent=seed.summoned_agent,
            rarity=seed.rarity,
            xp_gained=xp_gained,
            reveal=reveal,
            goal_reached=goal_reached,
            price_sats=seed.price_sats,
            tournament_id=tournament_id,
            tournament_archetype=tournament_archetype,
        )
