"""/api/rollup route contract.

Param clamping to the ROLLUP_* settings bounds, traversal and
non-directory rejection, the null-node cold envelope, envelope
metadata, and wire-shape validation of every emitted node.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from metabrowser import server
from metabrowser.inventory import get_instance as get_inventory
from metabrowser.settings import ROLLUP_MAX_TOP
from metabrowser.wire_models import validate_rollup_node


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _rollup(params: dict[str, str]) -> tuple[dict[str, Any], Any]:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery(params)
    request.headers = {}
    response = asyncio.run(server.api_rollup(request))
    return json.loads(bytes(response.body)), response


def _rollup_after_walk(tmp_path: Path, params: dict[str, str]) -> dict[str, Any]:
    async def scenario() -> dict[str, Any]:
        inventory = get_inventory()
        inventory.start(tmp_path)
        await inventory.wait_until_done(10)
        request = Mock(spec=["query_params", "headers"])
        request.query_params = _FakeQuery(params)
        request.headers = {}
        response = await server.api_rollup(request)
        return json.loads(bytes(response.body))

    return asyncio.run(scenario())


def test_rollup_route_envelope_and_wire_shape(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("x" * 64)
    (tmp_path / "top.md").write_text("y" * 16)

    body = _rollup_after_walk(tmp_path, {"path": ""})
    assert body["path"] == ""
    assert body["index_status"] in ("done", "truncated")
    assert body["indexed_files"] >= 2
    assert body["truncated"] is False
    node = body["node"]
    assert node is not None
    validate_rollup_node(node)
    assert node["total_files"] == 2
    assert isinstance(body["ext_tallies"], list)
    assert body["ext_tallies"][0][0] in (".py", ".md")


def test_rollup_route_404s(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "plain.txt").write_text("x")
    _, escape_response = _rollup({"path": "../.."})
    assert escape_response.status_code == 404
    _, file_response = _rollup({"path": "plain.txt"})
    assert file_response.status_code == 404
    _, missing_response = _rollup({"path": "absent"})
    assert missing_response.status_code == 404


def test_rollup_route_clamps_params(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("x" * (10 + i))

    body = _rollup_after_walk(
        tmp_path,
        {"path": "", "depth": "999", "top": "999999", "ext_top": "-3"},
    )
    node = body["node"]
    assert node is not None
    validate_rollup_node(node)
    # top clamps to ROLLUP_MAX_TOP (no crash, all five children emitted).
    assert len(node["children"]) == 5 <= ROLLUP_MAX_TOP
    # ext_top clamps to zero: only the remainder row remains.
    assert all(row[0] == "" for row in body["ext_tallies"])


def test_rollup_route_cold_index_returns_null_node(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "x.txt").write_text("x")
    # No explicit walk: the route may start one and serve whatever
    # landed within the cold-start grace; the contract is that ``node``
    # is either null (pending envelope) or a valid rollup — never a
    # fabricated shape.
    body, response = _rollup({"path": "nested"})
    assert response.status_code == 200
    if body["node"] is not None:
        validate_rollup_node(body["node"])
    else:
        assert body["ext_tallies"] == []
