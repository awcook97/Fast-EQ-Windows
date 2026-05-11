"""Fast_EQ_Windows plugin starter.

Copy this folder, rename it (for example `my_plugin`), then enable it by
adding the folder name to `~/.config/fast_eq_windows/plugins.json`:

    {"enabled": ["my_plugin"], "settings": {}}

DearPyGui calls must stay on the main thread.  If you use worker threads for
HTTP/TCP/file watching, push results into `queue.Queue` and drain in on_tick().
"""

from __future__ import annotations

from typing import Any

from fast_eq_windows.core.plugin import AppContext, Plugin


class ExamplePlugin(Plugin):
    """Copy-paste starter that exercises no UI by default."""

    name = "example"
    version = "0.1.0"
    requires: list[str] = []

    def on_load(self, ctx: AppContext) -> None:
        """Called once after the plugin is imported and enabled."""
        self.ctx = ctx
        ctx.log("loaded")

        # Settings are namespaced to this plugin in plugins.json.
        first_run = ctx.settings.get("first_run", True) if ctx.settings else True
        if first_run and ctx.settings:
            ctx.settings.set("first_run", False)

        # Add a menu item under Plugins.  The callback runs on the UI thread.
        ctx.register_menu("Example: print character count", self._print_count)

        # Optional: subscribe to events directly.
        if ctx.events:
            ctx.events.subscribe("button.clicked", self._on_button_clicked)

    def on_unload(self) -> None:
        """Close sockets, stop threads, cancel timers, and unsubscribe here."""
        if getattr(self, "ctx", None) and self.ctx.events:
            self.ctx.events.unsubscribe("button.clicked", self._on_button_clicked)
        self.ctx.log("unloaded")

    def on_snapshot(self, characters: list[Any]) -> None:
        """Called after a new character snapshot is rendered."""

    def on_button_create(self, button: Any) -> None:
        """Called when a CharacterButton enters the registry."""
        # Example APIs:
        # button.set_overlay_bar("health", 0.75, (0, 220, 0, 180))
        # button.set_status_badge("OK", (0, 120, 0, 220))
        # button.set_dim(0.25)

    def on_button_destroy(self, button: Any) -> None:
        """Called before a CharacterButton is destroyed."""

    def on_tick(self, dt: float) -> None:
        """Called every rendered frame on the main thread."""

    def on_event(self, name: str, payload: dict) -> None:
        """Called for every host/plugin event published on the EventBus."""

    def _print_count(self, *_args) -> None:
        self.ctx.log(f"{len(self.ctx.characters())} character(s) visible to plugins")

    def _on_button_clicked(self, payload: dict) -> None:
        self.ctx.log(f"clicked {payload.get('char_id')}")
