"""Tests for the built-in ``lmdb`` plugin (manifest classification + sidekick handlers).

Two layers:

1. Classification: a folder containing ``data.mdb`` resolves to kind
   ``lmdb-database`` via the manifest classifier (Tier A's ``folder_marker``
   match).
2. Sidekick handlers (keys / entry / stats): called directly with a Mock
   request, against a real on-disk LMDB env. No HTTP transport.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import lmdb
import msgpack
import pytest

from metabrowser import server
from metabrowser.builtin_plugins.lmdb.sidekick import (
    entry_handler,
    keys_handler,
    stats_handler,
)
from metabrowser.lmdb_reader import clear_value_decoders, register_value_decoder


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _make_request(params: dict[str, str]) -> Mock:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery(params)
    request.headers = {}
    return request


def _packb(value: object) -> bytes:
    return cast(bytes, msgpack.packb(value))


def _json_body(response: Any) -> Any:
    return json.loads(bytes(response.body))


def _populate_env(env_dir: Path, entries: dict[bytes, bytes]) -> None:
    env = lmdb.open(str(env_dir), max_dbs=8, map_size=10 * 1024 * 1024)
    with env.begin(write=True) as txn:
        for k, v in entries.items():
            txn.put(k, v)
    env.close()


@pytest.fixture
def env_under_root(tmp_path: Path) -> Path:
    """Create an LMDB env under the served root and point the server at the
    root so :func:`_safe_path` accepts a relative path to the env folder.
    """
    server._set_root_dir(tmp_path)  # noqa: SLF001
    env_dir = tmp_path / "rooms" / "ALPHA" / "metadata" / "blobs.index.lmdb"
    env_dir.mkdir(parents=True)
    _populate_env(
        env_dir,
        {
            b"blob:abc": _packb({"sourceDomain": "apple.com", "size": 1024}),
            b"blob:def": _packb({"sourceDomain": "sec.gov", "size": 4096}),
            b"urlh12:xyz": _packb({"blobKey": "abc", "canonicalUrl": "https://apple.com/"}),
            b"plain:1": b"hello",
        },
    )
    return env_dir


@pytest.fixture(autouse=True)
def _isolate_decoder_registry():
    clear_value_decoders()
    yield
    clear_value_decoders()


# ── Classification ──────────────────────────────────────────────────


def _api_file(path: str) -> dict[str, Any]:
    request = _make_request({"path": path})
    response = asyncio.run(server.api_file(request))
    return _json_body(response)


def test_lmdb_folder_classifies_as_lmdb_database(env_under_root: Path) -> None:
    # The classifier matches the marker file (data.mdb) inside the env.
    result = _api_file("rooms/ALPHA/metadata/blobs.index.lmdb/data.mdb")
    assert result["kind"] == "lmdb-database"
    view_ids = [v["id"] for v in result["views"]]
    assert "keys" in view_ids
    assert "entry" in view_ids
    assert "stats" in view_ids


# ── Sidekick: keys ──────────────────────────────────────────────────


def test_keys_handler_lists_all_keys(env_under_root: Path) -> None:
    resp = keys_handler(_make_request({"path": "rooms/ALPHA/metadata/blobs.index.lmdb"}))
    body = _json_body(resp)
    assert resp.status_code == 200
    assert len(body["keys"]) == 4
    keys = [bytes.fromhex(r["key"]) for r in body["keys"]]
    assert b"blob:abc" in keys
    assert b"urlh12:xyz" in keys
    assert b"plain:1" in keys


def test_keys_handler_prefix_filter(env_under_root: Path) -> None:
    resp = keys_handler(
        _make_request(
            {
                "path": "rooms/ALPHA/metadata/blobs.index.lmdb",
                "prefix": b"blob:".hex(),
            }
        )
    )
    body = _json_body(resp)
    keys = [bytes.fromhex(r["key"]) for r in body["keys"]]
    assert set(keys) == {b"blob:abc", b"blob:def"}


def test_keys_handler_pagination(env_under_root: Path) -> None:
    page1 = _json_body(
        keys_handler(_make_request({"path": "rooms/ALPHA/metadata/blobs.index.lmdb", "limit": "2"}))
    )
    assert len(page1["keys"]) == 2
    assert page1["nextCursor"] is not None
    page2 = _json_body(
        keys_handler(
            _make_request(
                {
                    "path": "rooms/ALPHA/metadata/blobs.index.lmdb",
                    "limit": "100",
                    "cursor": page1["nextCursor"],
                }
            )
        )
    )
    assert len(page2["keys"]) == 2  # 4 total - 2 already returned
    assert page2["nextCursor"] is None


def test_keys_handler_404_on_missing_env(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)  # noqa: SLF001
    resp = keys_handler(_make_request({"path": "does/not/exist"}))
    assert resp.status_code == 404


def test_keys_handler_uses_registered_decoder(env_under_root: Path) -> None:
    register_value_decoder(
        lambda subdb, key, value: key.startswith(b"blob:"),
        lambda value: {"__type": "BlobEntry", **msgpack.unpackb(value, raw=False)},
    )
    resp = keys_handler(
        _make_request(
            {
                "path": "rooms/ALPHA/metadata/blobs.index.lmdb",
                "prefix": b"blob:".hex(),
            }
        )
    )
    body = _json_body(resp)
    # decoderUsed reflects that the registered decoder ran (function name).
    decoders = {r["decoderUsed"] for r in body["keys"]}
    assert "<lambda>" in decoders or "decode" in decoders


# ── Sidekick: entry ─────────────────────────────────────────────────


def test_entry_handler_returns_decoded_value(env_under_root: Path) -> None:
    resp = entry_handler(
        _make_request(
            {
                "path": "rooms/ALPHA/metadata/blobs.index.lmdb",
                "key": b"plain:1".hex(),
            }
        )
    )
    body = _json_body(resp)
    assert resp.status_code == 200
    assert body["decoded"] == "hello"
    assert body["decoderUsed"] == "utf8"
    assert body["size"] == 5
    assert body["truncated"] is False


def test_entry_handler_404_on_missing_key(env_under_root: Path) -> None:
    resp = entry_handler(
        _make_request(
            {
                "path": "rooms/ALPHA/metadata/blobs.index.lmdb",
                "key": b"nope".hex(),
            }
        )
    )
    assert resp.status_code == 404


def test_entry_handler_requires_key_param(env_under_root: Path) -> None:
    resp = entry_handler(_make_request({"path": "rooms/ALPHA/metadata/blobs.index.lmdb"}))
    assert resp.status_code == 400


# ── Sidekick: stats ─────────────────────────────────────────────────


def test_stats_handler_returns_entry_count(env_under_root: Path) -> None:
    resp = stats_handler(_make_request({"path": "rooms/ALPHA/metadata/blobs.index.lmdb"}))
    body = _json_body(resp)
    assert resp.status_code == 200
    assert body["totalEntries"] >= 4
    assert len(body["subdbs"]) >= 1  # at least the main DB
    assert body["sizeBytes"] > 0
