# Plugin System Architecture — Fast_EQ_Windows

## Context

Fast_EQ_Windows is a DearPyGui multibox window manager that scans `wmctrl` output for running EverQuest clients and renders them as colored buttons in a server × class grid. Click a button → focuses that game window.

This plan covers the **plugin system architecture only** — the framework that lets plugins exist. Actual plugins (HealthBar, ManaBar, CrewMonitor, EQBC, LoadingDetection) are NOT implemented here; they're listed as motivating use cases the architecture must support.

The architecture must:
- Treat each button as an instance of a class with public (plugin-exposed) and private methods
- Define abstract interfaces so the app can be extended to other games (WoW, etc.)
- Support per-button live updates without DPG widget churn (so health drains, bars, badges, dimming are all possible)
- Provide hooks for external systems (HTTP, TCP, file watching) to feed data into plugins
- Discover and load plugins from disk
- Survive a misbehaving plugin without crashing the host

This plan is structured as **incremental phases with checkboxes**. Each phase ends with a working app — pick it up later or hand it off without a half-broken state.

Verifying after every phase is mandatory: there are no automated tests yet.

---

## Use cases the architecture must support (NOT implemented here)

These are the user's planned plugins. The architecture is correct only if each could be written against it without further changes:

- **HealthBarPlugin** — buttons fade toward red as health drops; green bar overlay shrinks
- **ManaBarPlugin** — blue bar stacked under the health bar
- **CrewMonitorPlugin** — HTTP poll an external app's endpoint for reset counts; badge on button
- **EQBCPlugin** — TCP socket to multibox chat network; flash buttons on activity
- **LoadingDetectionPlugin** — observe window title transitions; dim button while zoning

Each is referenced in the **Validation** section at the bottom — paper exercises confirming the architecture is sufficient.

---

## Plugin location — they actually plug in

Plugins live OUTSIDE the app binary. They are user-writable files the user drops into a known directory at runtime; the app discovers them from disk. They are NOT bundled into PyInstaller, NOT shipped in the wheel, NOT importable as `fast_eq_windows.plugins.*`.

**Plugin search path** (in priority order, first match wins for same-named plugin):

1. `$FAST_EQ_PLUGINS` (env var override; useful for dev)
2. `~/.config/fast_eq_windows/plugins/` (Linux user config — primary)
3. `~/.fast_eq_windows/plugins/` (fallback for users who prefer dotfile-style)

Settings live next to plugins, also user-writable:

- `$FAST_EQ_CONFIG` env override, else `~/.config/fast_eq_windows/plugins.json`

The app creates the directory on first launch if missing and writes a `README.md` and `_template/plugin.py` skeleton there. **No plugin source code lives inside the app's repo or PyInstaller bundle.**

## Target layout (in repo)

```
src/fast_eq_windows/
  app.py                      (slimmed; orchestrates plugin host)
  class_colors.py             (existing; sibling helper added)
  window_scanner.py           (existing; wrapped by EQGameAdapter)
  core/
    character.py              (Character protocol)
    game_adapter.py           (GameAdapter ABC)
    character_button.py       (CharacterButton class)
    button_registry.py        (lookup by char id / window id / iter)
    event_bus.py              (publish/subscribe)
    tick_scheduler.py         (frame-aligned dt callbacks)
    settings_store.py         (per-plugin namespaced JSON persistence)
    plugin.py                 (Plugin ABC + AppContext)
    plugin_loader.py          (discover, import, lifecycle)
    plugin_paths.py           (resolves user plugin/config dirs, creates on first launch)
  adapters/
    eq_adapter.py             (wraps existing window_scanner.py)
docs/
  PLUGINS.md                  (user-facing: where to drop plugins, API contract)
```

## Target layout (on the user's machine, NOT in repo)

```
~/.config/fast_eq_windows/
  plugins/
    README.md                 (auto-written on first launch)
    _template/
      plugin.py               (auto-written on first launch — copy-paste starter)
    <user's plugins go here, one folder per plugin>
  plugins.json                (enabled list + per-plugin settings)
```

---

## Phase 0 — Setup, no behavior change

