"""Application-owned inventory runtime helpers for integration tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from metabrowser.events_route import _EventBus
from metabrowser.inventory_engine.contract import InventoryConfig, LifecyclePhase
from metabrowser.inventory_engine.runtime import InventoryRuntime, default_inventory_config


@dataclass(frozen=True, slots=True)
class InventoryHarness:
    """One runtime, event bus, and request-app state owned by a test."""

    runtime: InventoryRuntime
    bus: _EventBus
    app: SimpleNamespace


async def wait_until_settled(runtime: InventoryRuntime, *, timeout: float = 5.0) -> None:
    """Wait until discovery reaches a terminal serving phase."""

    async def poll() -> None:
        while True:
            _cursor, _version, state = await runtime.coordinator.checkpoint()
            if state.phase in {
                LifecyclePhase.WATCHING,
                LifecyclePhase.FAILED,
                LifecyclePhase.STOPPED,
            }:
                return
            await asyncio.sleep(0.01)

    await asyncio.wait_for(poll(), timeout=timeout)


@asynccontextmanager
async def inventory_harness(
    root: Path,
    *,
    config: InventoryConfig | None = None,
    settle: bool = True,
) -> AsyncGenerator[InventoryHarness]:
    """Open and reliably close an application-shaped inventory plane."""

    runtime = InventoryRuntime(config=config or default_inventory_config())
    await runtime.open(root)
    if settle:
        await wait_until_settled(runtime)
    cursor, _version, _state = await runtime.coordinator.checkpoint()
    bus = _EventBus(runtime.coordinator, config=runtime.config)
    await bus.start(after=cursor)
    app = SimpleNamespace(
        state=SimpleNamespace(
            inventory_runtime=runtime,
            inventory_event_bus=bus,
        )
    )
    try:
        yield InventoryHarness(runtime=runtime, bus=bus, app=app)
    finally:
        await bus.close()
        await runtime.close()
