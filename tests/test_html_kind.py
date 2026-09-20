"""html kind: extension match, sniff-chosen default, capability-gated preview."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from metabrowser import server
from metabrowser.capabilities import (
    DEFAULT_CAPABILITIES,
    Capabilities,
    set_capabilities,
)
from metabrowser.inventory_engine.contract import canonical_inventory_path


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


def _view_ids(result: dict[str, Any]) -> list[str]:
    return [view["id"] for view in result["views"]]


def _default_id(result: dict[str, Any]) -> str:
    defaults = [view["id"] for view in result["views"] if view.get("default")]
    assert len(defaults) == 1
    return defaults[0]


def test_html_files_are_the_html_kind(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "page.html").write_text("<!doctype html><p>hi</p>\n", encoding="utf-8")
    (tmp_path / "legacy.htm").write_text("<html><p>old</p></html>\n", encoding="utf-8")

    page = _api_file("page.html")
    legacy = _api_file("legacy.htm")

    assert page["kind"] == "html"
    assert page["type"] == "text"
    assert _view_ids(page) == ["preview", "source"]
    assert _default_id(page) == "preview"
    assert legacy["kind"] == "html"
    assert _default_id(legacy) == "preview"

    views = {view["id"]: view for view in page["views"]}
    assert views["preview"]["container_class"] == "content-body metabrowser-html-host"
    assert views["preview"]["render_runtime"] == "client"
    assert views["source"]["printable"] is True
    assert views["source"]["print_profile"] == "source"


def test_fragment_defaults_to_source(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "card.html").write_text("<div class='card'>hello</div>\n", encoding="utf-8")
    result = _api_file("card.html")
    assert result["kind"] == "html"
    assert _view_ids(result) == ["preview", "source"]
    assert _default_id(result) == "source"


def test_active_content_off_drops_preview(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "page.html").write_text("<!doctype html><p>hi</p>\n", encoding="utf-8")
    set_capabilities(Capabilities(active_content=False, mutations=False))
    try:
        result = _api_file("page.html")
    finally:
        set_capabilities(DEFAULT_CAPABILITIES)

    assert result["kind"] == "html"
    assert _view_ids(result) == ["source"]
    assert _default_id(result) == "source"


def test_percent_name_stays_an_inventory_identity(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "100%.html").write_text("<!doctype html><p>pct</p>\n", encoding="utf-8")
    identity = canonical_inventory_path("100%.html")
    result = _api_file(identity)
    assert result["kind"] == "html"
    assert result["path"] == identity
    assert _default_id(result) == "preview"
