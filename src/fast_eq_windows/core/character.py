"""Game-agnostic character interface that plugins target."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Character(Protocol):
    id: str            # stable unique key (EQ uses f"{name}.{server}")
    display_name: str  # default button label
    group_row: str     # row grouping (EQ: server)
    group_col: str     # column grouping (EQ: class)
    sort_key: str      # within-cell secondary sort
    window_id: int     # OS window handle for focus
    raw: dict          # adapter-specific extras
