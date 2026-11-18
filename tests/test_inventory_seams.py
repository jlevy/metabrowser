"""The provider seams in `inventory_engine/seams.py` hold the selected provider as stated.

Product tests hold discovery and lower the continuation bound through these seams rather
than by patching one provider's internals, so each case here runs against the provider
`METABROWSER_INVENTORY_PROVIDER` selects, through the sealed factory.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from metabrowser.inventory_engine.contract import (
    MAX_ASSEMBLED_ROWS,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    InventoryConfig,
    InventoryHandle,
    LifecyclePhase,
    ReadRequest,
)
from metabrowser.inventory_engine.factory import create_inventory_backend
from metabrowser.inventory_engine.seams import DiscoveryGate, ProviderSeams
from tests.inventory_harness import selected_inventory_provider

# Long enough that a provider which ignored the gate would have finished discovering.
_HELD_S = 0.2


async def _open(root: Path, gate: DiscoveryGate) -> InventoryHandle:
    backend = create_inventory_backend(
        selected_inventory_provider(), seams=ProviderSeams(discovery_gate=gate)
    )
    return await backend.open(root, InventoryConfig(watch_mode="off"))


async def _presence(handle: InventoryHandle, path: str) -> EntryPresence:
    result = await handle.read(ReadRequest(queries=(EntryQuery(query_id="entry", path=path),)))
    projection = result.projection("entry")
    assert isinstance(projection, EntryProjection)
    return projection.presence


def test_a_gate_at_the_root_holds_discovery_until_released(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("x")

    async def run() -> tuple[LifecyclePhase, EntryPresence, LifecyclePhase, EntryPresence]:
        gate = DiscoveryGate(before="")
        handle = await _open(tmp_path, gate)
        try:
            await asyncio.wait_for(gate.wait_reached(), 5)
            await asyncio.sleep(_HELD_S)
            checkpoint = await handle.read(ReadRequest())
            unlisted = await _presence(handle, "file.txt")
            changes = handle.changes(after=checkpoint.cursor)
            gate.release()
            phase = checkpoint.state.phase
            async with asyncio.timeout(5):
                async for batch in changes:
                    phase = batch.state.phase
                    if phase not in {LifecyclePhase.OPENING, LifecyclePhase.DISCOVERING}:
                        break
            close = getattr(changes, "aclose", None)
            if close is not None:
                await close()
            return checkpoint.state.phase, unlisted, phase, await _presence(handle, "file.txt")
        finally:
            await handle.close()

    held, unlisted, phase, listed = asyncio.run(run())
    assert held is LifecyclePhase.DISCOVERING
    assert unlisted is EntryPresence.UNKNOWN
    assert phase is LifecyclePhase.READY
    assert listed is EntryPresence.PRESENT


def test_a_deeper_gate_lets_discovery_publish_everything_before_it(tmp_path: Path) -> None:
    (tmp_path / "a" / "b" / "held").mkdir(parents=True)
    (tmp_path / "a" / "b" / "held" / "inside.txt").write_text("x")
    (tmp_path / "a" / "b" / "beside.txt").write_text("x")

    async def run() -> dict[str, EntryPresence]:
        gate = DiscoveryGate(before="a/b/held")
        handle = await _open(tmp_path, gate)
        try:
            await asyncio.wait_for(gate.wait_reached(), 5)
            return {
                path: await _presence(handle, path)
                for path in ("a", "a/b", "a/b/beside.txt", "a/b/held", "a/b/held/inside.txt")
            }
        finally:
            await handle.close()

    presence = asyncio.run(run())
    assert presence == {
        "a": EntryPresence.PRESENT,
        "a/b": EntryPresence.PRESENT,
        "a/b/beside.txt": EntryPresence.PRESENT,
        "a/b/held": EntryPresence.PRESENT,
        "a/b/held/inside.txt": EntryPresence.UNKNOWN,
    }


def test_closing_a_held_provider_returns_promptly(tmp_path: Path) -> None:
    async def run() -> None:
        gate = DiscoveryGate(before="")
        handle = await _open(tmp_path, gate)
        await asyncio.wait_for(gate.wait_reached(), 5)
        await asyncio.wait_for(handle.close(), 5)

    asyncio.run(run())


def test_seams_are_validated() -> None:
    with pytest.raises(ValueError, match="canonical"):
        DiscoveryGate(before="/absolute")
    for bound in (0, MAX_ASSEMBLED_ROWS + 1):
        with pytest.raises(ValueError, match="max_retained_rows"):
            ProviderSeams(max_retained_rows=bound)
    assert ProviderSeams(max_retained_rows=MAX_ASSEMBLED_ROWS).max_retained_rows