- [x] Create `src/fast_eq_windows/core/` package with empty `__init__.py`
- [x] Create `src/fast_eq_windows/adapters/` package with empty `__init__.py`
- [x] Create `src/fast_eq_windows/core/plugin_paths.py` with:
  - `user_plugins_dir()` — returns `Path` resolved from `$FAST_EQ_PLUGINS` → `~/.config/fast_eq_windows/plugins/` → `~/.fast_eq_windows/plugins/`
  - `user_config_path()` — returns `$FAST_EQ_CONFIG` → `~/.config/fast_eq_windows/plugins.json`
  - `bootstrap()` — on first launch, `mkdir -p` the plugins dir, write a `README.md` explaining the convention, and write `_template/plugin.py` skeleton if absent. Idempotent: never overwrites existing files.
- [x] Wire `bootstrap()` into `App.__init__` so it runs once at startup before plugin discovery
- [x] Do NOT add a `plugins/` or `config/` directory inside the repo. Do NOT modify `pyproject.toml` or `build_launcher.py` to bundle plugins — plugins live outside the binary.

**Verify**: `uv run fast-eq-windows` still launches; on first launch `~/.config/fast_eq_windows/plugins/` is created with `README.md` and `_template/plugin.py`; no runtime change to existing UI; nothing inside the repo changed structurally beyond the `core/` and `adapters/` packages.

---

## Phase 1 — Refactor `_rebuild_table` button creation into `CharacterButton`

Extract per-button DPG creation into a class. No external behavior change.

- [x] Create `src/fast_eq_windows/core/character_button.py` with class `CharacterButton`
  - Constructor: `char`, `parent_id`, `on_click`, `width`, `height`, `display_name`, `display_class`, `display_server`, `tooltip_text`, `theme_id`
  - Holds DPG ids: `_button_id`, `_tooltip_id`, `_tooltip_text_id`
  - **Public API (plugin-facing, frozen contract):**
    - `set_label(text)`
    - `set_tooltip(text)`
    - `set_theme(theme_id)`, `set_colors(bg, fg, hover=None, active=None)`
    - `set_overlay_bar(kind: str, pct: float, color_rgba)` — slot-based bars (Phase 4 wires drawing)
    - `set_status_badge(text | None, color_rgba=None)` — corner overlay text
    - `set_dim(amount: 0..1)` — alpha multiplier (LoadingDetection use case)
    - `set_meta(key, value)` / `get_meta(key, default=None)` — free-form per-button per-plugin storage
    - `flash(color_rgba, ms)` — temporary highlight (depends on TickScheduler in Phase 5)
    - `destroy()`
    - `char` (read-only property), `dpg_id` (read-only escape hatch)
  - **Private:** `_create_dpg_button()`, `_apply_theme()`, `_rebuild_overlay()`, `_tick(dt)` (no-op until Phase 4)
- [x] In `src/fast_eq_windows/app.py` lines 282-313, replace the `dpg.add_button(...)` + tooltip block with `CharacterButton(...)`
- [x] `_rebuild_table` keeps `self._buttons: list[CharacterButton]`; calls `b.destroy()` on the previous list before rebuild

**Verify**: buttons render identically; click focuses window; tooltip works; search + anon modes unchanged.

---

## Phase 2 — Abstract `Character` and `GameAdapter`

Goal: nothing outside the adapter imports `EQChar` directly.

- [x] Create `src/fast_eq_windows/core/character.py` — `Character` `Protocol`:
  ```python
  id: str           # stable key, EQ uses f"{name}.{server}"
  display_name: str # default button label
  group_row: str    # row grouping (EQ: server)
  group_col: str    # column grouping (EQ: class)
  sort_key: str     # within-cell sort
  window_id: int    # OS handle for focus
  raw: dict         # adapter-specific extras (level, zone, etc.)
  ```
- [x] Create `src/fast_eq_windows/core/game_adapter.py` — `GameAdapter` ABC: `start`, `stop`, `request_refresh`, `add_listener(cb)`, `focus(character)`, optional `row_label`, `col_labels`, `tooltip_for`
- [x] Create `src/fast_eq_windows/adapters/eq_adapter.py` `EQGameAdapter` wrapping `WindowSnapshot`
  - Adds protocol attributes to `EQChar` (`id`, `display_name`, `group_row`, `group_col`, `sort_key`, `raw`) — protocol is duck-typed, so adding properties to `EQChar` is enough; do NOT subclass
  - `tooltip_for` reproduces tooltip logic from `app.py:289-301`
- [x] In `app.py`, replace `WindowSnapshot` with `self._adapter: GameAdapter = EQGameAdapter(...)`
- [x] `_rebuild_table` iterates `Character` objects via the protocol; anon helpers (`_anon_name`, `_anon_class`) stay in `app.py` as a presentation layer over the protocol

