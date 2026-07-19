"""Insight domain model — the psychological mechanism that drives the agent.

Lives in the domain layer (FIX 2) so ThoughtSeed can carry it without the
domain depending on the application layer. The extraction heuristics that
populate it live in `terramon/application/insight_engine.py`.

Per docs/dvizhok/phase1-strategy.md §3 INSIGHT ENGINE:

    DRIVER   = what the player WANTS
    BARRIER  = what BLOCKS it
    THEREFORE = the creature's hidden behavior directive (what the agent DOES)
"""

from dataclasses import dataclass


@dataclass
class Insight:
    """A derived psychological mechanism that drives the agent.

    driver   — what the player wants (the pull).
    barrier  — what blocks it (the friction).
    therefore — the creature's hidden behavior directive.
    """

    driver: str
    barrier: str
    therefore: str
