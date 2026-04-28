"""
PyInstaller entry point — production build.
Redirects all stdout/stderr to /dev/null so debug prints don't appear.
Use `uv run fast-eq-windows` directly if you want debug output.
"""
import os
import sys

sys.stdout = open(os.devnull, "w")
sys.stderr = open(os.devnull, "w")

from fast_eq_windows.app import main  # noqa: E402

if __name__ == "__main__":
    main()
