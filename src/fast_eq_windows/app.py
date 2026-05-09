import math
import queue
import random
import time
from pathlib import Path

import dearpygui.dearpygui as dpg

from .adapters.eq_adapter import EQGameAdapter
from .class_colors import build_class_theme
from .core.button_registry import ButtonRegistry
from .core.character import Character
from .core.character_button import CharacterButton
from .core.event_bus import EventBus
from .core.game_adapter import GameAdapter
from .core.plugin import AppContext, AppPaths, Plugin
from .core.plugin_loader import PluginHost
from .core.settings_store import SettingsStore
from .core.tick_scheduler import TickScheduler
from .core.plugin_paths import (
    bootstrap as _bootstrap_plugin_dirs,
    user_config_path,
    user_plugins_dir,
)
from .DearPyGui_EditThemePlugin.EditThemePlugin import EditThemePlugin
from .DearPyGui_EditThemePlugin.ChooseFontsPlugin import ChooseFontsPlugin

_BUTTON_WIDTH = 130
_BUTTON_HEIGHT = 38
_TABLE_CONTAINER = "eq_table_container"
_STATUS_TEXT = "eq_status_text"

_EQ_CLASSES = [
    "Warrior", "Cleric", "Paladin", "Ranger", "Shadow Knight", "Druid",
    "Monk", "Bard", "Rogue", "Shaman", "Necromancer", "Wizard",
    "Magician", "Enchanter", "Beastlord", "Berserker",
]
_ANON_OPTS = ["Off", "Anon: Names", "Anon: Names+Classes", "Oops: Only Paladins", "Full Anon: Norrath"]

_CHROME_H = 22 + 22 + 32 + 6   # menu bar + spacer + toolbar + separator
_TABLE_HEADER_H = 26
_BUTTON_ROW_H = _BUTTON_HEIGHT + 4

_CONSONANTS = "bcdfghjklmnprstvwxz"
_VOWELS = "aeiou"


def _anon_name(window_id: int) -> str:
    rng = random.Random(window_id)
    length = rng.randint(5, 9)
    return "".join(
        rng.choice(_CONSONANTS if i % 2 == 0 else _VOWELS) for i in range(length)
    ).capitalize()


def _anon_class(window_id: int) -> str:
    return random.Random(window_id ^ 0xDEAD).choice(_EQ_CLASSES)


