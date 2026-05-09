# Fast EQ Windows

A lightweight EverQuest window manager for Linux multiboxers. Scans running EQ clients, displays them in a server × class grid, and brings any window to the front with one click.

![Platform](https://img.shields.io/badge/platform-Linux-blue)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- Auto-detects all running EQ clients via a single `wmctrl` X11 round-trip (cheap even at 100+ boxes)
- Grid layout: **rows = servers**, **columns = classes** — only what's actually running
- Buttons sorted alphabetically by character name within each class
- Up to 6 characters per column before wrapping to a second column
- Per-class color coding using World of Warcraft class colors
- One-click window focus (raises + activates the target client)
- **Search bar** — filter characters by name in real time; status shows "N of M characters"
- **Anonymous mode** with four levels:
  - **Off** — real names and classes shown
  - **Anon: Names** — character names replaced with random pronounceable names
  - **Anon: Names+Classes** — names and classes both randomized
  - **Oops: Only Paladins** — everyone shows as Paladin
  - **Full Anon: Norrath** — names, classes, and server all randomized; all characters merged into one "Norrath" server
- Auto-refresh on a configurable interval (default: 1 hour) — runs on a single background thread
- **Zoning-aware** — characters whose titles haven't settled (mid-zone) are skipped on the current tick and pick up automatically on the next refresh
- Window auto-sizes to fit content — starts small and grows as characters populate
- Customizable theme and fonts via built-in editor
- Runtime plugin system — drop trusted Python plugins into your user config folder and reload them without rebuilding the app

---

## Plugins

Fast EQ Windows loads user plugins from disk at runtime. Plugins are **not**
bundled into release binaries; they live in your user config folder:

```text
~/.config/fast_eq_windows/plugins/<plugin_name>/plugin.py
```

Enable plugins in:

```text
~/.config/fast_eq_windows/plugins.json
```

Example:

```json
{
  "enabled": ["my_plugin"],
  "settings": {}
}
```

The app creates the plugin folder, a local README, and `_template/plugin.py` on
first launch. Use **Plugins → Reload** after editing `plugins.json` or plugin
source files. Use **Plugins → Open plugins folder** or **Plugins → Open settings
folder** from the menu for quick access.

See [docs/](docs/README.md) for the full documentation set:

- [docs/PLUGINS.md](docs/PLUGINS.md) — plugin API, lifecycle, AppContext, button surface
- [docs/EVENTS.md](docs/EVENTS.md) — built-in events and ordering guarantees
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module map, runtime data flow, threading
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — local setup, smoke testing, packaging

Security note: plugins are normal Python code with full access to your user
account. Only install plugins you trust.

---

## Requirements

- **Linux** with X11 (Wayland via XWayland should also work)
- [`wmctrl`](https://www.freedesktop.org/wiki/Software/wmctrl/) — used to list windows in one round-trip
- [`xdotool`](https://github.com/jordansissel/xdotool) — used only when you click a button (focus/raise)
- EverQuest running under **Wine** (`eqgame.exe patchme /login:...`)

---

## Install (release binary)

Download `fast-eq-windows-linux-x86_64` from the [latest release](../../releases/latest), then:

```bash
chmod +x fast-eq-windows-linux-x86_64
./fast-eq-windows-linux-x86_64
```

No Python or uv required.

---

## Install (from source)

```bash
git clone https://github.com/awcook97/Fast_EQ_Windows.git
cd Fast_EQ_Windows
./setup.sh
```

`setup.sh` will:
1. Install [uv](https://github.com/astral-sh/uv) if it isn't already
2. Install all Python dependencies
3. Check for `wmctrl` + `xdotool` and tell you how to install them if missing
4. Create two launcher scripts in the project directory

**Install wmctrl + xdotool if prompted:**

| Distro | Command |
|--------|---------|
| Ubuntu / Debian | `sudo apt install wmctrl xdotool` |
| Fedora / RHEL | `sudo dnf install wmctrl xdotool` |
| Arch | `sudo pacman -S wmctrl xdotool` |

---

## Usage

```bash
./fast-eq-windows.sh          # quiet (no terminal output)
./fast-eq-windows-debug.sh    # with full debug logging
```

Or directly via uv (debug output included):

```bash
uv run fast-eq-windows
```

### Controls

| Control | Action |
|---------|--------|
| **Refresh** button | Re-scan for EQ windows immediately |
| **Auto-refresh** checkbox | Toggle periodic background refresh |
| **Interval (s)** field | How often to auto-refresh (min 60 s) |
| **Anon** dropdown | Set anonymization level (Off / Names / Names+Classes / Only Paladins / Full Norrath) |
| **Search** field | Filter displayed characters by name |
| Click any character button | Raise + focus that EQ window |
| Hover over a button | Show character details (level, class, zone, instance) |
| **Theme → Configure** | Live color theme editor with save/load |
| **Fonts → Font Settings** | Font picker with size/scale controls |

---

## Window title format

The scanner expects EQ window titles in the standard format:

```
{Name}.{Server} (Lvl:{Level} {Class}) {Zone} {Instance}
```

Example: `Roubun.luclin (Lvl:115 Enchanter) Modest Guild Hall 14065`

---

## Class colors

Colors match World of Warcraft class colors for easy recognition at a glance.

| Class | Color |
|-------|-------|
| Warrior | Gold |
| Cleric | White |
| Paladin | Pink |
| Ranger | Hunter Green |
| Shadow Knight | Death Knight Red |
| Druid | Orange |
| Monk | Jade |
| Bard | Evoker Teal |
| Rogue | Yellow |
| Shaman | Blue |
| Necromancer | Warlock Purple |
| Wizard | Mage Cyan |
| Magician | Light Blue |
| Enchanter | Demon Hunter Purple |
| Beastlord | Orange |
| Berserker | Red |

Text color is automatically chosen for maximum contrast against the button background.

---

## Development

```bash
git clone https://github.com/awcook97/Fast_EQ_Windows.git
cd Fast_EQ_Windows
uv sync --group dev     # includes PyInstaller
uv run fast-eq-windows  # run with debug output
```

### Build a standalone binary locally

```bash
uv run pyinstaller \
  --onefile \
  --collect-all dearpygui \
  --hidden-import dearpygui.dearpygui \
  --name fast-eq-windows \
  build_launcher.py
# output: dist/fast-eq-windows
```

### Cut a release

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions will build binaries for Linux, Windows, and macOS and publish them as a release automatically.

---

## How it works

1. A single `wmctrl -lp` call returns every window on the display along with its PID and title — one X client connection, one round-trip
2. Rows whose titles don't match the EQ format are dropped (zoning windows, gnome panels, etc.)
3. For surviving PIDs, `/proc/<pid>/cmdline` is read directly to confirm `eqgame.exe patchme` (a file read, not a subprocess) — this filters out the Wine helper process
4. The result is cached in a `WindowSnapshot` refreshed by a single background thread; the UI reads from cache instantly
5. Mid-zone characters whose titles haven't matched yet are picked up on the next snapshot tick — no per-PID retry storm
6. Clicking a button calls `xdotool windowactivate` + `windowraise` + `windowfocus` for that one window only

### Why this matters at high box counts

The earlier implementation spawned `xdotool search` and `xdotool getwindowname` per PID per refresh — at 86 boxes that's 170+ subprocesses, each opening its own X11 client connection. X11 caps at ~256 concurrent clients and Wine already uses ~87 of those, so a refresh storm could push the display server past its limit and take down the desktop session. The current design uses **one** X client per refresh.

---

## License

MIT
