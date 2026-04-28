# Fast EQ Windows

A lightweight EverQuest window manager for Linux multiboxers. Scans running EQ clients, displays them in a server × class grid, and brings any window to the front with one click.

![Platform](https://img.shields.io/badge/platform-Linux-blue)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- Auto-detects all running EQ clients via `xdotool` + Wine process scanning
- Grid layout: **rows = servers**, **columns = classes** — only what's actually running
- Per-class color coding with high-contrast text
- One-click window focus (raises + activates the target client)
- Auto-refresh on a configurable interval (default: 1 hour)
- Threaded scanning — all clients polled in parallel, UI never blocks
- Customizable theme and fonts via built-in editor
- Debug output off by default in release builds; full logging available in dev mode

---

## Requirements

- **Linux** with X11 (Wayland via XWayland should also work)
- [`xdotool`](https://github.com/jordansissel/xdotool)
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
3. Check for `xdotool` and tell you how to install it if missing
4. Create two launcher scripts in the project directory

**Install xdotool if prompted:**

| Distro | Command |
|--------|---------|
| Ubuntu / Debian | `sudo apt install xdotool` |
| Fedora / RHEL | `sudo dnf install xdotool` |
| Arch | `sudo pacman -S xdotool` |

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
| Click any character button | Raise + focus that EQ window |
| Hover over a button | Show character details (level, zone, instance) |
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

| Class | Color |
|-------|-------|
| Warrior | Saddle Brown |
| Cleric | Silver |
| Paladin | Gold |
| Ranger | Forest Green |
| Shadow Knight | Dark Maroon |
| Druid | Olive |
| Monk | Burnt Orange |
| Bard | Purple |
| Rogue | Dark Slate |
| Shaman | Teal |
| Necromancer | Dark Red |
| Wizard | Royal Blue |
| Magician | Sky Blue |
| Enchanter | Indigo |
| Beastlord | Sienna |
| Berserker | Crimson |

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

1. `pgrep -f eqgame.exe` finds all Wine processes running EQ
2. Each PID's `/proc/<pid>/cmdline` is checked for `patchme` to skip Wine helper processes
3. `xdotool search --pid <pid> --onlyvisible` finds the X window for each game process
4. Window titles are parsed with a regex to extract name, server, level, class, zone, and instance
5. All PIDs are scanned in parallel via `ThreadPoolExecutor`
6. Clicking a button calls `xdotool windowactivate` + `windowraise` + `windowfocus`

---

## License

MIT