**Verify**: app behaves identically; anon modes still work; `app._adapter.name == "everquest"`.

---

## Phase 3 — Plugin lifecycle, AppContext, and loader

- [x] Create `src/fast_eq_windows/core/plugin.py` `Plugin` base class:
  - `name`, `version`, `requires` class attrs
  - Hooks: `on_load(ctx)`, `on_unload()`, `on_snapshot(chars)`, `on_button_create(button)`, `on_button_destroy(button)`, `on_tick(dt)`, `on_event(name, payload)`
- [x] Define `AppContext` dataclass exposing:
  - `characters() -> list[Character]` (read-only snapshot)
  - `buttons` → `ButtonRegistry`
  - `events` → `EventBus` (Phase 5)
  - `scheduler` → `TickScheduler` (Phase 5)
  - `settings` → namespaced `SettingsNamespace` (Phase 6)
  - `adapter` → the `GameAdapter`
  - `log(msg)` — namespaced print
  - `paths` → `plugin_dir`, `data_dir`, `config_path`
  - `register_menu(label, callback)` — adds under "Plugins" menu
- [x] Create `src/fast_eq_windows/core/button_registry.py`: `get(char_id)`, `by_window_id(wid)`, `all()`, `for_class(group_col)`, internal `_register/_unregister`
- [x] Create `src/fast_eq_windows/core/plugin_loader.py` `PluginHost`:
  - `discover(plugins_dir)` — `importlib.util.spec_from_file_location` per subdir
  - `load(enabled_names)` — topological sort over `requires`, calls `on_load(ctx)`
  - `unload_all()` — reverse order, calls `on_unload()`
  - `dispatch(method_name, *args)` — fan-out, per-plugin try/except so a bad plugin can't crash the host (logs traceback with plugin name)
- [x] In `app.py`:
  - Add a "Plugins" menu in `_setup_ui` next to Theme/Fonts
  - In `__init__`: build `AppContext`, `host.discover()`, `host.load(enabled)`
  - In `run()`: dispatch `on_tick(dt)` per frame
  - In `_on_snapshot` flow: dispatch `on_snapshot(characters)` after `_rebuild_table`
  - In `_rebuild_table`: dispatch `on_button_create(button)` after each `CharacterButton` is registered; `on_button_destroy(button)` before destruction
  - Before `dpg.destroy_context()`: `host.unload_all()`
- [x] For verification only: drop a tiny throwaway `_smoketest/plugin.py` in the user plugins dir (`~/.config/fast_eq_windows/plugins/_smoketest/plugin.py`) that logs in `on_load` and `on_button_create`. Enable in `~/.config/fast_eq_windows/plugins.json`, verify, then delete. **This is verification scaffolding done on the user's machine, NOT a file checked into the repo.** Verified with an isolated temporary plugin/config smoke test so no persistent user plugin files were left behind.

**Verify**: smoketest logs appear when enabled; disabling silences logs; `raise RuntimeError("test")` inside the smoketest does NOT crash the app. Then delete `~/.config/fast_eq_windows/plugins/_smoketest/`.

---

## Phase 4 — Per-button live mutation (no full rebuild)

Goal: plugins update buttons every frame/tick without DPG widget churn. This is the technical foundation for any visual plugin.

- [x] Restructure `CharacterButton` rendering: per-button `dpg.child_window` (no scrollbar/padding) holding a `dpg.drawlist` and the actual button. Bars + badges drawn onto the drawlist as `draw_rectangle`/`draw_text` primitives — cheap to clear and re-add
- [x] Implement `set_overlay_bar(kind, pct, color)`:
  - Stores in `self._bars[kind]`
  - `_rebuild_overlay()` clears drawlist and redraws all bars in insertion-slot order (slot 0 top, slot 1 below, etc.) — plugin doesn't pick slot, button does
- [x] Implement `set_status_badge(text, color)` — `draw_text` in top-right of drawlist
- [x] Implement `set_dim(amount)` — translucent black `draw_rectangle` overlay with given alpha
- [x] Implement `set_colors(bg, fg, hover=None, active=None)` — builds an ad-hoc theme via a new `class_colors.build_dynamic_theme(bg, fg, hover, active)` helper (sibling of `build_class_theme` at line 31) and binds it
- [x] **Optimization (recommended last in this phase):** in `_rebuild_table`, diff new char list against `self._buttons` by `char.id`. Only destroy gone, only create new, update labels/themes on existing. Preserves plugin state across rebuilds. If too invasive, defer to Phase 4b — but then plugins must be idempotent in `on_button_create` (re-apply from cached state keyed by `char.id`). **Status:** deferred per the plan; `docs/PLUGINS.md` documents the idempotent `on_button_create` requirement.

