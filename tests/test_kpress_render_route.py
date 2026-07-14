"""KPress host adapter and route contract tests."""

from __future__ import annotations

import asyncio
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

from kpress import ASSET_MANIFEST_SCHEMA_VERSION, __version__

from metabrowser import kpress_adapter, server


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _request(
    *,
    query: dict[str, str] | None = None,
    path_params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    request = Mock(spec=["query_params", "headers", "path_params"])
    request.query_params = _FakeQuery(query or {})
    request.path_params = path_params or {}
    request.headers = headers or {}
    return request


def _json_body(response: Any) -> dict[str, Any]:
    return json.loads(response.body)


def _empty_asset_manifest() -> dict[str, object]:
    return {
        "schema_version": ASSET_MANIFEST_SCHEMA_VERSION,
        "assets": [],
        "import_map": {},
    }


def test_kpress_render_invalid_request_maps_to_400(tmp_path: Path, monkeypatch) -> None:
    """``server.py`` catches ``KPressInvalidRequestError`` and returns 400 with
    type ``kpress_render_error`` for malformed requests such as a bogus print
    profile.
    """

    server._set_root_dir(tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n")

    def _bad(**_kwargs: Any) -> dict[str, Any]:
        raise kpress_adapter.KPressInvalidRequestError("Unsupported KPress print profile 'bogus'")

    monkeypatch.setattr(kpress_adapter, "render_kpress_view", _bad)
    response = asyncio.run(
        server.api_kpress_render(_request(query={"path": "doc.md", "view": "rendered"}))
    )
    assert response.status_code == 400
    payload = _json_body(response)
    assert payload["type"] == "kpress_render_error"
    assert payload["error"] == "Invalid KPress render request"
    assert "Unsupported KPress print profile" in payload["detail"]
    assert payload["diagnostics"] == ["Unsupported KPress print profile 'bogus'"]


def test_kpress_render_rejects_path_traversal(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    response = asyncio.run(
        server.api_kpress_render(_request(query={"path": "../outside.md", "view": "rendered"}))
    )
    assert response.status_code == 404


def test_kpress_render_route_delegates_file_context(tmp_path: Path, monkeypatch) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "doc.md").write_text("---\ntitle: Test\n---\n# Heading\n")
    seen: dict[str, Any] = {}

    def _fake_render(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {
            "type": "kpress-rendered-document",
            "html": '<article class="kpress kpress-doc">ok</article>',
            "profile": "document",
            "printable": True,
            "assets": _empty_asset_manifest(),
            "diagnostics": [],
        }

    monkeypatch.setattr(kpress_adapter, "render_kpress_view", _fake_render)
    response = asyncio.run(
        server.api_kpress_render(_request(query={"path": "doc.md", "view": "rendered"}))
    )
    assert response.status_code == 200
    payload = _json_body(response)
    assert payload["html"] == '<article class="kpress kpress-doc">ok</article>'
    assert seen["source_path"] == "doc.md"
    assert seen["source_text"].endswith("# Heading\n")
    assert seen["kind"] == "markdown"
    assert seen["view"] == "rendered"
    assert seen["frontmatter"] == {"title": "Test"}
    assert seen["theme_mode"] == "system"


def test_kpress_render_route_uses_logical_size_for_gzip(tmp_path: Path, monkeypatch) -> None:
    server._set_root_dir(tmp_path)
    content = "# Heading\n" + ("Repeated content.\n" * 200)
    compressed = gzip.compress(content.encode())
    source = tmp_path / "doc.md.gz"
    source.write_bytes(compressed)
    seen: dict[str, Any] = {}

    def _fake_render(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {
            "type": "kpress-rendered-document",
            "html": '<article class="kpress kpress-doc">ok</article>',
            "profile": "document",
            "printable": True,
            "assets": _empty_asset_manifest(),
            "diagnostics": [],
        }

    monkeypatch.setattr(kpress_adapter, "render_kpress_view", _fake_render)
    response = asyncio.run(
        server.api_kpress_render(_request(query={"path": "doc.md.gz", "view": "rendered"}))
    )

    assert response.status_code == 200
    assert seen["source_text"] == content
    assert seen["size"] == len(content.encode())
    assert seen["size"] > source.stat().st_size


def test_kpress_static_asset_serving_and_304(tmp_path: Path) -> None:
    static_root = tmp_path / "static"
    static_root.mkdir()
    (static_root / "document.css").write_text(".kpress{color:black}\n")
    kpress_adapter.set_kpress_static_root_for_tests(static_root)
    try:
        first = asyncio.run(
            server.kpress_static_asset(_request(path_params={"path": "document.css"}))
        )
        assert first.status_code == 200
        assert first.body == b".kpress{color:black}\n"
        etag = first.headers["etag"]
        second = asyncio.run(
            server.kpress_static_asset(
                _request(path_params={"path": "document.css"}, headers={"if-none-match": etag})
            )
        )
        assert second.status_code == 304
    finally:
        kpress_adapter.set_kpress_static_root_for_tests(None)


def test_kpress_static_asset_serves_format_static_package_layout() -> None:
    kpress_adapter.set_kpress_static_root_for_tests(None)

    asset = kpress_adapter.get_kpress_static_asset("css/document.css")
    assert b".kpress" in asset.content
    assert asset.media_type == "text/css"


def test_kpress_versioned_static_asset_revalidates_via_no_cache() -> None:

    kpress_adapter.set_kpress_static_root_for_tests(None)
    response = asyncio.run(
        server.kpress_static_asset(
            _request(path_params={"path": f"v{__version__}/css/document.css"})
        )
    )
    assert response.status_code == 200
    # The /kpress-static/ URL is keyed by the KPress *version*, not by content,
    # so a same-version asset change isn't reflected in the URL. A long max-age
    # would then serve stale CSS/JS until the cache expired — and because these
    # assets are injected dynamically, even a hard reload doesn't bust them.
    # `no-cache` forces revalidation against the content-addressed ETag on every
    # load: a cheap 304 when unchanged, fresh bytes the moment an asset changes.
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["ETag"].startswith('"kp-')


def test_kpress_versioned_font_asset_is_immutable() -> None:

    kpress_adapter.set_kpress_static_root_for_tests(None)
    response = asyncio.run(
        server.kpress_static_asset(
            _request(
                path_params={"path": f"v{__version__}/fonts/source-sans-3-latin-wght-normal.woff2"}
            )
        )
    )
    assert response.status_code == 200
    # Fonts are the one asset class cached hard: large, stable per KPress
    # version, and not edited during local dev. An immutable cache means repeat
    # MetaBrowser visits pay zero font bytes and skip the revalidation round-trip
    # before first paint (the preloaded chrome face in the page <head>).
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_kpress_versioned_static_asset_revalidates_with_304() -> None:

    kpress_adapter.set_kpress_static_root_for_tests(None)
    path = f"v{__version__}/css/document.css"
    first = asyncio.run(server.kpress_static_asset(_request(path_params={"path": path})))
    etag = first.headers["ETag"]
    # A conditional reload carrying the matching ETag returns a cheap 304 — the
    # mechanism a normal browser reload uses now that the asset isn't immutable.
    second = asyncio.run(
        server.kpress_static_asset(
            _request(path_params={"path": path}, headers={"if-none-match": etag})
        )
    )
    assert second.status_code == 304


def test_kpress_static_asset_rejects_traversal(tmp_path: Path) -> None:
    kpress_adapter.set_kpress_static_root_for_tests(tmp_path)
    try:
        response = asyncio.run(
            server.kpress_static_asset(_request(path_params={"path": "../secret.css"}))
        )
        assert response.status_code == 404
    finally:
        kpress_adapter.set_kpress_static_root_for_tests(None)


def test_kpress_adapter_builds_runtime_request(monkeypatch) -> None:
    seen: list[Any] = []

    class FakeRequest:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            seen.append(self)

    def render_view(request: FakeRequest) -> dict[str, Any]:
        return {
            "type": "kpress-rendered-document",
            "html": "<article>rendered</article>",
            "profile": request.kwargs["profile"],
            "printable": True,
            "assets": {
                "schema_version": ASSET_MANIFEST_SCHEMA_VERSION,
                "assets": [
                    {
                        "id": "css/document.css",
                        "path": "css/document.css",
                        "public_url": "/kpress-static/css/document.css",
                        "entry_point": True,
                        "loading": "stylesheet",
                    }
                ],
                "import_map": {},
            },
            "diagnostics": [],
        }

    fake_runtime = SimpleNamespace(
        KPressRenderRequest=FakeRequest,
        render_view=render_view,
    )
    monkeypatch.setattr(kpress_adapter, "_kpress_runtime", fake_runtime)

    result = kpress_adapter.render_kpress_view(
        source_text="# One\n",
        source_path="doc.md",
        kind="markdown",
        view="rendered",
        ext=".md",
        mtime_hash="a",
        size=6,
        profile="document",
        frontmatter={"title": "One"},
    )

    assert result["html"] == "<article>rendered</article>"
    assert len(seen) == 1
    assert seen[0].kwargs["source_text"] == "# One\n"
    assert seen[0].kwargs["frontmatter"] == {"title": "One"}
    assert seen[0].kwargs["asset_url_prefix"] == "/kpress-static/"
    assert seen[0].kwargs["host"] == "metabrowser"
