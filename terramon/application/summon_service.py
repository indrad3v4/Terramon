"""SummonService — the core use case: seed -> router -> agent -> memory -> event.

Build-via-learn (v2): adds rarity + optional payment gating without breaking
the original contract. The first three tests pass unchanged because `payment`
and `rarity_classifier` default to Nothing/Common.

Maps to:
- Phase 10/11 LLMs: classifier decides the agent
- Day 59 (ROADMAP_2027): rarity derived from thought seed
- Day 14 (LEARNING_PATH): PaymentPort gating rare summons
"""

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
    ) -> None:
        """Wire the ports and event bus."""
        self.router = IntentRouter(classifier)
        self.memory = memory
        self.bus = bus
        self.clock = clock
        self.gate = PaymentGate(payment)
        self.rarity_classifier = rarity_classifier

    def summon(self, raw_input: str) -> ThoughtSeed:
        """Route input to an agent, persist memory, and emit a signal."""
        agent_name = self.router.route(raw_input)
        rarity = self.rarity_classifier(raw_input)

        paid = True
        if self.gate.requires_payment(rarity.price_sats):
            # Free tier / unpaid -> still summon but flagged unpaid.
            # Real UI would block until settle(); here we record the intent.
            paid = False

        seed = ThoughtSeed.make(
            raw_input=raw_input,
            summoned_agent=agent_name,
            timestamp=self.clock(),
            rarity=rarity.rarity,
            price_sats=rarity.price_sats,
            paid=paid,
            # FIX 2: the agent is driven by the INSIGHT, not by the rarity label.
            insight=extract_insight(raw_input),
        )
        self.memory.save_seed(seed)
        self.bus.publish(AgentSummoned(raw_input, agent_name, seed.timestamp))
        return seed

    def summon_paid(self, raw_input: str, proof: str) -> ThoughtSeed:
        """Rare summon flow: require + verify payment before releasing."""
        agent_name = self.router.route(raw_input)
        rarity = self.rarity_classifier(raw_input)
        if not self.gate.requires_payment(rarity.price_sats):
            raise RuntimeError(f"{rarity.rarity} summon is free; use summon()")

        request = self.gate.request(rarity.price_sats, f"rare summon: {raw_input[:40]}")
        if not self.gate.settle(request, proof):
            raise RuntimeError("Payment not verified — creature stays sealed")

        seed = ThoughtSeed.make(
            raw_input=raw_input,
            summoned_agent=agent_name,
            timestamp=self.clock(),
            rarity=rarity.rarity,
            price_sats=rarity.price_sats,
            paid=True,
            # FIX 2: rare summons also carry an insight.
            insight=extract_insight(raw_input),
        )
        self.memory.save_seed(seed)
        self.bus.publish(AgentSummoned(raw_input, agent_name, seed.timestamp))
        return seed
