import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

_TITLE_RE = re.compile(
    r'^(\w+)\.(\w+)\s+\(Lvl:(\d+)\s+(.*?)\)\s+(.+?)(?:\s+(\d+))?\s*$'
)


@dataclass
class EQChar:
    name: str
    server: str
    level: int
    eq_class: str
    zone: str
    instance: int
    window_id: int


def _run(args: list[str], timeout: int = 5) -> str:
    try:
        r = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        if r.stderr:
            print(f"[xdotool stderr] {r.stderr.strip()}")
        return r.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        print(f"[scanner error] {args[0]}: {e}")
        return ""


def _get_eqgame_pids() -> list[int]:
    """
    Find PIDs of actual EQ game processes.
    eqgame.exe has two Wine processes per instance; the real one has 'patchme'
    in its cmdline (C:\\path\\eqgame.exe patchme /login:...).
    """
    raw = []
    for line in _run(["pgrep", "-f", "eqgame.exe"]).splitlines():
        line = line.strip()
        if line:
            try:
                raw.append(int(line))
            except ValueError:
                pass

    game_pids = []
    for pid in raw:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                cmdline = fh.read().replace(b"\x00", b" ").decode("utf-8", errors="replace")
            if "patchme" in cmdline.lower():
                game_pids.append(pid)
            else:
                print(f"[scanner] skipping pid {pid} (no 'patchme' in cmdline): {cmdline[:80]}")
        except OSError as e:
            print(f"[scanner] could not read cmdline for pid {pid}: {e}")

    return game_pids


def _scan_one_pid(pid: int) -> EQChar | None:
    wids_raw = _run(["xdotool", "search", "--pid", str(pid), "--onlyvisible"])
    print(f"[scanner] pid {pid} -> wids: {wids_raw.strip()!r}")

    for line in wids_raw.splitlines():
        wid_str = line.strip()
        if not wid_str:
            continue
        try:
            wid = int(wid_str)
        except ValueError:
            continue
        if wid == 0:
            continue

        title = _run(["xdotool", "getwindowname", str(wid)], timeout=2).strip()
        print(f"[scanner]   wid {wid} title: {title!r}")
        char = _parse_title(title, wid)
        if char:
            print(f"[scanner]   -> matched: {char.name}.{char.server} ({char.eq_class})")
            return char

    return None


def scan_eq_windows() -> list[EQChar]:
    pids = _get_eqgame_pids()
    if not pids:
        return []

    chars: list[EQChar] = []
    with ThreadPoolExecutor(max_workers=len(pids)) as pool:
        futures = {pool.submit(_scan_one_pid, pid): pid for pid in pids}
        for future in as_completed(futures):
            char = future.result()
            if char:
                chars.append(char)

    return chars


def _parse_title(title: str, window_id: int) -> EQChar | None:
    m = _TITLE_RE.match(title)
    if not m:
        return None
    name, server, level, eq_class, zone, instance = m.groups()
    return EQChar(
        name=name,
        server=server,
        level=int(level),
        eq_class=eq_class.strip(),
        zone=zone.strip(),
        instance=int(instance) if instance else 0,
        window_id=window_id,
    )


def focus_window(window_id: int) -> None:
    print(f"[focus] windowactivate {window_id}")
    _run(["xdotool", "windowactivate", str(window_id)])
    print(f"[focus] windowraise {window_id}")
    _run(["xdotool", "windowraise", str(window_id)])
    print(f"[focus] windowfocus {window_id}")
    _run(["xdotool", "windowfocus", str(window_id)])
