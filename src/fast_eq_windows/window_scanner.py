import os
import re
import subprocess
import threading
import time
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


def _run(args: list[str], timeout: int = 10) -> str:
    try:
        r = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        if r.stderr:
            print(f"[{args[0]} stderr] {r.stderr.strip()}")
        return r.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        print(f"[scanner error] {args[0]}: {e}")
        return ""


def _is_eq_pid(pid: int) -> bool:
    """eqgame.exe has two Wine processes; the real one has 'patchme' in cmdline."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            cmdline = fh.read().replace(b"\x00", b" ").decode("utf-8", errors="replace")
        return "eqgame.exe" in cmdline.lower() and "patchme" in cmdline.lower()
    except OSError:
        return False


def scan_windows() -> list[EQChar]:
    """One wmctrl call → all EQ windows. Single X client, single round-trip.

    Replaces the per-pid xdotool storm. Windows whose titles haven't settled
    (zoning) simply don't match _TITLE_RE and are skipped — they'll appear on
    a later snapshot once their title updates.
    """
    out = _run(["wmctrl", "-lp"])
    if not out:
        return []

    chars: list[EQChar] = []
    for line in out.splitlines():
        # format: <wid> <desktop> <pid> <hostname> <title...>
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        wid_s, _desktop, pid_s, _host, title = parts
        try:
            wid = int(wid_s, 16)
            pid = int(pid_s)
        except ValueError:
            continue
        if pid <= 0 or wid == 0:
            continue
        char = _parse_title(title, wid)
        if char is None:
            continue
        if not _is_eq_pid(pid):
            continue
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


class WindowSnapshot:
    """Background-refreshed cache of EQ windows.

    A single worker thread runs scan_windows() every refresh_interval seconds.
    The UI reads from cache instantly with no subprocess work on the main
    thread. At N=86 boxes this drops xdotool spawns per refresh from ~172 to
    one wmctrl call, so we never saturate X11's 256-client limit.
    """

    def __init__(self, refresh_interval: float = 3600.0):
        self._refresh_interval = refresh_interval
        self._chars: list[EQChar] = []
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._last_refresh = 0.0
        self._on_update: list = []
        self._thread: threading.Thread | None = None
        self._auto = True

    @property
    def refresh_interval(self) -> float:
        return self._refresh_interval

    @refresh_interval.setter
    def refresh_interval(self, v: float) -> None:
        self._refresh_interval = float(v)
        self._wake.set()

    def add_listener(self, cb) -> None:
        """cb(chars) is called on the worker thread after each successful scan."""
        self._on_update.append(cb)

    def get(self) -> list[EQChar]:
        with self._lock:
            return list(self._chars)

    @property
    def age(self) -> float:
        with self._lock:
            return time.time() - self._last_refresh if self._last_refresh else float("inf")

    def request_refresh(self) -> None:
        self._wake.set()

    def set_auto(self, enabled: bool) -> None:
        self._auto = enabled
        self._wake.set()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="eq-snapshot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                chars = scan_windows()
                with self._lock:
                    self._chars = chars
                    self._last_refresh = time.time()
                for cb in self._on_update:
                    try:
                        cb(chars)
                    except Exception as e:
                        print(f"[snapshot listener error] {e}")
            except Exception as e:
                print(f"[snapshot scan error] {e}")
            # When auto-refresh is off, sleep until explicitly woken.
            timeout = self._refresh_interval if self._auto else None
            self._wake.wait(timeout=timeout)
            self._wake.clear()


def focus_window(window_id: int) -> None:
    print(f"[focus] activating {window_id}")
    _run(["xdotool", "windowactivate", str(window_id)])
    _run(["xdotool", "windowraise", str(window_id)])
    _run(["xdotool", "windowfocus", str(window_id)])
