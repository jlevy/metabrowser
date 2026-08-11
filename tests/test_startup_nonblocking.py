"""Startup work must not block the event loop before the server binds."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from metabrowser import inventory as inventory_module
from metabrowser.inventory import InventoryIndex


def test_inventory_start_offloads_gitignore_build(monkeypatch, tmp_path: Path) -> None:
    """The inventory walker may crawl in the background, but its first
    synchronous setup step must not stall the event loop.
    """

    def slow_gitignore_build(_root: Path):
        time.sleep(0.2)
        return

    monkeypatch.setattr(inventory_module, "_build_gitignore_check_for", slow_gitignore_build)

    async def _run() -> float:
        inv = InventoryIndex()
        inv.start(tmp_path)
        started = time.perf_counter()
        await asyncio.sleep(0)
        elapsed_ms = (time.perf_counter() - started) * 1000
        await inv.wait_until_done(timeout=5.0)
        return elapsed_ms

    elapsed_ms = asyncio.run(_run())
    assert elapsed_ms < 50
