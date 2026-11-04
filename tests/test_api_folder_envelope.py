"""/api/file returns a folder envelope for directories.

Locks in the directory branch of _api_file_impl: kind/views come from
the merged folder plugin manifest, aggregates come from the inventory
(null-tolerant while scanning), README detection is case-insensitive
and scoped to direct children, and the envelope is no-store. Paths
outside the root still 404.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from metabrowser import server
from metabrowser.inventory_engine.contract import InventoryEntry
from tests.git_pin_harness import fast_import_store, pinned_client
from tests.inventory_harness import inventory_harness
from tests.required_tools import needs_git


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _request(path: str, *, app: object) -> Mock:
    request = Mock(spec=["query_params", "headers", "app"])
    request.query_params = _FakeQuery({"path": path})
    request.headers = {}
    request.app = app
    return request


def _api_file(
    root: Path,
    path: str,
    *,
    settle: bool = True,
) -> tuple[dict[str, Any], Any]:
    async def run() -> tuple[dict[str, Any], Any]:
        async with inventory_harness(root, settle=settle) as harness:
            response = await server.api_file(_request(path, app=harness.app))
            return json.loads(bytes(response.body)), response

    return asyncio.run(run())


def test_directory_returns_folder_envelope(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "data.txt").write_text("x" * 32)
    body, response = _api_file(tmp_path, "sub")
    assert body["type"] == "folder"
    assert body["kind"] == "folder"
    assert body["path"] == "sub"
    assert body["name"] == "sub"
    view_ids = [v["id"] for v in body["views"]]
    assert view_ids == ["overview", "treemap"]
    defaults = [v["id"] for v in body["views"] if v.get("default")]
    assert defaults == ["overview"]
    assert response.headers["cache-control"] == "no-store"


def test_root_directory_envelope_and_pending_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def blocked_walk(
        *_args: object,
        **_kwargs: object,
    ) -> AsyncIterator[InventoryEntry]:
        if False:
            yield InventoryEntry.for_observed_dir(path="", parent="", name=tmp_path.name)
        await asyncio.Event().wait()

    monkeypatch.setattr(
        "metabrowser.inventory_engine.providers.python_inventory.walk_tree",
        blocked_walk,
    )
    server._set_root_dir(tmp_path)
    (tmp_path / "a.txt").write_text("hello")
    body, _ = _api_file(tmp_path, "", settle=False)
    assert body["kind"] == "folder"
    assert body["path"] == ""
    # No inventory has run: aggregates are pending, never fabricated.
    assert body["dir"]["total_files"] is None
    assert body["dir"]["state"] == "pending"


def test_envelope_aggregates_come_from_inventory(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "one.txt").write_text("x" * 10)
    (sub / "two.txt").write_text("y" * 30)

    body, _response = _api_file(tmp_path, "sub")
    assert body["dir"]["state"] == "complete"
    assert body["dir"]["total_files"] == 2
    assert body["dir"]["total_size"] == 40
    assert body["dir"]["unignored_files"] == 2
    assert body["dir"]["unignored_size"] == 40
    assert body["dir"]["mtime"] > 0


def test_readme_detection_direct_children_only(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ReadMe.MD").write_text("# docs")
    nested = docs / "nested"
    nested.mkdir()
    (nested / "other.txt").write_text("no readme here")

    body, _ = _api_file(tmp_path, "docs")
    assert body["readme_path"] == "docs/ReadMe.MD"
    nested_body, _ = _api_file(tmp_path, "docs/nested")
    assert nested_body["readme_path"] == ""


def test_traversal_still_404(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    _, response = _api_file(tmp_path, "../outside")
    assert response.status_code == 404


def test_missing_path_still_404(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    _, response = _api_file(tmp_path, "nope")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "path",
    [".hidden", ".hidden/", ".hidden/sub", "shown/.hidden", "shown/.hidden/deeper"],
)
def test_hidden_folder_keeps_its_envelope_and_says_it_is_not_indexed(
    tmp_path: Path, path: str
) -> None:
    """The inventory leaves hidden folders out, so the aggregates will never arrive."""
    (tmp_path / ".hidden" / "sub").mkdir(parents=True)
    (tmp_path / "shown" / ".hidden" / "deeper").mkdir(parents=True)
    server._set_root_dir(tmp_path)
    body, response = _api_file(tmp_path, path)
    assert response.status_code == 200
    assert body["kind"] == "folder"
    assert [view["id"] for view in body["views"]] == ["overview", "treemap"]
    assert body["dir"]["total_files"] is None
    assert body["dir"]["state"] == "pending"
    assert body["dir"]["not_indexed"] == "hidden"


def test_hidden_folder_keeps_its_readme(tmp_path: Path) -> None:
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "README.md").write_text("# GH readme\n")
    server._set_root_dir(tmp_path)
    body, _response = _api_file(tmp_path, ".github/")
    assert body["readme_path"] == ".github/README.md"


def test_file_in_a_hidden_folder_still_opens(tmp_path: Path) -> None:
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "notes.txt").write_text("plain\n")
    server._set_root_dir(tmp_path)
    body, response = _api_file(tmp_path, ".hidden/notes.txt")
    assert response.status_code == 200
    assert body["kind"] == "text"


@pytest.mark.parametrize("path", ["link", "link/", "link/nested"])
def test_folder_through_a_symlink_says_it_is_not_indexed(tmp_path: Path, path: str) -> None:
    """The inventory keeps a symlink without following it, so nothing tallies through one."""
    (tmp_path / "target" / "nested").mkdir(parents=True)
    (tmp_path / "target" / "README.md").write_text("# target\n")
    (tmp_path / "link").symlink_to("target")
    server._set_root_dir(tmp_path)
    body, response = _api_file(tmp_path, path)
    assert response.status_code == 200
    assert body["kind"] == "folder"
    assert body["dir"]["total_files"] is None
    assert body["dir"]["not_indexed"] == "symlink"


def test_served_root_through_a_symlink_is_an_ordinary_folder(tmp_path: Path) -> None:
    """A symlink above the root is not on any path the inventory walks."""
    (tmp_path / "real" / "sub").mkdir(parents=True)
    (tmp_path / "real" / "sub" / "data.txt").write_text("plain\n")
    (tmp_path / "alias").symlink_to("real")
    root = tmp_path / "alias"
    server._set_root_dir(root)
    for path in ("", "sub"):
        body, response = _api_file(root, path)
        assert response.status_code == 200
        assert "not_indexed" not in body["dir"], path


@pytest.mark.parametrize("path", ["", "sub", ".logs", ".state", ".logs/sub"])
def test_a_folder_the_inventory_lists_carries_no_reason(tmp_path: Path, path: str) -> None:
    """`.logs` and `.state` are the inventory's own allowlist, so they are ordinary folders."""
    for folder in ("sub", ".logs/sub", ".state"):
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "run.txt").write_text("plain\n")
    server._set_root_dir(tmp_path)
    body, response = _api_file(tmp_path, path)
    assert response.status_code == 200
    assert body["kind"] == "folder"
    assert body["dir"]["state"] == "complete"
    assert "not_indexed" not in body["dir"]


@needs_git
def test_a_pins_dot_folder_keeps_its_totals_and_readme(tmp_path: Path) -> None:
    """A pin answers from its tree, where a dot-folder is a folder like any other."""
    store, commit = fast_import_store(
        tmp_path,
        {b".github/README.md": b"# GH readme\n", b"README.md": b"# root\n"},
    )
    wire = "g1-LmdpdGh1Yg"

    async def run() -> tuple[dict[str, Any], dict[str, Any], int]:
        async with pinned_client(store, commit) as (client, _subject):
            folder = await client.get("/api/file", params={"path": wire})
            rollup = await client.get("/api/rollup", params={"path": wire})
            readme = await client.get("/api/file", params={"path": folder.json()["readme_path"]})
            assert folder.status_code == 200
            assert rollup.status_code == 200
            return folder.json(), rollup.json(), readme.status_code

    folder, rollup, readme_status = asyncio.run(run())
    assert folder["kind"] == "folder"
    assert folder["dir"]["total_files"] == 1
    assert "not_indexed" not in folder["dir"]
    assert folder["readme_path"] == f"{wire}/g1-UkVBRE1FLm1k"
    assert readme_status == 200
    assert rollup["file_type_breakdown"]["metrics"]["all"]["files"] == 1
