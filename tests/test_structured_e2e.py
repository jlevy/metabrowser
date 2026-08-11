"""End-to-end test for the structured plugin's sidekick endpoint.

Boots a Starlette TestClient with the built-in structured plugin
mounted, drops a small JSON file under ROOT_DIR, and hits
``GET /api/plugin/structured/parsed?path=<rel>``. Asserts the
response envelope shape + the parsed payload + the canonical YAML
re-serialization.
"""

from __future__ import annotations

import gzip
import json
import zlib
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import paths_safe
from metabrowser import server as proc_browser  # noqa: F401  # pyright: ignore[reportUnusedImport]
from metabrowser.plugin_loader.discovery import _try_load_plugin
from metabrowser.plugin_loader.static_assets import build_plugin_routes

_STRUCTURED_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "metabrowser" / "builtin_plugins" / "structured"
)


@pytest.fixture
def structured_app(tmp_path: Path) -> TestClient:
    paths_safe._set_root_dir(tmp_path)
    plugin = _try_load_plugin(_STRUCTURED_DIR, source="builtin:test")
    assert plugin is not None and not isinstance(plugin, str), plugin
    routes = build_plugin_routes([plugin])
    app = Starlette(routes=routes)
    return TestClient(app)


def test_parsed_endpoint_round_trips_json(tmp_path: Path, structured_app: TestClient) -> None:
    f = tmp_path / "bundle.json"
    f.write_text(json.dumps({"spec": "Demo/0.1", "n": 3, "items": ["a", "b"]}))
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "bundle.json"})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["type"] == "structured"
    assert payload["ext"] == ".json"
    assert payload["parse_error"] is None
    assert payload["truncated"] is False
    assert payload["comments_supported"] is False
    assert payload["parsed"] == {"spec": "Demo/0.1", "n": 3, "items": ["a", "b"]}
    assert "pretty_yaml" in payload
    assert payload["pretty_yaml"].strip() != ""
    assert payload["node_count"] >= 3
    assert payload["mtime_hash"]


def test_parsed_endpoint_surfaces_parse_error(tmp_path: Path, structured_app: TestClient) -> None:
    f = tmp_path / "bad.json"
    f.write_text("{not valid json")
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "bad.json"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["parse_error"] is not None
    assert payload["parsed"] is None


def test_parsed_endpoint_404_for_unknown_path(structured_app: TestClient) -> None:
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "nope.json"})
    assert resp.status_code == 404


def test_parsed_endpoint_400_for_wrong_ext(tmp_path: Path, structured_app: TestClient) -> None:
    f = tmp_path / "note.md"
    f.write_text("# hello")
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "note.md"})
    assert resp.status_code == 400


def test_parsed_endpoint_etag_header(tmp_path: Path, structured_app: TestClient) -> None:
    f = tmp_path / "x.yaml"
    f.write_text("a: 1\nb: 2\n")
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "x.yaml"})
    assert resp.status_code == 200
    assert resp.headers["ETag"]


def test_parsed_endpoint_handles_gzipped_json(tmp_path: Path, structured_app: TestClient) -> None:
    """``foo.json.gz`` should classify on its logical extension (``.json``)
    and decompress transparently. Caught a real bug pre-test where
    target.suffix.lower() == ".gz" 400'd otherwise-valid files."""

    f = tmp_path / "bundle.json.gz"
    payload = json.dumps({"compressed": True, "n": 7}).encode()
    with gzip.open(f, "wb") as fh:
        fh.write(payload)
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "bundle.json.gz"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ext"] == ".json"
    assert body["parsed"] == {"compressed": True, "n": 7}
    assert body["parse_error"] is None


def test_parsed_endpoint_handles_zlib_json(tmp_path: Path, structured_app: TestClient) -> None:
    source = tmp_path / "bundle.json.zlib"
    source.write_bytes(zlib.compress(json.dumps({"compressed": "zlib", "n": 8}).encode()))

    response = structured_app.get("/api/plugin/structured/parsed", params={"path": source.name})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ext"] == ".json"
    assert body["parsed"] == {"compressed": "zlib", "n": 8}
    assert body["parse_error"] is None
