# Implementation note: the public mutation API (set_overlay_bar,
# set_status_badge, set_dim) currently encodes state via label suffix
# and dynamic theme blending rather than a separate drawlist overlay.
# This keeps construction simple and DPG-context-friendly.  A future
# refactor can swap _rebuild_overlay() for true drawlist-based
# rendering (bars as colored rectangles, badges as draw_text) without
# changing the public API contract.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import dearpygui.dearpygui as dpg

from ..class_colors import build_dynamic_theme

if TYPE_CHECKING:
    from .tick_scheduler import TickScheduler


class CharacterButton:
    """Wraps a single DPG button widget representing one EQ character.

    Public API is a frozen contract — plugins depend on it.  Private methods
    and internal layout may change in later phases.
    """

    def __init__(
        self,
        char: Any,
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

        # Overlay state — set_colors populates _base_bg/_base_fg once a plugin
        # calls it; until then they're None and the class theme is left intact.
        self._bars: dict[str, tuple[float, tuple[int, int, int, int]]] = {}
        self._badge: tuple[str | None, tuple[int, int, int, int] | None] = (None, None)
        self._dim: float = 0.0
        self._meta: dict[str, Any] = {}
        self._base_bg: tuple[int, int, int, int] | None = None
        self._base_fg: tuple[int, int, int, int] | None = None

        # DPG item ids — set by _create_dpg_button
        self._button_id: int = 0
        self._tooltip_id: int = 0
        self._tooltip_text_id: int = 0

        self._create_dpg_button()

    # ------------------------------------------------------------------
    # Private: DPG construction
    # ------------------------------------------------------------------

    def _create_dpg_button(self) -> None:
        """Create the DPG button widget in the currently active container."""
        self._button_id = dpg.add_button(
            label=self._display_name,
            callback=self._on_click,
            user_data=self._char.window_id,
            width=self._width,
            height=self._height,
        )
        dpg.bind_item_theme(self._button_id, self._theme_id)
        with dpg.tooltip(self._button_id) as self._tooltip_id:
            self._tooltip_text_id = dpg.add_text(self._tooltip_text)

    def _apply_theme(self, theme_id: int) -> None:
        """Bind a pre-built theme to the button."""
        dpg.bind_item_theme(self._button_id, theme_id)

    def _rebuild_overlay(self) -> None:
        """Recompose the button's visual state from stored bars/badge/dim.

        Implementation detail: encodes overlay state via label suffix +
        dynamic theme rather than a separate drawlist.  Future refactor
        can switch to drawlist-based rendering (bars as colored rectangles,
        badges as draw_text) without changing the public API contract.
        """
        # 1. Label = display_name + badge suffix
        badge_text, _badge_color = self._badge
        label = self._display_name
        if badge_text:
            label = f"{label}  [{badge_text}]"
        dpg.configure_item(self._button_id, label=label)

        # 2. Theme = base color blended with bar colors, then darkened by dim.
        # Guard: if set_colors has never been called we don't know the base
        # colors, so leave the class theme intact (skip dim too — punt).
        if self._base_bg is None or self._base_fg is None:
            return

        bg: tuple[int, int, int, int] = self._base_bg
        fg: tuple[int, int, int, int] = self._base_fg

        # Blend each bar color into bg by (pct * 0.4) — visible but not overwhelming
        for _kind, (pct, color) in self._bars.items():
            weight = max(0.0, min(1.0, pct)) * 0.4
            bg = tuple(  # type: ignore[assignment]
                int(bg[i] * (1 - weight) + color[i] * weight) for i in range(4)
            )

        # Apply dim by lerping toward black (alpha channel preserved)
        if self._dim > 0:
            bg = tuple(  # type: ignore[assignment]
                int(bg[i] * (1 - self._dim)) if i < 3 else bg[i] for i in range(4)
            )

        new_theme = build_dynamic_theme(bg, fg)
        self._apply_theme(new_theme)

    def _tick(self, dt: float) -> None:
        """No-op stub — Phase 5 wires per-frame updates (flash, scheduler)."""
        pass

    # ------------------------------------------------------------------
    # Public API — frozen contract
    # ------------------------------------------------------------------

    @property
    def char(self) -> Any:
        """The underlying character object."""
        return self._char

    @property
    def dpg_id(self) -> int:
        """Raw DPG item id for the button — escape hatch for advanced use."""
        return self._button_id

    def set_label(self, text: str) -> None:
        dpg.configure_item(self._button_id, label=text)

    def set_tooltip(self, text: str) -> None:
        dpg.set_value(self._tooltip_text_id, text)

    def set_theme(self, theme_id: int) -> None:
        dpg.bind_item_theme(self._button_id, theme_id)

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
        self._flash_handle = self._scheduler.after(
            ms / 1000.0,
            lambda: (self._apply_theme(prev_theme), setattr(self, "_flash_handle", None)),
        )

    def destroy(self) -> None:
        """Delete the button widget; tooltip is a child so it cascades."""
        dpg.delete_item(self._button_id)
