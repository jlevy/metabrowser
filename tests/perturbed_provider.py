"""A test-only provider that wraps any backend and perturbs its granularity and identity.

The host above the contract was written against one provider, and a second engine finds
the places where it relied on that provider's habits rather than on the contract: fdu
committed a refresh's state change as a version of its own, so one refresh reached the
browser as two envelopes, and its change relay could trail ``refresh()``, so a read
after a refresh saw an older host version than the receipt named. Both are legal
provider behavior. This wrapper reproduces them deterministically over any provider,
the Python one included, so a host fix can be tested without fdu:

- ``split_batches`` delivers every provider batch that carries data as a state-only
  batch followed by the data batch. It doubles every sequence (provider ``N`` is
  ``2N``; the state-only batch before it is ``2N - 1``) and maps a pinned read or a
  resume cursor back with ``sequence // 2``, so a pin at a state-only version reads the
  provider version before the data, as a provider that commits state first would.
- ``provider_name`` renames the provider in diagnostics, so identity is not pinned.
- ``replay_capacity`` shrinks the provider's change history, in its own batches.
- ``delivery_delay_s`` delays every batch the change iterator delivers.

Each opened handle also carries a fault seam, so relay recovery can be tested:
:meth:`PerturbedHandle.fail_next_read` and :meth:`PerturbedHandle.fail_changes` raise
a chosen exception, a `BaseException` that is not an `Exception` included, from the
next read or from the change iterator, waking it if it is waiting.

The wrapper changes nothing else: projections, receipts, and states are the wrapped
provider's own, and every perturbation is off by default.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass, replace
from pathlib import Path

from metabrowser.inventory_engine.contract import (
    ChangeBatch,
    ChangeCursor,
    DiagnosticsProjection,
    EngineVersion,
    InventoryBackend,
    InventoryConfig,
    InventoryHandle,
    PriorityRequest,
    ProjectionResult,
    ReadRequest,
    ReadResult,
    RefreshReceipt,
    RefreshRequest,
)


@dataclass(frozen=True, slots=True)
class Perturbation:
    """What a :class:`PerturbedBackend` changes about the provider it wraps."""

    split_batches: bool = False
    provider_name: str | None = None
    replay_capacity: int | None = None
    delivery_delay_s: float = 0.0

    def __post_init__(self) -> None:
        if self.provider_name is not None and not self.provider_name:
            raise ValueError("provider_name must not be empty")
        if self.replay_capacity is not None and self.replay_capacity <= 0:
            raise ValueError("replay_capacity must be positive")
        if self.delivery_delay_s < 0:
            raise ValueError("delivery_delay_s must not be negative")


class PerturbedBackend:
    """Open the wrapped backend's handles behind a :class:`PerturbedHandle`."""

    def __init__(self, inner: InventoryBackend, perturbation: Perturbation) -> None:
        self._inner = inner
        self._perturbation = perturbation
        self.handles: list[PerturbedHandle] = []

    async def open(self, root: Path, config: InventoryConfig) -> PerturbedHandle:
        capacity = self._perturbation.replay_capacity
        if capacity is not None and capacity < config.change_queue_size:
            config = replace(config, change_queue_size=capacity)
        handle = PerturbedHandle(await self._inner.open(root, config), self._perturbation)
        self.handles.append(handle)
        return handle


