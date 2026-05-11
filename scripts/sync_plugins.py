#!/usr/bin/env python3
"""Sync in-repo plugins into the user plugin directory.

Source layout (in this repo):

    src/fast_eq_windows/plugins/<name>/plugin.py     # public, in git
    src/fast_eq_windows/private/<name>/plugin.py     # private, gitignored

Target:

    $FAST_EQ_PLUGINS  or  ~/.config/fast_eq_windows/plugins/<name>/

For every plugin folder copied, an optional ``requirements.txt`` is
installed into the workspace's uv-managed environment via
``uv pip install -r``.  Symlinks (e.g. ``private/pyEQLib``) are followed.

Run manually::

    uv run python scripts/sync_plugins.py

Or let the post-commit git hook fire it after each commit.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PUBLIC = REPO_ROOT / "src" / "fast_eq_windows" / "plugins"
SRC_PRIVATE = REPO_ROOT / "src" / "fast_eq_windows" / "private"

# Filenames inside the source dirs that aren't plugins themselves.
_NON_PLUGIN_NAMES = {
    "__init__.py",
    "__pycache__",
    "README.md",
    "plugins.json",
    ".gitignore",
}


def target_dir() -> Path:
    env = os.environ.get("FAST_EQ_PLUGINS")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".config" / "fast_eq_windows" / "plugins"


def config_path() -> Path:
    env = os.environ.get("FAST_EQ_CONFIG")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".config" / "fast_eq_windows" / "plugins.json"


def _load_user_config(path: Path) -> dict:
    if not path.exists():
        return {"enabled": [], "settings": {}}
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        print(f"  ! could not parse {path}: {exc}; starting fresh")
        return {"enabled": [], "settings": {}}
    data.setdefault("enabled", [])
    data.setdefault("settings", {})
    return data


def _save_user_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _read_manifest(plugin_src: Path) -> dict:
    """Return manifest dict, or empty dict if none."""
    mf = plugin_src / "manifest.json"
    if not mf.exists():
        return {}
    try:
        return json.loads(mf.read_text())
    except Exception as exc:
        print(f"  ! {plugin_src.name}/manifest.json invalid ({exc}); ignoring")
        return {}


def _merge_manifest(
    user_cfg: dict, plugin_name: str, manifest: dict,
) -> tuple[bool, list[str]]:
    """Apply manifest defaults to user_cfg, never clobbering existing values.

    Returns (changed, log_lines).
    """
    changed = False
    log: list[str] = []

    # Auto-enable if requested and not already disabled-by-user.  Once a
    # plugin appears in either ``enabled`` or the new ``disabled`` list, we
    # never touch its enabled-state on subsequent syncs.
    enabled = user_cfg.setdefault("enabled", [])
    disabled = user_cfg.setdefault("disabled", [])
    seen = plugin_name in enabled or plugin_name in disabled
    if manifest.get("auto_enable", False) and not seen:
        enabled.append(plugin_name)
        changed = True
        log.append("auto-enabled")

    # Merge default settings (only fill missing keys).
    defaults = manifest.get("default_settings") or {}
    if defaults:
        ns = user_cfg.setdefault("settings", {}).setdefault(plugin_name, {})
        added = []
        for k, v in defaults.items():
            if k not in ns:
                ns[k] = v
                added.append(k)
        if added:
            changed = True
            log.append(f"defaults: {', '.join(added)}")

    return changed, log


def _is_plugin_folder(p: Path) -> bool:
    if not p.is_dir():
        return False
    if p.name in _NON_PLUGIN_NAMES or p.name.startswith("_") or p.name.startswith("."):
        return False
    return (p / "plugin.py").exists()


def _iter_sources() -> tuple[list[Path], list[Path]]:
    plugins: list[Path] = []
    libs: list[Path] = []
    for src in (SRC_PUBLIC, SRC_PRIVATE):
        if not src.exists():
            continue
        for entry in sorted(src.iterdir()):
            real = entry.resolve() if entry.is_symlink() else entry
            if not real.is_dir():
                continue
            if real.name in _NON_PLUGIN_NAMES or real.name.startswith("."):
                continue
            if (real / "plugin.py").exists():
                if entry.name.startswith("_"):
                    # Skip starter templates (e.g. _template/).
                    continue
                plugins.append(real)
            elif src is SRC_PRIVATE and not entry.name.startswith("_"):
                # Bare library folder shipped alongside private plugins
                # (e.g. pyEQLib).  Copy so private plugins can import it.
                libs.append(real)
    return plugins, libs


def _copy_plugin(src: Path, dst_root: Path) -> Path:
    dst = dst_root / src.name
    if dst.exists():
        shutil.rmtree(dst)
    # symlinks=False resolves them; ignore __pycache__ noise.
    shutil.copytree(
        src,
        dst,
        symlinks=False,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return dst


def _install_requirements(plugin_dst: Path) -> None:
    req = plugin_dst / "requirements.txt"
    if not req.exists():
        return
    print(f"  • installing {plugin_dst.name}/requirements.txt")
    subprocess.run(
        ["uv", "pip", "install", "-r", str(req)],
        check=False,
        cwd=REPO_ROOT,
    )


def main() -> int:
    dst_root = target_dir()
    dst_root.mkdir(parents=True, exist_ok=True)
    libs_root = dst_root / "_libs"
    print(f"Syncing plugins → {dst_root}")

    plugins, libs = _iter_sources()
    if not plugins and not libs:
        print("  (nothing to sync)")
        return 0

    cfg_path = config_path()
    user_cfg = _load_user_config(cfg_path)
    cfg_changed = False

    for src in plugins:
        print(f"  ↪ {src.name}  (from {src.parent.name}/)")
        dst = _copy_plugin(src, dst_root)
        _install_requirements(dst)

        manifest = _read_manifest(src)
        if manifest:
            changed, notes = _merge_manifest(user_cfg, src.name, manifest)
            for note in notes:
                print(f"     • {note}")
            cfg_changed = cfg_changed or changed

    if libs:
        libs_root.mkdir(parents=True, exist_ok=True)
        for src in libs:
            print(f"  ↪ _libs/{src.name}  (from {src.parent.name}/)")
            _copy_plugin(src, libs_root)

    if cfg_changed:
        _save_user_config(cfg_path, user_cfg)
        print(f"  ✎ updated {cfg_path}")

    print(f"Done. {len(plugins)} plugin(s), {len(libs)} lib(s) synced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
