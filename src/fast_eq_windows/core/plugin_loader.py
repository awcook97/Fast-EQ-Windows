"""PluginHost: discovery, dependency-ordered loading, and dispatch.

Discovery imports each `<plugin_dir>/<name>/plugin.py` under a unique module
name so two plugins can't collide in `sys.modules`.  Loading is topologically
sorted by `Plugin.requires`, with cycles and missing deps demoted to a
best-effort tail load.  Every dispatch is wrapped in try/except per plugin so
a single broken hook can't take down the host.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

from .plugin import Plugin


class PluginHost:
    """Discovers, loads, and dispatches lifecycle hooks to plugins.

    Plugin discovery scans a directory for subfolders containing a
    `plugin.py` file.  Each module is imported with a unique name to
    avoid sys.modules collisions, and any subclass of Plugin is
    registered as a candidate.

    The host catches all exceptions per-plugin during dispatch so a
    misbehaving plugin can't take down the app.  Errors are logged with
    the plugin name and a traceback.
    """

    def __init__(
        self,
        plugins_dir: Path,
        ctx_factory: Callable[[Plugin, Path], Any],
    ) -> None:
        """plugins_dir: directory to scan (e.g. ~/.config/fast_eq_windows/plugins).
        ctx_factory: called with (plugin_instance, plugin_dir) -> AppContext.
                     The host calls this once per loaded plugin to build a
                     plugin-specific AppContext (so paths.plugin_dir, settings
                     namespace, log prefix are all bound).
        """
        self._plugins_dir = plugins_dir
        self._ctx_factory = ctx_factory

        # Discovered plugin classes keyed by folder name.
        self._discovered: dict[str, type[Plugin]] = {}

        # Loaded plugin instances in load order (so unload runs in reverse).
        self._loaded: list[Plugin] = []
        self._by_name: dict[str, Plugin] = {}

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> dict[str, type[Plugin]]:
        """Scan plugins_dir for subdirs containing plugin.py and import them.

        Folders starting with '_' or '.' are skipped (template / hidden).
        Returns a {folder_name: Plugin subclass} mapping.

        Discovery is idempotent — calling it again replaces the discovered set.
        """
        self._discovered = {}
        if not self._plugins_dir.exists():
            return self._discovered

        for entry in sorted(self._plugins_dir.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith("_") or entry.name.startswith("."):
                continue
            plugin_py = entry / "plugin.py"
            if not plugin_py.exists():
                continue

            klass = self._import_plugin_module(entry.name, plugin_py)
            if klass is not None:
                self._discovered[entry.name] = klass

        return self._discovered

    def _import_plugin_module(self, folder_name: str, plugin_py: Path) -> type[Plugin] | None:
        """Import plugin.py from the given path and find its Plugin subclass."""
        module_name = f"fast_eq_windows_plugin_{folder_name}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_py)
            if spec is None or spec.loader is None:
                print(f"[plugin_loader] could not build spec for {plugin_py}")
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception:
            print(f"[plugin_loader] error importing {plugin_py}:")
            traceback.print_exc()
            return None

        candidates = [
            obj for _, obj in inspect.getmembers(module, inspect.isclass)
            if issubclass(obj, Plugin) and obj is not Plugin and obj.__module__ == module_name
        ]
        if not candidates:
            print(f"[plugin_loader] no Plugin subclass in {plugin_py}")
            return None
        if len(candidates) > 1:
            print(f"[plugin_loader] multiple Plugin subclasses in {plugin_py}; using {candidates[0].__name__}")
        return candidates[0]

    # ------------------------------------------------------------------
    # Load / unload
    # ------------------------------------------------------------------

    def load(self, enabled_names: list[str]) -> None:
        """Instantiate enabled plugins and call on_load(ctx) in dependency order."""
        order = self._resolve_load_order(enabled_names)
        for folder_name in order:
            klass = self._discovered.get(folder_name)
            if klass is None:
                print(f"[plugin_loader] enabled plugin '{folder_name}' was not discovered")
                continue
            try:
                instance = klass()
            except Exception:
                print(f"[plugin_loader] failed to instantiate {folder_name}:")
                traceback.print_exc()
                continue

            plugin_dir = self._plugins_dir / folder_name
            try:
                ctx = self._ctx_factory(instance, plugin_dir)
                instance.on_load(ctx)
            except Exception:
                print(f"[plugin_loader] error in on_load for {folder_name}:")
                traceback.print_exc()
                continue

            self._loaded.append(instance)
            self._by_name[folder_name] = instance

    def _resolve_load_order(self, enabled: list[str]) -> list[str]:
        """Topological sort over .requires.  Cycles or missing deps are
        warned about but don't block; offending plugins are loaded last."""
        remaining = set(enabled)
        order: list[str] = []
        while remaining:
            ready = [
                n for n in remaining
                if all(
                    dep in order or dep not in self._discovered or dep not in enabled
                    for dep in getattr(self._discovered.get(n), "requires", [])
                )
            ]
            if not ready:
                print(f"[plugin_loader] dependency cycle or unresolvable; loading remaining in arbitrary order: {sorted(remaining)}")
                order.extend(sorted(remaining))
                break
            ready.sort()
            for n in ready:
                order.append(n)
                remaining.remove(n)
        return order

    def unload_all(self) -> None:
        """Call on_unload on every loaded plugin in reverse load order."""
        for plugin in reversed(self._loaded):
            try:
                plugin.on_unload()
            except Exception:
                print(f"[plugin_loader] error in on_unload for {plugin.name}:")
                traceback.print_exc()
        self._loaded.clear()
        self._by_name.clear()

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, hook_name: str, *args, **kwargs) -> None:
        """Call hook_name(*args, **kwargs) on every loaded plugin.

        Exceptions are caught per-plugin so one bad plugin can't block
        the rest or crash the host.
        """
        for plugin in self._loaded:
            method = getattr(plugin, hook_name, None)
            if method is None:
                continue
            try:
                method(*args, **kwargs)
            except Exception:
                print(f"[plugin_loader] error in {plugin.name}.{hook_name}:")
                traceback.print_exc()

    @property
    def loaded(self) -> list[Plugin]:
        return list(self._loaded)
