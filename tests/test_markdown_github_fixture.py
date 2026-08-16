"""GitHub-style repository fixture coverage for Markdown navigation."""

from __future__ import annotations

import asyncio
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from starlette.testclient import TestClient

from metabrowser import server

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "github-markdown-repo"


class _Targets(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        href = values.get("href")
        source = values.get("src")
        if tag == "a" and href:
            self.hrefs.append(href)
        if tag in {"audio", "img", "source", "video"} and source:
            self.sources.append(source)


def _request(path: str) -> Any:
    request = Mock(spec=["query_params", "headers", "path_params"])
    request.query_params = {"path": path, "view": "rendered"}
    request.path_params = {}
    request.headers = {}
    return request


def test_github_fixture_renders_authored_link_conventions() -> None:
    server._set_root_dir(FIXTURE_ROOT)
    response = asyncio.run(server.api_kpress_render(_request("README.md")))

    assert response.status_code == 200
    parser = _Targets()
    parser.feed(json.loads(response.body)["html"])
    assert parser.hrefs == [
        "docs/guide.md",
        "docs/guide.md#overview",
        "docs/raw.md",
        "/CONTRIBUTING.md",
        "docs/",
        "docs/guide.md?plain=1#installation",
        "docs/missing.md",
        "docs/space%20name.md",
        "docs/%E9%9B%AA.md",
        "docs/100%25.md",
        "docs/what%3F%23.md",
    ]
    assert parser.sources == ["assets/map.svg"]


def test_github_fixture_contains_raw_html_media_and_exact_targets() -> None:
    source = (FIXTURE_ROOT / "README.md").read_text()

    assert '<a href="docs/raw.md">' in source
    assert '<audio src="assets/sample.mp3" controls>' in source
    for target in (
        "CONTRIBUTING.md",
        "assets/map.svg",
        "assets/sample.mp3",
        "docs/guide.md",
        "docs/raw.md",
        "docs/space name.md",
        "docs/雪.md",
        "docs/100%.md",
        "docs/what?#.md",
    ):
        assert (FIXTURE_ROOT / target).is_file(), target
    assert not (FIXTURE_ROOT / "docs/missing.md").exists()


def test_github_fixture_canonical_urls_reload_and_resources_are_safe() -> None:
    server._set_root_dir(FIXTURE_ROOT)
    try:
        client = TestClient(server.app)
        for route in (
            "/view/README.md",
            "/view/docs/",
            "/view/docs/guide.md?plain=1#installation",
            "/view/docs/space%20name.md",
            "/view/docs/%E9%9B%AA.md",
            "/view/docs/100%25.md",
            "/view/docs/what%3F%23.md",
            "/view/docs/missing.md",
        ):
            response = client.get(route)
            assert response.status_code == 200, route
            assert "<title>Metabrowser</title>" in response.text

        resource = client.get("/raw?path=assets%2Fmap.svg")
        assert resource.status_code == 200
        assert resource.headers["content-type"].startswith("image/svg+xml")
        assert b"Repository map fixture" in resource.content
    finally:
        server._set_root_dir(Path())
