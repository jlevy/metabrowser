"""The coordinator's supervisor replaces a failed provider handle (D14, R26).

Each case serves the provider the environment selects behind `tests/perturbed_provider.py`,
whose fault seams fail the change iterator, a read, the reopen, or the close, and checks
what the host does: close the failed handle within a bound, reopen the root, publish a
reset, and keep live updates and decorations; or, past the reopen cap, leave the root in
a typed failed state that a later open clears.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from metabrowser.inventory_engine import coordinator as coordinator_module
from metabrowser.inventory_engine.contract import (
    EntryPresence,
    EntryProjection,
    EntryQuery,
    InventoryBackend,
    InventoryConfig,
    IssueCode,
    LifecyclePhase,
    ObservationKind,
    ProviderFailureError,
    ReadRequest,
    RefreshObservation,
    RefreshRequest,
)
from metabrowser.inventory_engine.coordinator import HostChange, InventoryCoordinator
from metabrowser.inventory_engine.overlay import InventoryDecoration
from tests.inventory_harness import inventory_harness, wait_until_settled
from tests.perturbed_provider import Perturbation, PerturbedBackend

_CONFIG = InventoryConfig(watch_mode="off")
_DECORATION = InventoryDecoration(active=True)


class _Panic(BaseException):
    """A failure that is not an `Exception`, as a native panic surfaces."""


@pytest.fixture(autouse=True)
def immediate_reopens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(coordinator_module, "RECOVERY_ATTEMPT_DELAYS_S", (0.0, 0.0, 0.0))


class _Wrapper:
    """Wrap the harness's backend and keep the wrapper, so a case can reach its faults."""

    def __init__(self) -> None:
        self.backend: PerturbedBackend | None = None

    def __call__(self, inner: InventoryBackend) -> InventoryBackend:
        self.backend = PerturbedBackend(inner, Perturbation(provider_name="renamed"))
        return self.backend

    @property
    def wrapped(self) -> PerturbedBackend:
        assert self.backend is not None
        return self.backend


async def _next(changes: AsyncIterator[HostChange], timeout: float = 5.0) -> HostChange:
    return await asyncio.wait_for(anext(changes), timeout)


async def _present(coordinator: InventoryCoordinator, path: str) -> bool:
    read = await coordinator.read(ReadRequest(queries=(EntryQuery(query_id="entry", path=path),)))
    projection = read.result.projection("entry")
    assert isinstance(projection, EntryProjection)
    return projection.presence is EntryPresence.PRESENT


async def _assert_live(coordinator: InventoryCoordinator, root: Path, name: str) -> None:
    """A refresh after recovery reaches the host stream: live updates did not stop.

    The reopened handle may still be discovering, so changes from that discovery can
    come first; the refresh's change converges among them.
    """

    cursor, _version, _state = await coordinator.checkpoint()
    changes = coordinator.changes(after=cursor)
    (root / name).write_text(name, encoding="utf-8")
    await coordinator.refresh(
        RefreshRequest(observations=(RefreshObservation(path=name, kind=ObservationKind.CREATED),))
    )
    try:
        async with asyncio.timeout(5):
            while name not in (await anext(changes)).dirty_paths:
                pass
    finally:
        await changes.aclose()
    assert await _present(coordinator, name)


@pytest.mark.parametrize(
    "error", [RuntimeError("injected"), _Panic("injected")], ids=lambda error: type(error).__name__
)
def test_a_failed_change_stream_reopens_the_root_and_keeps_live_updates(
    tmp_path: Path, error: BaseException
) -> None:
    """A provider failure in `changes()`, a native panic included, is recovered.

    Before the supervisor, an `Exception` published a reset and ended live updates, and a
    `BaseException` escaped the relay's TaskGroup: no reset, and the group raised again
    from the coordinator's close.
    """

    (tmp_path / "kept.txt").write_text("kept", encoding="utf-8")
    wrapper = _Wrapper()

    async def run() -> None:
        async with inventory_harness(tmp_path, config=_CONFIG, wrap=wrapper) as harness:
            coordinator = harness.runtime.coordinator
            await coordinator.replace_decoration("kept.txt", _DECORATION)
            cursor, _version, _state = await coordinator.checkpoint()
            changes = coordinator.changes(after=cursor)
            failed = wrapper.wrapped.handles[0]
            failed.fail_changes(error)

            reset = await _next(changes)
            await changes.aclose()
            assert reset.reset
            assert reset.cursor.session != cursor.session
            assert failed.closed
            assert len(wrapper.wrapped.handles) == 2
            await wait_until_settled(harness.runtime)
            read = await coordinator.read(
                ReadRequest(queries=(EntryQuery(query_id="entry", path="kept.txt"),))
            )
            assert read.entries["kept.txt"].decoration == _DECORATION
            await _assert_live(coordinator, tmp_path, "after.txt")

    asyncio.run(run())


