"""Tests for tree-row marker_basename decoration (Tier A, dataset-plugin spec).

When a plugin declares ``[[kind]] match.folder_marker = "<basename>"``,
metabrowser's tree renderer should add ``marker_basename: "<basename>"`` to
the row dict for every directory whose direct children include that file.
The shell uses the field to paint a marker badge + steer default-click on
the folder to the marker file.

These tests exercise the tree.py side of the contract directly, injecting
markers via :func:`set_folder_markers` rather than spinning up a real
plugin-discovery cycle. Plugin-discovery → marker propagation is covered
end-to-end in ``test_plugin_loader.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from metabrowser.paths_safe import _set_root_dir
from metabrowser.tree import _dir_tree, set_folder_markers


@pytest.fixture(autouse=True)
def _clear_markers():  # pyright: ignore[reportUnusedFunction]
    """Each test starts with an empty marker set; tear down likewise."""
    set_folder_markers(set())
    yield
    set_folder_markers(set())


@pytest.fixture
def served_root(tmp_path: Path):
    """Treat *tmp_path* as the served root for the duration of the test so
    ``_rel_path`` in tree.py emits stable relative paths."""
    _set_root_dir(tmp_path)
    yield tmp_path
    _set_root_dir(Path())


TreeRow = dict[str, Any]


def _find_dir(entries: list[TreeRow], name: str) -> TreeRow | None:
    for e in entries:
        if e.get("name") == name and e.get("type") == "dir":
            return e
    return None


def _children(row: TreeRow) -> list[TreeRow]:
    children = row.get("children")
    assert isinstance(children, list)
    return children


def test_marker_basename_set_when_marker_present(served_root: Path) -> None:
    set_folder_markers({"dataset.yml"})
    room = served_root / "rooms" / "ALPHA"
    room.mkdir(parents=True)
    (room / "dataset.yml").write_text("spec: ExampleDataset/0.1\n")
    (room / "blobs").mkdir()

    tree = _dir_tree(served_root)
    rooms_dir = _find_dir(tree, "rooms")
    assert rooms_dir is not None
    project_dir = _find_dir(_children(rooms_dir), "ALPHA")
    assert project_dir is not None
    assert project_dir.get("marker_basename") == "dataset.yml"


def test_marker_basename_absent_when_no_marker(served_root: Path) -> None:
    set_folder_markers({"dataset.yml"})
    plain = served_root / "ordinary"
    plain.mkdir()
    (plain / "notes.txt").write_text("hi\n")

    tree = _dir_tree(served_root)
    plain_dir = _find_dir(tree, "ordinary")
    assert plain_dir is not None
    assert "marker_basename" not in plain_dir


def test_marker_basename_absent_when_marker_set_empty(served_root: Path) -> None:
    # Even if a file with a known dataset-style name exists, no markers
    # registered means no decoration.
    set_folder_markers(set())
    room = served_root / "rooms" / "ALPHA"
    room.mkdir(parents=True)
    (room / "dataset.yml").write_text("spec: ExampleDataset/0.1\n")

    tree = _dir_tree(served_root)
    rooms_dir = _find_dir(tree, "rooms")
    assert rooms_dir is not None
    project_dir = _find_dir(_children(rooms_dir), "ALPHA")
    assert project_dir is not None
    assert "marker_basename" not in project_dir


def test_marker_basename_picks_stably_when_two_markers_coexist(served_root: Path) -> None:
    set_folder_markers({"dataset.yml", "catalog.yml"})
    weird = served_root / "weird"
    weird.mkdir()
    (weird / "dataset.yml").write_text("a\n")
    (weird / "catalog.yml").write_text("b\n")

    tree = _dir_tree(served_root)
    weird_dir = _find_dir(tree, "weird")
    assert weird_dir is not None
    # Two markers in the same dir is rare; we pick the alphabetically-first
    # name so the choice is stable across runs.
    assert weird_dir.get("marker_basename") == "catalog.yml"


def test_marker_basename_set_on_lazy_sentinel(served_root: Path) -> None:
    """When ``remaining_depth`` causes the renderer to emit a lazy-load
    sentinel for a directory (no children list), the marker still decorates
    the row via :func:`_scan_marker_basename`."""
    set_folder_markers({"dataset.yml"})
    room = served_root / "rooms" / "ALPHA"
    room.mkdir(parents=True)
    (room / "dataset.yml").write_text("spec: ExampleDataset/0.1\n")

    # depth=1 means rooms/ emits its children but ALPHA/'s children are
    # represented by a sentinel (children=None).
    tree = _dir_tree(served_root, remaining_depth=1)
    rooms_dir = _find_dir(tree, "rooms")
    assert rooms_dir is not None
    project_dir = _find_dir(_children(rooms_dir), "ALPHA")
    assert project_dir is not None
    assert project_dir.get("children") is None  # sentinel
    assert project_dir.get("marker_basename") == "dataset.yml"
