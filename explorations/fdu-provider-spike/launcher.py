"""Spike-only `metab` entry point that can serve through the fdu adapter.

`METABROWSER_INVENTORY_PROVIDER=fdu` selects the spike backend; any other value goes to
the shipping sealed factory unchanged, so the Python side of every comparison runs
through this same launcher, interpreter, and startup path. The patch replaces only the
runtime composition root's constructor reference for this process; nothing in `src/` is
modified and the shipping factory still rejects `fdu`.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def install() -> None:
    if str(_HERE) not in sys.path:
        sys.path.insert(0, str(_HERE))
    runtime = importlib.import_module("metabrowser.inventory_engine.runtime")
    original = runtime.create_inventory_backend
    adapter = importlib.import_module("adapter")

    def create(provider: object = "python") -> object:
        if str(provider).strip().lower() == adapter.PROVIDER_ID:
            return adapter.FduInventoryBackend()
        return original(provider)

    # The composition root's module attribute is the one seam; patched for this process.
    setattr(runtime, "create_inventory_backend", create)  # noqa: B010


def main() -> int:
    install()
    from metabrowser.cli.entrypoint import main as metab_main

    return metab_main()


if __name__ == "__main__":
    raise SystemExit(main())
