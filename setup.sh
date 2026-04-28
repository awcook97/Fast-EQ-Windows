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
if ! command -v xdotool >/dev/null 2>&1; then
    echo ""
    echo "  WARNING: xdotool not found. Install it:"
    echo "    Ubuntu/Debian : sudo apt install xdotool"
    echo "    Fedora/RHEL   : sudo dnf install xdotool"
    echo "    Arch          : sudo pacman -S xdotool"
    echo ""
else
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

echo ""
echo "=== Done ==="
echo ""
echo "  ./fast-eq-windows.sh        — run (quiet)"
echo "  ./fast-eq-windows-debug.sh  — run (debug output)"
echo ""
