# Architecture

Fast_EQ_Windows is a single-process DearPyGui application with a small
plugin host bolted on. There is no daemon, no IPC, and no server. This
document describes the runtime shape so contributors can find their way
around without having to read every file.

## Module map

```text
src/fast_eq_windows/
├── app.py                  Host application + main loop
├── window_scanner.py       wmctrl/xdotool wrapper, runs the scan thread
├── class_colors.py         WoW-style class color palette + theme builders
├── adapters/
│   └── eq_adapter.py       EQGameAdapter — wraps window_scanner behind GameAdapter
└── core/
    ├── game_adapter.py     GameAdapter ABC (game-agnostic source of Characters)
    ├── character.py        Character Protocol — the shape plugins consume
    ├── character_button.py CharacterButton — DPG button wrapper, plugin-facing
    ├── button_registry.py  Lookup index for live buttons
    ├── event_bus.py        Synchronous publish/subscribe bus
    ├── tick_scheduler.py   Frame-pumped after()/every() timer
    ├── settings_store.py   plugins.json reader/writer with namespaces
    ├── plugin.py           Plugin base class + AppContext + AppPaths
    ├── plugin_loader.py    PluginHost — discovery, dependency-ordered load
    └── plugin_paths.py     User config layout, env overrides, bootstrap
```

`adapters/` is the only place that knows about EverQuest specifically.
The host (`app.py`) talks to the abstract `GameAdapter`, the public
`Character` Protocol, and `CharacterButton`. Adding another game means
writing a new adapter that produces objects satisfying `Character`.

## Runtime data flow

A new snapshot lifecycle, end to end:

```text
EQGameAdapter (worker thread)
  └─ wmctrl round-trip
     └─ list[EQChar]                            ← satisfies Character Protocol
        └─ App._on_snapshot(chars)              ← still on worker thread
           └─ result_queue.put(chars)           ← thread hand-off

App.run() main loop (DPG thread)
  ├─ result_queue.get_nowait()                  ← drain pending snapshots
  ├─ App._rebuild_table()                       ← teardown + rebuild buttons
  │     ├─ for each old button:
  │     │     plugin_host.dispatch("on_button_destroy", b)
  │     │     button_registry._unregister(b)    → publishes "button.destroyed"
  │     │     b.destroy()
  │     └─ for each new button:
  │           CharacterButton(...)
  │           button_registry._register(b)      → publishes "button.created"
  │           plugin_host.dispatch("on_button_create", b)
  ├─ plugin_host.dispatch("on_snapshot", chars)
  ├─ events.publish("snapshot.updated", {...})
  ├─ scheduler.pump(now)                        ← fires due after()/every()
  ├─ plugin_host.dispatch("on_tick", dt)
  └─ dpg.render_dearpygui_frame()
```

Two invariants worth knowing:

1. **All plugin code runs on the DPG thread.** The only producer thread is
   the window scanner, and it never touches DPG or plugins directly — it
   only puts results on `result_queue`.
2. **`button.created` fires before `on_button_create`.** The registry is
   the source of truth, so it publishes the event before we dispatch the
   hook. Plugins that subscribe to the event get the same button their
   `on_button_create` hook would later receive.

## Threading model

| Thread                    | Owns                                                   |
| ------------------------- | ------------------------------------------------------ |
| DPG main thread           | Everything in `core/`, `app.py`, plugin hooks, DPG     |
| Scanner worker            | `window_scanner.WindowSnapshot._loop`, `wmctrl` calls  |
| Plugin worker (optional)  | Anything a plugin starts; must not touch DPG           |

The boundary is `App._on_snapshot(chars)` → `result_queue.put(...)`. The
main loop drains the queue at the top of every iteration. Plugins that
need worker threads must follow the same pattern: push results into a
`queue.Queue`, drain in `on_tick(dt)`, and apply changes from there.

## Settings and persistence

`SettingsStore` owns `~/.config/fast_eq_windows/plugins.json`. Layout:

```json
{
  "enabled": ["plugin_a", "plugin_b"],
  "settings": {
    "plugin_a": { "any": "json", "the": ["plugin", "wants"] }
  }
}
```

* Reads are O(1) against an in-memory cache.
* Writes are debounced through `TickScheduler.after(0.5s, save)` so a
  burst of `set()` calls collapses into one disk write.
* `SettingsNamespace` is the per-plugin view; the host is the only thing
  that ever sees the full document.
* `reload()` re-reads from disk and discards in-memory changes; called
  during **Plugins → Reload**.

## Plugin host integration

```text
PluginHost (core/plugin_loader.py)
  ├─ discover()           imports each <dir>/<name>/plugin.py uniquely
  ├─ load(enabled)        topo-sorts on .requires; calls on_load(ctx)
  ├─ unload_all()         on_unload in reverse order
  └─ dispatch(name, …)    forwards to every loaded plugin, isolated by try/except
```

The host (`App._make_plugin_context`) hands every plugin its own
`AppContext` bound to:

* a plugin-specific `paths.plugin_dir`
* a `SettingsNamespace` keyed to `plugin.name`
* a `ctx.log()` prefix that includes the plugin name
* the same shared `EventBus`, `TickScheduler`, `ButtonRegistry`,
  `GameAdapter`, and characters provider

`App` also bridges every event published on the bus into
`Plugin.on_event` via `EventBus.subscribe_all` so plugins that want a
catch-all observer don't have to enumerate names.

## Reload contract

**Plugins → Reload** is implemented in `App._reload_plugins`:

1. `plugin_host.unload_all()` — calls `on_unload` in reverse load order.
2. `_clear_plugin_menu_items()` — deletes any DPG menu items the host
   recorded from `register_menu`.
3. `settings.reload()` — re-reads `plugins.json` so newly enabled
   plugins are picked up.
4. `_load_plugins()` — re-discovers and loads enabled plugins.
5. **Replay:** for each currently registered button the host dispatches
   a fresh `on_button_create`, then dispatches `on_snapshot` with the
   current character list. Newly loaded plugins get the same view of the
   world they would have gotten at app start.

Plugins are responsible for tearing themselves down in `on_unload`.
Background threads, sockets, scheduler handles, and event subscriptions
that survive `on_unload` will leak across a reload.

## Anonymization

Anonymization is a *display* concern, not a data concern. `app.py` keeps
the original `Character` objects and only swaps the rendered label /
class / server through `_display_name`, `_display_class`, and
`_display_server`. Plugins that read `character.display_name` or
`button.char.*` always see real data. The bundled `anonymous_server`
plugin does its own per-button label rewriting on top.

## Extending

Common changes and where they live:

| Change                                     | Touch                                              |
| ------------------------------------------ | -------------------------------------------------- |
| New game adapter                           | New `adapters/<game>_adapter.py`, register in `App.__init__` |
| New built-in event                         | Publish in `app.py`, document in `EVENTS.md`       |
| New `CharacterButton` decoration kind      | Add public method in `character_button.py`, document in `PLUGINS.md` |
| New plugin lifecycle hook                  | Add no-op default to `Plugin`, dispatch from `App`, document in `PLUGINS.md` |
| New menu item                              | `_setup_ui` in `app.py`                            |
