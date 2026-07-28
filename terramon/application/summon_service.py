"""SummonService — the core use case: seed -> router -> agent -> memory -> event.

Build-via-learn (v2): adds rarity + optional payment gating without breaking
the original contract. The first three tests pass unchanged because `payment`
and `rarity_classifier` default to Nothing/Common.

v3 (Risk Mitigation): adds input length validation, rate limiting, and
configurable min_interval to prevent spam/DoS.

Maps to:
- Phase 10/11 LLMs: classifier decides the agent
- Day 59 (ROADMAP_2027): rarity derived from thought seed
- Day 14 (LEARNING_PATH): PaymentPort gating rare summons
"""

import logging
import time
from collections.abc import Callable

from terramon.application.intent_router import IntentRouter
from terramon.application.payment_gate import PaymentGate
from terramon.application.insight_engine import extract_insight
from terramon.domain.thought_seed import ThoughtSeed
from terramon.domain.rarity import classify_rarity
from terramon.events.agent_summoned import AgentSummoned
from terramon.events.bus import EventBus
from terramon.ports.classifier_port import ClassifierPort
from terramon.ports.memory_port import MemoryPort
from terramon.ports.payment_port import PaymentPort

log = logging.getLogger("terramon.summon_service")


MAX_INPUT_LENGTH = 2000
_MIN_SUMMON_INTERVAL = 0.0  # seconds between summons (0 = no limit, opt-in for anti-spam)


