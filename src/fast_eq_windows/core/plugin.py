from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .button_registry import ButtonRegistry
    from .character import Character
    from .character_button import CharacterButton
    from .game_adapter import GameAdapter
    from .event_bus import EventBus
    from .tick_scheduler import TickScheduler
    from .settings_store import SettingsNamespace


class Plugin:
    """Base class for Fast_EQ_Windows plugins.

    All hooks are optional — override only what you need.  Default
    implementations are no-ops so the host can dispatch unconditionally.
    """

    name: str = "unnamed"
    version: str = "0.0.0"
    requires: list[str] = []  # other plugin names this depends on

    def on_load(self, ctx: "AppContext") -> None:
        pass

    def on_unload(self) -> None:
        pass

    def on_snapshot(self, characters: list["Character"]) -> None:
        pass

    def on_button_create(self, button: "CharacterButton") -> None:
        pass

    def on_button_destroy(self, button: "CharacterButton") -> None:
        pass

    def on_tick(self, dt: float) -> None:
        pass

    def on_event(self, name: str, payload: dict) -> None:
        pass


@dataclass
class AppPaths:
    plugin_dir: Path        # this plugin's own folder (e.g. ~/.config/fast_eq_windows/plugins/foo/)
    data_dir: Path          # ~/.config/fast_eq_windows/  — shared across plugins
    config_path: Path       # ~/.config/fast_eq_windows/plugins.json


@dataclass
class AppContext:
    """The interface a plugin uses to talk to the host application.

    Each plugin gets its own bound AppContext (paths.plugin_dir is
    plugin-specific; settings is namespaced by plugin name; log prefix
    includes the plugin name).
    """

    plugin_name: str
    adapter: "GameAdapter"
    buttons: "ButtonRegistry"
    paths: AppPaths

    # _characters_provider returns a snapshot list each time it's called.
    # Use a callable so the live underlying list isn't shared mutably.
    _characters_provider: Callable[[], list["Character"]]

    # _menu_register: takes (label, callback), returns the DPG menu-item id.
    _menu_register: Callable[[str, Callable], int]

    events: "EventBus"
    scheduler: "TickScheduler"
    settings: "SettingsNamespace"

    def characters(self) -> list["Character"]:
        """Return a fresh snapshot of the current character list."""
        return self._characters_provider()

    def register_menu(self, label: str, callback: Callable) -> int:
        """Add a menu item under the host's "Plugins" menu."""
        return self._menu_register(label, callback)

    def log(self, msg: str) -> None:
        print(f"[{self.plugin_name}] {msg}")
