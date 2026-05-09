from __future__ import annotations

from typing import Callable

from ..core.character import Character
from ..core.game_adapter import GameAdapter
from ..window_scanner import EQChar, WindowSnapshot, focus_window


class EQGameAdapter(GameAdapter):
    """EverQuest game adapter — wraps the existing wmctrl/xdotool window scanner."""

    name = "everquest"

    def __init__(self, refresh_interval: float = 3600.0) -> None:
        self._snapshot = WindowSnapshot(refresh_interval=refresh_interval)

    # Expose the underlying snapshot so app.py can still tweak refresh_interval
    # via the existing input_float callback.  Phase 3 may move this onto a
    # standardized AppContext API.
    @property
    def snapshot(self) -> WindowSnapshot:
        return self._snapshot

    def start(self) -> None:
        self._snapshot.start()

    def stop(self) -> None:
        self._snapshot.stop()

    def request_refresh(self) -> None:
        self._snapshot.request_refresh()

    def set_auto(self, enabled: bool) -> None:
        self._snapshot.set_auto(enabled)

    def set_refresh_interval(self, seconds: float) -> None:
        self._snapshot.refresh_interval = float(seconds)

    def add_listener(self, cb: Callable[[list[Character]], None]) -> None:
        # WindowSnapshot fires with list[EQChar]; EQChar satisfies Character.
        self._snapshot.add_listener(cb)

    def focus(self, character: Character) -> None:
        focus_window(character.window_id)

    def row_label(self) -> str:
        return "Server"

    def tooltip_for(self, character: Character) -> str:
        # Reproduce app.py:295-301 exactly — the "Off" anon-mode branch.
        # The anon-mode tooltip variant stays in app.py because it's
        # presentation, not adapter concern.
        c = character
        # Use raw-dict access so this works through the Protocol without
        # casting to EQChar.
        level = c.raw.get("level", "?")
        eq_class = c.raw.get("eq_class", "?")
        zone = c.raw.get("zone", "")
        instance = c.raw.get("instance", 0)
        tail = f"  ({instance})" if instance else ""
        return (
            f"{c.display_name}.{c.group_row}\n"
            f"Lvl {level} {eq_class}\n"
            f"{zone}{tail}"
        )