**Verify**: from a temporary smoketest plugin, `ctx.buttons.all()[0].set_overlay_bar("foo", 0.5, (0,255,0,180))` shows a green half-bar; `set_dim(0.5)` darkens; clicks still focus (drawlist must not eat input). Remove smoketest after.

---

## Phase 5 — Event bus + tick scheduler

- [x] Create `src/fast_eq_windows/core/event_bus.py`: `subscribe`, `unsubscribe`, `publish(name, payload)` synchronous fan-out, per-subscriber try/except
  - Built-in events emitted by the host: `snapshot.updated`, `button.created`, `button.destroyed`, `button.clicked`, `app.shutdown`. Plugins are free to define their own namespaces (`health.update`, `loading.started`, etc.) — the host doesn't reserve names.
- [x] Create `src/fast_eq_windows/core/tick_scheduler.py`: `every(seconds, cb)`, `after(seconds, cb)`, `cancel(handle)`, `pump(now)` — called from main loop
- [x] In `app.run()`: `self._ctx.scheduler.pump(time.monotonic())` per frame, then `host.dispatch("on_tick", dt)`
- [x] `ButtonRegistry` publishes `button.created`/`button.destroyed`. Button click path publishes `button.clicked` with `{char_id, window_id}`
- [x] Wire `CharacterButton.flash(color, ms)` to use `scheduler.after(ms, clear)` now that the scheduler exists

**Verify**: temporary smoketest subscribes to `button.clicked` and logs char id on click; `scheduler.every(1.0, ...)` logs once per second. Remove smoketest after.

---

## Phase 6 — Plugin settings persistence

- [x] Create `src/fast_eq_windows/core/settings_store.py`:
  - `SettingsStore(path)` loads/saves single JSON file
  - `namespace(plugin_name) -> SettingsNamespace` with `get(key, default)`, `set(key, value)`, `save()`
  - Auto-saves on `set` debounced ≤500ms via `TickScheduler`
- [x] `AppContext.settings` is the namespace bound to that plugin's name
- [x] Add "Plugins → Open settings folder" menu (full GUI editor out of scope)
- [x] `config/plugins.json` schema:
  ```json
  {
    "enabled": [],
    "settings": {}
  }
  ```
  Format documented; per-plugin keys filled in by users when they install plugins.

**Verify**: temporary smoketest sets a value, restart app, smoketest reads it back. Remove smoketest after.

---

## Phase 7 — Polish + documentation

- [x] `_template/plugin.py` skeleton (the one written by `bootstrap()` in Phase 0) gets fleshed out with comments showing every lifecycle hook and `AppContext` surface — a real copy-paste starter
- [x] The auto-written `README.md` in `~/.config/fast_eq_windows/plugins/` gets fleshed out: directory convention, how to enable a plugin, link to docs/PLUGINS.md
- [x] `docs/PLUGINS.md` (in the repo) documenting:
  - **Where plugins go**: `~/.config/fast_eq_windows/plugins/<name>/plugin.py` (and the env-var override + fallback path)
  - The `Plugin` lifecycle hooks
  - The `AppContext` API surface
  - The `CharacterButton` public API as a frozen contract (private methods may change)
  - The `Character` protocol — what plugins can read about a character
  - Threading rules (DPG calls must happen on the main thread; use `queue.Queue` from worker threads, drain in `on_tick`)
  - Built-in event names
  - Convention: plugin-emitted events use a namespace (`<plugin_name>.<event>`)
  - Settings file format and location
- [x] "Plugins → Reload" menu — `unload_all → re-discover → load`. Plugins MUST honor `on_unload` (close sockets, cancel scheduler handles). Caveats documented in PLUGINS.md.
- [x] "Plugins → Open plugins folder" menu — opens `user_plugins_dir()` in the system file manager
- [x] Update repo `README.md` with a Plugins section pointing users to `~/.config/fast_eq_windows/plugins/` and `docs/PLUGINS.md`

**Verify**: repo README and on-disk `~/.config/fast_eq_windows/plugins/README.md` both read cleanly; the `_template` plugin can be enabled and runs without errors; reload menu works.

