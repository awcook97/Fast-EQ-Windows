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
