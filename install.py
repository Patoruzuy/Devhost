#!/usr/bin/env python3
"""Devhost installer entrypoint shim."""

from __future__ import annotations

import sys

from devhost_cli.installer import main

if __name__ == "__main__":
    sys.exit(main())
