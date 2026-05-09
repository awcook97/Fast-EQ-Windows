"""Game-agnostic character interface that plugins target.

Adapters produce concrete objects (e.g. `EQChar` from the EverQuest scanner)
that satisfy this Protocol structurally.  Plugins should treat instances as
immutable: the host rebuilds the list on every snapshot rather than mutating
in place.

Field conventions:
    id            stable unique key, survives window-id churn
    display_name  default button label (anonymization is applied separately)
    group_row     row grouping (EQ: server)
    group_col     column grouping (EQ: class)
    sort_key      within-cell secondary sort
    window_id     OS window handle for focus
    raw           adapter-specific extras (level, zone, instance, eq_class, …)
"""
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