class App:
    def __init__(self) -> None:
        _bootstrap_plugin_dirs()
        self._characters: list[Character] = []
        self._buttons: list[CharacterButton] = []
        self._class_themes: dict[str, int] = {}
        self._result_queue: queue.Queue[list[Character]] = queue.Queue()
        self._anon = "Off"
        self._search = ""
        self._adapter: GameAdapter = EQGameAdapter(refresh_interval=3600.0)
        self._adapter.add_listener(self._on_snapshot)

        self._button_registry = ButtonRegistry()
        self._events = EventBus()
        self._scheduler = TickScheduler()
        self._settings = SettingsStore(path=user_config_path(), scheduler=self._scheduler)
        self._plugins_menu_id: int | None = None
        self._plugin_host = PluginHost(
            plugins_dir=user_plugins_dir(),
            ctx_factory=self._make_plugin_context,
        )
        self._last_tick: float = 0.0

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="Fast EQ Windows", width=600, height=300, min_width=500, min_height=300)

        self._setup_ui()

        dpg.setup_dearpygui()
        dpg.set_primary_window("main_window", True)
        dpg.show_viewport()

        self._load_plugins()

        self._adapter.start()
        self._last_tick = time.monotonic()

        while dpg.is_dearpygui_running():
            latest: list[Character] | None = None
            while True:
                try:
                    latest = self._result_queue.get_nowait()
                except queue.Empty:
                    break
            if latest is not None:
                self._characters = latest
                self._rebuild_table()
                self._plugin_host.dispatch("on_snapshot", list(self._characters))
                self._events.publish("snapshot.updated", {"characters": list(self._characters)})

            now = time.monotonic()
            dt = now - self._last_tick
            self._last_tick = now
            self._scheduler.pump(now)
            self._plugin_host.dispatch("on_tick", dt)

            dpg.render_dearpygui_frame()

        self._events.publish("app.shutdown", {})
        self._plugin_host.unload_all()
        self._scheduler.clear()
        self._events.clear()
        self._adapter.stop()
        dpg.destroy_context()

    # ------------------------------------------------------------------
    # Plugin host wiring
    # ------------------------------------------------------------------

    def _load_plugins(self) -> None:
        """Discover plugins from disk and load the ones enabled in plugins.json."""
        self._plugin_host.discover()
        self._plugin_host.load(self._settings.enabled_plugins)

    def _make_plugin_context(self, plugin: Plugin, plugin_dir: Path) -> AppContext:
        """Build a plugin-specific AppContext.  Used by PluginHost as ctx_factory."""
        config_path = user_config_path()
        return AppContext(
            plugin_name=plugin.name,
            adapter=self._adapter,
            buttons=self._button_registry,
            paths=AppPaths(
                plugin_dir=plugin_dir,
                data_dir=config_path.parent,
                config_path=config_path,
            ),
            _characters_provider=lambda: list(self._characters),
            _menu_register=self._register_plugin_menu,
            events=self._events,
            scheduler=self._scheduler,
            settings=self._settings.namespace(plugin.name),
        )

    def _register_plugin_menu(self, label: str, callback) -> int:
        """Add a menu item under the Plugins menu.  Returns the DPG item id."""
        if self._plugins_menu_id is None:
            print(f"[app] _register_plugin_menu called before menu was created")
            return 0
        item = dpg.add_menu_item(label=label, callback=callback, parent=self._plugins_menu_id)
        return int(item) if isinstance(item, int) else 0

    def _setup_ui(self) -> None:
        with dpg.viewport_menu_bar():
            with dpg.menu(label="File"):
                dpg.add_menu_item(label="Refresh Now", callback=self._on_refresh_clicked)
                dpg.add_separator()
                dpg.add_menu_item(label="Quit", callback=dpg.stop_dearpygui)

            with dpg.menu(label="Theme") as theme_menu:
                pass
            with dpg.menu(label="Fonts") as font_menu:
                pass
            with dpg.menu(label="Plugins") as plugins_menu:
                pass

        self._theme_plugin = EditThemePlugin(menu_parent=theme_menu)
        self._font_plugin = ChooseFontsPlugin(menu_parent=font_menu)
        self._plugins_menu_id = plugins_menu

        with dpg.window(tag="main_window", label="EQ Window Manager", no_title_bar=True, no_close=True, no_move=True, no_resize=True, no_scrollbar=True):
            dpg.add_spacer(height=22)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Refresh", callback=self._on_refresh_clicked, height=28)
                dpg.add_text("  Auto-refresh:")
                dpg.add_checkbox(
                    tag="eq_auto_refresh",
                    default_value=True,
                    callback=lambda s, v: self._adapter.set_auto(bool(v)),
                )
                dpg.add_text("  Interval (s):")
                dpg.add_input_float(
                    tag="eq_interval",
                    default_value=3600.0,
                    width=100,
                    min_value=60.0,
                    max_value=86400.0,
                    step=0,
                    callback=lambda s, v: self._adapter.set_refresh_interval(float(v)),
                )
                dpg.add_text("  Anon:")
                dpg.add_combo(
                    tag="eq_anon",
                    items=_ANON_OPTS,
                    default_value="Off",
                    width=200,
                    callback=self._on_anon_change,
                )
                dpg.add_text("  Search:")
                dpg.add_input_text(
                    tag="eq_search",
                    width=160,
                    hint="filter by name",
                    callback=self._on_search_change,
                )
                dpg.add_text("", tag=_STATUS_TEXT)

            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_text("Always on top?")
                dpg.add_checkbox(
                    tag="eq_always_on_top",
                    default_value=False,
                    callback=lambda s, v: dpg.set_viewport_always_top(v),
                )

            with dpg.child_window(tag=_TABLE_CONTAINER, autosize_x=True, autosize_y=True, no_scrollbar=False):
                dpg.add_text("Scanning...")

    def _get_class_theme(self, eq_class: str) -> int:
        if eq_class not in self._class_themes:
            self._class_themes[eq_class] = build_class_theme(eq_class)
        return self._class_themes[eq_class]

    def _on_refresh_clicked(self) -> None:
        dpg.set_value(_STATUS_TEXT, "   Scanning...")
        self._adapter.request_refresh()

    def _on_button_clicked(self, char: Character) -> None:
        self._adapter.focus(char)
        self._events.publish("button.clicked", {"char_id": char.id, "window_id": char.window_id})

    def _on_snapshot(self, chars: list[Character]) -> None:
        # Called on the snapshot worker thread. Hand off to the UI thread
        # via the queue — DPG calls on a background thread can crash.
        self._result_queue.put(list(chars))

    def _on_anon_change(self, sender, app_data, user_data) -> None:
        self._anon = app_data
        self._rebuild_table()

    def _on_search_change(self, sender, app_data, user_data) -> None:
        self._search = app_data.strip().lower()
        self._rebuild_table()

    def _display_name(self, char: Character) -> str:
        if self._anon != "Off":
            return _anon_name(char.window_id)
        return char.display_name

    def _display_class(self, char: Character) -> str:
        if self._anon == "Oops: Only Paladins":
            return "Paladin"
        if self._anon in ("Anon: Names+Classes", "Full Anon: Norrath"):
            return _anon_class(char.window_id)
        return char.group_col

    def _display_server(self, char: Character) -> str:
        if self._anon == "Full Anon: Norrath":
            return "Norrath"
        return char.group_row

    @staticmethod
    def _cell_cols(count: int, target_rows: int) -> int:
        return max(1, math.ceil(count / target_rows))

    def _rebuild_table(self) -> None:
        for b in self._buttons:
            self._plugin_host.dispatch("on_button_destroy", b)
            self._events.publish("button.destroyed", {"button": b})
            self._button_registry._unregister(b)
            b.destroy()
        self._buttons = []
        self._button_registry._clear()
        dpg.delete_item(_TABLE_CONTAINER, children_only=True)

        # Apply search filter against display names
        chars = self._characters
        if self._search:
            chars = [c for c in chars if self._search in self._display_name(c).lower()]

        n_total = len(self._characters)
        n_shown = len(chars)

        if not chars:
            msg = (
                f"No results for '{self._search}'." if self._search and self._characters
                else "No EverQuest windows found. Make sure EQ clients are running."
            )
            dpg.add_text(msg, parent=_TABLE_CONTAINER)
            dpg.set_value(_STATUS_TEXT, f"   Found {n_total} character{'s' if n_total != 1 else ''}")
            dpg.set_viewport_height(300)
            return

        if self._search:
            dpg.set_value(_STATUS_TEXT, f"   {n_shown} of {n_total} character{'s' if n_total != 1 else ''}")
        else:
            dpg.set_value(_STATUS_TEXT, f"   Found {n_total} character{'s' if n_total != 1 else ''}")

        servers = sorted({self._display_server(c) for c in chars})
        classes = sorted({self._display_class(c) for c in chars})

        grid: dict[str, dict[str, list[Character]]] = {
            s: {cls: [] for cls in classes} for s in servers
        }
        for char in chars:
            grid[self._display_server(char)][self._display_class(char)].append(char)

        # Sort each cell alphabetically by display name
        for s in servers:
            for cls in classes:
                grid[s][cls].sort(key=lambda c: self._display_name(c).lower())

        target_rows = 6

        class_weight = {
            cls: max(self._cell_cols(len(grid[s][cls]), target_rows) for s in servers)
            for cls in classes
        }

        with dpg.table(
            parent=_TABLE_CONTAINER,
            header_row=True,
            borders_innerH=True,
            borders_outerH=True,
            borders_innerV=True,
            borders_outerV=True,
            resizable=True,
            row_background=True,
            scrollX=False,
            scrollY=False,
        ):
            dpg.add_table_column(label="Server", width_fixed=True, init_width_or_weight=130)
            for cls in classes:
                dpg.add_table_column(
                    label=cls,
                    width_stretch=True,
                    init_width_or_weight=float(class_weight[cls]),
                )

            for server in servers:
                with dpg.table_row():
                    dpg.add_text(server)
                    for cls in classes:
                        cell_chars = grid[server][cls]
                        if not cell_chars:
                            dpg.add_text("")
                            continue

                        ncols = self._cell_cols(len(cell_chars), target_rows)
                        chunks = [cell_chars[i:i+ncols] for i in range(0, len(cell_chars), ncols)]

                        with dpg.table(
                            header_row=False,
                            policy=dpg.mvTable_SizingFixedFit,
                            borders_innerH=False,
                            borders_outerH=False,
                            borders_innerV=False,
                            borders_outerV=False,
                            pad_outerX=False,
                        ):
                            for _ in range(ncols):
                                dpg.add_table_column(
                                    width_fixed=True,
                                    init_width_or_weight=_BUTTON_WIDTH + 4,
                                )

                            for chunk in chunks:
                                with dpg.table_row():
                                    for char in chunk:
                                        disp_name = self._display_name(char)
                                        disp_class = self._display_class(char)
                                        disp_server = self._display_server(char)
                                        if self._anon == "Off":
                                            tooltip = self._adapter.tooltip_for(char)
                                        else:
                                            level = char.raw.get("level", "?")
                                            zone = char.raw.get("zone", "")
                                            instance = char.raw.get("instance", 0)
                                            tail = f"  ({instance})" if instance else ""
                                            tooltip = (
                                                f"{disp_name}.{disp_server}\n"
                                                f"Lvl {level} {disp_class}\n"
                                                f"{zone}{tail}"
                                            )
                                        button = CharacterButton(
                                            char=char,
                                            on_click=lambda s, a, u, c=char: self._on_button_clicked(c),
                                            width=_BUTTON_WIDTH,
                                            height=_BUTTON_HEIGHT,
                                            display_name=disp_name,
                                            display_class=disp_class,
                                            display_server=disp_server,
                                            tooltip_text=tooltip,
                                            theme_id=self._get_class_theme(disp_class),
                                            scheduler=self._scheduler,
                                        )
                                        self._buttons.append(button)
                                        self._button_registry._register(button)
                                        self._plugin_host.dispatch("on_button_create", button)
                                        self._events.publish("button.created", {"button": button})
                                    for _ in range(ncols - len(chunk)):
                                        dpg.add_text("")

        self._fit_viewport(servers, classes, class_weight, grid, target_rows)

    def _fit_viewport(
        self,
        servers: list[str],
        classes: list[str],
        class_weight: dict[str, int],
        grid: dict[str, dict[str, list[Character]]],
        target_rows: int,
    ) -> None:
        # Width: fixed server col + each class col's natural pixel width + borders/padding
        class_px = sum(class_weight[cls] * (_BUTTON_WIDTH + 4) + 4 for cls in classes)
        vp_width = 130 + class_px + 30

        # Height: toolbar chrome + table header + per-server rows
        row_h_total = 0
        for s in servers:
            max_btn_rows = max(
                (
                    math.ceil(len(grid[s][cls]) / self._cell_cols(len(grid[s][cls]), target_rows))
                    for cls in classes if grid[s][cls]
                ),
                default=1,
            )
            row_h_total += max_btn_rows * _BUTTON_ROW_H + 8

        vp_height = _CHROME_H + _TABLE_HEADER_H + row_h_total + 16

        dpg.set_viewport_width(max(500, vp_width))
        dpg.set_viewport_height(max(300, vp_height))


def main() -> None:
    App().run()
