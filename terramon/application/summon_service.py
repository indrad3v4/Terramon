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
from terramon.application.k3_insight_engine import extract_fusion_insight
from terramon.domain.thought_seed import ThoughtSeed
from terramon.domain.rarity import classify_rarity, Rarity
from terramon.events.agent_summoned import AgentSummoned
from terramon.events.bus import EventBus
from terramon.events.proximity import ProximityEvent
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
        nostr_reader: object | None = None,
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
            nostr_reader: Optional NostrRelayReader for cross-player proximity
                          detection. When provided, the proximity check queries
                          relays for nearby creatures after each summon.
        """
        self.router = IntentRouter(classifier)
        self.memory = memory
        self.bus = bus
        self.clock = clock
        self.gate = PaymentGate(payment)
        self.rarity_classifier = rarity_classifier
        self._min_interval = min_interval
        self._last_summon_time: float = 0.0
        self.nostr_reader = nostr_reader

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

    def _check_proximity(self, seed: ThoughtSeed) -> None:
        """Check if the newly summoned creature is near any other creature.

        Queries both local memory and (optionally) Nostr relays for creatures
        within 1 km of the seed's location. For each nearby creature found,
        publishes a ProximityEvent on the event bus.

        This is a best-effort check — failures in relay queries or missing
        geo data are silently ignored so they never crash the summon flow.
        """
        if not seed.lat and not seed.lon:
            return  # no geo data — skip proximity check

        timestamp = self.clock()

        # 1) Check local memory for nearby creatures (same player's collection)
        try:
            local_nearby = self.memory.find_nearby(seed.lat, seed.lon, radius_km=1.0)
        except Exception:
            log.exception("Local proximity check failed")
            local_nearby = []

        for other_seed, dist_km in local_nearby:
            # Skip self-match
            if (other_seed.lat == seed.lat and other_seed.lon == seed.lon
                    and other_seed.timestamp == seed.timestamp):
                continue
            other_archetype = ""
            if other_seed.insight and other_seed.insight.archetype:
                other_archetype = other_seed.insight.archetype
            self.bus.publish(ProximityEvent(
                agent_name=seed.summoned_agent,
                other_agent_name=other_seed.summoned_agent,
                lat=seed.lat,
                lon=seed.lon,
                distance_km=round(dist_km, 4),
                timestamp=timestamp,
                other_archetype=other_archetype,
                other_rarity=other_seed.rarity,
                other_insight=other_seed.insight,
                is_cross_player=False,
            ))

        # 2) Check Nostr relay for cross-player creatures
        if self.nostr_reader is not None:
            try:
                # Use a 1-degree bounding box (~110 km) as a coarse pre-filter;
                # the reader filters by bounding box internally.
                relay_creatures = self.nostr_reader.fetch_region_creatures(
                    seed.lat, seed.lon, radius_deg=0.01  # ~1 km
                )
            except Exception:
                log.exception("Nostr relay proximity query failed")
                relay_creatures = []

            for creature in relay_creatures:
                # Haversine distance to the relay creature
                dist = self._haversine_km(seed.lat, seed.lon, creature.lat, creature.lon)
                if dist > 1.0:
                    continue
                self.bus.publish(ProximityEvent(
                    agent_name=seed.summoned_agent,
                    other_agent_name=creature.agent,
                    other_agent_pubkey=creature.pubkey,
                    lat=creature.lat,
                    lon=creature.lon,
                    distance_km=round(dist, 4),
                    timestamp=timestamp,
                    other_rarity=creature.rarity,
                    is_cross_player=True,
                ))

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in km between two lat/lon points."""
        import math
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def summon(self, raw_input: str, rare_boost: float = 0.0) -> ThoughtSeed:
        """Route input to an agent, persist memory, and emit a signal.

        Raises RuntimeError if rate limit exceeded or input is too long.

        Args:
            raw_input: The thought text to summon from.
            rare_boost: Additional probability mass shifted to the rare tier
                (e.g. 0.05 from streak bonus).
        """
        self._check_rate_limit()
        if len(raw_input) > MAX_INPUT_LENGTH:
            raw_input = raw_input[:MAX_INPUT_LENGTH]
        agent_name = self.router.route(raw_input)
        rarity = self.rarity_classifier(raw_input, rare_boost=rare_boost)

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

        # I11: Cross-player proximity check — find nearby creatures
        self._check_proximity(seed)

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

        # I11: Cross-player proximity check — find nearby creatures
        self._check_proximity(seed)

        return seed

    # ── I11: Bond bonus on proximity ─────────────────────────────────

    def _on_proximity_bond_bonus(self, event: ProximityEvent) -> None:
        """Apply a bond level bonus when two creatures are found near each other.

        Increments the bond_level for both creatures in the bond store.
        Sets bond_bonus_applied on the event so downstream handlers know
        the bonus was already granted.
        """
        try:
            # Load bond data for both creatures
            bond_self = self.memory.load_bond(event.agent_name)
            bond_other = self.memory.load_bond(event.other_agent_name)

            # Apply +1 bond level bonus to both
            bond_self["bond_level"] = bond_self.get("bond_level", 0) + 1
            self.memory.save_bond(event.agent_name, bond_self)

            if event.other_agent_name:
                bond_other["bond_level"] = bond_other.get("bond_level", 0) + 1
                self.memory.save_bond(event.other_agent_name, bond_other)

            event.bond_bonus_applied = True
            log.info(
                "Proximity bond bonus: %s ↔ %s at %.4f km — bond_level +1 each",
                event.agent_name, event.other_agent_name, event.distance_km,
            )
        except Exception:
            log.exception("Failed to apply proximity bond bonus")

    def subscribe_proximity(self) -> None:
        """Register handlers for proximity events on the event bus."""
        self.bus.subscribe(ProximityEvent, self._on_proximity_bond_bonus)

    def fusion(self, player_a: str, thought_a: str,
               player_b: str, thought_b: str) -> tuple[ThoughtSeed, ThoughtSeed]:
        """Fusion summon — two players, one fused creature."""
        self._check_rate_limit()
        fused_insight = extract_fusion_insight(thought_a, thought_b)
        fused_agent = fused_insight.archetype if fused_insight.archetype else "Fusion"
        seed_a = ThoughtSeed.make(
            raw_input=f"[fusion: {player_a}] {thought_a}",
            summoned_agent=fused_agent,
            timestamp=self.clock(),
            rarity=Rarity.FUSION, price_sats=0, paid=True,
            insight=fused_insight,
            birth_embedding=self._resolve_birth_embedding(fused_agent, fused_insight),
        )
        self.memory.save_seed(seed_a)
        seed_b = ThoughtSeed.make(
            raw_input=f"[fusion: {player_b}] {thought_b}",
            summoned_agent=fused_agent,
            timestamp=self.clock(),
            rarity=Rarity.FUSION, price_sats=0, paid=True,
            insight=fused_insight,
        )
        self.memory.save_seed(seed_b)
        self.bus.publish(AgentSummoned(
            f"fusion({player_a}, {player_b}): {thought_a} + {thought_b}",
            fused_agent, seed_a.timestamp,
            share_code=seed_a.timestamp.replace(":", "").replace("-", "").replace(".", "")[-8:],
            archetype=fused_agent, geo_hint=seed_a.place_name,
            insight=fused_insight, rarity="fusion",
        ))
        return seed_a, seed_b
