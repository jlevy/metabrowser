"""Shared helper for invoking the exact, locked npm development tools."""

from __future__ import annotations

import sys
from pathlib import Path


def npx_no_install(root: Path, tool: str, *args: str) -> list[str]:
    """Build an offline npx command and fail clearly when tools are absent."""
    if not (root / "node_modules" / ".bin").is_dir():
        print(
            "node_modules is missing; run `make install` (or `npm ci`) first.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return ["npx", "--no-install", tool, *args]
