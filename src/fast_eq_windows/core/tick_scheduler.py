from __future__ import annotations

import itertools
import traceback
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class _Handle:
    """Opaque handle returned by every() / after().  Plugins keep this to cancel."""
    id: int
    next_fire: float
    interval: float | None  # None means one-shot
    callback: Callable[[], None]
    cancelled: bool = field(default=False)


class TickScheduler:
    """Frame-pumped timer.

    The host calls pump(now) once per render frame with a monotonic
    timestamp.  Due callbacks fire synchronously on the main thread —
    safe for DPG calls.

    Recurring callbacks reschedule themselves based on next_fire +
    interval, NOT now + interval, so drift is bounded.  If a callback
    is "behind" by more than one interval (e.g. user dragged the
    window for 2 s), it fires once and skips ahead, never spamming.
    """

    def __init__(self) -> None:
        self._handles: list[_Handle] = []
        self._id_gen = itertools.count(1)

    def every(self, seconds: float, callback: Callable[[], None]) -> _Handle:
        """Schedule a recurring callback every `seconds`.  First fire is `seconds` from now."""
        # The "now" used to schedule the first fire is whatever the
        # next pump() supplies; use 0 as a placeholder that will be
        # corrected on first pump.  Simpler: register relative to
        # the next pump's `now` by setting next_fire to a sentinel.
        # We use float("inf") as the sentinel meaning "rebase on
        # first pump".
        h = _Handle(
            id=next(self._id_gen),
            next_fire=float("inf"),
            interval=float(seconds),
            callback=callback,
        )
        h._pending_first_delay = float(seconds)  # type: ignore[attr-defined]
        self._handles.append(h)
        return h

    def after(self, seconds: float, callback: Callable[[], None]) -> _Handle:
        """One-shot callback fired `seconds` from now."""
        h = _Handle(
            id=next(self._id_gen),
            next_fire=float("inf"),
            interval=None,
            callback=callback,
        )
        h._pending_first_delay = float(seconds)  # type: ignore[attr-defined]
        self._handles.append(h)
        return h

    def cancel(self, handle: _Handle) -> None:
        handle.cancelled = True

    def pump(self, now: float) -> None:
        """Fire all due callbacks.  Called once per frame by the host."""
        # Rebase pending handles whose next_fire is the inf sentinel.
        for h in self._handles:
            if h.next_fire == float("inf"):
                delay = getattr(h, "_pending_first_delay", 0.0)
                h.next_fire = now + delay

        due: list[_Handle] = [h for h in self._handles if not h.cancelled and h.next_fire <= now]
        for h in due:
            try:
                h.callback()
            except Exception:
                print(f"[tick_scheduler] error in callback (handle {h.id}):")
                traceback.print_exc()
                h.cancelled = True
                continue
            if h.interval is None:
                h.cancelled = True  # one-shot complete
            else:
                # Drift-bounded reschedule: if we're so far behind that
                # next_fire would still be in the past, jump to now+interval.
                h.next_fire += h.interval
                if h.next_fire <= now:
                    h.next_fire = now + h.interval

        # Garbage-collect cancelled handles to keep the list small.
        self._handles = [h for h in self._handles if not h.cancelled]

    def clear(self) -> None:
        """Cancel everything — used at app shutdown / plugin reload."""
        for h in self._handles:
            h.cancelled = True
        self._handles.clear()
