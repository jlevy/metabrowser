"""Inventory runtime composition and projection invalidation tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import metabrowser.inventory_engine.runtime as runtime_module
from metabrowser.inventory_engine.contract import LifecyclePhase
from metabrowser.inventory_engine.runtime import InventoryRuntime


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


def test_discovery_does_not_invalidate_projections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A first walk has nothing to invalidate, and paid to say so.

    The coordinator publishes every entry it discovers, so wiring this listener
    to all of them meant one `invalidate_projection_path` per entry against
    caches that were empty. Each of those resolves the path -- a syscall -- once
    per projection cache, which measured about two seconds of a five second walk.

    Skipping it is safe rather than merely cheap: the projection caches are mtime
    keyed and revalidate on read, so a stale entry is a miss and never a wrong
    answer.
    """

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
                state=SimpleNamespace(phase=LifecyclePhase.DISCOVERING),
            ),
        )
    )

    assert broad_invalidations == []
    assert path_invalidations == []


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
