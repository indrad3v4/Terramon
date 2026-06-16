"""In-process pub/sub event bus for agent signals."""

from collections.abc import Callable
from typing import Any


class EventBus:
    """Simple synchronous event bus."""

    def __init__(self) -> None:
        """Create an empty event bus."""
        self._handlers: dict[type, list[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        """Register a handler for a given event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: object) -> None:
        """Dispatch an event to all subscribed handlers."""
        for handler in self._handlers.get(type(event), []):
            handler(event)