class PerturbedHandle:
    """One wrapped handle: translated sequences, renamed diagnostics, and faults."""

    def __init__(self, inner: InventoryHandle, perturbation: Perturbation) -> None:
        self._inner = inner
        self._perturbation = perturbation
        self._read_fault: BaseException | None = None
        self._changes_fault: BaseException | None = None
        self._changes_fault_armed = asyncio.Event()

    def fail_next_read(self, error: BaseException) -> None:
        """Make the next :meth:`read` raise *error* instead of reading."""

        self._read_fault = error

    def fail_changes(self, error: BaseException) -> None:
        """Make the change iterator raise *error* at once, or when it next starts."""

        self._changes_fault = error
        self._changes_fault_armed.set()

    async def read(self, request: ReadRequest) -> ReadResult:
        fault, self._read_fault = self._read_fault, None
        if fault is not None:
            raise fault
        if request.at_version is not None:
            request = replace(request, at_version=self._inner_version(request.at_version))
        result = await self._inner.read(request)
        version = self._outer_version(result.version)
        return replace(
            result,
            version=version,
            cursor=version.cursor,
            projections=tuple(self._rename(projection) for projection in result.projections),
        )

    def changes(self, *, after: ChangeCursor | None) -> AsyncGenerator[ChangeBatch]:
        return self._changes(after=after)

    async def refresh(self, request: RefreshRequest) -> RefreshReceipt:
        receipt = await self._inner.refresh(request)
        return replace(receipt, version=self._outer_version(receipt.version))

    async def prioritize(self, request: PriorityRequest) -> None:
        await self._inner.prioritize(request)

    async def close(self) -> None:
        await self._inner.close()

    async def _changes(self, *, after: ChangeCursor | None) -> AsyncGenerator[ChangeBatch]:
        inner_after = (
            None
            if after is None
            else ChangeCursor(session=after.session, sequence=self._inner_sequence(after.sequence))
        )
        # A provider resumed from a state-only cursor replays the batch that state
        # belongs to, whose state-only half the caller has already seen.
        floor = -1 if after is None else after.sequence
        inner = self._inner.changes(after=inner_after)
        armed = asyncio.ensure_future(self._changes_fault_armed.wait())
        pending: asyncio.Future[ChangeBatch] | None = None
        try:
            while True:
                self._raise_armed_changes_fault()
                pending = asyncio.ensure_future(anext(inner))
                await asyncio.wait({pending, armed}, return_when=asyncio.FIRST_COMPLETED)
                self._raise_armed_changes_fault()
                try:
                    batch = pending.result()
                except StopAsyncIteration:
                    return
                finally:
                    pending = None
                for delivered in self._delivered(batch):
                    if delivered.cursor.sequence <= floor:
                        continue
                    if self._perturbation.delivery_delay_s:
                        await asyncio.sleep(self._perturbation.delivery_delay_s)
                    self._raise_armed_changes_fault()
                    yield delivered
        finally:
            armed.cancel()
            if pending is not None:
                pending.cancel()
                with contextlib.suppress(BaseException):
                    await pending
            close = getattr(inner, "aclose", None)
            if close is not None:
                await close()

    def _raise_armed_changes_fault(self) -> None:
        fault = self._changes_fault
        if fault is not None:
            self._changes_fault = None
            self._changes_fault_armed.clear()
            raise fault

    def _delivered(self, batch: ChangeBatch) -> tuple[ChangeBatch, ...]:
        version = self._outer_version(batch.version)
        whole = replace(batch, version=version, cursor=version.cursor)
        carries_data = (
            batch.dirty_paths or batch.non_file_paths or batch.dirty_queries or batch.all_dirty
        )
        if (
            not self._perturbation.split_batches
            or batch.reset
            or not carries_data
            or batch.version.sequence == 0
        ):
            return (whole,)
        state_version = replace(version, sequence=version.sequence - 1)
        state_only = ChangeBatch(
            cursor=state_version.cursor, version=state_version, state=batch.state
        )
        return (state_only, whole)

    def _outer_sequence(self, sequence: int) -> int:
        return sequence * 2 if self._perturbation.split_batches else sequence

    def _inner_sequence(self, sequence: int) -> int:
        return sequence // 2 if self._perturbation.split_batches else sequence

    def _outer_version(self, version: EngineVersion) -> EngineVersion:
        return replace(version, sequence=self._outer_sequence(version.sequence))

    def _inner_version(self, version: EngineVersion) -> EngineVersion:
        return replace(version, sequence=self._inner_sequence(version.sequence))

    def _rename(self, projection: ProjectionResult) -> ProjectionResult:
        name = self._perturbation.provider_name
        if name is None or not isinstance(projection, DiagnosticsProjection):
            return projection
        return replace(projection, payload=replace(projection.payload, provider=name))


__all__ = ["Perturbation", "PerturbedBackend", "PerturbedHandle"]