---

## Critical files

- `src/fast_eq_windows/app.py` — major refactor of `_rebuild_table` (188-315), `__init__` (44-51), `run` (53-79), `_setup_ui` (81-143)
- `src/fast_eq_windows/window_scanner.py` — add Character protocol fields onto `EQChar` (13-21); listener pattern at 130-132 is the model for the new event bus
- `src/fast_eq_windows/class_colors.py` — `build_class_theme` (line 31) gets a sibling `build_dynamic_theme(bg, fg, hover, active)` for `set_colors`
- `src/fast_eq_windows/core/character_button.py` (NEW) — keystone class
- `src/fast_eq_windows/core/plugin_loader.py` (NEW) — lifecycle host
- `src/fast_eq_windows/core/plugin.py` (NEW) — `Plugin` ABC + `AppContext`
- `src/fast_eq_windows/core/event_bus.py` (NEW)
- `src/fast_eq_windows/core/tick_scheduler.py` (NEW)
- `src/fast_eq_windows/core/settings_store.py` (NEW)
- `src/fast_eq_windows/core/button_registry.py` (NEW)
- `src/fast_eq_windows/core/character.py` (NEW)
- `src/fast_eq_windows/core/game_adapter.py` (NEW)
- `src/fast_eq_windows/adapters/eq_adapter.py` (NEW)
- `src/fast_eq_windows/core/plugin_paths.py` (NEW) — resolves user plugin/config directories
- `docs/PLUGINS.md` (NEW)
- `README.md` — Plugins section pointing at the user plugins directory

**NOT touched (intentionally)**: `pyproject.toml` and `build_launcher.py` do NOT need plugin-related changes. Plugins live outside the binary. PyInstaller bundles only the framework that loads them.

---

## Open questions (review before starting)

1. **Plugin distribution**: file-drop `plugins/<name>/plugin.py` (recommended, "super simple") vs pip-installable via `entry_points`. `PluginHost.discover` interface stays the same either way — start with file-drop.
2. **Hot-reload**: Python module reload is fragile. Recommend full `unload_all → re-discover → load` cycle with strict `on_unload` contract (close sockets, cancel handles). Plugins that don't honor it require app restart — document.
3. **Sandboxing**: none. Plugins are full Python with full app access. Fine for personal tool, dangerous if you share builds. Ship a "trusted plugins only" warning in README.
4. **Inter-plugin communication**: event bus only (loose coupling), or a `ctx.services.register(name, self)` registry too? Recommend events-only — plugins publish/subscribe under their own namespace. Direct method calls between plugins create import-coupling that breaks hot-reload. Document.
5. **Threading**: adapter scan thread + plugin worker threads (HTTP, TCP) all funnel via `queue.Queue` into the DPG main thread. No DPG calls outside main thread — matches existing `WindowSnapshot` pattern.
6. **Button lifetime across snapshots**: Phase 4 diff-and-reuse keeps plugin state automatically. If skipped, plugins must be idempotent in `on_button_create` (re-apply from cached state keyed by `char.id`). Recommend doing the diff.
7. **Anon mode and plugins**: plugins should see real `Character` data; anonymized text only flows through `CharacterButton.set_label` set by `app.py`. Plugin code never reasons about anon. Confirm.
8. **`Character.id`**: use `f"{name}.{server}"` not `window_id` so plugin state survives window-id churn (logout/login on the same window). Confirm.
9. **WoW-adapter realism**: `group_row`/`group_col` are just adapter-chosen strings — no game semantics encoded. Generic enough for any roster-grouped game.

---

## Validation — does the architecture actually support the planned plugins?

Paper exercise. NOT implementing these — just confirming the architecture is sufficient. Each is a one-liner sketch of how it would be written against the framework. If any is impossible, the architecture has a gap.

