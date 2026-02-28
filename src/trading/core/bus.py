"""In-process event bus for connecting pipeline stages."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


class EventBus:
    """Simple pub/sub event bus. Handlers are called synchronously."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        self._handlers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        self._handlers[topic].remove(handler)

    def publish(self, topic: str, event: Any) -> None:
        for handler in self._handlers[topic]:
            handler(event)
