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
    return user_plugins_dir().parent / "plugins.json"


_README_STUB = """\
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
"""

_TEMPLATE_STUB = '''\
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
'''

_CONFIG_STUB = '{\n  "enabled": [],\n  "settings": {}\n}\n'


def bootstrap() -> None:
    plugins_dir = user_plugins_dir()
    plugins_dir.mkdir(parents=True, exist_ok=True)

    readme = plugins_dir / "README.md"
    if not readme.exists():
        readme.write_text(_README_STUB)

    template_dir = plugins_dir / "_template"
    template_dir.mkdir(exist_ok=True)
    template_plugin = template_dir / "plugin.py"
    if not template_plugin.exists():
        template_plugin.write_text(_TEMPLATE_STUB)

    config = user_config_path()
    if not config.exists():
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(_CONFIG_STUB)
