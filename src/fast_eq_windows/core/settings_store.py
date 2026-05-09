"""Persistent JSON-backed settings with per-plugin namespaces.

The on-disk layout is `{"enabled": [...], "settings": {<plugin>: {...}}}`.
Writes are debounced through the host's `TickScheduler` so a burst of
`set()` calls collapses into a single disk write.  Reads are O(1) against
the in-memory cache.
"""
from __future__ import annotations

import json
import threading
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .tick_scheduler import TickScheduler


class SettingsStore:
    """JSON-backed key-value store with per-plugin namespaces.

    Plugins receive a SettingsNamespace bound to their name.  Reads
    return cached values; writes mutate in-memory state and schedule a
    debounced save (≤500 ms) via the host's TickScheduler.
    """

    DEBOUNCE_S = 0.5

    def __init__(self, path: Path, scheduler: "TickScheduler | None" = None) -> None:
        self._path = path
        self._scheduler = scheduler
        self._data: dict[str, Any] = self._load()
        self._dirty = False
        self._save_handle: Any = None
        self._lock = threading.Lock()

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"enabled": [], "settings": {}}
        try:
            return json.loads(self._path.read_text())
        except Exception:
            print(f"[settings_store] could not parse {self._path}; treating as empty:")
            traceback.print_exc()
            return {"enabled": [], "settings": {}}

    def reload(self) -> None:
        """Re-read from disk, discarding any unsaved in-memory changes.

        Called by the host on plugin reload.
        """
        with self._lock:
            self._data = self._load()
            self._dirty = False

    def save(self) -> None:
        """Force an immediate synchronous save."""
        with self._lock:
            self._do_save_locked()

    def _do_save_locked(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2) + "\n")
            self._dirty = False
        except Exception:
            print(f"[settings_store] failed to save {self._path}:")
            traceback.print_exc()

    def _schedule_save(self) -> None:
        """Debounced save via TickScheduler.  Called after each set()."""
        if self._scheduler is None:
            # No scheduler available — save synchronously.
            self.save()
            return
        # If a save is already pending, leave it; the in-memory dict is
        # the source of truth and the pending save will pick up the
        # latest values when it fires.
        if self._save_handle is not None:
            return
        self._save_handle = self._scheduler.after(self.DEBOUNCE_S, self._on_debounced_save)

    def _on_debounced_save(self) -> None:
        self._save_handle = None
        with self._lock:
            if self._dirty:
                self._do_save_locked()

    @property
    def enabled_plugins(self) -> list[str]:
        """The list of plugin folder names enabled in plugins.json."""
        return list(self._data.get("enabled", []))

    def namespace(self, plugin_name: str) -> "SettingsNamespace":
        return SettingsNamespace(self, plugin_name)

    # ------------------------------------------------------------------
    # Per-namespace internal helpers
    # ------------------------------------------------------------------

    def _ns_get(self, plugin_name: str, key: str, default: Any) -> Any:
        with self._lock:
            return self._data.get("settings", {}).get(plugin_name, {}).get(key, default)

    def _ns_set(self, plugin_name: str, key: str, value: Any) -> None:
        with self._lock:
            settings = self._data.setdefault("settings", {})
            ns = settings.setdefault(plugin_name, {})
            ns[key] = value
            self._dirty = True
        self._schedule_save()

    def _ns_all(self, plugin_name: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._data.get("settings", {}).get(plugin_name, {}))


class SettingsNamespace:
    """Bound view of a single plugin's settings.

    Plugins receive this via AppContext.settings.  Reads and writes
    touch only the per-plugin sub-dict; saves are debounced.
    """

    def __init__(self, store: SettingsStore, plugin_name: str) -> None:
        self._store = store
        self._plugin_name = plugin_name

    def get(self, key: str, default: Any = None) -> Any:
        return self._store._ns_get(self._plugin_name, key, default)

    def set(self, key: str, value: Any) -> None:
        self._store._ns_set(self._plugin_name, key, value)

    def all(self) -> dict[str, Any]:
        """Return a snapshot of all settings for this plugin."""
        return self._store._ns_all(self._plugin_name)

    def save(self) -> None:
        """Force an immediate save (skipping debounce)."""
        self._store.save()
