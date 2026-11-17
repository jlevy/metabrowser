"""Provider-owned seams that tests and measurement harnesses can hold a provider at.

A test that needs discovery stopped at a known point, or a retention bound small enough
to reach, used to patch one provider's private functions and constants. A patch of that
kind exercises one engine and silently tests nothing once another engine serves the
same suite. These seams are the same request made through the contract instead: every
provider accepts them in its backend constructor and implements their meaning, so a
product test written against them runs unchanged against any provider.

They travel beside `InventoryConfig`, never inside it, because they change neither
scope nor semantics: a config is part of an opened root's identity, and these are not.
The sealed factory (`create_inventory_backend`) and `InventoryRuntime` pass them
through, and the application's lifespan passes none, so a served root never has one.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from metabrowser.inventory_engine.contract import (
    MAX_ASSEMBLED_ROWS,
    require_canonical_inventory_path,
)


class DiscoveryGate:
    """Hold opened discovery before it reads one directory, until released.

    A provider awaits :meth:`hold` with each directory's canonical path immediately
    before it enumerates that directory during its opening discovery. At the gate's
    directory it reports :attr:`reached` and waits for :meth:`release`; every other
    directory passes straight through, and so does every directory once the gate is
    released. ``before=""`` therefore holds discovery before it lists anything below the
    root, and a deeper path lets discovery publish everything level order reaches before
    that directory, which is how a test scripts a partially discovered tree.

    Only opening discovery is gated: a later rescan, such as one an observed directory
    creation starts, passes. A held provider still answers reads, reports the
    ``discovering`` phase, and closes promptly without being released.
    """

    def __init__(self, *, before: str = "") -> None:
        require_canonical_inventory_path(before, "before", allow_root=True)
        self.before = before
        self._reached = asyncio.Event()
        self._released = asyncio.Event()

    @property
    def reached(self) -> bool:
        """Whether discovery has arrived at the gate's directory."""

        return self._reached.is_set()

    async def wait_reached(self) -> None:
        """Return once discovery is held at, or has passed, the gate's directory."""

        await self._reached.wait()

    def release(self) -> None:
        """Let discovery continue, now and at every later arrival."""

        self._released.set()

    async def hold(self, directory: str) -> None:
        """Called by a provider before it reads *directory*; waits there at the gate."""

        if directory != self.before:
            return
        self._reached.set()
        await self._released.wait()


@dataclass(frozen=True, slots=True)
class ProviderSeams:
    """The seams one opened provider honors; each is absent in production.

    ``max_retained_rows`` lowers the bound on rows a provider retains to serve
    continuations, which is `MAX_ASSEMBLED_ROWS` otherwise, so a test can reach the
    eviction a production-sized tree reaches.
    """

    discovery_gate: DiscoveryGate | None = None
    max_retained_rows: int | None = None

    def __post_init__(self) -> None:
        bound = self.max_retained_rows
        if bound is not None and not 0 < bound <= MAX_ASSEMBLED_ROWS:
            raise ValueError(f"max_retained_rows must be between 1 and {MAX_ASSEMBLED_ROWS}")


__all__ = ["DiscoveryGate", "ProviderSeams"]
