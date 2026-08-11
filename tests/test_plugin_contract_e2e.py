"""End-to-end test of the metabrowser plugin contract.

Loads two fixture plugins (one pure JS, one with a Python sidekick),
spins up a Starlette TestClient against a server with those plugins
mounted, and asserts:

* /plugin-static/<plugin>/<resource> serves files with correct ETag
  + 304 round-trip;
* /plugin-static/ rejects path-traversal;
* /api/plugin/<plugin>/<route> dispatches to the configured sidekick;
* discovery handles a fixture dir with no manifest gracefully.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser.plugin_loader.discovery import _try_load_plugin
from metabrowser.plugin_loader.static_assets import build_plugin_routes

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _ensure_fixture_importable() -> None:  # pyright: ignore[reportUnusedFunction]
    """Make tests/fixtures/ importable so the sidekick handler resolves."""
    if str(_FIXTURES) not in sys.path:
        sys.path.insert(0, str(_FIXTURES))


@pytest.fixture
def plugin_app() -> TestClient:
    """A Starlette app with both fixture plugins mounted via build_plugin_routes."""
    pure = _try_load_plugin(_FIXTURES / "sample_plugin", source="local:test")
    side = _try_load_plugin(_FIXTURES / "sidekick_sample", source="entry-point:test")
    assert pure is not None and not isinstance(pure, str), pure
    assert side is not None and not isinstance(side, str), side
    routes = build_plugin_routes([pure, side])
    app = Starlette(routes=routes)
    return TestClient(app)


# ── /plugin-static ─────────────────────────────────────────


def test_plugin_static_serves_index_js(plugin_app: TestClient) -> None:
    resp = plugin_app.get("/plugin-static/sample/index.js")
    assert resp.status_code == 200
    assert "registerView" in resp.text
    assert resp.headers["ETag"]


def test_plugin_static_etag_304_on_match(plugin_app: TestClient) -> None:
    first = plugin_app.get("/plugin-static/sample/index.js")
    etag = first.headers["ETag"]
    second = plugin_app.get("/plugin-static/sample/index.js", headers={"If-None-Match": etag})
    assert second.status_code == 304


def test_plugin_static_serves_styles_css(plugin_app: TestClient) -> None:
    resp = plugin_app.get("/plugin-static/sample/styles.css")
    assert resp.status_code == 200
    assert ".mb-plugin-sample" in resp.text


def test_plugin_static_rejects_traversal(plugin_app: TestClient) -> None:
    resp = plugin_app.get("/plugin-static/sample/../../../etc/passwd")
    assert resp.status_code == 404


def test_plugin_static_404_for_unknown_plugin(plugin_app: TestClient) -> None:
    resp = plugin_app.get("/plugin-static/does-not-exist/anything.js")
    assert resp.status_code == 404


def test_plugin_static_404_for_missing_file(plugin_app: TestClient) -> None:
    resp = plugin_app.get("/plugin-static/sample/no-such-file.js")
    assert resp.status_code == 404


# ── /api/plugin/<plugin>/<route> ───────────────────────────


def test_data_hook_dispatches_to_sidekick(plugin_app: TestClient) -> None:
    resp = plugin_app.get("/api/plugin/sidekick-sample/echo", params={"msg": "hello", "path": "p"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload == {"echo": "hello", "path": "p"}


def test_data_hook_404_for_pure_js_plugin(plugin_app: TestClient) -> None:
    # The pure-JS plugin doesn't declare any data hooks — no route is mounted.
    resp = plugin_app.get("/api/plugin/sample/anything")
    assert resp.status_code == 404


def test_local_plugin_data_hooks_are_not_mounted() -> None:
    local = _try_load_plugin(_FIXTURES / "sidekick_sample", source="local:test")
    assert local is not None and not isinstance(local, str), local
    app = Starlette(routes=build_plugin_routes([local]))

    with TestClient(app) as client:
        response = client.get("/api/plugin/sidekick-sample/echo")

    assert response.status_code == 404


def test_data_hook_exception_returns_degraded_warning(plugin_app: TestClient) -> None:
    resp = plugin_app.get("/api/plugin/sidekick-sample/explode")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["type"] == "plugin_error"
    assert payload["plugin"] == "sidekick-sample"
    assert payload["route"] == "explode"
    assert "RuntimeError: boom" in payload["detail"]
    assert "server 500" in payload["warning"]


def test_data_hook_explicit_500_returns_degraded_warning(plugin_app: TestClient) -> None:
    resp = plugin_app.get("/api/plugin/sidekick-sample/explicit-500")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["type"] == "plugin_error"
    assert payload["route"] == "explicit-500"
    assert payload["detail"] == "explicit boom"
    assert "server 500" in payload["warning"]
