from __future__ import annotations

import traceback
from collections import defaultdict
from typing import Callable


class EventBus:
    """Synchronous publish-subscribe bus.

    Plugins subscribe to event names; the host or other plugins publish
    payloads that fan out to all subscribers.  Per-subscriber try/except
    means one bad listener can't block the rest.

    The host emits these built-in events:
        snapshot.updated   payload={"characters": list[Character]}
        button.created     payload={"button": CharacterButton}
        button.destroyed   payload={"button": CharacterButton}
        button.clicked     payload={"char_id": str, "window_id": int}
        app.shutdown       payload={}

    Plugins are encouraged to namespace their own events under
    "<plugin_name>.<event>" (e.g. health.update, eqbc.send).
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)
        self._all_subscribers: list[Callable[[str, dict], None]] = []

    def subscribe(self, event_name: str, callback: Callable[[dict], None]) -> None:
        self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable[[dict], None]) -> None:
        try:
            self._subscribers[event_name].remove(callback)
        except (KeyError, ValueError):
            pass

    def subscribe_all(self, callback: Callable[[str, dict], None]) -> None:
        """Subscribe to every event.  Used by the host to drive Plugin.on_event."""
        self._all_subscribers.append(callback)

    def unsubscribe_all(self, callback: Callable[[str, dict], None]) -> None:
        try:
            self._all_subscribers.remove(callback)
        except ValueError:
            pass

    def publish(self, event_name: str, payload: dict | None = None) -> None:
        """Fan out to subscribers synchronously.  Exceptions are logged
        per-subscriber and don't propagate."""
        if payload is None:
            payload = {}
        for cb in list(self._subscribers.get(event_name, [])):
            try:
                cb(payload)
            except Exception:
                print(f"[event_bus] error in subscriber for '{event_name}':")
                traceback.print_exc()
        for cb in list(self._all_subscribers):
            try:
                cb(event_name, payload)
            except Exception:
                print(f"[event_bus] error in all-event subscriber for '{event_name}':")
                traceback.print_exc()

    def clear(self) -> None:
        """Remove all subscribers — used at app shutdown."""
        self._subscribers.clear()
        self._all_subscribers.clear()
