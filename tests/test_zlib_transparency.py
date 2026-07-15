"""End-to-end transparency and safety contracts for ``*.zlib`` artifacts."""

from __future__ import annotations

import asyncio
import json
import threading
import zlib
from pathlib import Path
from typing import Any

import pytest
from starlette.responses import StreamingResponse

from metabrowser import gz_io, server
from metabrowser.file_kinds import FileContext
from metabrowser.gz_io import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactDecompressionTimeoutError,
    ArtifactPath,
)
from metabrowser.plugin_loader.classify import CompiledKindRule, build_classifier
from metabrowser.plugin_loader.manifest import KindMatch, KindRule


class _Params:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)


class _Headers:
    def get(self, key: str, default: str = "") -> str:
        del key
        return default


class _Request:
    def __init__(self, **params: str) -> None:
        self.query_params = _Params(params)
        self.headers = _Headers()


def _json_response(response: Any) -> dict[str, Any]:
    return json.loads(bytes(response.body).decode())


def test_zlib_artifact_preserves_logical_identity_and_streams(tmp_path: Path) -> None:
    payload = "alpha\nβeta\n".encode()
    source = tmp_path / "notes.txt.zlib"
    source.write_bytes(zlib.compress(payload))

    artifact = ArtifactPath(source)

    assert artifact.is_compressed is True
    assert artifact.is_gzip is False
    assert artifact.is_zlib is True
    assert artifact.logical_ext == ".txt"
    assert artifact.logical_name == "notes.txt"
    assert artifact.compression == "zlib"
    assert artifact.logical_size == len(payload)
    with artifact.open_binary() as stream:
        assert stream.read() == payload
    with artifact.open_text(errors="strict") as stream:
        assert stream.read() == payload.decode()


def test_zlib_reader_enforces_decompressed_output_limit(tmp_path: Path) -> None:
    source = tmp_path / "bomb.txt.zlib"
    source.write_bytes(zlib.compress(b"x" * 10_000))

    with (
        pytest.raises(ArtifactDecompressionLimitError, match="decompressed content"),
        ArtifactPath(source).open_binary(max_output_bytes=128) as stream,
    ):
        stream.read()


def test_zlib_reader_enforces_compressed_input_limit(tmp_path: Path) -> None:
    source = tmp_path / "large.txt.zlib"
    source.write_bytes(zlib.compress(bytes(range(256)) * 16))

    with pytest.raises(ArtifactDecompressionLimitError, match="compressed content"):
        ArtifactPath(source).open_binary(max_compressed_bytes=8)


def test_zlib_reader_rejects_truncated_and_trailing_streams(tmp_path: Path) -> None:
    valid = zlib.compress(b"payload")
    malformed = {
        "truncated.txt.zlib": valid[:-2],
        "trailing.txt.zlib": valid + b"unexpected",
    }

    for name, encoded in malformed.items():
        source = tmp_path / name
        source.write_bytes(encoded)
        with (
            pytest.raises(ArtifactCompressionError),
            ArtifactPath(source).open_binary() as stream,
        ):
            stream.read()


def test_zlib_reader_enforces_cpu_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "slow.txt.zlib"
    source.write_bytes(zlib.compress(b"payload"))
    cpu_times = iter((10.0, 10.1))
    monkeypatch.setattr(gz_io.time, "thread_time", lambda: next(cpu_times))

    with (
        pytest.raises(ArtifactDecompressionTimeoutError, match="CPU seconds"),
        ArtifactPath(source).open_binary(max_cpu_seconds=0.01) as stream,
    ):
        stream.read()


def test_zlib_text_preview_and_tree_use_logical_wire_identity(tmp_path: Path) -> None:
    payload = ("0123456789abcdef" * 32).encode()
    source = tmp_path / "notes.txt.zlib"
    source.write_bytes(zlib.compress(payload))
    server._set_root_dir(tmp_path)

    request = _Request(path=source.name, offset="11", limit="23")
    file_response = asyncio.run(server.api_file(request))  # pyright: ignore[reportArgumentType]
    body = _json_response(file_response)

    assert body["type"] == "text_chunk"
    assert body["content"] == payload[11:34].decode()
    assert body["bytes_read"] == 34
    assert body["content_truncated"] is True
    assert body["logical_ext"] == ".txt"
    assert body["compressed"] is True
    assert body["compression"] == "zlib"
    assert body["size_uncompressed"] == len(payload)

    tree_response = asyncio.run(
        server.api_tree(_Request(path=""))  # pyright: ignore[reportArgumentType]
    )
    tree_body = _json_response(tree_response)
    entry = next(item for item in tree_body["tree"] if item["name"] == source.name)
    assert entry["logical_ext"] == ".txt"
    assert entry["compressed"] is True
    assert entry["compression"] == "zlib"


def test_zlib_markdown_preserves_frontmatter_and_classification(tmp_path: Path) -> None:
    markdown = "---\ntitle: Compressed report\n---\n# Body\n"
    source = tmp_path / "report.md.zlib"
    source.write_bytes(zlib.compress(markdown.encode()))
    server._set_root_dir(tmp_path)

    response = asyncio.run(
        server.api_file(_Request(path=source.name))  # pyright: ignore[reportArgumentType]
    )
    body = _json_response(response)

    assert body["type"] == "text"
    assert body["kind"] == "markdown"
    assert body["content"] == markdown
    assert body["frontmatter"] == {"title": "Compressed report"}


