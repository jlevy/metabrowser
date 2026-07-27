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
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from metabrowser import server
from metabrowser.inventory import get_instance as get_inventory


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _request(path: str) -> Mock:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery({"path": path})
    request.headers = {}
    return request


def _api_file(path: str) -> tuple[dict[str, Any], Any]:
    response = asyncio.run(server.api_file(_request(path)))
    return json.loads(bytes(response.body)), response


def test_directory_returns_folder_envelope(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "data.txt").write_text("x" * 32)
    body, response = _api_file("sub")
    assert body["type"] == "folder"
    assert body["kind"] == "folder"
    assert body["path"] == "sub"
    assert body["name"] == "sub"
    view_ids = [v["id"] for v in body["views"]]
    assert view_ids == ["treemap"]
    defaults = [v["id"] for v in body["views"] if v.get("default")]
    assert defaults == ["treemap"]
    assert body["readme_path"] == ""
    assert response.headers["cache-control"] == "no-store"


def test_root_directory_envelope_and_pending_state(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "a.txt").write_text("hello")
    body, _ = _api_file("")
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

    async def scenario() -> dict[str, Any]:
        inventory = get_inventory()
        inventory.start(tmp_path)
        await inventory.wait_until_done(5)
        response = await server.api_file(_request("sub"))
        return json.loads(bytes(response.body))

    body = asyncio.run(scenario())
    assert body["dir"]["state"] == "complete"
    assert body["dir"]["total_files"] == 2
    assert body["dir"]["total_size"] == 40
    assert body["dir"]["mtime"] > 0


def test_readme_detection_direct_children_only(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ReadMe.MD").write_text("# docs")
    nested = docs / "nested"
    nested.mkdir()
    (nested / "other.txt").write_text("no readme here")

    body, _ = _api_file("docs")
    assert body["readme_path"] == "docs/ReadMe.MD"
    assert [view["id"] for view in body["views"]] == ["treemap", "readme"]
    nested_body, _ = _api_file("docs/nested")
    assert nested_body["readme_path"] == ""
    assert [view["id"] for view in nested_body["views"]] == ["treemap"]


def test_traversal_still_404(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    _, response = _api_file("../outside")
    assert response.status_code == 404


def test_missing_path_still_404(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    _, response = _api_file("nope")
    assert response.status_code == 404
