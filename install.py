#!/usr/bin/env python3
"""
Devhost installer wrapper.
Delegates to the Python CLI for a single source of truth.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    devhost = root / "devhost"
    if not devhost.exists():
        print("devhost script not found.", file=sys.stderr)
        return 1
    cmd = [sys.executable, str(devhost), "install"] + sys.argv[1:]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
