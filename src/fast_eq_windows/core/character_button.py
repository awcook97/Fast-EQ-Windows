from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import dearpygui.dearpygui as dpg

from ..class_colors import build_dynamic_theme

if TYPE_CHECKING:
    from .tick_scheduler import TickScheduler

DpgId = int | str


class CharacterButton:
    """Wraps a single DPG button widget representing one EQ character.

    Public API is a frozen contract — plugins depend on it.  Private methods
    and internal layout may change in later phases.
    """

    def __init__(
        self,
        char: Any,
        parent_id: int | str | None,
        on_click: Callable,
        width: int,
        height: int,
        display_name: str,
        display_class: str,
        display_server: str,
        tooltip_text: str,
        theme_id: int,
        scheduler: "TickScheduler | None" = None,
    ) -> None:
        self._char = char
        self._parent_id = parent_id
        self._on_click = on_click
        self._width = width
        self._height = height
        self._display_name = display_name
        self._display_class = display_class
        self._display_server = display_server
        self._tooltip_text = tooltip_text
        self._theme_id = theme_id
        self._scheduler = scheduler
        self._flash_handle: Any = None

        # Overlay state.  Bars retain insertion order so the button owns slot
        # assignment: first kind is slot 0, second kind is slot 1, etc.
        self._bars: dict[str, tuple[float, tuple[int, int, int, int]]] = {}
        self._badge: tuple[str | None, tuple[int, int, int, int] | None] = (None, None)
        self._dim: float = 0.0
        self._meta: dict[str, Any] = {}
        self._base_bg: tuple[int, int, int, int] | None = None
        self._base_fg: tuple[int, int, int, int] | None = None

        # DPG item ids — set by _create_dpg_button
        self._container_id: DpgId = 0
        self._button_id: DpgId = 0
        self._drawlist_id: DpgId = 0
        self._tooltip_id: DpgId = 0
        self._tooltip_text_id: DpgId = 0

        self._create_dpg_button()

    # ------------------------------------------------------------------
    # Private: DPG construction
    # ------------------------------------------------------------------

    def _create_dpg_button(self) -> None:
        """Create the DPG child-window, button, and overlay drawlist."""
        kwargs: dict[str, Any] = {
            "width": self._width,
            "height": self._height,
            "border": False,
            "no_scrollbar": True,
        }
        if self._parent_id is not None:
            kwargs["parent"] = self._parent_id

        self._container_id = dpg.add_child_window(**kwargs)
        self._button_id = dpg.add_button(
            label=self._display_name,
            callback=self._on_click,
            user_data=self._char.window_id,
            width=self._width,
            height=self._height,
            pos=(0, 0),
            parent=self._container_id,
        )
        dpg.bind_item_theme(self._button_id, self._theme_id)
        self._drawlist_id = dpg.add_drawlist(
            width=self._width,
            height=self._height,
            pos=(0, 0),
            parent=self._container_id,
        )
        # Drawlists have no handlers, but disabling the item keeps it from
        # becoming an input target on DearPyGui versions that consider it
        # hoverable.  The actual button remains the click/tooltip target.
        try:
            dpg.configure_item(self._drawlist_id, enabled=False)
        except Exception:
            pass
        with dpg.tooltip(self._button_id) as self._tooltip_id:
            self._tooltip_text_id = dpg.add_text(self._tooltip_text)
        self._rebuild_overlay()

    def _apply_theme(self, theme_id: int) -> None:
        """Bind a pre-built theme to the button."""
        self._theme_id = theme_id
        if self._button_id and dpg.does_item_exist(self._button_id):
            dpg.bind_item_theme(self._button_id, theme_id)

    def _rebuild_overlay(self) -> None:
        """Clear and redraw the overlay primitives."""
        if not self._drawlist_id or not dpg.does_item_exist(self._drawlist_id):
            return

        dpg.delete_item(self._drawlist_id, children_only=True)

        # Slot-based overlay bars.  Each plugin supplies a kind; the button
        # owns placement and stacks bars in insertion order from the top down.
        bar_h = 5
        for slot, (_kind, (pct, color)) in enumerate(self._bars.items()):
            y0 = slot * (bar_h + 1)
            y1 = min(self._height, y0 + bar_h)
            if y0 >= self._height:
                break
            pct = max(0.0, min(1.0, pct))
            dpg.draw_rectangle(
                (0, y0),
                (self._width, y1),
                color=(0, 0, 0, 90),
                fill=(0, 0, 0, 90),
                parent=self._drawlist_id,
            )
            dpg.draw_rectangle(
                (0, y0),
                (int(self._width * pct), y1),
                color=color,
                fill=color,
                parent=self._drawlist_id,
            )

        # Dim after bars so it affects the whole button state, but before the
        # badge so status text remains legible while a client is loading.
        if self._dim > 0:
            alpha = int(210 * max(0.0, min(1.0, self._dim)))
            dpg.draw_rectangle(
                (0, 0),
                (self._width, self._height),
                color=(0, 0, 0, alpha),
                fill=(0, 0, 0, alpha),
                parent=self._drawlist_id,
            )

        badge_text, badge_color = self._badge
        if badge_text:
            bg = badge_color or (30, 30, 30, 220)
            text_color = self._contrast_text(bg)
            badge_w = min(self._width - 4, max(18, len(badge_text) * 7 + 10))
            x0 = self._width - badge_w - 2
            y0 = 2
            dpg.draw_rectangle(
                (x0, y0),
                (self._width - 2, y0 + 16),
                color=bg,
                fill=bg,
                rounding=4,
                parent=self._drawlist_id,
            )
            dpg.draw_text(
                (x0 + 5, y0 + 2),
                badge_text,
                color=text_color,
                size=12,
                parent=self._drawlist_id,
            )

    def _tick(self, dt: float) -> None:
        """No-op stub — Phase 5 wires per-frame updates (flash, scheduler)."""
        pass

    @staticmethod
    def _contrast_text(color: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        r, g, b, _a = color
        luminance = (0.299 * r) + (0.587 * g) + (0.114 * b)
        return (0, 0, 0, 255) if luminance > 150 else (255, 255, 255, 255)

    # ------------------------------------------------------------------
    # Public API — frozen contract
    # ------------------------------------------------------------------

    @property
    def char(self) -> Any:
        """The underlying character object."""
        return self._char

    @property
    def dpg_id(self) -> DpgId:
        """Raw DPG item id for the button — escape hatch for advanced use."""
        return self._button_id

    def set_label(self, text: str) -> None:
        self._display_name = text
        dpg.configure_item(self._button_id, label=text)
        self._rebuild_overlay()

    def set_tooltip(self, text: str) -> None:
        dpg.set_value(self._tooltip_text_id, text)

    def set_theme(self, theme_id: int) -> None:
        self._base_bg = None
        self._base_fg = None
        self._apply_theme(theme_id)

    def set_colors(
        self,
        bg: tuple[int, int, int, int],
        fg: tuple[int, int, int, int],
        hover: tuple[int, int, int, int] | None = None,
        active: tuple[int, int, int, int] | None = None,
    ) -> None:
        """Build a dynamic theme from the given colors and bind it.

        Delegates to build_dynamic_theme in class_colors.py.  Also stores
        the bg/fg as the new base colors so subsequent set_overlay_bar /
        set_dim calls can blend relative to this baseline.
        """
        theme_id = build_dynamic_theme(bg, fg, hover, active)
        self._apply_theme(theme_id)
        # Remember the "base" colors for set_overlay_bar / set_dim recomposition.
        self._base_bg = bg
        self._base_fg = fg
        self._rebuild_overlay()

    def set_overlay_bar(
        self,
        kind: str,
        pct: float,
        color_rgba: tuple[int, int, int, int],
    ) -> None:
        """Store bar data and recompose the button's visual state."""
        self._bars[kind] = (pct, color_rgba)
        self._rebuild_overlay()

    def set_status_badge(
        self,
        text: str | None,
        color_rgba: tuple[int, int, int, int] | None = None,
    ) -> None:
        """Store badge data and recompose the button's visual state."""
        self._badge = (text, color_rgba)
        self._rebuild_overlay()

    def set_dim(self, amount: float) -> None:
        """Dim the button by blending toward black (0 = normal, 1 = black)."""
        self._dim = max(0.0, min(1.0, amount))
        self._rebuild_overlay()

    def set_meta(self, key: str, value: Any) -> None:
        self._meta[key] = value

    def get_meta(self, key: str, default: Any = None) -> Any:
        return self._meta.get(key, default)

    def flash(self, color_rgba: tuple[int, int, int, int], ms: int) -> None:
        """Briefly tint the button by overlaying color_rgba; auto-reverts after ms.

        Requires a scheduler at construction time.  Without one, this is a no-op.
        """
        if self._scheduler is None:
            return
        if self._flash_handle is not None:
            self._scheduler.cancel(self._flash_handle)
            self._flash_handle = None
        prev_theme = self._theme_id
        # Build a flash theme using color_rgba as bg with white text.
        flash_theme = build_dynamic_theme(color_rgba, (255, 255, 255, 255))
        self._apply_theme(flash_theme)

        def clear_flash() -> None:
            self._apply_theme(prev_theme)
            self._flash_handle = None

        self._flash_handle = self._scheduler.after(ms / 1000.0, clear_flash)

    def destroy(self) -> None:
        """Delete the child-window; all button/drawlist children cascade."""
        if self._flash_handle is not None and self._scheduler is not None:
            self._scheduler.cancel(self._flash_handle)
            self._flash_handle = None
        if self._container_id and dpg.does_item_exist(self._container_id):
            dpg.delete_item(self._container_id)
