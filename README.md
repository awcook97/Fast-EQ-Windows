# Fast EQ Windows

A lightweight EverQuest window manager for Linux multiboxers. Scans running EQ clients, displays them in a server × class grid, and brings any window to the front with one click.

![Platform](https://img.shields.io/badge/platform-Linux-blue)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- Auto-detects all running EQ clients via `xdotool` + Wine process scanning
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
- Auto-refresh on a configurable interval (default: 1 hour)
- **Streaming scan** — characters pop into the grid as they're found; UI never blocks
- **Zoning retry** — characters mid-zone (non-EQ window title) are retried every 2 s for up to 30 s in the background, then added to the grid when they finish loading
- Window auto-sizes to fit content — starts small and grows as characters populate
- Customizable theme and fonts via built-in editor

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

1. `pgrep -f eqgame.exe` finds all Wine processes running EQ
2. Each PID's `/proc/<pid>/cmdline` is checked for `patchme` to skip Wine helper processes
3. All PIDs are scanned in parallel via `ThreadPoolExecutor` (capped at 16 concurrent X connections)
4. For each PID: `xdotool search --pid <pid> --onlyvisible` finds the X window
5. Window titles are parsed with a regex to extract name, server, level, class, zone, and instance
6. Characters appear in the UI as each PID resolves — no waiting for all scans to finish
7. PIDs whose window title doesn't match (character is mid-zone) are retried every 2 s for up to 30 s in a background thread, then added when ready
8. Clicking a button calls `xdotool windowactivate` + `windowraise` + `windowfocus`

---

## License

MIT
