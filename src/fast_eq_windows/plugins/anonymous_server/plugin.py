"""Anonymous server plugin for Fast_EQ_Windows.

Anonymizes button names and presents every server as "Norrath" while leaving
classes visible.  The plugin is deterministic per window id, matching the app's
built-in anon-name style without requiring the app's anon dropdown.
"""

from __future__ import annotations

import random
from typing import Any

import dearpygui.dearpygui as dpg

from fast_eq_windows.core.plugin import AppContext, Plugin

_TABLE_CONTAINER = "eq_table_container"
_CONSONANTS = "bcdfghjklmnprstvwxz"
_VOWELS = "aeiou"


def _anon_name(window_id: int) -> str:
    rng = random.Random(window_id)
    length = rng.randint(5, 9)
    return "".join(
        rng.choice(_CONSONANTS if i % 2 == 0 else _VOWELS) for i in range(length)
    ).capitalize()


class AnonymousServerPlugin(Plugin):
    """Anon names + Norrath server labels, implemented as a plugin."""

    name = "anonymous_server"
    version = "0.1.0"
    requires: list[str] = []

    def on_load(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.server_name = str(ctx.settings.get("server_name", "Norrath"))
        self.active = bool(ctx.settings.get("active", True))
        self._last_servers: list[str] = []
        self._menu_id = ctx.register_menu("Anonymous Server: Toggle", self._toggle)
        self._apply_all()
        ctx.log(f"loaded ({'active' if self.active else 'inactive'}, server={self.server_name!r})")

    def on_unload(self) -> None:
        self._restore_all()
        self.ctx.log("unloaded")

    def on_snapshot(self, characters: list[Any]) -> None:
        self._last_servers = sorted({c.group_row for c in characters})
        self._apply_all()

    def on_button_create(self, button: Any) -> None:
        if self.active:
            self._apply_button(button)

    def _toggle(self, *_args: Any) -> None:
        self.active = not self.active
        self.ctx.settings.set("active", self.active)
        self.ctx.settings.save()
        if self.active:
            self._apply_all()
        else:
            self._restore_all()
        self.ctx.log("active" if self.active else "inactive")

    def _apply_all(self) -> None:
        if not self.active:
            return
        self._last_servers = sorted({c.group_row for c in self.ctx.characters()})
        for button in self.ctx.buttons.all():
            self._apply_button(button)
        self._set_server_row_labels(self.server_name)

    def _restore_all(self) -> None:
        for button in self.ctx.buttons.all():
            self._restore_button(button)
        self._restore_server_row_labels()

    def _apply_button(self, button: Any) -> None:
        char = button.char
        anon = _anon_name(char.window_id)
        button.set_label(anon)
        button.set_tooltip(self._tooltip_for(char, anon, self.server_name))
        button.set_meta("anonymous_server.anon_name", anon)

    def _restore_button(self, button: Any) -> None:
        char = button.char
        button.set_label(char.display_name)
        button.set_tooltip(self._tooltip_for(char, char.display_name, char.group_row))
        button.set_meta("anonymous_server.anon_name", None)

    def _tooltip_for(self, char: Any, display_name: str, display_server: str) -> str:
        level = char.raw.get("level", "?")
        eq_class = char.raw.get("eq_class", char.group_col)
        zone = char.raw.get("zone", "")
        instance = char.raw.get("instance", 0)
        tail = f"  ({instance})" if instance else ""
        return (
            f"{display_name}.{display_server}\n"
            f"Lvl {level} {eq_class}\n"
            f"{zone}{tail}"
        )

    def _set_server_row_labels(self, text: str) -> None:
        for item in self._walk_items(_TABLE_CONTAINER):
            try:
                value = dpg.get_value(item)
            except Exception:
                continue
            if value in self._last_servers:
                dpg.set_value(item, text)

    def _restore_server_row_labels(self) -> None:
        if not self._last_servers:
            self._last_servers = sorted({c.group_row for c in self.ctx.characters()})
        if not self._last_servers:
            return

        replacement_iter = iter(self._last_servers)
        for item in self._walk_items(_TABLE_CONTAINER):
            try:
                value = dpg.get_value(item)
            except Exception:
                continue
            if value != self.server_name:
                continue
            try:
                dpg.set_value(item, next(replacement_iter))
            except StopIteration:
                break

    def _walk_items(self, root: int | str) -> list[int | str]:
        if not dpg.does_item_exist(root):
            return []

        found: list[int | str] = []
        stack: list[int | str] = [root]
        while stack:
            item = stack.pop()
            found.append(item)
            try:
                children_by_slot: Any = dpg.get_item_children(item)
            except Exception:
                continue
            if isinstance(children_by_slot, dict):
                child_groups = children_by_slot.values()
            elif isinstance(children_by_slot, list):
                child_groups = [children_by_slot]
            else:
                child_groups = []
            for children in child_groups:
                stack.extend(reversed(children))
        return found