- **HealthBarPlugin**: subscribes to `health.update` events; stores `dict[char_id, pct]`; in handler calls `ctx.buttons.get(id).set_colors(...)` (lerped) + `set_overlay_bar("health", pct, ...)`. Re-applies in `on_button_create` for rebuild safety. ✅
- **ManaBarPlugin**: identical shape; uses slot via `set_overlay_bar("mana", ...)`; `CharacterButton` stacks bars in insertion order. ✅
- **CrewMonitorPlugin**: worker thread polls HTTP; `queue.Queue` drained in `on_tick`; per entry calls `ctx.buttons.get(...).set_status_badge(...)` and `set_meta("crew.status", ...)`. Settings: `endpoint` + `interval_s` via `ctx.settings`. ✅
- **EQBCPlugin**: TCP socket worker thread; lines → queue → `on_tick` drain; publishes `chat.received` events; subscribes to `eqbc.send` for outgoing. Other plugins call `button.flash(...)` in their own `chat.received` handlers. ✅
- **LoadingDetectionPlugin**: hooks `on_snapshot`; compares title/zone vs prior; emits `loading.started`/`loading.ended`; in handlers calls `button.set_dim(...)` and `set_status_badge(...)`. ✅

If a plugin author needs something the public API doesn't provide, the `dpg_id` escape hatch on `CharacterButton` exists for raw DPG access — but new use cases should bubble back into the public API.

---

## Verification (end-to-end, manual)

After each phase:
- `uv run fast-eq-windows` launches without error
- All buttons render, click-to-focus still works
- Search filter + anon modes still work (regression check)
- Phase-specific verification listed inline above

After Phase 7:
- A user can drop a `plugin.py` in `~/.config/fast_eq_windows/plugins/<name>/`, list `<name>` in `~/.config/fast_eq_windows/plugins.json`'s `enabled` array, restart the app, and see it load
- The Reload menu reloads it without restart
- A misbehaving plugin logs a traceback but doesn't crash the host
- A PyInstaller build (`build_launcher.py`) does NOT contain any user plugin code — only the framework — and still finds plugins on the user's machine when run

No automated tests until plugin system stabilizes — defer to a later cleanup pass.

---

## Suggested commit cadence

One PR per phase. Run the app at the end of each phase. Don't merge the next phase until the previous is verified.

---

## Execution strategy — how the implementing Claude session should run the work

**Model selection**: Sonnet subagents do the grunt coding in parallel. Opus (the orchestrator) stays at the architectural level — designing interfaces, integrating subagent output, resolving conflicts, reviewing diffs. **Haiku is NOT used for this project** — too weak for code of this complexity and the protocol/ABC work in particular.

**Parallelism rules per phase:**

- **Phase 0** — single Sonnet subagent (trivial setup; not worth fanning out).
- **Phase 1** — single Sonnet subagent (one file `character_button.py` + one localized edit in `app.py`; serialized).
- **Phase 2** — fan out 3 Sonnet subagents in parallel:
  1. `core/character.py` (Protocol)
  2. `core/game_adapter.py` (ABC)
  3. `adapters/eq_adapter.py` + `EQChar` property additions
  Then orchestrator integrates and edits `app.py` to use them (sequential after the three).
- **Phase 3** — fan out 3 Sonnet subagents in parallel:
  1. `core/plugin.py` (Plugin ABC + AppContext dataclass)
  2. `core/button_registry.py`
  3. `core/plugin_loader.py` (PluginHost)
  Then orchestrator wires them into `app.py` (sequential after).
- **Phase 4** — single Sonnet subagent for the rendering restructure (it's all inside `character_button.py` and tightly coupled). The diff-and-reuse optimization is a separate Sonnet subagent if pursued.
- **Phase 5** — fan out 2 Sonnet subagents in parallel: `event_bus.py` and `tick_scheduler.py`. Orchestrator wires both into `app.py` after.
- **Phase 6** — single Sonnet subagent (`settings_store.py` + `app.py` wiring; small).
- **Phase 7** — fan out 3 Sonnet subagents in parallel:
  1. `_template/plugin.py` skeleton + on-disk README content (written by `bootstrap()`)
  2. `docs/PLUGINS.md`
  3. Reload + Open-folder menu items in `app.py` and repo `README.md` updates

**Subagent briefing rules**: each Sonnet subagent gets a self-contained prompt with the relevant section of this plan, the current file paths and line refs it must read, and a clear deliverable. Do NOT delegate synthesis decisions ("based on the architecture, decide…") — those belong to the orchestrator. Subagents return code; orchestrator decides whether it integrates cleanly.

**After each subagent batch returns**: orchestrator reads the actual files written (trust-but-verify), runs `uv run fast-eq-windows` to confirm the app still launches, then performs the phase's manual verification checklist before moving on.

**Cost discipline**: the user is on limited weekly Anthropic credits. Sonnet for grunt work, Opus only for orchestration and integration. Avoid redundant exploration once a phase is briefed — pass exploration output forward instead of re-discovering.
