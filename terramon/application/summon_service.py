"""SummonService — the core use case: seed → router → agent → memory → event."""

from terramon.application.intent_router import IntentRouter
from terramon.domain.thought_seed import ThoughtSeed
from terramon.events.agent_summoned import AgentSummoned
from terramon.events.bus import EventBus
from terramon.ports.classifier_port import ClassifierPort
from terramon.ports.memory_port import MemoryPort


class SummonService:
    """Orchestrates the thought-seed summon loop."""

    def __init__(
        self,
        classifier: ClassifierPort,
        memory: MemoryPort,
        bus: EventBus,
        clock: callable[[], str],
    ) -> None:
        """Wire the ports and event bus."""
        self.router = IntentRouter(classifier)
        self.memory = memory
        self.bus = bus
        self.clock = clock

    def summon(self, raw_input: str) -> ThoughtSeed:
        """Route input to an agent, persist memory, and emit a signal."""
        agent_name = self.router.route(raw_input)
        seed = ThoughtSeed(
            raw_input=raw_input,
            summoned_agent=agent_name,
            timestamp=self.clock(),
        )
        self.memory.save_seed(seed)
        self.bus.publish(AgentSummoned(raw_input, agent_name, seed.timestamp))
        return seed