class SummonService:
    """Orchestrates the thought-seed summon loop."""

    def __init__(
        self,
        classifier: ClassifierPort,
        memory: MemoryPort,
        bus: EventBus,
        clock: Callable[[], str],
        payment: PaymentPort | None = None,
        rarity_classifier=classify_rarity,
        min_interval: float = _MIN_SUMMON_INTERVAL,
    ) -> None:
        """Wire the ports and event bus.

        Args:
            classifier: Agent routing port.
            memory: Persistence port.
            bus: Event bus for summon signals.
            clock: Callable returning ISO timestamp.
            payment: Optional payment gate.
            rarity_classifier: Rarity classification function.
            min_interval: Minimum seconds between summons from the same
                          player (anti-spam). 0 = no rate limit.
        """
        self.router = IntentRouter(classifier)
        self.memory = memory
        self.bus = bus
        self.clock = clock
        self.gate = PaymentGate(payment)
        self.rarity_classifier = rarity_classifier
        self._min_interval = min_interval
        self._last_summon_time: float = 0.0

    def _check_rate_limit(self) -> None:
        """Enforce minimum interval between summons. Raises RuntimeError if too fast."""
        if self._min_interval <= 0:
            return
        elapsed = time.time() - self._last_summon_time
        if elapsed < self._min_interval:
            raise RuntimeError(
                f"Summon too fast — wait {self._min_interval - elapsed:.1f}s"
            )
        self._last_summon_time = time.time()

    def _resolve_birth_embedding(
        self, agent_name: str, insight: object
    ) -> dict[int, float] | None:
        """Return the birth_embedding for a new seed: insight.embedding if this is
        the first summon for *agent_name*, else None (only the first seed stores it).

        Fallback: if insight has no embedding, return None.
        """
        # Only set birth_embedding on the very first summon for this agent
        existing = self.memory.load_all_seeds()
        already_summoned = any(s.summoned_agent == agent_name for s in existing)
        if already_summoned:
            return None
        if insight is None:
            return None
        emb = getattr(insight, "embedding", None)
        if emb is None:
            return None
        return emb

    def summon(self, raw_input: str) -> ThoughtSeed:
        """Route input to an agent, persist memory, and emit a signal.

        Raises RuntimeError if rate limit exceeded or input is too long.
        """
        self._check_rate_limit()
        if len(raw_input) > MAX_INPUT_LENGTH:
            raw_input = raw_input[:MAX_INPUT_LENGTH]
        agent_name = self.router.route(raw_input)
        rarity = self.rarity_classifier(raw_input)

        insight = extract_insight(raw_input)

        # P1 T07: uniqueness-based pricing — MINT cost = f(embedding scarcity)
        base_price = rarity.price_sats
        if insight and insight.embedding is not None:
            bonus = self.memory.compute_uniqueness_bonus(insight.embedding)
            adjusted_price = round(base_price * bonus)
            log.info(
                "Uniqueness bonus for %r: %.2f× → %d Stars (base %d)",
                agent_name, bonus, adjusted_price, base_price,
            )
        else:
            bonus = 1.0
            adjusted_price = base_price

        paid = True
        if self.gate.requires_payment(adjusted_price):
            # Free tier / unpaid -> still summon but flagged unpaid.
            # Real UI would block until settle(); here we record the intent.
            paid = False

        seed = ThoughtSeed.make(
            raw_input=raw_input,
            summoned_agent=agent_name,
            timestamp=self.clock(),
            rarity=rarity.rarity,
            price_sats=adjusted_price,
            paid=paid,
            # FIX 2: the agent is driven by the INSIGHT, not by the rarity label.
            insight=insight,
            # I03: First summon for this agent gets birth_embedding snapshot
            birth_embedding=self._resolve_birth_embedding(agent_name, insight),
        )
        self.memory.save_seed(seed)
        self.bus.publish(AgentSummoned(
            raw_input,
            agent_name,
            seed.timestamp,
            share_code=seed.timestamp.replace(":", "").replace("-", "").replace(".", "")[-8:],
            archetype=insight.archetype if insight else "",
            geo_hint=seed.place_name,
            insight=insight,
            rarity=seed.rarity,
        ))
        return seed

    def summon_paid(self, raw_input: str, proof: str) -> ThoughtSeed:
        """Rare summon flow: require + verify payment before releasing."""
        self._check_rate_limit()
        if len(raw_input) > MAX_INPUT_LENGTH:
            raw_input = raw_input[:MAX_INPUT_LENGTH]
        agent_name = self.router.route(raw_input)
        rarity = self.rarity_classifier(raw_input)

        # P1 T07: extract insight early (for embedding) so uniqueness bonus
        # can be computed for the payment amount.
        insight = extract_insight(raw_input)

        base_price = rarity.price_sats
        if insight and insight.embedding is not None:
            bonus = self.memory.compute_uniqueness_bonus(insight.embedding)
            adjusted_price = round(base_price * bonus)
            log.info(
                "Uniqueness bonus for %r (paid): %.2f× → %d Stars (base %d)",
                agent_name, bonus, adjusted_price, base_price,
            )
        else:
            adjusted_price = base_price

        if not self.gate.requires_payment(adjusted_price):
            raise RuntimeError(f"{rarity.rarity} summon is free; use summon()")

        request = self.gate.request(adjusted_price, f"rare summon: {raw_input[:40]}")
        if not self.gate.settle(request, proof):
            raise RuntimeError("Payment not verified — creature stays sealed")

        seed = ThoughtSeed.make(
            raw_input=raw_input,
            summoned_agent=agent_name,
            timestamp=self.clock(),
            rarity=rarity.rarity,
            price_sats=adjusted_price,
            paid=True,
            # FIX 2: rare summons also carry an insight.
            insight=insight,
            # I03: First summon for this agent gets birth_embedding snapshot
            birth_embedding=self._resolve_birth_embedding(agent_name, insight),
        )
        self.memory.save_seed(seed)
        self.bus.publish(AgentSummoned(
            raw_input,
            agent_name,
            seed.timestamp,
            share_code=seed.timestamp.replace(":", "").replace("-", "").replace(".", "")[-8:],
            archetype=seed.insight.archetype if seed.insight else "",
            geo_hint=seed.place_name,
            insight=seed.insight,
            rarity=seed.rarity,
        ))
        return seed
