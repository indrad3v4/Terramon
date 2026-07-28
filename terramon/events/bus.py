"""In-process pub/sub event bus for agent signals.

Audit fix (Phase 0): handler failures are isolated so one broken subscriber
does not crash other subscribers listening to the same event type.

Phase 11 (Alignment): adds middleware support — pre-processing layers that can
inspect, filter, or annotate events before they reach subscribed handlers.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from terramon.events.agent_summoned import AgentSummoned

log = logging.getLogger("terramon.bus")

# A middleware is a callable that receives an event and returns (event, should_dispatch).
# Returning should_dispatch=False drops the event before it reaches handlers.
Middleware = Callable[[Any], tuple[Any, bool]]


@dataclass
class _MiddlewareEntry:
    """Registered middleware with optional event-type filter."""
    fn: Middleware
    event_type: type | None  # None = run on all events


class EventBus:
    """Simple synchronous event bus with middleware support.

    Middleware runs in registration order before any handlers. Each middleware
    can modify the event or drop it (return False for the second tuple element).
    """

    def __init__(self) -> None:
        """Create an empty event bus."""
        self._handlers: dict[type, list[Callable[[Any], None]]] = {}
        self._middleware: list[_MiddlewareEntry] = []

    # ── Middleware ─────────────────────────────────────────────────────

    def add_middleware(
        self, fn: Middleware, event_type: type | None = None
    ) -> None:
        """Register a middleware function.

        Args:
            fn: Callable(event) -> (event, should_dispatch).
            event_type: Optional — only run this middleware for the given
                        event type. None means run on every event.
        """
        self._middleware.append(_MiddlewareEntry(fn=fn, event_type=event_type))

    def _run_middleware(self, event: object) -> tuple[object, bool]:
        """Run all applicable middleware on an event.

        Returns (modified_event, should_dispatch).
        """
        modified = event
        for entry in self._middleware:
            if entry.event_type is not None and not isinstance(modified, entry.event_type):
                continue
            try:
                modified, should_dispatch = entry.fn(modified)
                if not should_dispatch:
                    log.info("Middleware %s dropped event %s", entry.fn.__name__, type(modified).__name__)
                    return modified, False
            except Exception:
                log.exception("Middleware %s failed — allowing event through", entry.fn.__name__)
        return modified, True

    # ── Sub/Pub ────────────────────────────────────────────────────────

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        """Register a handler for a given event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: object) -> None:
        """Dispatch an event to all subscribed handlers.

        Middleware runs first (in registration order). If middleware drops the
        event, no handlers execute. Each handler runs independently — a single
        failure does not prevent other handlers from executing.
        """
        # Run middleware
        modified, should_dispatch = self._run_middleware(event)
        if not should_dispatch:
            return

        # Dispatch to handlers
        for handler in self._handlers.get(type(modified), []):
            try:
                handler(modified)
            except Exception:
                log.exception("Event handler %s failed for %s", handler, type(modified).__name__)


# ---------------------------------------------------------------------------
# Built-in safety middleware
# ---------------------------------------------------------------------------

# Simple keyword-based harmful content detection (Phase 11: Alignment).
# These are basic patterns — a production system would use a classifier.
_HARMFUL_PATTERNS: list[tuple[str, str]] = [
    # Violence patterns
    ("kill everyone", "violence"),
    ("i will hurt", "violence"),
    ("destroy them", "violence"),
    ("massacre", "violence"),
    ("torture", "violence"),
    # Hate speech patterns
    ("hate all", "hate_speech"),
    ("exterminate", "hate_speech"),
    ("eliminate the", "hate_speech"),
    ("superior race", "hate_speech"),
    # Self-harm
    ("hurt myself", "self_harm"),
    ("end my life", "self_harm"),
    ("i want to die", "self_harm"),
]


def content_safety_middleware(event: object) -> tuple[object, bool]:
    """Check AgentSummoned events for harmful content in the thought seed.

    Flags the event with safety_flagged and safety_reason but does NOT drop it
    (the event still reaches handlers for observability).

    Returns (event, True) — always dispatches, never blocks.
    """
    if not isinstance(event, AgentSummoned):
        return event, True

    lowered = event.thought_seed.lower()
    for pattern, category in _HARMFUL_PATTERNS:
        if pattern in lowered:
            event.safety_flagged = True
            event.safety_reason = f"content_safety: {category} keyword '{pattern}' detected"
            log.warning(
                "Content safety flag on AgentSummoned[%s]: %s",
                event.agent_name, event.safety_reason,
            )
            break

    return event, True
