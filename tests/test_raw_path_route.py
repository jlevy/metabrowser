"""Path-shaped ``/raw/{path}`` shares one resolver and response path with ``/raw``.

The query form stays the public API (inventory identities). The path form is a
document URL so relative stylesheets and sibling links resolve under ``/raw/``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.inventory_engine.contract import canonical_inventory_path
from metabrowser.server import app

_RAW_CSP = "sandbox allow-scripts allow-popups allow-forms allow-downloads"


def _assert_raw_trust_headers(response: Any) -> None:
    csp = response.headers["content-security-policy"]
    assert csp == _RAW_CSP
    assert "allow-same-origin" not in csp
    assert "frame-ancestors" not in csp
    assert response.headers["x-content-type-options"] == "nosniff"


def _write_raw_tree(root: Path) -> None:
    docs = root / "docs"
    docs.mkdir()
    (docs / "page.html").write_text(
        "<!doctype html><link rel='stylesheet' href='style.css'>\n",
        encoding="utf-8",
    )
    (docs / "style.css").write_text("body { color: black; }\n", encoding="utf-8")
    (docs / "a b.html").write_text("<!doctype html><p>space</p>\n", encoding="utf-8")
    (docs / "100%.html").write_text("<!doctype html><p>percent</p>\n", encoding="utf-8")


def test_path_form_matches_query_form_and_keeps_trust_headers(tmp_path: Path) -> None:
    _write_raw_tree(tmp_path)
    server._set_root_dir(tmp_path)
    with TestClient(app) as client:
        query = client.get("/raw", params={"path": "docs/page.html"})
        path = client.get("/raw/docs/page.html")
        style = client.get("/raw/docs/style.css")

    assert query.status_code == 200
    assert path.status_code == 200
    assert style.status_code == 200
    assert path.content == query.content
    assert path.headers["content-type"] == query.headers["content-type"]
    _assert_raw_trust_headers(path)
    _assert_raw_trust_headers(style)
    assert b"style.css" in path.content


def test_percent_encoding_is_equivalent_across_route_shapes(tmp_path: Path) -> None:
    _write_raw_tree(tmp_path)
    server._set_root_dir(tmp_path)
    spaced = canonical_inventory_path("docs/a b.html")
    percent = canonical_inventory_path("docs/100%.html")
    with TestClient(app) as client:
        space_path = client.get("/raw/docs/a%20b.html")
        space_query = client.get("/raw", params={"path": spaced})
        percent_path = client.get("/raw/docs/100%25.html")
        percent_query = client.get("/raw", params={"path": percent})

    assert space_path.status_code == 200
    assert space_query.status_code == 200
    assert space_path.content == space_query.content
    assert percent_path.status_code == 200
    assert percent_query.status_code == 200
    assert percent_path.content == percent_query.content


def test_both_raw_shapes_reject_traversal_and_escaping_symlinks(tmp_path: Path) -> None:
    served = tmp_path / "served"
    served.mkdir()
    (served / "ok.html").write_text("<!doctype html><p>ok</p>\n", encoding="utf-8")
    outside = tmp_path / "secret.html"
    outside.write_text("secret\n", encoding="utf-8")
    (served / "leak.html").symlink_to(outside)
    server._set_root_dir(served)
    with TestClient(app) as client:
        encoded_traversal = client.get("/raw/%2e%2e/secret.html")
        traversal_query = client.get("/raw", params={"path": "../secret.html"})
        symlink_path = client.get("/raw/leak.html")
        symlink_query = client.get("/raw", params={"path": "leak.html"})
        ok = client.get("/raw/ok.html")

    # httpx collapses a literal `..` segment before the request leaves the
    # client, so the handler-level path is the one that still contains it.
    handler_traversal = asyncio.run(
        server.raw_file(
            SimpleNamespace(  # pyright: ignore[reportArgumentType]
                path_params={"path": "../secret.html"},
                query_params={},
            )
        )
    )

    assert encoded_traversal.status_code == 404
    assert traversal_query.status_code == 404
    assert handler_traversal.status_code == 404
    assert symlink_path.status_code == 404
    assert symlink_query.status_code == 404
    assert ok.status_code == 200
    _assert_raw_trust_headers(encoded_traversal)
    _assert_raw_trust_headers(handler_traversal)
    _assert_raw_trust_headers(symlink_path)
    assert b"secret" not in encoded_traversal.content
    assert b"secret" not in handler_traversal.body
    assert b"secret" not in symlink_path.content


def test_path_form_stays_reachable_from_opaque_origin(tmp_path: Path) -> None:
    _write_raw_tree(tmp_path)
    server._set_root_dir(tmp_path)
    with TestClient(app) as client:
        response = client.get("/raw/docs/page.html", headers={"origin": "null"})
    assert response.status_code == 200
    _assert_raw_trust_headers(response)
