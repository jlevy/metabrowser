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
import os
import zlib
from pathlib import Path
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

import metabrowser.builtin_plugins.structured as structured_sidekick
import metabrowser.builtin_plugins.structured.parser as structured_parser
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
    f = tmp_path / "bundle%20.json"
    f.write_text(json.dumps({"spec": "Demo/0.1", "n": 3, "items": ["a", "b"]}))
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "bundle%2520.json"})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["type"] == "structured"
    assert payload["path"] == "bundle%2520.json"
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


def test_parsed_endpoint_reports_the_stored_size_and_truncation_past_the_cap(
    tmp_path: Path, structured_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``size`` is the file's size on disk, and ``truncated`` says the cap was passed.

    ``size`` is not what was read or parsed: for a compressed file it is the
    compressed size, as ``/api/file`` reports it, and past the cap it is still the
    whole file's, not the cap. v0.11.0 answered it this way, and an answer taken from
    the bounded read gave 22 for the 40-byte ``small.json.gz`` and 1000 for a file
    over a 1000-byte cap.

    Past the cap the route answers ``truncated`` with nothing parsed, which is what
    sends the Tree view to Source. A compressed file is over the cap by what it
    decodes to, whatever it weighs on disk.
    """

    cap = 1000
    monkeypatch.setattr(structured_sidekick, "STRUCTURED_PARSE_MAX_BYTES", cap)
    monkeypatch.setattr(structured_parser, "STRUCTURED_PARSE_MAX_BYTES", cap)
    small = json.dumps({"a": 1, "b": [2, 3]}).encode()
    big = json.dumps({"x": "y" * (2 * cap)}).encode()
    (tmp_path / "small.json").write_bytes(small)
    (tmp_path / "small.json.gz").write_bytes(gzip.compress(small))
    (tmp_path / "big.json").write_bytes(big)
    (tmp_path / "big.json.gz").write_bytes(gzip.compress(big))
    on_disk = {name: (tmp_path / name).stat().st_size for name in sorted(os.listdir(tmp_path))}
    # The fixture separates the three quantities a wrong `size` could be taken from.
    assert on_disk["small.json.gz"] != len(small)
    assert on_disk["big.json"] > cap > on_disk["big.json.gz"]

    def parsed(name: str) -> dict[str, Any]:
        response = structured_app.get("/api/plugin/structured/parsed", params={"path": name})
        assert response.status_code == 200, response.text
        return response.json()

    for name in ("small.json", "small.json.gz"):
        body = parsed(name)
        assert body["size"] == on_disk[name], name
        assert body["truncated"] is False, name
        assert body["parsed"] == {"a": 1, "b": [2, 3]}, name
    for name in ("big.json", "big.json.gz"):
        body = parsed(name)
        assert body["size"] == on_disk[name], name
        assert body["truncated"] is True, name
        assert (body["parsed"], body["pretty_yaml"], body["parse_error"]) == (None, "", None), name
        assert (body["node_count"], body["max_depth"]) == (0, 0), name
    # A second request is answered from the payload cache, and says the same.
    assert [parsed(name)["size"] for name in on_disk] == list(on_disk.values())
