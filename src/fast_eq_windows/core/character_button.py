"""`CharacterButton` — the plugin-facing wrapper around one DPG button.

Each button is a child-window containing a real DPG button plus a drawlist
overlay used for plugin decorations (overlay bars, status badges, dim
layer).  Plugins should restrict themselves to the public API marked
below as the "frozen contract"; private members may shift.
"""
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
        theme_id: DpgId,
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
        self._theme_id: DpgId = theme_id
        self._original_theme_id: DpgId = theme_id
        self._scheduler = scheduler
        self._flash_handle: Any = None
        # Themes built by set_colors()/flash() that this button owns and must
        # delete to avoid leaking DPG items across rebinds.
        self._owned_themes: set[DpgId] = set()

        # Overlay state.  Bars retain insertion order so the button owns slot
        # assignment: first kind is slot 0, second kind is slot 1, etc.
        self._bars: dict[str, tuple[float, tuple[int, int, int, int]]] = {}
        self._badge: tuple[str | None, tuple[int, int, int, int] | None] = (None, None)
        self._caption: tuple[str | None, tuple[int, int, int, int] | None] = (None, None)
        self._fill_depletion: tuple[float, tuple[int, int, int, int]] | None = None
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

    def _apply_theme(self, theme_id: DpgId) -> None:
        """Bind a pre-built theme to the button.

        Does not take ownership of `theme_id`; callers that build a fresh
        theme (set_colors / flash) must register it via `_owned_themes` and
        clean it up themselves.
        """
        self._theme_id = theme_id
        if self._button_id and dpg.does_item_exist(self._button_id):
            dpg.bind_item_theme(self._button_id, theme_id)

    def _rebuild_overlay(self) -> None:
        """Clear and redraw the overlay primitives."""
        if not self._drawlist_id or not dpg.does_item_exist(self._drawlist_id):
            return

        dpg.delete_item(self._drawlist_id, children_only=True)

        # Full-button depletion mask (e.g. HP "full bar" mode).  Drawn first
        # so other overlays sit on top.  We darken the right (1-pct) slice of
        # the button so the underlying class color shows through the left
        # (filled) portion.
        if self._fill_depletion is not None:
            pct, color = self._fill_depletion
            pct = max(0.0, min(1.0, pct))
            x_split = int(self._width * pct)
            if x_split < self._width:
                dpg.draw_rectangle(
                    (x_split, 0),
                    (self._width, self._height),
                    color=color,
                    fill=color,
                    parent=self._drawlist_id,
                )

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

        caption_text, caption_color = self._caption
        if caption_text:
            text_color = caption_color or (255, 255, 255, 230)
            dpg.draw_text(
                (3, max(0, self._height - 14)),
                caption_text,
                color=text_color,
                size=12,
                parent=self._drawlist_id,
            )

    def _tick(self, dt: float) -> None:
        """Reserved for per-frame work driven by the host scheduler.

        Currently unused — flash uses TickScheduler.after directly.  Kept as
        a hook so the host can opt buttons into per-frame updates later
        without changing the call site.
        """
        return

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

    def set_theme(self, theme_id: DpgId) -> None:
        self._base_bg = None
        self._base_fg = None
        self._apply_theme(theme_id)

    def reset_theme(self) -> None:
        """Revert to the class theme bound at construction time.

        Plugins that call ``set_colors`` (which builds and binds a fresh
        theme) should call this when they're done so the button returns to
        its original class color.
        """
        prev_owned = self._theme_id if self._theme_id in self._owned_themes else None
        self._base_bg = None
        self._base_fg = None
        self._apply_theme(self._original_theme_id)
        if prev_owned is not None:
            self._discard_owned_theme(prev_owned)

    def set_colors(
        self,
        bg: tuple[int, int, int, int],
        fg: tuple[int, int, int, int],
        hover: tuple[int, int, int, int] | None = None,
        active: tuple[int, int, int, int] | None = None,
    ) -> None:
        """Build a dynamic theme from the given colors and bind it.

        Delegates to `build_dynamic_theme` in `class_colors.py`.  The previous
        button-owned theme (if any) is deleted to keep DPG's item table from
        growing unbounded across repeated calls.  Also stores bg/fg as the new
        base colors so subsequent set_overlay_bar / set_dim calls can blend
        relative to this baseline.
        """
        theme_id = build_dynamic_theme(bg, fg, hover, active)
        self._owned_themes.add(theme_id)
        prev_owned = self._theme_id if self._theme_id in self._owned_themes else None
        self._apply_theme(theme_id)
        if prev_owned is not None and prev_owned != theme_id:
            self._discard_owned_theme(prev_owned)
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

    def set_fill_depletion(
        self,
        pct: float | None,
        color_rgba: tuple[int, int, int, int] = (0, 0, 0, 200),
    ) -> None:
        """Darken the right (1-pct) of the button to fake a full-button bar.

        Pass ``pct=None`` to clear.  The button's base color (set via
        ``set_colors`` / class theme) shows through the un-darkened left
        slice, producing an EverQuest-style depleting fill.
        """
        if pct is None:
            self._fill_depletion = None
        else:
            self._fill_depletion = (max(0.0, min(1.0, pct)), color_rgba)
        self._rebuild_overlay()

    def set_caption(
        self,
        text: str | None,
        color_rgba: tuple[int, int, int, int] | None = None,
    ) -> None:
        """Set bottom-left caption text (e.g. platinum). Pass None to clear."""
        self._caption = (text, color_rgba)
        self._rebuild_overlay()

    def set_meta(self, key: str, value: Any) -> None:
        self._meta[key] = value

    def get_meta(self, key: str, default: Any = None) -> Any:
        return self._meta.get(key, default)

    def flash(self, color_rgba: tuple[int, int, int, int], ms: int) -> None:
        """Briefly tint the button by overlaying color_rgba; auto-reverts after ms.

        Requires a scheduler at construction time.  Without one, this is a no-op.
        The flash theme is registered as button-owned and deleted on revert
        (or on the next flash) so repeated flashes don't leak DPG items.
        """
        if self._scheduler is None:
            return
        if self._flash_handle is not None:
            self._scheduler.cancel(self._flash_handle)
            self._flash_handle = None
        prev_theme = self._theme_id
        # Build a flash theme using color_rgba as bg with white text.
        flash_theme = build_dynamic_theme(color_rgba, (255, 255, 255, 255))
        self._owned_themes.add(flash_theme)
        self._apply_theme(flash_theme)

        def clear_flash() -> None:
            self._apply_theme(prev_theme)
            self._discard_owned_theme(flash_theme)
            self._flash_handle = None

        self._flash_handle = self._scheduler.after(ms / 1000.0, clear_flash)

    def destroy(self) -> None:
        """Delete the child-window; all button/drawlist children cascade."""
        if self._flash_handle is not None and self._scheduler is not None:
            self._scheduler.cancel(self._flash_handle)
            self._flash_handle = None
        if self._container_id and dpg.does_item_exist(self._container_id):
            dpg.delete_item(self._container_id)
        for theme_id in list(self._owned_themes):
            self._discard_owned_theme(theme_id)

    def _discard_owned_theme(self, theme_id: DpgId) -> None:
        """Delete a theme this button created and remove it from the owned set."""
        self._owned_themes.discard(theme_id)
        if theme_id and dpg.does_item_exist(theme_id):
            try:
                dpg.delete_item(theme_id)
            except Exception:
                # DPG occasionally raises if the item was already cleaned up
                # via a parent cascade; safe to ignore.
                pass
