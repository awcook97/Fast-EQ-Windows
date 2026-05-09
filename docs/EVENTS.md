# Event reference

The `EventBus` is the canonical channel for cross-cutting communication
between the host and plugins, and between plugins. It is synchronous and
in-process: `publish()` runs every subscriber on the calling thread
before returning. Built-in events are all published from the DPG main
thread, so subscribers can safely touch widgets.

## Subscribing

```python
def on_load(self, ctx):
    ctx.events.subscribe("button.clicked", self._on_click)

def on_unload(self):
    self.ctx.events.unsubscribe("button.clicked", self._on_click)

def _on_click(self, payload):
    char_id = payload["char_id"]
    ...
```

`subscribe_all(callback)` receives `(name, payload)` for every event;
the host uses it to bridge the bus into `Plugin.on_event`. Most plugins
should prefer named subscriptions.

Exceptions raised by a subscriber are caught, logged, and do not affect
other subscribers or the publisher.

## Built-in events

All payloads are plain `dict`. Keys are stable; the host may add new
keys in a backward-compatible release but will not rename or remove
existing ones without a major-version bump.

### `snapshot.updated`

Published once per accepted snapshot, after the table has been rebuilt
and after `Plugin.on_snapshot` has dispatched.

```python
{"characters": list[Character]}
```

* `characters` is a fresh list owned by the host. Iterating is safe;
  mutating is undefined.
* Use this if you want to react to *any* snapshot churn including the
  first one at app start.

### `button.created`

Published by `ButtonRegistry._register` whenever a new
`CharacterButton` enters the registry, *before* the matching
`Plugin.on_button_create` hook runs.

```python
{"button": CharacterButton}
```

### `button.destroyed`

Published by `ButtonRegistry._unregister` immediately before the host
deletes the underlying DPG widgets. The `CharacterButton` instance is
still usable for read-only inspection inside the subscriber, but its
DPG ids will be invalid by the time the subscriber returns.

```python
{"button": CharacterButton}
```

### `button.clicked`

Published from `App._on_button_clicked` after the adapter focuses the
target window.

```python
{"char_id": str, "window_id": int}
```

### `app.shutdown`

Published once, just before the plugin host unloads everything during
normal app exit.

```python
{}
```

This is your last chance to flush state from a subscriber. `on_unload`
runs immediately afterward and is the recommended place to release
resources.

## Ordering guarantees

Within a single snapshot cycle, events fire in this order:

```text
button.destroyed (per old button) ── then `on_button_destroy` per old button
button.created   (per new button) ── then `on_button_create` per new button
on_snapshot
snapshot.updated
```

Within `pump(now)`:

```text
scheduler.pump(now)        ← due `after()`/`every()` callbacks
on_tick                    ← per loaded plugin
dpg.render_dearpygui_frame
```

There are no async events; everything is synchronous on the main thread.

## Plugin-published events

Plugins may publish anything they like:

```python
ctx.events.publish("health.update", {"char_id": char.id, "pct": 0.42})
```

Conventions:

* Use a `<plugin>.<event>` namespace so unrelated plugins don't collide
  (`health.update`, `eqbc.send`, `loading.started`).
* Keep payloads JSON-serialisable when reasonable; future tooling may
  want to log or replay events.
* Document the events your plugin publishes in its own README so
  consumers don't have to read source.

The `Plugin.on_event(name, payload)` hook receives every event the bus
publishes (built-in *and* plugin-published). Use it for cross-cutting
observers; for normal listening, prefer a named `subscribe()`.
