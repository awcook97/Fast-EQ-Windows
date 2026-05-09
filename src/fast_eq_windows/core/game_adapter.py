from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable

from .character import Character


class GameAdapter(ABC):
    """Abstract source of Character objects for the app to render.

    EQGameAdapter (the concrete EverQuest one) wraps the existing
    window_scanner; future game adapters could wrap other backends.
    """

    # Concrete subclasses MUST set this — no default is provided intentionally.
    name: str  # e.g. "everquest", "wow"

    @abstractmethod
    def start(self) -> None:
        """Begin background scanning."""

    @abstractmethod
    def stop(self) -> None:
        """Tear down background work."""

    @abstractmethod
    def request_refresh(self) -> None:
        """Hint to refresh now (e.g. user clicked Refresh)."""

    @abstractmethod
    def add_listener(self, cb: Callable[[list[Character]], None]) -> None:
        """Register a callback fired with the latest character list."""

    @abstractmethod
    def focus(self, character: Character) -> None:
        """Bring the given character's window to the foreground."""

    @abstractmethod
    def set_auto(self, enabled: bool) -> None:
        """Enable or disable periodic auto-refresh."""

    @abstractmethod
    def set_refresh_interval(self, seconds: float) -> None:
        """Update the auto-refresh interval (seconds)."""

    # Optional UI metadata — concrete subclasses may override.
    def row_label(self) -> str:
        return "Group"

    def col_labels(self) -> list[str] | None:
        """Fixed column labels, or None to derive from data."""
        return None

    def tooltip_for(self, character: Character) -> str:
        return character.display_name
