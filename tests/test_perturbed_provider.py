"""The test-only perturbing provider does what `tests/perturbed_provider.py` says.

Each case wraps the provider the environment selects, so the wrapper is proven over a
real provider, and checks one perturbation or fault at the provider boundary. The last
cases reach the host through the inventory harness and pin the host rules the
perturbations once broke: a refresh's split halves publish as one host change (D8) unless
they arrive further apart than the coordinator's hold, and a refresh returns only after
the host has published its receipt's version (R27).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from pathlib import Path

import pytest

from metabrowser.inventory_engine.contract import (
    ChangeBatch,
    DiagnosticsProjection,
    DiagnosticsQuery,
    Freshness,
    InventoryConfig,
    LifecyclePhase,
    ObservationKind,
    ReadRequest,
    RefreshObservation,
    RefreshRequest,
    VersionUnavailableError,
)
from metabrowser.inventory_engine.coordinator import RECONCILING_HOLD_S, HostChange
from metabrowser.inventory_engine.factory import create_inventory_backend
from tests.inventory_harness import inventory_harness, selected_inventory_provider
from tests.perturbed_provider import Perturbation, PerturbedBackend, PerturbedHandle

_SETTLED = frozenset(
    {LifecyclePhase.READY, LifecyclePhase.WATCHING, LifecyclePhase.STOPPED, LifecyclePhase.FAILED}
)
# Long enough to see on a loaded runner, short enough to keep the module fast.
_DELAY_S = 0.2


class _Panic(BaseException):
    """A failure that is not an `Exception`, as a native panic can surface."""


def _wrapped(perturbation: Perturbation) -> PerturbedBackend:
    return PerturbedBackend(create_inventory_backend(selected_inventory_provider()), perturbation)


async def _open_settled(
    backend: PerturbedBackend, root: Path, *, config: InventoryConfig | None = None
) -> PerturbedHandle:
    handle = await backend.open(root, config or InventoryConfig(watch_mode="off"))
    for _attempt in range(500):
        if (await handle.read(ReadRequest())).state.phase in _SETTLED:
            return handle
        await asyncio.sleep(0.005)
    await handle.close()
    raise AssertionError("the wrapped provider did not settle")


def _refresh(path: str) -> RefreshRequest:
    return RefreshRequest(
        observations=(RefreshObservation(path=path, kind=ObservationKind.CREATED),)
    )


async def _until(
    changes: AsyncIterator[ChangeBatch], done: Callable[[ChangeBatch], bool]
) -> list[ChangeBatch]:
    seen: list[ChangeBatch] = []
    async with asyncio.timeout(5):
        async for batch in changes:
            seen.append(batch)
            if done(batch):
                return seen
    raise AssertionError(f"the change stream ended first: {seen}")


def test_identity_and_sequences_translate_through_reads_and_receipts(tmp_path: Path) -> None:
    (tmp_path / "one.txt").write_text("one")

    async def run() -> None:
        backend = _wrapped(Perturbation(split_batches=True, provider_name="renamed"))
        handle = await _open_settled(backend, tmp_path)
        try:
            read = await handle.read(
                ReadRequest(queries=(DiagnosticsQuery(query_id="diagnostics"),))
            )
            diagnostics = read.projection("diagnostics")
            assert isinstance(diagnostics, DiagnosticsProjection)
            assert diagnostics.payload.provider == "renamed"
            assert read.version.sequence % 2 == 0
            assert read.cursor == read.version.cursor
            pinned = await handle.read(ReadRequest(at_version=read.version))
            assert pinned.version == read.version

            (tmp_path / "two.txt").write_text("two")
            receipt = await handle.refresh(_refresh("two.txt"))
            assert receipt.accepted_paths == ("two.txt",)
            assert receipt.version.sequence % 2 == 0
            assert receipt.version.sequence > read.version.sequence
            with pytest.raises(VersionUnavailableError):
                await handle.read(ReadRequest(at_version=read.version))
        finally:
            await handle.close()

    asyncio.run(run())


def test_split_delivers_state_before_data_and_resumes_past_the_half_seen(
    tmp_path: Path,
) -> None:
    async def run() -> tuple[list[ChangeBatch], list[ChangeBatch]]:
        backend = _wrapped(Perturbation(split_batches=True))
        handle = await _open_settled(backend, tmp_path)
        try:
            start = (await handle.read(ReadRequest())).cursor
            changes = handle.changes(after=start)
            (tmp_path / "new.txt").write_text("new")
            await handle.refresh(_refresh("new.txt"))
            first = await _until(changes, lambda batch: "new.txt" in batch.dirty_paths)
            await changes.aclose()
            state_only = first[-2]
            resumed = handle.changes(after=state_only.cursor)
            second = await _until(resumed, lambda batch: "new.txt" in batch.dirty_paths)
            await resumed.aclose()
            return first, second
        finally:
            await handle.close()

    first, second = asyncio.run(run())
    state_only, data = first[-2:]
    assert state_only.version.sequence == data.version.sequence - 1
    assert state_only.state.freshness is Freshness.RECONCILING
    assert replace(state_only.state, freshness=data.state.freshness) == data.state
    assert (state_only.dirty_paths, state_only.dirty_queries) == ((), frozenset())
    assert not (state_only.reset or state_only.all_dirty)
    # Resumed from the state-only cursor, the stream starts at that batch's data half.
    assert second == [data]


def test_replay_capacity_turns_an_older_resume_into_a_reset(tmp_path: Path) -> None:
    async def run() -> ChangeBatch:
        backend = _wrapped(Perturbation(replay_capacity=1))
        handle = await _open_settled(backend, tmp_path)
        try:
            start = (await handle.read(ReadRequest())).cursor
            for name in ("a.txt", "b.txt"):
                (tmp_path / name).write_text(name)
                await handle.refresh(_refresh(name))
            changes = handle.changes(after=start)
            first = (await _until(changes, lambda _batch: True))[0]
            await changes.aclose()
            return first
        finally:
            await handle.close()

    assert asyncio.run(run()).reset


def test_delivery_delay_holds_each_batch(tmp_path: Path) -> None:
    async def run() -> float:
        backend = _wrapped(Perturbation(delivery_delay_s=_DELAY_S))
        handle = await _open_settled(backend, tmp_path)
        try:
            changes = handle.changes(after=(await handle.read(ReadRequest())).cursor)
            (tmp_path / "late.txt").write_text("late")
            refreshed = time.monotonic()
            await handle.refresh(_refresh("late.txt"))
            await _until(changes, lambda batch: "late.txt" in batch.dirty_paths)
            await changes.aclose()
            return time.monotonic() - refreshed
        finally:
            await handle.close()

    assert asyncio.run(run()) >= _DELAY_S


@pytest.mark.parametrize(
    "error", [RuntimeError("injected"), _Panic("injected")], ids=lambda error: type(error).__name__
)
def test_faults_raise_from_the_next_read_and_from_a_waiting_change_iterator(
    tmp_path: Path, error: BaseException
) -> None:
    async def run() -> None:
        handle = await _open_settled(_wrapped(Perturbation()), tmp_path)
        try:
            handle.fail_next_read(error)
            with pytest.raises(type(error), match="injected"):
                await handle.read(ReadRequest())
            await handle.read(ReadRequest())

            changes = handle.changes(after=(await handle.read(ReadRequest())).cursor)
            waiting = asyncio.ensure_future(anext(changes))
            await asyncio.sleep(0.05)
            assert not waiting.done()
            handle.fail_changes(error)
            with pytest.raises(type(error), match="injected"):
                await waiting
            # The iterator it raised from has ended, so another may start and wait.
            again = handle.changes(after=None)
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(anext(again), 0.05)
            await again.aclose()
        finally:
            await handle.close()

    asyncio.run(run())


def _wrap(perturbation: Perturbation) -> Callable[..., PerturbedBackend]:
    return lambda inner: PerturbedBackend(inner, perturbation)


async def _host_changes_after_refresh(
    harness_changes: AsyncIterator[HostChange],
    refresh: Callable[[], Awaitable[object]],
    path: str,
) -> list[HostChange]:
    await refresh()
    seen: list[HostChange] = []
    async with asyncio.timeout(5):
        async for change in harness_changes:
            seen.append(change)
            if path in change.dirty_paths:
                return seen
    raise AssertionError(f"the host stream ended first: {seen}")


async def _split_refresh_host_changes(tmp_path: Path, delay_s: float) -> list[HostChange]:
    config = InventoryConfig(watch_mode="off")
    wrap = _wrap(
        Perturbation(split_batches=True, provider_name="renamed", delivery_delay_s=delay_s)
    )
    async with inventory_harness(tmp_path, config=config, wrap=wrap) as harness:
        coordinator = harness.runtime.coordinator
        read = await coordinator.read(
            ReadRequest(queries=(DiagnosticsQuery(query_id="diagnostics"),))
        )
        diagnostics = read.result.projection("diagnostics")
        assert isinstance(diagnostics, DiagnosticsProjection)
        assert diagnostics.payload.provider == "renamed"
        cursor, _version, _state = await coordinator.checkpoint()
        changes = coordinator.changes(after=cursor)
        (tmp_path / "new.txt").write_text("new")
        seen = await _host_changes_after_refresh(
            changes, lambda: coordinator.refresh(_refresh("new.txt")), "new.txt"
        )
        await changes.aclose()
        return seen


def test_a_split_refresh_reaches_the_host_as_one_change(tmp_path: Path) -> None:
    """A refresh committed as a state-only version then its data is one host change (D8).

    The halves arrive apart, as fdu's commits did, but within the coordinator's hold,
    so the `reconciling` state-only half waits for the data and publishes with it.
    """

    seen = asyncio.run(_split_refresh_host_changes(tmp_path, RECONCILING_HOLD_S / 5))
    assert len(seen) == 1
    (change,) = seen
    assert change.facts_changed
    assert change.state.freshness is not Freshness.RECONCILING
    assert change.version.engine.sequence % 2 == 0


def test_split_halves_further_apart_than_the_hold_publish_separately(tmp_path: Path) -> None:
    """The hold is bounded: halves that arrive after it expires are two host changes."""

    seen = asyncio.run(_split_refresh_host_changes(tmp_path, RECONCILING_HOLD_S * 2))
    state_only, data = seen[-2:]
    assert not state_only.facts_changed
    assert state_only.state.freshness is Freshness.RECONCILING
    assert state_only.version.engine.sequence == data.version.engine.sequence - 1


def test_a_refresh_returns_after_the_host_publishes_its_receipt_version(
    tmp_path: Path,
) -> None:
    """A read after a refresh sees at least the receipt's version, however late the relay.

    The wrapper's delivery delay makes the change relay trail the refresh, as fdu's
    commit poll did, so the coordinator has to wait for the relay (R27). The refresh's
    change is then already in host history, so a subscriber from before the refresh
    replays it at once.
    """

    config = InventoryConfig(watch_mode="off")

    async def run() -> tuple[int, int, HostChange]:
        wrap = _wrap(Perturbation(delivery_delay_s=_DELAY_S))
        async with inventory_harness(tmp_path, config=config, wrap=wrap) as harness:
            coordinator = harness.runtime.coordinator
            before, _version, _state = await coordinator.checkpoint()
            (tmp_path / "new.txt").write_text("new")
            receipt = await coordinator.refresh(_refresh("new.txt"))
            _cursor, version, _state = await coordinator.checkpoint()
            changes = coordinator.changes(after=before)
            replayed = await asyncio.wait_for(anext(changes), _DELAY_S / 4)
            await changes.aclose()
            return version.engine.sequence, receipt.version.sequence, replayed

    checkpoint, receipt, replayed = asyncio.run(run())
    assert checkpoint >= receipt
    assert "new.txt" in replayed.dirty_paths
