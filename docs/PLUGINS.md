# Fast_EQ_Windows Plugin API

Fast_EQ_Windows loads user plugins from disk at runtime. Plugins are not bundled
into the app or PyInstaller binary; they are normal Python files that live in a
user-writable folder.

## Where plugins go

Default layout:

```text
~/.config/fast_eq_windows/
  plugins/
    README.md
    _template/
      plugin.py
    my_plugin/
      plugin.py
  plugins.json
```

Search path:

1. `FAST_EQ_PLUGINS` environment variable, if set
2. `~/.config/fast_eq_windows/plugins/`
3. `~/.fast_eq_windows/plugins/` if that legacy folder exists and the primary
   config folder does not

Settings path:

1. `FAST_EQ_CONFIG` environment variable, if set
2. `~/.config/fast_eq_windows/plugins.json`

Each plugin gets one folder. The folder name is the name users put in the
`enabled` array. The folder must contain a `plugin.py` file defining a subclass
of `fast_eq_windows.core.plugin.Plugin`.

Folders beginning with `_` or `.` are ignored, so `_template/` is safe to keep
beside real plugins.

## Enabling plugins

Two ways:

1. **Manifest (recommended for shipped plugins)** — drop a `manifest.json`
   next to `plugin.py`. The repo's `scripts/sync_plugins.py` reads it on each
   sync and updates the user's `plugins.json` (without ever clobbering values
   the user has already set).

   ```json
   {
     "auto_enable": true,
     "default_settings": {
       "active": true,
       "anonymize_names": true
     }
   }
   ```

   - `auto_enable` adds the plugin to `enabled` *only the first time* — once
     a user moves the entry to `disabled` (or removes it manually) sync
     leaves their choice alone.
   - `default_settings` keys are filled in only when missing, so user edits
     always win.

2. **Manual edit** — open `~/.config/fast_eq_windows/plugins.json` and add
   the plugin folder name to the `enabled` array:

   ```json
   {
     "enabled": ["my_plugin"],
     "disabled": [],
     "settings": {}
   }
   ```

Restart the app or choose **Plugins → Reload**.

## Minimal plugin

```python
from fast_eq_windows.core.plugin import Plugin


class MyPlugin(Plugin):
    name = "my_plugin"
    version = "0.1.0"
    requires = []

    def on_load(self, ctx):
        self.ctx = ctx
        ctx.log("loaded")

    def on_unload(self):
        self.ctx.log("unloaded")
```

## Lifecycle hooks

All hooks are optional. Override only what the plugin needs.

```python
class Plugin:
    name = "unnamed"
    version = "0.0.0"
    requires = []

    def on_load(self, ctx): ...
    def on_unload(self): ...
    def on_snapshot(self, characters): ...
    def on_button_create(self, button): ...
    def on_button_destroy(self, button): ...
    def on_tick(self, dt): ...
    def on_event(self, name, payload): ...
```

- `on_load(ctx)` runs once after the plugin is imported and enabled.
- `on_unload()` runs during app shutdown and before **Plugins → Reload**.
- `on_snapshot(characters)` runs after a scan result is rendered.
- `on_button_create(button)` runs after a character button enters the registry.
- `on_button_destroy(button)` runs before a character button is destroyed.
- `on_tick(dt)` runs once per rendered frame on the main thread.
- `on_event(name, payload)` runs for every event published through the host
  event bus, including plugin-published events.

The host catches exceptions per plugin. A plugin traceback is logged, but the
app continues running.

## Dependencies

`requires` is a list of other enabled plugin folder names that should load
first:

```python
class MyPlugin(Plugin):
    name = "overlay_consumer"
    requires = ["overlay_provider"]
```

Missing or cyclic dependencies are logged and the host still attempts to load
the remaining plugins.

## AppContext API

Plugins receive `ctx` in `on_load()`.

### `ctx.characters()`

Returns a snapshot list of current `Character` objects. The returned list is a
copy; mutating it does not alter host state.

### `ctx.buttons`

`ButtonRegistry` lookup methods:

- `get(char_id)` → button or `None`
- `by_window_id(window_id)` → button or `None`
- `all()` → snapshot list of all live buttons
- `for_class(group_col)` → buttons matching a class/column label

