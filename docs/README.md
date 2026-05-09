# Fast_EQ_Windows docs

Project-level documentation lives here. The top-level
[README.md](../README.md) covers user-facing install and usage.

| Doc                                  | Audience                  | What's in it                                                                       |
| ------------------------------------ | ------------------------- | ---------------------------------------------------------------------------------- |
| [ARCHITECTURE.md](ARCHITECTURE.md)   | Contributors              | Module map, runtime data flow, threading model, plugin host integration            |
| [EVENTS.md](EVENTS.md)               | Plugin & host authors     | Built-in event names, payload shapes, ordering guarantees, naming conventions      |
| [DEVELOPMENT.md](DEVELOPMENT.md)     | Contributors              | Local setup, running, smoke-testing, packaging, conventions                        |
| [PLUGINS.md](PLUGINS.md)             | Plugin authors            | Plugin API contract, lifecycle hooks, AppContext, CharacterButton public surface   |

If you are writing a plugin, start at [PLUGINS.md](PLUGINS.md) and dip into
[EVENTS.md](EVENTS.md) when you need to publish or subscribe to host events.

If you are changing the host app, read [ARCHITECTURE.md](ARCHITECTURE.md)
first — it explains what is allowed to call what, and why the rebuild path
goes through the plugin host.
