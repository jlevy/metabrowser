"""Inventory runtime composition and projection invalidation tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import metabrowser.inventory_engine.runtime as runtime_module
from metabrowser.inventory_engine.contract import LifecyclePhase
from metabrowser.inventory_engine.runtime import InventoryRuntime
from metabrowser.mtime_cache import MtimeCache


@pytest.mark.parametrize(("reset", "all_dirty"), ((True, False), (False, True)))
def test_broad_inventory_changes_clear_every_projection_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reset: bool,
    all_dirty: bool,
) -> None:
    broad_invalidations: list[None] = []
    path_invalidations: list[Path] = []
    monkeypatch.setattr(
        runtime_module,
        "invalidate_all_projection_caches",
        lambda: broad_invalidations.append(None),
    )
    monkeypatch.setattr(
        runtime_module,
        "invalidate_projection_path",
        path_invalidations.append,
    )
    runtime = InventoryRuntime()
    runtime._root = tmp_path

    runtime._invalidate_host_projections(
        cast(
            Any,
            SimpleNamespace(
                facts_changed=False,
                reset=reset,
                all_dirty=all_dirty,
                dirty_paths=(),
            ),
        )
    )

    assert broad_invalidations == [None]
    assert path_invalidations == []


def test_bounded_inventory_change_invalidates_only_dirty_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broad_invalidations: list[None] = []
    path_invalidations: list[Path] = []
    monkeypatch.setattr(
        runtime_module,
        "invalidate_all_projection_caches",
        lambda: broad_invalidations.append(None),
    )
    monkeypatch.setattr(
        runtime_module,
        "invalidate_projection_path",
        path_invalidations.append,
    )
    runtime = InventoryRuntime()
    runtime._root = tmp_path

    runtime._invalidate_host_projections(
        cast(
            Any,
            SimpleNamespace(
                facts_changed=True,
                reset=False,
                all_dirty=False,
                dirty_paths=("a.log", "runs/b.log"),
                state=SimpleNamespace(phase=LifecyclePhase.WATCHING),
            ),
        )
    )

    assert broad_invalidations == []
    assert path_invalidations == [tmp_path / "a.log", tmp_path / "runs/b.log"]


def test_discovery_costs_no_syscalls_against_empty_projection_caches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A first walk has nothing to invalidate, and used to pay a syscall to say so.

    The coordinator publishes every entry it discovers, so wiring this listener to all of
    them meant one `invalidate_projection_path` per entry against caches that were empty.
    Each of those resolves the path -- a syscall -- once per projection cache, which
    measured about two seconds of a five second walk.

    What is pinned here is the *property*, not a skip. An earlier fix gated the listener
    on the DISCOVERING phase, which also dropped real watcher and `refresh()`
    invalidations arriving during the walk -- the watcher starts first, so those exist --
    and was safe only because these caches revalidate on read, an invariant in another
    module that nothing tied to the gate. Returning before `resolve()` when the cache is
    empty gets the same walk back and decides nothing about semantics, so the test
    measures the syscall rather than the skip.
    """

    cache: MtimeCache[str] = MtimeCache(max_size=8, name="probe")
    resolves = 0
    real_resolve = Path.resolve

    def counting_resolve(self: Path, *args: Any, **kwargs: Any) -> Path:
        nonlocal resolves
        resolves += 1
        return real_resolve(self, *args, **kwargs)

    target = tmp_path / "a.log"
    target.write_text("a")

    monkeypatch.setattr(Path, "resolve", counting_resolve)
    for _ in range(100):
        cache.delete(target)
    assert resolves == 0, "an empty cache must not resolve the path it was asked to drop"

    # A populated cache still invalidates, which is the behaviour being preserved.
    cache.update(target, "value")
    resolves = 0
    cache.delete(target)
    assert resolves > 0


def test_a_reset_still_clears_everything_during_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A root swap is not discovery noise, and must still clear the caches."""

    broad_invalidations: list[None] = []
    monkeypatch.setattr(
        runtime_module,
        "invalidate_all_projection_caches",
        lambda: broad_invalidations.append(None),
    )
    runtime = InventoryRuntime()
    runtime._root = tmp_path

    runtime._invalidate_host_projections(
        cast(
            Any,
            SimpleNamespace(
                facts_changed=True,
                reset=True,
                all_dirty=False,
                dirty_paths=(),
                state=SimpleNamespace(phase=LifecyclePhase.DISCOVERING),
            ),
        )
    )

    assert broad_invalidations == [None]
