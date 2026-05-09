# Development

This is the contributor-facing setup. End-user install lives in the
top-level [README.md](../README.md).

## Prerequisites

* Linux with X11 (XWayland is fine)
* Python **3.14+**
* [`uv`](https://github.com/astral-sh/uv) for environment + lockfile management
* `wmctrl` and `xdotool` on `$PATH` for the live window scanner

## First-time setup

```sh
git clone <this repo>
cd Fast_EQ_Windows
uv sync
```

`uv sync` creates `.venv/` and installs the project in editable mode
from `pyproject.toml` + `uv.lock`.

## Running

```sh
uv run fast-eq-windows
```

The app creates `~/.config/fast_eq_windows/` and a `plugins/` folder on
first launch. To point the app at a sandbox config:

```sh
FAST_EQ_PLUGINS=/tmp/feq/plugins FAST_EQ_CONFIG=/tmp/feq/plugins.json uv run fast-eq-windows
```

Both env vars are honored at every read; restart the app after changing
them.

## Project layout

```text
src/fast_eq_windows/      Source — see docs/ARCHITECTURE.md
docs/                     Contributor + plugin-author docs (this folder)
themes/, Fonts/           Bundled assets shipped with the package
build_launcher.py         PyInstaller entry-point shim for binary releases
setup.sh, setup.ps1       One-shot installer scripts for end users
pyproject.toml            Build metadata + dependencies
uv.lock                   Pinned resolution
```

## Smoke testing

There is no automated test suite yet. The project relies on a
reproducible end-to-end smoke that loads the app headlessly with a fake
adapter:

```sh
uv run python - <<'PY'
from types import SimpleNamespace
import dearpygui.dearpygui as dpg
from fast_eq_windows.app import App

class FakeAdapter:
    name = "fake"
    def add_listener(self, cb): pass
    def start(self): pass
    def stop(self): pass
    def request_refresh(self): pass
    def set_auto(self, e): pass
    def set_refresh_interval(self, s): pass
    def focus(self, c): pass
    def tooltip_for(self, c): return "fake"

char = SimpleNamespace(
    id="Alice.Test", display_name="Alice", group_row="Test",
    group_col="Cleric", sort_key="alice", window_id=12345,
    raw={"level": 1, "zone": "Test Zone", "instance": 0, "eq_class": "Cleric"},
)

dpg.create_context()
dpg.create_viewport(title="smoke", width=600, height=300)
try:
    app = App()
    app._adapter = FakeAdapter()
    app._setup_ui()
    app._load_plugins()
    app._characters = [char]
    app._rebuild_table()
    assert app._buttons, "no button created"
    app._plugin_host.unload_all()
finally:
    dpg.destroy_context()
print("smoke ok")
PY
```

This exercises the full snapshot pipeline (rebuild, register, dispatch,
unload) without touching real EQ windows.

For a quick "does it start" check:

```sh
PYTHONUNBUFFERED=1 timeout --signal=INT 4 uv run fast-eq-windows
```

The app should print plugin load lines (e.g.
`[anonymous_server] loaded (active, server='Norrath')`) and exit 130 on
the SIGINT.

## Coding conventions

* `from __future__ import annotations` at the top of every module.
* Module docstring before imports; class and public-method docstrings
  required on anything in `core/` or under `adapters/`.
* `int | str` (DearPyGui id alias `DpgId`) for any value that came from
  `dpg.add_*`. Don't `int(...)` cast — string tags are real.
* Background work is exclusively producer-side. The DPG thread owns the
  rest of the world. Cross-thread hand-off is via `queue.Queue`.
* Plugin-facing surface is whatever is documented in
  [PLUGINS.md](PLUGINS.md). Anything else is private and may change.

## Packaging

`build_launcher.py` drives a PyInstaller build for the binary release.
It is intentionally minimal — the heavy lifting lives in PyInstaller's
spec generation.

```sh
uv run python build_launcher.py
```

Output binary lands in `dist/`. Plugins are deliberately not bundled:
they live in the user's config folder and are loaded at runtime from
disk.