### `ctx.events`

Synchronous event bus:

- `subscribe(name, callback)`
- `unsubscribe(name, callback)`
- `publish(name, payload=None)`

Callbacks receive one `payload` dictionary. Exceptions are caught per
subscriber.

### `ctx.scheduler`

Frame-pumped scheduler. Callbacks run on the main thread and may safely touch
DearPyGui widgets.

- `every(seconds, callback)` → handle
- `after(seconds, callback)` → handle
- `cancel(handle)`

Plugins must cancel recurring handles in `on_unload()`.

### `ctx.settings`

Namespaced persistence in `plugins.json`:

- `get(key, default=None)`
- `set(key, value)`
- `all()`
- `save()`

`set()` schedules a debounced save within 500 ms.

### `ctx.adapter`

The active `GameAdapter`. Current adapter name is `everquest`.

### `ctx.paths`

- `plugin_dir` — this plugin's folder
- `data_dir` — shared user config folder
- `config_path` — `plugins.json`

### `ctx.log(msg)`

Prints a plugin-prefixed message.

### `ctx.register_menu(label, callback)`

Adds a menu item under **Plugins** and returns its DearPyGui item id. The host
removes registered plugin menu items during **Plugins → Reload**.

## Character protocol

Plugins can read these attributes from each character:

```python
id: str
display_name: str
group_row: str
group_col: str
sort_key: str
window_id: int
raw: dict
```

For EverQuest:

- `id` is `"{name}.{server}"` and is stable across window-id churn.
- `group_row` is the server.
- `group_col` is the class.
- `raw` includes `level`, `zone`, `instance`, and `eq_class`.

Plugins see real character data even when the UI is anonymized.

## CharacterButton public API

This is the frozen plugin-facing contract. Private methods may change.

```python
button.char
button.dpg_id
button.set_label(text)
button.set_tooltip(text)
button.set_theme(theme_id)
button.set_colors(bg, fg, hover=None, active=None)
button.set_overlay_bar(kind, pct, color_rgba)
button.set_status_badge(text_or_none, color_rgba=None)
button.set_dim(amount)
button.set_meta(key, value)
button.get_meta(key, default=None)
button.flash(color_rgba, ms)
button.destroy()
```

Notes:

- `set_overlay_bar()` clamps `pct` to `0..1` and stacks bars by insertion order.
- `set_status_badge(None)` clears the badge.
- `set_dim()` clamps `amount` to `0..1`.
- `dpg_id` is an escape hatch for raw DearPyGui access. Prefer the public API
  when possible.
- Buttons may be rebuilt after search/anon/snapshot changes. Plugins should be
  idempotent in `on_button_create()` and reapply cached state keyed by
  `button.char.id`.

## Built-in events

The host publishes:

- `snapshot.updated` — `{"characters": list[Character]}`
- `button.created` — `{"button": CharacterButton}`
- `button.destroyed` — `{"button": CharacterButton}`
- `button.clicked` — `{"char_id": str, "window_id": int}`
- `app.shutdown` — `{}`

Plugins may publish their own events. Use a namespace such as
`health.update`, `loading.started`, or `eqbc.send`.

## Threading rules

DearPyGui is not thread-safe. Do not call `dpg.*`, `button.*`, or `ctx.*` UI
mutation methods from worker threads.

Recommended worker pattern:

1. Worker thread polls HTTP/TCP/files.
2. Worker pushes parsed data into `queue.Queue`.
3. `on_tick(dt)` drains the queue on the main thread.
4. `on_tick(dt)` updates buttons or publishes events.

## Reload contract

**Plugins → Reload** performs:

1. `on_unload()` on loaded plugins in reverse load order
2. rediscovery from the plugin folder
3. loading enabled plugins from `plugins.json`
4. replaying current buttons and snapshot to newly loaded plugins

Plugins must make `on_unload()` clean up everything they own:

- stop worker threads
- close sockets/files
- cancel scheduler handles
- unsubscribe event callbacks
- release external resources

Python module hot-reload is inherently imperfect. If a plugin keeps background
threads or references alive after `on_unload()`, restart the app.

## Security

Plugins are full Python code with the same permissions as your user account.
There is no sandbox. Only install trusted plugins.
