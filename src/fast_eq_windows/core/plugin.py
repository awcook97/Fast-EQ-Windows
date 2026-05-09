"""Plugin base class and the AppContext passed into `on_load`.

This module is the public surface plugins import.  Everything else under
`fast_eq_windows.core` is host plumbing that plugins should treat as private.

Three types live here:

* `Plugin` — subclass this and override hooks.
* `AppPaths` — the on-disk locations a plugin may read/write.
* `AppContext` — the bound runtime handle each plugin receives in `on_load`.

All plugin hooks run on the DearPyGui thread.  See `docs/PLUGINS.md` for the
threading rules and worker pattern.
"""
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

    Class attributes:
        name: Stable identifier used for settings namespacing and logs.
            Should match (or be a sensible alias of) the plugin folder name.
        version: Free-form version string.  Not parsed by the host.
        requires: Folder names of other plugins that must load first.
            Cycles or missing entries are warned and don't block loading.

    Lifecycle (in dispatch order):
        on_load            once, after import + enable
        on_button_create   per button as the table is built (and replayed on reload)
        on_snapshot        after every accepted character snapshot
        on_button_destroy  per button before the table is rebuilt or app exits
        on_tick            once per rendered frame
        on_event           for every event published on the EventBus
        on_unload          once, before reload or app shutdown
    """

    name: str = "unnamed"
    version: str = "0.0.0"
    requires: list[str] = []  # other plugin names this depends on

    def on_load(self, ctx: "AppContext") -> None:
        """Called once after import.  Stash `ctx`, register menus / events / timers here.

        Anything created here (subscriptions, scheduler handles, threads,
        sockets) must be torn down in `on_unload` so reload is clean.
        """

    def on_unload(self) -> None:
        """Called before reload and at app shutdown.  Release everything you own.

        After this returns the host drops its reference to the plugin.
        Background threads kept alive past this point will outlive reload
        and require an app restart.
        """

    def on_snapshot(self, characters: list["Character"]) -> None:
        """Called after a fresh character snapshot is rendered.

        `characters` is a fresh list owned by the host — safe to iterate but
        do not mutate.  This fires *after* `on_button_create` for any new
        buttons in the same snapshot.
        """

    def on_button_create(self, button: "CharacterButton") -> None:
        """Called when a CharacterButton enters the registry.

        Apply per-button decorations (overlay bars, badges, dim, themes)
        here, ideally keyed off `button.char.id` so plugin state survives
        a table rebuild.
        """

    def on_button_destroy(self, button: "CharacterButton") -> None:
        """Called before a CharacterButton is removed.

        The DPG widgets are still alive when this fires.  Don't hold a
        reference past this call — the underlying items will be deleted
        immediately afterward.
        """

    def on_tick(self, dt: float) -> None:
        """Called once per rendered frame on the main thread.

        `dt` is seconds since the previous tick (monotonic).  Drain any
        worker-thread queues here and apply the results to buttons.
        """

    def on_event(self, name: str, payload: dict) -> None:
        """Called for every event published on the EventBus, host or plugin.

        Prefer `ctx.events.subscribe(name, ...)` for targeted listening;
        this hook is convenient for cross-cutting observers (logging,
        metrics) that want every event without enumerating names.
        """


@dataclass
class AppPaths:
    """Filesystem locations exposed to plugins via `AppContext.paths`."""

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

    # _menu_register: takes (label, callback), returns the DPG menu-item id
    # (DearPyGui returns int or str, both are valid item handles).
    _menu_register: Callable[[str, Callable], int | str]

    events: "EventBus"
    scheduler: "TickScheduler"
    settings: "SettingsNamespace"

    def characters(self) -> list["Character"]:
        """Return a fresh snapshot of the current character list."""
        return self._characters_provider()

    def register_menu(self, label: str, callback: Callable) -> int | str:
        """Add a menu item under the host's "Plugins" menu."""
        return self._menu_register(label, callback)

    def log(self, msg: str) -> None:
        print(f"[{self.plugin_name}] {msg}")
