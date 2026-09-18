"""Content-to-API boundary: sandboxed /raw and same-origin proof on /api.

These are transport-layer assertions. They do not require a browser, and they
are the properties that regress if a later raw_file branch or middleware path
forgets the headers or the origin check.
"""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.server import app

_RAW_CSP = "sandbox allow-scripts allow-popups allow-forms allow-downloads"


def _assert_raw_trust_headers(response: Any) -> None:
    csp = response.headers["content-security-policy"]
    assert csp == _RAW_CSP
    assert "allow-same-origin" not in csp
    assert "frame-ancestors" not in csp
    assert response.headers["x-content-type-options"] == "nosniff"


def _write_html_tree(root: Path) -> None:
    (root / "page.html").write_text(
        "<!doctype html><iframe src='frame.html'></iframe>\n",
        encoding="utf-8",
    )
    (root / "frame.html").write_text(
        "<!doctype html><p>inner</p>\n",
        encoding="utf-8",
    )
    (root / "frameset.html").write_text(
        "<!doctype html><frameset cols='50%,50%'><frame src='frame.html'></frameset>\n",
        encoding="utf-8",
    )
    (root / "icon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>x</text></svg>\n',
        encoding="utf-8",
    )
    (root / "doc.md").write_text("# Doc\n", encoding="utf-8")
    gz = root / "page.html.gz"
    gz.write_bytes(gzip.compress((root / "page.html").read_bytes(), mtime=0))


def test_raw_html_svg_and_gzip_share_the_sandbox_headers(tmp_path: Path) -> None:
    _write_html_tree(tmp_path)
    server._set_root_dir(tmp_path)
    with TestClient(app) as client:
        html = client.get("/raw", params={"path": "page.html"})
        svg = client.get("/raw", params={"path": "icon.svg"})
        gz = client.get(
            "/raw",
            params={"path": "page.html.gz"},
            headers={"accept-encoding": "gzip"},
        )
        inner = client.get("/raw", params={"path": "frame.html"})
        frameset = client.get("/raw", params={"path": "frameset.html"})

    assert html.status_code == 200
    assert svg.status_code == 200
    assert gz.status_code == 200
    assert inner.status_code == 200
    assert frameset.status_code == 200
    for response in (html, svg, gz, inner, frameset):
        _assert_raw_trust_headers(response)
    assert "svg" in (svg.headers.get("content-type") or "")
    assert gz.headers.get("content-encoding") == "gzip"


def test_raw_stays_reachable_from_opaque_and_foreign_origins(tmp_path: Path) -> None:
    """Content surfaces must remain loadable as subresources."""

    _write_html_tree(tmp_path)
    server._set_root_dir(tmp_path)
    with TestClient(app) as client:
        opaque = client.get("/raw", params={"path": "page.html"}, headers={"origin": "null"})
        foreign = client.get(
            "/raw",
            params={"path": "icon.svg"},
            headers={"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
        )

    assert opaque.status_code == 200
    assert foreign.status_code == 200
    _assert_raw_trust_headers(opaque)
    _assert_raw_trust_headers(foreign)


def test_api_same_origin_proof_matrix() -> None:
    with TestClient(app) as client:
        accepted = (
            {},
            {"origin": "http://testserver"},
            {"sec-fetch-site": "same-origin"},
            {"origin": "http://testserver", "sec-fetch-site": "same-origin"},
            {"host": "localhost:8411", "origin": "http://localhost:8411"},
        )
        rejected = (
            {"origin": "null"},
            {"origin": "NULL"},
            {"origin": "https://evil.example"},
            {"sec-fetch-site": "cross-site"},
            {"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
            {"origin": "null", "sec-fetch-site": "same-origin"},
            {"host": "localhost:8411", "origin": "http://localhost:9999"},
        )
        for headers in accepted:
            resp = client.get("/api/capabilities", headers=headers)
            assert resp.status_code == 200, headers
        for headers in rejected:
            resp = client.get("/api/capabilities", headers=headers)
            assert resp.status_code == 403, headers
            assert "same-origin" in resp.text.lower() or "origin" in resp.text.lower()


def test_form_post_export_from_opaque_origin_is_rejected_before_write(
    tmp_path: Path,
) -> None:
    _write_html_tree(tmp_path)
    server._set_root_dir(tmp_path)
    destination = tmp_path / "out.html"
    with TestClient(app) as client:
        resp = client.post(
            "/api/kpress/export",
            data={"path": "doc.md", "destination": "out.html"},
            headers={"origin": "null"},
        )
    assert resp.status_code == 403
    assert not destination.exists()


def test_state_changing_api_requires_json_content_type(tmp_path: Path) -> None:
    _write_html_tree(tmp_path)
    server._set_root_dir(tmp_path)
    form_dest = tmp_path / "form.html"
    plain_dest = tmp_path / "plain.html"
    body = b'{"path":"doc.md","destination":"plain.html"}'
    with TestClient(app) as client:
        form = client.post(
            "/api/kpress/export",
            data={"path": "doc.md", "destination": "form.html"},
        )
        plain = client.post(
            "/api/kpress/export",
            content=body,
            headers={"content-type": "text/plain"},
        )
        json_ok = client.post(
            "/api/kpress/export",
            json={"path": "doc.md", "destination": "json.html"},
        )
    assert form.status_code == 415
    assert plain.status_code == 415
    assert json_ok.status_code not in {403, 415}
    assert not form_dest.exists()
    assert not plain_dest.exists()


def test_raw_drops_allow_scripts_when_active_content_is_off(tmp_path: Path) -> None:
    from metabrowser.capabilities import Capabilities, set_capabilities

    _write_html_tree(tmp_path)
    server._set_root_dir(tmp_path)
    set_capabilities(Capabilities(active_content=False, mutations=False))
    with TestClient(app) as client:
        resp = client.get("/raw", params={"path": "page.html"})
    assert resp.status_code == 200
    csp = resp.headers["content-security-policy"]
    assert csp == "sandbox allow-popups allow-forms allow-downloads"
    assert "allow-scripts" not in csp
    assert resp.headers["x-content-type-options"] == "nosniff"
