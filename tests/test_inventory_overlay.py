"""Tests for sparse host-owned inventory decorations."""

from __future__ import annotations

from typing import Any, cast

import pytest

import metabrowser.inventory_engine.overlay as overlay_module
from metabrowser.inventory_engine.overlay import (
    EMPTY_DECORATION,
    InventoryDecoration,
    InventoryOverlay,
)


def test_overlay_retains_only_nondefault_records_and_revisions_real_changes() -> None:
    overlay = InventoryOverlay()
    active = InventoryDecoration(active=True)

    assert overlay.replace("runs/a.log", None) == 0
    assert overlay.replace("runs/a.log", active) == 1
    assert overlay.replace("runs/a.log", active) == 1
    assert overlay.retained_count == 1

    snapshot = overlay.snapshot(("runs/a.log", "runs/not-retained.log"))
    assert snapshot.revision == 1
    assert snapshot.decorations == {"runs/a.log": active}

    assert overlay.replace("runs/a.log", EMPTY_DECORATION) == 2
    assert overlay.retained_count == 0


def test_overlay_applies_batches_atomically_and_returns_immutable_snapshots() -> None:
    overlay = InventoryOverlay()
    first = InventoryDecoration(views=("source",))
    second = InventoryDecoration(labels=(("pid_alive", "1"),))

    assert overlay.replace_many({"a": first, "b": second}) == 1
    snapshot = overlay.snapshot(("a", "b"))
    assert snapshot.revision == 1
    assert snapshot.decorations == {"a": first, "b": second}
    with pytest.raises(TypeError):
        cast(Any, snapshot.decorations)["a"] = second

    assert overlay.clear() == 2
    assert overlay.clear() == 2


@pytest.mark.parametrize(
    "path",
    ["/absolute", "../escape", "a/../b", "a//b", "./a", "a\\b", "a\x00b"],
)
def test_overlay_rejects_noncanonical_paths(path: str) -> None:
    overlay = InventoryOverlay()
    with pytest.raises(ValueError, match="canonical"):
        overlay.replace(path, InventoryDecoration(active=True))


def test_overlay_validates_writes_but_snapshot_is_only_a_sparse_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlay = InventoryOverlay()
    decoration = InventoryDecoration(active=True)
    overlay.replace("known.txt", decoration)

    def unexpected_validation(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("provider-returned read paths must not be revalidated")

    monkeypatch.setattr(
        overlay_module,
        "require_canonical_inventory_path",
        unexpected_validation,
    )
    assert overlay.snapshot(("known.txt",)).decorations == {"known.txt": decoration}
    with pytest.raises(AssertionError, match="must not be revalidated"):
        overlay.replace("later.txt", decoration)


def test_decoration_requires_deterministic_unique_views_and_labels() -> None:
    with pytest.raises(ValueError, match="unique"):
        InventoryDecoration(views=("source", "source"))
    with pytest.raises(ValueError, match="unique"):
        InventoryDecoration(labels=(("state", "a"), ("state", "b")))
    with pytest.raises(ValueError, match="sorted"):
        InventoryDecoration(labels=(("z", "1"), ("a", "2")))
