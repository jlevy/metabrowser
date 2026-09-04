"""Startup work must not block the event loop before the server binds."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from threading import Event

import pytest

from metabrowser.events import FsEntry
from metabrowser.inventory_engine.providers import python_inventory as python_provider
from metabrowser.inventory_engine.providers.python_inventory import (
    _PythonInventoryStore as PythonInventoryStore,
)


def test_inventory_start_offloads_gitignore_build(monkeypatch, tmp_path: Path) -> None:
    """The inventory walker may crawl in the background, but its first
    synchronous setup step must not stall the event loop.
    """

    def slow_gitignore_build(
        _root: Path,
        *,
        cancel_event: Event | None = None,
    ) -> None:
        del cancel_event
        time.sleep(0.2)

    monkeypatch.setattr(python_provider, "_build_gitignore_check_for", slow_gitignore_build)

    async def _run() -> float:
        inv = PythonInventoryStore()
        inv.start(tmp_path)
        started = time.perf_counter()
        await asyncio.sleep(0)
        elapsed_ms = (time.perf_counter() - started) * 1000
        await inv.wait_until_done(timeout=5.0)
        return elapsed_ms

    elapsed_ms = asyncio.run(_run())
    assert elapsed_ms < 50


def test_inventory_walker_yields_to_request_tasks_between_entry_batches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A wide directory must not monopolize the request event loop."""

    started = asyncio.Event()

    async def immediate_entries(_root: Path, **_kwargs: object) -> AsyncIterator[FsEntry]:
        started.set()
        for index in range(1_000):
            yield FsEntry.for_observed_file(
                path=f"file-{index}.txt",
                parent="",
                name=f"file-{index}.txt",
                size=1,
                mtime_ns=1,
            )

    monkeypatch.setattr(python_provider, "walk_tree", immediate_entries)

    async def _run() -> int:
        inventory = PythonInventoryStore()
        walker = inventory.start(tmp_path)
        finished = asyncio.Event()
        interleavings = 0

        async def request_probe() -> None:
            nonlocal interleavings
            await started.wait()
            while not finished.is_set():
                await asyncio.sleep(0)
                if not finished.is_set():
                    interleavings += 1

        probe = asyncio.create_task(request_probe())
        await walker
        finished.set()
        await probe
        return interleavings

    assert asyncio.run(_run()) > 0
