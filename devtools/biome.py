"""Run the pinned Biome formatter/linter for metabrowser browser assets."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devtools.npm_tools import npx_no_install


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[1]
    cmd = npx_no_install(root, "biome", *args)
    return subprocess.run(cmd, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
