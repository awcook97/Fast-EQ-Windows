#!/usr/bin/env bash
set -e

echo "=== Fast EQ Windows Setup ==="
echo ""

# ── uv ────────────────────────────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
    echo "[1/3] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
else
    echo "[1/3] uv already installed ($(uv --version))"
fi

# ── Python deps ───────────────────────────────────────────────────────────────
echo "[2/3] Installing Python dependencies..."
uv sync

# ── System deps ───────────────────────────────────────────────────────────────
echo "[3/3] Checking system dependencies..."
missing=()
command -v wmctrl  >/dev/null 2>&1 || missing+=("wmctrl")
command -v xdotool >/dev/null 2>&1 || missing+=("xdotool")
if [ ${#missing[@]} -ne 0 ]; then
    echo ""
    echo "  WARNING: missing: ${missing[*]}. Install with:"
    echo "    Ubuntu/Debian : sudo apt install ${missing[*]}"
    echo "    Fedora/RHEL   : sudo dnf install ${missing[*]}"
    echo "    Arch          : sudo pacman -S ${missing[*]}"
    echo ""
else
    echo "  wmctrl OK  ($(wmctrl -m 2>/dev/null | head -1))"
    echo "  xdotool OK ($(xdotool --version 2>&1 | head -1))"
fi

# ── Launchers ─────────────────────────────────────────────────────────────────
PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat > "$PROJ_DIR/fast-eq-windows.sh" << EOF
#!/usr/bin/env bash
cd "$PROJ_DIR"
exec uv run fast-eq-windows "\$@" >/dev/null 2>&1
EOF
chmod +x "$PROJ_DIR/fast-eq-windows.sh"

cat > "$PROJ_DIR/fast-eq-windows-debug.sh" << EOF
#!/usr/bin/env bash
cd "$PROJ_DIR"
exec uv run fast-eq-windows "\$@"
EOF
chmod +x "$PROJ_DIR/fast-eq-windows-debug.sh"

# ── Git hooks + initial plugin sync ──────────────────────────────────────────
if [ -d "$PROJ_DIR/.git" ]; then
    git -C "$PROJ_DIR" config core.hooksPath .githooks
    echo "  git hooks → .githooks/"
fi
uv run python "$PROJ_DIR/scripts/sync_plugins.py" || true

echo ""
echo "=== Done ==="
echo ""
echo "  ./fast-eq-windows.sh        — run (quiet)"
echo "  ./fast-eq-windows-debug.sh  — run (debug output)"
echo ""
