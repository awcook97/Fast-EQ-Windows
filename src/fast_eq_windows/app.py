import math
import queue
import threading
import time
import dearpygui.dearpygui as dpg

from .class_colors import build_class_theme
from .window_scanner import EQChar, scan_eq_windows, focus_window
from .DearPyGui_EditThemePlugin.EditThemePlugin import EditThemePlugin
from .DearPyGui_EditThemePlugin.ChooseFontsPlugin import ChooseFontsPlugin

_BUTTON_WIDTH = 130
_BUTTON_HEIGHT = 38
_TABLE_CONTAINER = "eq_table_container"
_STATUS_TEXT = "eq_status_text"


class App:
    def __init__(self) -> None:
        self._characters: list[EQChar] = []
        self._class_themes: dict[str, int] = {}
        self._auto_refresh = True
        self._refresh_interval = 3600.0
        self._last_refresh = 0.0
        self._scanning = False
        self._result_queue: queue.Queue[list[EQChar]] = queue.Queue()

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="Fast EQ Windows", width=1200, height=800, min_width=500, min_height=300)

        self._setup_ui()

        dpg.setup_dearpygui()
        dpg.set_primary_window("main_window", True)
        dpg.show_viewport()

        self._refresh()

        while dpg.is_dearpygui_running():
            # Apply completed scan results on the main thread
            try:
                chars = self._result_queue.get_nowait()
                self._characters = chars
                self._rebuild_table()
                n = len(chars)
                dpg.set_value(_STATUS_TEXT, f"   Found {n} character{'s' if n != 1 else ''}")
            except queue.Empty:
                pass

            now = time.time()
            if self._auto_refresh and not self._scanning and (now - self._last_refresh >= self._refresh_interval):
                self._refresh()

            dpg.render_dearpygui_frame()

        dpg.destroy_context()

    def _setup_ui(self) -> None:
        with dpg.viewport_menu_bar():
            with dpg.menu(label="File"):
                dpg.add_menu_item(label="Refresh Now", callback=self._refresh)
                dpg.add_separator()
                dpg.add_menu_item(label="Quit", callback=dpg.stop_dearpygui)

            with dpg.menu(label="Theme") as theme_menu:
                pass
            with dpg.menu(label="Fonts") as font_menu:
                pass

        self._theme_plugin = EditThemePlugin(menu_parent=theme_menu)
        self._font_plugin = ChooseFontsPlugin(menu_parent=font_menu)

        with dpg.window(tag="main_window", label="EQ Window Manager", no_title_bar=True, no_close=True, no_move=True, no_resize=True, no_scrollbar=True):
            dpg.add_spacer(height=22)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Refresh", callback=self._refresh, height=28)
                dpg.add_text("  Auto-refresh:")
                dpg.add_checkbox(
                    tag="eq_auto_refresh",
                    default_value=True,
                    callback=lambda s, v: setattr(self, "_auto_refresh", v),
                )
                dpg.add_text("  Interval (s):")
                dpg.add_input_float(
                    tag="eq_interval",
                    default_value=3600.0,
                    width=100,
                    min_value=60.0,
                    max_value=86400.0,
                    step=0,
                    callback=lambda s, v: setattr(self, "_refresh_interval", float(v)),
                )
                dpg.add_text("", tag=_STATUS_TEXT)

            dpg.add_separator()

            with dpg.child_window(tag=_TABLE_CONTAINER, autosize_x=True, autosize_y=True, no_scrollbar=False):
                dpg.add_text("Scanning...")

    def _get_class_theme(self, eq_class: str) -> int:
        if eq_class not in self._class_themes:
            self._class_themes[eq_class] = build_class_theme(eq_class)
        return self._class_themes[eq_class]

    def _refresh(self) -> None:
        if self._scanning:
            return
        self._scanning = True
        self._last_refresh = time.time()
        dpg.set_value(_STATUS_TEXT, "   Scanning...")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        try:
            chars = scan_eq_windows()
            self._result_queue.put(chars)
        finally:
            self._scanning = False

    @staticmethod
    def _cell_cols(count: int, target_rows: int) -> int:
        return max(1, math.ceil(count / target_rows))

    def _rebuild_table(self) -> None:
        dpg.delete_item(_TABLE_CONTAINER, children_only=True)

        if not self._characters:
            dpg.add_text(
                "No EverQuest windows found. Make sure EQ clients are running.",
                parent=_TABLE_CONTAINER,
            )
            return

        servers = sorted({c.server for c in self._characters})
        classes = sorted({c.eq_class for c in self._characters})

        grid: dict[str, dict[str, list[EQChar]]] = {
            s: {cls: [] for cls in classes} for s in servers
        }
        for char in self._characters:
            grid[char.server][char.eq_class].append(char)

        # target_rows derived from the busiest class so layout scales with data
        max_count = max((len(grid[s][cls]) for s in servers for cls in classes), default=1)
        target_rows = max(1, math.ceil(math.sqrt(max_count)))

        # Weight each outer column by the most sub-columns it'll ever need
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
                                        tooltip = (
                                            f"{char.name}.{char.server}\n"
                                            f"Lvl {char.level} {char.eq_class}\n"
                                            f"{char.zone}"
                                            + (f"  ({char.instance})" if char.instance else "")
                                        )
                                        btn = dpg.add_button(
                                            label=char.name,
                                            callback=lambda s, a, u: focus_window(u),
                                            user_data=char.window_id,
                                            width=_BUTTON_WIDTH,
                                            height=_BUTTON_HEIGHT,
                                        )
                                        dpg.bind_item_theme(btn, self._get_class_theme(char.eq_class))
                                        with dpg.tooltip(btn):
                                            dpg.add_text(tooltip)
                                    # pad incomplete last row
                                    for _ in range(ncols - len(chunk)):
                                        dpg.add_text("")


def main() -> None:
    App().run()
