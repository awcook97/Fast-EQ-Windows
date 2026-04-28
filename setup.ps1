# Fast EQ Windows — Windows setup script
# NOTE: This app requires xdotool and X11, so it only works on Linux.
# This script sets up the dev environment for Python/uv on Windows if needed.

Write-Host "=== Fast EQ Windows Setup ===" -ForegroundColor Cyan
Write-Host ""

# ── uv ────────────────────────────────────────────────────────────────────────
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[1/2] Installing uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
} else {
    $uvVer = (uv --version) 2>&1
    Write-Host "[1/2] uv already installed ($uvVer)" -ForegroundColor Green
}

# ── Python deps ───────────────────────────────────────────────────────────────
Write-Host "[2/2] Installing Python dependencies..." -ForegroundColor Yellow
uv sync

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host ""
Write-Host "NOTE: This app requires Linux + xdotool to run (EverQuest via Wine)." -ForegroundColor Red
Write-Host "Run with: uv run fast-eq-windows" -ForegroundColor White
Write-Host ""