def test_zlib_json_and_yaml_support_content_based_plugin_classification(tmp_path: Path) -> None:
    json_source = tmp_path / "report.json.zlib"
    json_source.write_bytes(zlib.compress(b'{"schema":"Report/1"}'))
    yaml_source = tmp_path / "report.yaml.zlib"
    yaml_source.write_bytes(zlib.compress(b"schema: Report/1\n"))
    rules = [
        CompiledKindRule(
            rule=KindRule(
                id="json-report",
                match=KindMatch(ext=".json", json_has_key="schema", json_value_prefix="Report/"),
            ),
            plugin_name="test",
            discovery_index=0,
        ),
        CompiledKindRule(
            rule=KindRule(
                id="yaml-report",
                match=KindMatch(ext=".yaml", yaml_has_key="schema", yaml_value_prefix="Report/"),
            ),
            plugin_name="test",
            discovery_index=1,
        ),
    ]
    classifier = build_classifier(rules)

    assert classifier(FileContext(json_source, ".json")) == "json-report"
    assert classifier(FileContext(yaml_source, ".yaml")) == "yaml-report"


def test_zlib_jsonl_uses_structured_log_preview(tmp_path: Path) -> None:
    payload = b'{"type":"result","subtype":"success","is_error":false}\n'
    source = tmp_path / "events.jsonl.zlib"
    source.write_bytes(zlib.compress(payload))
    server._set_root_dir(tmp_path)

    response = asyncio.run(
        server.api_file(_Request(path=source.name))  # pyright: ignore[reportArgumentType]
    )
    body = _json_response(response)

    assert body["type"] == "jsonl"
    assert body["summary"]["total_events"] == 1
    assert body["logical_ext"] == ".jsonl"
    assert body["compression"] == "zlib"


def test_raw_zlib_streams_decompressed_identity_body(tmp_path: Path) -> None:
    payload = b"raw zlib payload\n" * 20
    source = tmp_path / "payload.txt.zlib"
    source.write_bytes(zlib.compress(payload))
    server._set_root_dir(tmp_path)

    response = asyncio.run(
        server.raw_file(_Request(path=source.name))  # pyright: ignore[reportArgumentType]
    )
    assert isinstance(response, StreamingResponse)
    chunks: list[bytes] = []

    async def _drain() -> None:
        async for chunk in response.body_iterator:
            assert isinstance(chunk, (bytes, bytearray, memoryview))
            chunks.append(bytes(chunk))

    asyncio.run(_drain())
    assert b"".join(chunks) == payload


def test_live_stream_rejects_sealed_zlib_artifact(tmp_path: Path) -> None:
    source = tmp_path / "events.jsonl.zlib"
    source.write_bytes(zlib.compress(b'{"type":"result"}\n'))
    server._set_root_dir(tmp_path)

    response = asyncio.run(
        server.api_stream(_Request(path=source.name))  # pyright: ignore[reportArgumentType]
    )

    assert response.status_code == 400
    assert b"sealed" in response.body


def test_malformed_zlib_surfaces_endpoint_errors(tmp_path: Path) -> None:
    source = tmp_path / "broken.md.zlib"
    source.write_bytes(b"not a zlib stream")
    server._set_root_dir(tmp_path)

    file_response = asyncio.run(
        server.api_file(_Request(path=source.name))  # pyright: ignore[reportArgumentType]
    )
    file_body = _json_response(file_response)
    assert file_body["type"] == "error"
    assert "zlib" in file_body["error"].lower()

    render_response = asyncio.run(
        server.api_kpress_render(  # pyright: ignore[reportArgumentType]
            _Request(path=source.name, view="rendered")
        )
    )
    assert render_response.status_code == 400
    assert _json_response(render_response)["type"] == "kpress_render_error"

    raw_response = asyncio.run(
        server.raw_file(_Request(path=source.name))  # pyright: ignore[reportArgumentType]
    )
    assert raw_response.status_code == 400


def test_zlib_bomb_preview_and_render_stay_within_endpoint_limits(tmp_path: Path) -> None:
    payload = b"# Heading\n" + b"x" * (server._TEXT_PREVIEW_MAX_CHUNK_BYTES + 1)
    source = tmp_path / "bomb.md.zlib"
    source.write_bytes(zlib.compress(payload))
    server._set_root_dir(tmp_path)

    file_response = asyncio.run(
        server.api_file(_Request(path=source.name))  # pyright: ignore[reportArgumentType]
    )
    file_body = _json_response(file_response)
    assert file_body["type"] == "text"
    assert file_body["content_bytes"] == server._TEXT_PREVIEW_CHUNK_BYTES
    assert file_body["content_truncated"] is True

    render_response = asyncio.run(
        server.api_kpress_render(  # pyright: ignore[reportArgumentType]
            _Request(path=source.name, view="rendered")
        )
    )
    assert render_response.status_code == 413
    assert _json_response(render_response)["max_size"] == server._TEXT_PREVIEW_MAX_CHUNK_BYTES


def test_zlib_validation_scan_runs_off_the_request_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "notes.txt.zlib"
    source.write_bytes(zlib.compress(b"payload"))
    server._set_root_dir(tmp_path)
    request_thread = threading.get_ident()
    scan_threads: list[int] = []
    original = gz_io._zlib_uncompressed_size

    def _recording_size(path: Path) -> int:
        scan_threads.append(threading.get_ident())
        return original(path)

    monkeypatch.setattr(gz_io, "_zlib_uncompressed_size", _recording_size)
    response = asyncio.run(
        server.api_file(_Request(path=source.name))  # pyright: ignore[reportArgumentType]
    )

    assert _json_response(response)["type"] == "text"
    assert scan_threads
    assert all(thread_id != request_thread for thread_id in scan_threads)
