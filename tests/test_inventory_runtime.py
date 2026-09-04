"""Inventory runtime composition and projection invalidation tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import metabrowser.inventory_engine.runtime as runtime_module
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
            ),
        )
    )

    assert broad_invalidations == []
    assert path_invalidations == [tmp_path / "a.log", tmp_path / "runs/b.log"]
