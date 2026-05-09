from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .character_button import CharacterButton


class ButtonRegistry:
    """Lookup index for live CharacterButton instances.

    The host (App) calls _register / _unregister as buttons come and go.
    Plugins query via the public methods.

    Phase 5 will hook this into the EventBus to publish button.created /
    button.destroyed events on register/unregister.  For Phase 3 the
    registry is purely a lookup table.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, "CharacterButton"] = {}      # char.id -> button
        self._by_window: dict[int, "CharacterButton"] = {}  # window_id -> button

    # ------------------------------------------------------------------
    # Public API — plugins use these
    # ------------------------------------------------------------------

    def get(self, char_id: str) -> Optional["CharacterButton"]:
        return self._by_id.get(char_id)

    def by_window_id(self, window_id: int) -> Optional["CharacterButton"]:
        return self._by_window.get(window_id)

    def all(self) -> list["CharacterButton"]:
        """All currently registered buttons.  Snapshot list; safe to iterate."""
        return list(self._by_id.values())

    def for_class(self, group_col: str) -> list["CharacterButton"]:
        """All buttons whose underlying character has the given group_col
        (EQ: class)."""
        return [b for b in self._by_id.values() if b.char.group_col == group_col]

    # ------------------------------------------------------------------
    # Internal — host (App) only
    # ------------------------------------------------------------------

    def _register(self, button: "CharacterButton") -> None:
        char = button.char
        self._by_id[char.id] = button
        self._by_window[char.window_id] = button

    def _unregister(self, button: "CharacterButton") -> None:
        char = button.char
        self._by_id.pop(char.id, None)
        self._by_window.pop(char.window_id, None)

    def _clear(self) -> None:
        """Clear all entries — used when the table is fully rebuilt."""
        self._by_id.clear()
        self._by_window.clear()
