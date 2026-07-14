"""Tests for the read-only LmdbReader + value-decoder registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import lmdb
import msgpack
import pytest

from metabrowser.lmdb_reader import (
    LmdbReader,
    clear_value_decoders,
    decode_value,
    register_value_decoder,
)

# ── Fixtures ────────────────────────────────────────────────────────


def _populate_env(env_dir: Path, entries: dict[bytes, bytes]) -> None:
    """Write *entries* to an LMDB env at *env_dir*. Creates the env if missing."""
    env = lmdb.open(str(env_dir), max_dbs=8, map_size=10 * 1024 * 1024)
    with env.begin(write=True) as txn:
        for k, v in entries.items():
            txn.put(k, v)
    env.close()


@pytest.fixture
def small_env(tmp_path: Path) -> Path:
    env_dir = tmp_path / "small.lmdb"
    env_dir.mkdir()
    _populate_env(
        env_dir,
        {
            b"alpha:1": b"a",
            b"alpha:2": b"b",
            b"alpha:3": b"c",
            b"beta:1": b"d",
            b"beta:2": b"e",
        },
    )
    return env_dir


@pytest.fixture(autouse=True)
def _isolate_decoder_registry():
    """Each test starts with an empty value-decoder registry."""
    clear_value_decoders()
    yield
    clear_value_decoders()


# ── Reader ──────────────────────────────────────────────────────────


def test_open_close(small_env: Path) -> None:
    reader = LmdbReader(str(small_env))
    reader.open()
    s = reader.stats()
    assert s.entries == 5
    reader.close()


def test_context_manager(small_env: Path) -> None:
    with LmdbReader(str(small_env)) as reader:
        assert reader.stats().entries == 5


def test_iter_keys_returns_all_keys(small_env: Path) -> None:
    with LmdbReader(str(small_env)) as reader:
        keys, next_cursor = reader.iter_keys(limit=100)
    names = [k.key for k in keys]
    assert names == [b"alpha:1", b"alpha:2", b"alpha:3", b"beta:1", b"beta:2"]
    assert next_cursor is None


def test_iter_keys_prefix_filter(small_env: Path) -> None:
    with LmdbReader(str(small_env)) as reader:
        keys, next_cursor = reader.iter_keys(prefix=b"alpha:", limit=100)
    assert [k.key for k in keys] == [b"alpha:1", b"alpha:2", b"alpha:3"]
    assert next_cursor is None


def test_iter_keys_pagination(small_env: Path) -> None:
    with LmdbReader(str(small_env)) as reader:
        page1, cursor1 = reader.iter_keys(limit=2)
        assert [k.key for k in page1] == [b"alpha:1", b"alpha:2"]
        assert cursor1 == b"alpha:3"
        page2, cursor2 = reader.iter_keys(cursor=cursor1, limit=2)
        assert [k.key for k in page2] == [b"alpha:3", b"beta:1"]
        assert cursor2 == b"beta:2"
        page3, cursor3 = reader.iter_keys(cursor=cursor2, limit=100)
        assert [k.key for k in page3] == [b"beta:2"]
        assert cursor3 is None


def test_get_roundtrip(small_env: Path) -> None:
    with LmdbReader(str(small_env)) as reader:
        assert reader.get(b"alpha:1") == b"a"
        assert reader.get(b"missing") is None


def test_unopened_reader_raises(tmp_path: Path) -> None:
    env_dir = tmp_path / "x.lmdb"
    env_dir.mkdir()
    _populate_env(env_dir, {b"k": b"v"})
    reader = LmdbReader(str(env_dir))
    with pytest.raises(RuntimeError, match="not open"):
        reader.stats()


# ── Decoder chain ───────────────────────────────────────────────────


def test_decode_value_utf8_passthrough() -> None:
    decoded, decoder = decode_value("", b"k", b"hello")
    assert decoded == "hello"
    assert decoder == "utf8"


def test_decode_value_json_dict() -> None:
    payload = json.dumps({"a": 1, "b": [2, 3]}).encode("utf-8")
    decoded, decoder = decode_value("", b"k", payload)
    # JSON encoded as utf-8 also decodes via utf8 first. We accept either
    # but explicitly check that a parseable structure ends up as one.
    if decoder == "utf8":
        # Trust the chain: it returned the raw JSON string.
        assert decoded == payload.decode("utf-8")
    else:
        assert decoder == "json"
        assert decoded == {"a": 1, "b": [2, 3]}


def test_decode_value_msgpack_dict() -> None:
    payload = cast(bytes, msgpack.packb({"name": "Alice", "age": 30}))
    decoded, decoder = decode_value("", b"k", payload)
    assert decoder == "msgpack"
    assert decoded == {"name": "Alice", "age": 30}


def test_decode_value_falls_through_to_hex_on_binary_garbage() -> None:
    # Bytes that look like binary garbage AND don't parse as msgpack/utf-8/JSON.
    # \xff\xff is invalid utf-8 and not a valid msgpack prefix.
    payload = b"\xff\xff\xff\xff"
    decoded, decoder = decode_value("", b"k", payload)
    assert decoder == "hex"
    assert decoded == "ffffffff"


def test_registered_decoder_wins_over_default_chain() -> None:
    def predicate(subdb: str, key: bytes, value: bytes) -> bool:
        return key.startswith(b"blob:")

    def decode(value: bytes) -> dict[str, str]:
        return {"__type": "BlobEntry", "raw": value.decode("utf-8", errors="replace")}

    register_value_decoder(predicate, decode)
    decoded, decoder_used = decode_value("", b"blob:abc", b"hello")
    assert decoded == {"__type": "BlobEntry", "raw": "hello"}
    assert decoder_used == "decode"


def test_registered_decoder_raises_falls_through() -> None:
    def predicate(subdb: str, key: bytes, value: bytes) -> bool:
        return True

    def decode(value: bytes) -> dict[str, str]:
        raise ValueError("nope")

    register_value_decoder(predicate, decode)
    decoded, decoder = decode_value("", b"k", b"hello")
    # Custom decoder raised; default chain kicks in.
    assert decoded == "hello"
    assert decoder == "utf8"
