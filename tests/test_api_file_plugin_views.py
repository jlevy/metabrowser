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
