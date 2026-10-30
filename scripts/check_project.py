"""Run the checks shared by Git and Codex hooks."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    checks = [
        ("working-tree whitespace", ["git", "diff", "--check"]),
        ("staged whitespace", ["git", "diff", "--cached", "--check"]),
        (
            "Python syntax",
            [sys.executable, "-m", "compileall", "-q", "backend/app", "scripts", "evals", ".codex/hooks"],
        ),
        ("frontend build", [shutil.which("npm") or "npm", "--prefix", "frontend", "run", "build"]),
    ]
    for label, command in checks:
        print(f"[checks] {label}", flush=True)
        try:
            result = subprocess.run(command, cwd=ROOT, check=False)
        except OSError as error:
            print(f"[checks] {label} failed: {error}", file=sys.stderr)
            return 1
        if result.returncode != 0:
            print(f"[checks] {label} failed (exit {result.returncode})", file=sys.stderr)
            return result.returncode
    print("[checks] all passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