def test_a_read_that_reports_provider_failure_starts_recovery(tmp_path: Path) -> None:
    wrapper = _Wrapper()

    async def run() -> None:
        async with inventory_harness(tmp_path, config=_CONFIG, wrap=wrapper) as harness:
            coordinator = harness.runtime.coordinator
            cursor, _version, _state = await coordinator.checkpoint()
            changes = coordinator.changes(after=cursor)
            wrapper.wrapped.handles[0].fail_next_read(ProviderFailureError("poisoned root"))
            with pytest.raises(ProviderFailureError, match="poisoned root"):
                await coordinator.read(ReadRequest())
            assert (await _next(changes)).reset
            await changes.aclose()
            assert len(wrapper.wrapped.handles) == 2
            await _assert_live(coordinator, tmp_path, "after.txt")

    asyncio.run(run())


def test_past_the_reopen_cap_the_root_is_failed_until_it_opens_again(tmp_path: Path) -> None:
    attempts = len(coordinator_module.RECOVERY_ATTEMPT_DELAYS_S)
    wrapper = _Wrapper()

    async def run() -> None:
        async with inventory_harness(tmp_path, config=_CONFIG, wrap=wrapper) as harness:
            coordinator = harness.runtime.coordinator
            cursor, _version, _state = await coordinator.checkpoint()
            changes = coordinator.changes(after=cursor)
            wrapper.wrapped.fail_opens(*(OSError(f"open {index}") for index in range(attempts)))
            wrapper.wrapped.handles[0].fail_changes(_Panic("injected"))

            failed = await _next(changes)
            assert failed.reset
            assert failed.state.phase is LifecyclePhase.FAILED
            assert [issue.code for issue in failed.state.issues] == [IssueCode.PROVIDER_FAILURE]
            assert "OSError" in failed.state.issues[0].detail
            _cursor, _version, state = await coordinator.checkpoint()
            assert state == failed.state
            with pytest.raises(ProviderFailureError) as raised:
                await coordinator.read(ReadRequest())
            assert isinstance(raised.value.__cause__, OSError)
            assert len(wrapper.wrapped.handles) == 1

            # Opening the root again is the way out, and the stream carries on.
            await coordinator.open(tmp_path)
            reopened = await _next(changes)
            await changes.aclose()
            assert reopened.reset
            assert reopened.state.phase is not LifecyclePhase.FAILED
            await _assert_live(coordinator, tmp_path, "after.txt")

    asyncio.run(run())


def test_a_close_that_hangs_is_abandoned_after_its_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bound = 0.05
    monkeypatch.setattr(coordinator_module, "RECOVERY_CLOSE_TIMEOUT_S", bound)
    wrapper = _Wrapper()

    async def run() -> float:
        async with inventory_harness(tmp_path, config=_CONFIG, wrap=wrapper) as harness:
            coordinator = harness.runtime.coordinator
            cursor, _version, _state = await coordinator.checkpoint()
            changes = coordinator.changes(after=cursor)
            failed = wrapper.wrapped.handles[0]
            failed.delay_close(bound * 10)
            started = time.monotonic()
            failed.fail_changes(RuntimeError("injected"))
            assert (await _next(changes)).reset
            elapsed = time.monotonic() - started
            await changes.aclose()
            assert not failed.closed
            await _assert_live(coordinator, tmp_path, "after.txt")
            # The abandoned close still finishes on its own.
            for _attempt in range(100):
                if failed.closed:
                    break
                await asyncio.sleep(bound)
            assert failed.closed
            return elapsed

    assert asyncio.run(run()) < 0.4


def test_close_during_the_reopen_backoff_ends_recovery_without_reopening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(coordinator_module, "RECOVERY_ATTEMPT_DELAYS_S", (0.0, 30.0))
    wrapper = _Wrapper()

    async def run() -> float:
        async with inventory_harness(tmp_path, config=_CONFIG, wrap=wrapper) as harness:
            coordinator = harness.runtime.coordinator
            wrapper.wrapped.fail_opens(OSError("open"))
            wrapper.wrapped.handles[0].fail_changes(RuntimeError("injected"))
            # The first attempt fails at once; then the supervisor is backing off.
            await asyncio.sleep(0.2)
            started = time.monotonic()
            await coordinator.close()
            elapsed = time.monotonic() - started
            assert len(wrapper.wrapped.handles) == 1
            return elapsed

    assert asyncio.run(run()) < 5.0
