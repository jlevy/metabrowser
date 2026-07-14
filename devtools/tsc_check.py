"""Run TypeScript checkJs over metabrowser native browser JavaScript."""

from __future__ import annotations

import subprocess
from pathlib import Path

from devtools.npm_tools import npx_no_install


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for config in ("tsconfig.json", "tsconfig.legacy.json"):
        cmd = npx_no_install(root, "tsc", "--noEmit", "-p", config)
        result = subprocess.run(cmd, cwd=root, check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
