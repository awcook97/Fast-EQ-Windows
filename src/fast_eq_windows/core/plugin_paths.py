"""User-config layout helpers and bootstrap for `~/.config/fast_eq_windows/`.

Resolves the plugins folder and `plugins.json` path, honoring two env vars:

* `FAST_EQ_PLUGINS` overrides the plugins folder.
* `FAST_EQ_CONFIG`  overrides the settings JSON path.

`bootstrap()` runs at app start and writes the README, `_template/plugin.py`,
and an empty `plugins.json` if any are missing.  Existing user files are not
overwritten; only known stale auto-generated stubs are upgraded in place.
"""
import os
from pathlib import Path


_PRIMARY_DIR = Path.home() / ".config" / "fast_eq_windows"
_FALLBACK_DIR = Path.home() / ".fast_eq_windows"


def user_plugins_dir() -> Path:
    env = os.environ.get("FAST_EQ_PLUGINS")
    if env:
        return Path(env).expanduser()
    if _FALLBACK_DIR.exists() and not _PRIMARY_DIR.exists():
        return _FALLBACK_DIR / "plugins"
    return _PRIMARY_DIR / "plugins"


def user_config_path() -> Path:
    env = os.environ.get("FAST_EQ_CONFIG")
    if env:
        return Path(env).expanduser()
    return _PRIMARY_DIR / "plugins.json"


_README_STUB = """\
# Fast_EQ_Windows plugins

This folder is scanned at app startup and when you choose **Plugins → Reload**.
Install one plugin per folder:

    ~/.config/fast_eq_windows/
      plugins/
        my_plugin/
          plugin.py
      plugins.json

Enable a plugin by adding its folder name to `~/.config/fast_eq_windows/plugins.json`:

    {
      "enabled": ["my_plugin"],
      "settings": {}
    }

`plugin.py` must define exactly one class that derives from
`fast_eq_windows.core.plugin.Plugin`.  Copy `_template/plugin.py` as a starter.

Environment overrides:

- `FAST_EQ_PLUGINS=/path/to/plugins` changes the scanned plugin folder.
- `FAST_EQ_CONFIG=/path/to/plugins.json` changes the settings file.

Threading rule: DearPyGui calls must run on the main thread.  Worker threads
should push data into `queue.Queue`; drain that queue from `on_tick()`.

Security note: plugins are normal Python code with full access to your user
account.  Only install plugins you trust.

See `docs/PLUGINS.md` in the Fast_EQ_Windows repository for the full API
contract, lifecycle hooks, events, and settings format.
"""

_TEMPLATE_STUB = '''\
"""Fast_EQ_Windows plugin starter.

Copy this folder, rename it (for example `my_plugin`), then enable it by
adding the folder name to `~/.config/fast_eq_windows/plugins.json`:

    {"enabled": ["my_plugin"], "settings": {}}

DearPyGui calls must stay on the main thread.  If you use worker threads for
HTTP/TCP/file watching, push results into `queue.Queue` and drain in on_tick().
"""

from __future__ import annotations

from typing import Any

from fast_eq_windows.core.plugin import AppContext, Plugin


class ExamplePlugin(Plugin):
    """Copy-paste starter that exercises no UI by default."""

    name = "example"
    version = "0.1.0"
    requires: list[str] = []

    def on_load(self, ctx: AppContext) -> None:
        """Called once after the plugin is imported and enabled."""
        self.ctx = ctx
        ctx.log("loaded")

        # Settings are namespaced to this plugin in plugins.json.
        first_run = ctx.settings.get("first_run", True) if ctx.settings else True
        if first_run and ctx.settings:
            ctx.settings.set("first_run", False)

        # Add a menu item under Plugins.  The callback runs on the UI thread.
        ctx.register_menu("Example: print character count", self._print_count)

        # Optional: subscribe to events directly.
        if ctx.events:
            ctx.events.subscribe("button.clicked", self._on_button_clicked)

    def on_unload(self) -> None:
        """Close sockets, stop threads, cancel timers, and unsubscribe here."""
        if getattr(self, "ctx", None) and self.ctx.events:
            self.ctx.events.unsubscribe("button.clicked", self._on_button_clicked)
        self.ctx.log("unloaded")

    def on_snapshot(self, characters: list[Any]) -> None:
        """Called after a new character snapshot is rendered."""

    def on_button_create(self, button: Any) -> None:
        """Called when a CharacterButton enters the registry."""
        # Example APIs:
        # button.set_overlay_bar("health", 0.75, (0, 220, 0, 180))
        # button.set_status_badge("OK", (0, 120, 0, 220))
        # button.set_dim(0.25)

    def on_button_destroy(self, button: Any) -> None:
        """Called before a CharacterButton is destroyed."""

    def on_tick(self, dt: float) -> None:
        """Called every rendered frame on the main thread."""

    def on_event(self, name: str, payload: dict) -> None:
        """Called for every host/plugin event published on the EventBus."""

    def _print_count(self, *_args) -> None:
        self.ctx.log(f"{len(self.ctx.characters())} character(s) visible to plugins")

    def _on_button_clicked(self, payload: dict) -> None:
        self.ctx.log(f"clicked {payload.get('char_id')}")
'''

_OLD_README_STUBS = (
    """\
# Fast_EQ_Windows plugins

Drop a plugin folder here, then enable it in `../plugins.json`.

Layout:

    ~/.config/fast_eq_windows/
      plugins/
        my_plugin/
          plugin.py     <-- defines a class deriving from Plugin
      plugins.json      <-- {"enabled": ["my_plugin"], "settings": {}}

Copy `_template/plugin.py` as a starting point. See `docs/PLUGINS.md` in the
Fast_EQ_Windows repo for the full API contract.
""",
)

_OLD_TEMPLATE_STUBS = (
    '''\
"""Plugin skeleton. Copy this folder and rename it to install your plugin.

Enable by adding the folder name to `enabled` in plugins.json.
"""

# from fast_eq_windows.core.plugin import Plugin


# class MyPlugin(Plugin):
#     name = "my_plugin"
#     version = "0.1.0"
#
#     def on_load(self, ctx) -> None:
#         ctx.log("loaded")
#
#     def on_unload(self) -> None:
#         pass
''',
)

_CONFIG_STUB = '{\n  "enabled": [],\n  "settings": {}\n}\n'


def _write_default(path: Path, content: str, old_stubs: tuple[str, ...] = ()) -> None:
    """Write a generated helper file if missing, or upgrade old generated stubs.

    User-customized files are left untouched.  Only exact known stub content is
    replaced so existing plugin folders remain safe.
    """
    if not path.exists():
        path.write_text(content)
        return
    try:
        if path.read_text() in old_stubs:
            path.write_text(content)
    except OSError:
        pass


def bootstrap() -> None:
    plugins_dir = user_plugins_dir()
    plugins_dir.mkdir(parents=True, exist_ok=True)

    readme = plugins_dir / "README.md"
    _write_default(readme, _README_STUB, _OLD_README_STUBS)

    template_dir = plugins_dir / "_template"
    template_dir.mkdir(exist_ok=True)
    template_plugin = template_dir / "plugin.py"
    _write_default(template_plugin, _TEMPLATE_STUB, _OLD_TEMPLATE_STUBS)

    config = user_config_path()
    if not config.exists():
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(_CONFIG_STUB)
