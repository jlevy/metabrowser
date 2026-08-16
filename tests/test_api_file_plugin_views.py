"""api/file emits plugin-supplied views in the response.

Locks in the integration between the manifest-driven classifier
(_classify_with_plugins) and the view-list merger (_views_for_kind):

* Plugin [[kind]] rules win over the legacy detector chain when their
  priority is higher.
* Plugin [[view]] entries merge into the response alongside built-in
  VIEW_REGISTRY entries.
* Same-id plugin views override the built-in entry.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from metabrowser import server


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _api_file(path: str) -> dict[str, Any]:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery({"path": path})
    request.headers = {}
    response = asyncio.run(server.api_file(request))
    return json.loads(bytes(response.body))


def test_plain_markdown_resolves_via_markdown_plugin(tmp_path: Path) -> None:
    """A .md file with no frontmatter resolves to 'markdown' via the
    builtin markdown plugin manifest.
    """
    server._set_root_dir(tmp_path)
    md = tmp_path / "plain.md"
    md.write_text("# heading\n\nbody only.\n")
    result = _api_file("plain.md")
    assert result["kind"] == "markdown"
    view_ids = [v["id"] for v in result["views"]]
    # rendered + source come from both the legacy VIEW_REGISTRY and the
    # plugin manifest — should appear once each.
    assert view_ids.count("rendered") == 1
    assert view_ids.count("source") == 1
    views = {v["id"]: v for v in result["views"]}
    assert views["rendered"]["printable"] is True
    assert views["rendered"]["print_profile"] == "document"
    assert views["rendered"]["render_runtime"] == "kpress"
    assert views["source"]["printable"] is True
    assert views["source"]["print_profile"] == "source"


def test_plain_text_source_view_is_printable(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    txt = tmp_path / "notes.txt"
    txt.write_text("plain text\n")
    result = _api_file("notes.txt")
    assert result["kind"] == "text"
    assert result["views"] == [
        {
            "id": "source",
            "label": "Source",
            "default": True,
            "container_class": "content-body metabrowser-source-host",
            "printable": True,
            "print_profile": "source",
            "render_runtime": "client",
        }
    ]


def test_unknown_jsonl_gets_default_log_view(tmp_path: Path) -> None:
    """Unknown JSONL still needs an initial visible tab in the browser."""
    server._set_root_dir(tmp_path)
    log = tmp_path / "agent.jsonl"
    log.write_text('{"type":"thread.started","thread_id":"abc"}\n')
    result = _api_file("agent.jsonl")
    assert result["kind"] == "unknown-jsonl"
    assert [v["id"] for v in result["views"] if v.get("default")] == ["log"]


def test_binary_files_get_a_default_bytes_view(tmp_path: Path) -> None:
    """A binary file must not fall through to the shell's no-preview branch.

    ``VIEW_REGISTRY["binary"]`` is empty, so the view arrives purely from the
    built-in binary plugin's manifest. While it was absent, ``views`` came back
    empty and ``static/app.js`` painted "No preview is available for this
    binary file".
    """
    server._set_root_dir(tmp_path)
    blob = tmp_path / "opaque.bin"
    blob.write_bytes(bytes(range(256)) * 4096)

    result = _api_file("opaque.bin")

    assert result["kind"] == "binary"
    assert result["views"] == [
        {
            "id": "bytes",
            "label": "Bytes",
            "default": True,
            "container_class": "content-body metabrowser-binary-host",
            "printable": False,
            "print_profile": "plain",
            "render_runtime": "client",
        }
    ]


def test_plugin_classification_runs_off_the_request_event_loop(tmp_path: Path, monkeypatch) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "data.json").write_text('{"schema":"example"}\n')
    request_thread = threading.get_ident()
    classifier_threads: list[int] = []

    def _classify(*_args: Any, **_kwargs: Any) -> str:
        classifier_threads.append(threading.get_ident())
        return "text"

    monkeypatch.setattr(server, "_classify_with_plugins", _classify)
    _api_file("data.json")
    assert classifier_threads
    assert classifier_threads[0] != request_thread


def test_small_binary_reaches_the_bytes_view(tmp_path: Path) -> None:
    """A small file with no text extension is classified by its content.

    Size used to decide this: anything under 512 KiB was read as text with
    ``errors="replace"``, so a 4 KB binary rendered as a field of U+FFFD and
    the Bytes view was unreachable for exactly the files it exists to show.
    """
    server._set_root_dir(tmp_path)
    blob = tmp_path / "small.bin"
    blob.write_bytes(bytes(range(256)) * 16)
    result = _api_file("small.bin")
    assert result["kind"] == "binary"
    assert [v["id"] for v in result["views"]] == ["bytes"]
    # The bytes themselves never travel through the text envelope.
    assert "content" not in result


def test_small_extensionless_text_still_renders_as_source(tmp_path: Path) -> None:
    """The other direction: content decides, so LICENSE and Makefile stay text."""
    server._set_root_dir(tmp_path)
    (tmp_path / "LICENSE").write_text("Permission is hereby granted...\n")
    result = _api_file("LICENSE")
    assert result["kind"] == "text"
    assert [v["id"] for v in result["views"]] == ["source"]


def test_large_extensionless_text_is_no_longer_forced_to_binary(tmp_path: Path) -> None:
    """Size used to cut the other way too, above the old 512 KiB threshold."""
    server._set_root_dir(tmp_path)
    big = tmp_path / "CHANGELOG"
    big.write_text("a line of ordinary text\n" * 40_000)
    assert big.stat().st_size > 512 * 1024
    result = _api_file("CHANGELOG")
    assert result["kind"] == "text"


def test_binary_content_under_a_text_extension_is_still_text(tmp_path: Path) -> None:
    """A known text extension is trusted without reading the file.

    This is what keeps the content check off the path for almost everything:
    it is consulted only once the extension has failed to answer.
    """
    server._set_root_dir(tmp_path)
    odd = tmp_path / "weird.txt"
    odd.write_bytes(b"\x00\x01\x02\x03" * 64)
    result = _api_file("weird.txt")
    assert result["kind"] == "text"
