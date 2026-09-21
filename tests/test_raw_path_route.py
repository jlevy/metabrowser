"""Path-shaped ``/raw/{path}`` shares one resolver and response path with ``/raw``.

The query form stays the public API (inventory identities). The path form is a
document URL so relative stylesheets and sibling links resolve under ``/raw/``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urljoin, urlsplit

from conftest import document_references
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.inventory_engine.contract import canonical_inventory_path
from metabrowser.server import app

_RAW_CSP = "sandbox allow-scripts allow-popups allow-forms allow-downloads"

# A real one-pixel RGBA PNG (signature, IHDR, IDAT, IEND, CRCs valid), so the
# subdirectory subresource is a genuine binary asset rather than text wearing
# a ``.png`` name.
_ONE_PIXEL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _assert_raw_trust_headers(response: Any) -> None:
    csp = response.headers["content-security-policy"]
    assert csp == _RAW_CSP
    assert "allow-same-origin" not in csp
    assert "frame-ancestors" not in csp
    assert response.headers["x-content-type-options"] == "nosniff"


def _write_raw_tree(root: Path) -> None:
    """A small static site: a page, a sibling stylesheet and link, a nested image."""

    docs = root / "docs"
    docs.mkdir()
    (docs / "page.html").write_text(
        "<!doctype html>"
        "<link rel='stylesheet' href='style.css'>"
        "<img src='assets/logo.png' alt='logo'>"
        "<a href='about.html'>about</a>\n",
        encoding="utf-8",
    )
    (docs / "style.css").write_text("body { color: black; }\n", encoding="utf-8")
    (docs / "about.html").write_text("<!doctype html><p>about</p>\n", encoding="utf-8")
    assets = docs / "assets"
    assets.mkdir()
    (assets / "logo.png").write_bytes(_ONE_PIXEL_PNG)
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


def test_relative_references_resolve_to_the_expected_raw_paths(tmp_path: Path) -> None:
    """A sibling stylesheet, a subdirectory image, and a sibling link.

    What this proves, on the server side: the URLs a browser derives from
    the returned document — RFC 3986 resolution of each relative
    reference against the document's own ``/raw/docs/page.html`` address —
    are the raw paths of the intended files, every one of those files is
    served back at its own media type, and each carries the sandbox CSP
    and ``nosniff`` in its own right rather than only as part of the page
    that referenced it.

    What it cannot prove without a real browser: that a browser issues
    those requests, applies the stylesheet, decodes the image, or paints
    anything. No layout or fetch engine runs here, so the spec's
    "renders as it does when opened directly in a browser" fidelity claim
    is out of reach; this covers the addressing half of it, which is the
    half the route shape decides.
    """

    _write_raw_tree(tmp_path)
    server._set_root_dir(tmp_path)
    with TestClient(app) as client:
        page = client.get("/raw/docs/page.html")
        assert page.status_code == 200
        _assert_raw_trust_headers(page)

        references = {
            reference.value: reference
            for reference in document_references(page.text, str(page.url))
        }
        assert set(references) == {"style.css", "assets/logo.png", "about.html"}

        expected_paths = {
            "style.css": "/raw/docs/style.css",
            "assets/logo.png": "/raw/docs/assets/logo.png",
            "about.html": "/raw/docs/about.html",
        }
        expected_types = {
            "style.css": "text/css; charset=utf-8",
            "assets/logo.png": "image/png",
            "about.html": "text/html; charset=utf-8",
        }
        for value, reference in references.items():
            resolved = urlsplit(reference.resolved)
            assert resolved.path == expected_paths[value], reference
            subresource = client.get(reference.resolved)
            assert subresource.status_code == 200, reference
            assert subresource.headers["content-type"] == expected_types[value], reference
            _assert_raw_trust_headers(subresource)

        assert client.get("/raw/docs/assets/logo.png").content == _ONE_PIXEL_PNG

    # Why the path form exists at all: the same document served from the
    # query form has ``/raw`` as its base, so a browser would resolve the
    # sibling stylesheet to ``/style.css`` and leave the route entirely.
    # That is URL arithmetic rather than server behavior, and it is the
    # regression this route shape prevents.
    assert urlsplit(urljoin("http://testserver/raw?path=docs/page.html", "style.css")).path == (
        "/style.css"
    )


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
    # Only the refusal is asserted here: the trust headers belong to the
    # ``/raw`` transport layer, not to a handler return value, and they are
    # asserted on the wire in tests/test_content_trust.py.
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
    _assert_raw_trust_headers(symlink_path)
    assert b"secret" not in encoded_traversal.content
    assert b"secret" not in handler_traversal.body
    assert b"secret" not in symlink_path.content


def test_both_raw_shapes_reject_an_embedded_nul(tmp_path: Path) -> None:
    """``%00`` in either shape is a missing file, not a server error."""

    _write_raw_tree(tmp_path)
    server._set_root_dir(tmp_path)
    with TestClient(app) as client:
        path_form = client.get("/raw/a%00b")
        nested_path_form = client.get("/raw/docs/page.html%00.png")
        query_form = client.get("/raw", params={"path": "a\x00b"})

    assert path_form.status_code == 404
    assert nested_path_form.status_code == 404
    assert query_form.status_code == 404
    _assert_raw_trust_headers(path_form)
    _assert_raw_trust_headers(query_form)


def test_path_form_stays_reachable_from_opaque_origin(tmp_path: Path) -> None:
    _write_raw_tree(tmp_path)
    server._set_root_dir(tmp_path)
    with TestClient(app) as client:
        response = client.get("/raw/docs/page.html", headers={"origin": "null"})
    assert response.status_code == 200
    _assert_raw_trust_headers(response)
