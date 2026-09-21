"""Content-to-API boundary: sandboxed /raw and same-origin proof on /api.

These are transport-layer assertions. They do not require a browser, and they
are the properties that regress if a later raw_file branch or middleware path
forgets the headers or the origin check.
"""

from __future__ import annotations

import gzip
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from conftest import document_references
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route, request_response
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.capabilities import Capabilities, set_capabilities
from metabrowser.server import app

_RAW_CSP = "sandbox allow-scripts allow-popups allow-forms allow-downloads"
_RAW_CSP_NO_SCRIPTS = "sandbox allow-popups allow-forms allow-downloads"
_RAW_ROUTE_PATHS = frozenset({"/raw", "/raw/{path:path}"})


def _assert_raw_trust_headers(response: Any, *, active_content: bool = True) -> None:
    csp = response.headers["content-security-policy"]
    assert csp == (_RAW_CSP if active_content else _RAW_CSP_NO_SCRIPTS)
    assert "allow-same-origin" not in csp
    assert "frame-ancestors" not in csp
    assert response.headers["x-content-type-options"] == "nosniff"


def _csp_directive_names(response: Any) -> set[str]:
    """The directive names in the policy, so absence is checked by name."""

    csp = str(response.headers["content-security-policy"])
    return {part.split()[0].lower() for part in csp.split(";") if part.split()}


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


# ── Dangerous types on the wire ─────────────────────────────────────

# Each of these is script-capable, or sniffable into something that is,
# when a browser navigates to it at top level. The sandbox is what denies
# them the application origin, and the design says so explicitly: the
# header is unconditional precisely so that no type has to be enumerated.
#
# ``expected_content_types`` holds every value the route may legitimately
# send, because the media type comes from ``mimetypes.guess_type``, whose
# table is supplied by the platform. On this machine (macOS, reading
# ``/etc/apache2/mime.types``) the first value of each set is what was
# measured; the alternates are what Python's built-in table alone
# returns, which is what a container without a system table would send.
# That spread is the spec's own argument against a dangerous-type list,
# so it is recorded here rather than assumed away.
_DANGEROUS_ON_THE_WIRE = [
    pytest.param(
        "page.xhtml",
        b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml">'
        b"<body><script>alert(1)</script></body></html>\n",
        None,
        frozenset({"application/xhtml+xml", "application/octet-stream"}),
        id="xhtml",
    ),
    pytest.param(
        "data.xml",
        b'<?xml version="1.0"?><root><item/></root>\n',
        None,
        frozenset({"application/xml", "text/xml; charset=utf-8"}),
        id="xml",
    ),
    pytest.param(
        "doc.pdf",
        b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n",
        None,
        frozenset({"application/pdf"}),
        id="pdf",
    ),
    pytest.param(
        "app.js",
        b"alert(1)\n",
        None,
        frozenset({"text/javascript; charset=utf-8", "application/javascript"}),
        id="js",
    ),
    pytest.param(
        # No extension at all: nothing names a type, and the bytes are
        # markup. This is the case ``nosniff`` exists for.
        "README",
        b"<!doctype html><script>alert(1)</script>\n",
        None,
        frozenset({"application/octet-stream"}),
        id="no-extension",
    ),
    pytest.param(
        # The gzip passthrough. The logical name drives the type, so the
        # on-disk ``.gz`` ships verbatim as ``text/html``: a compressed
        # file is not an escape hatch from the sandbox.
        "archived.html.gz",
        gzip.compress(b"<!doctype html><script>alert(1)</script>\n", mtime=0),
        "gzip",
        frozenset({"text/html; charset=utf-8"}),
        id="html-gz-passthrough",
    ),
]


@pytest.mark.parametrize(
    ("name", "body", "expected_encoding", "expected_content_types"),
    _DANGEROUS_ON_THE_WIRE,
)
def test_dangerous_types_are_sandboxed_on_the_wire(
    tmp_path: Path,
    name: str,
    body: bytes,
    expected_encoding: str | None,
    expected_content_types: frozenset[str],
) -> None:
    """Every script-capable or sniffable type carries the same sandbox.

    What this proves: each of these reaches the wire with the exact
    sandbox CSP and ``nosniff``, at a media type derived from the file
    name and from nothing else. The second assertion is the one with
    teeth for the future — it fails if any branch of the route starts
    special-casing a type, whether to downgrade it to ``text/plain`` or
    to upgrade it. Together they say what the design claims: the
    containment does not depend on getting a type list right, because no
    type changes what is sent.

    What it cannot prove without a real browser: that a browser honours
    either header. A CSP ``sandbox`` directive only produces an opaque
    origin, and ``nosniff`` only suppresses sniffing, because the engine
    implements them. This is the server keeping its half of the contract.
    """

    _write_html_tree(tmp_path)
    (tmp_path / name).write_bytes(body)
    server._set_root_dir(tmp_path)
    with TestClient(app) as client:
        response = client.get(f"/raw/{name}", headers={"accept-encoding": "gzip"})

    assert response.status_code == 200
    _assert_raw_trust_headers(response)
    assert _csp_directive_names(response) == {"sandbox"}

    content_type = response.headers["content-type"]
    assert content_type in expected_content_types, content_type
    # The rule behind those values, asserted independently of the table:
    # the type is whatever the logical file name guesses, with the
    # octet-stream fallback, and no branch of the route overrides it.
    guessed, _ = mimetypes.guess_type(name)
    assert content_type.split(";")[0].strip() == (guessed or "application/octet-stream")
    assert response.headers.get("content-encoding") == expected_encoding


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
            # A user-initiated navigation: a typed URL, a bookmark, a
            # restored tab. It has no initiator document, so no page can
            # cause a browser to send it, and there is no origin to match.
            {"sec-fetch-site": "none"},
            {"sec-fetch-site": "None"},
        )
        rejected = (
            {"origin": "null"},
            {"origin": "NULL"},
            {"origin": "https://evil.example"},
            {"sec-fetch-site": "cross-site"},
            {"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
            {"origin": "null", "sec-fetch-site": "same-origin"},
            {"host": "localhost:8411", "origin": "http://localhost:9999"},
            # Accepting `none` must not widen to the other document-initiated
            # values, and must not survive an opaque origin alongside it.
            {"sec-fetch-site": "same-site"},
            {"origin": "null", "sec-fetch-site": "none"},
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
    _write_html_tree(tmp_path)
    server._set_root_dir(tmp_path)
    set_capabilities(Capabilities(active_content=False, mutations=False))
    with TestClient(app) as client:
        resp = client.get("/raw", params={"path": "page.html"})
    assert resp.status_code == 200
    csp = resp.headers["content-security-policy"]
    assert csp == _RAW_CSP_NO_SCRIPTS
    assert "allow-scripts" not in csp
    assert resp.headers["x-content-type-options"] == "nosniff"


# ── Frames load, which is what omitting frame-ancestors buys ────────


def _write_nested_frame_tree(root: Path) -> None:
    """A page whose frame is a sibling, whose frame is a level deeper."""

    site = root / "site"
    site.mkdir()
    deep = site / "deep"
    deep.mkdir()
    (site / "index.html").write_text(
        "<!doctype html><title>outer</title><iframe src='inner.html'></iframe>\n",
        encoding="utf-8",
    )
    (site / "inner.html").write_text(
        "<!doctype html><title>inner</title><iframe src='deep/leaf.html'></iframe>\n",
        encoding="utf-8",
    )
    (deep / "leaf.html").write_text(
        "<!doctype html><title>leaf</title><p>leaf</p>\n",
        encoding="utf-8",
    )
    (site / "frameset.html").write_text(
        "<!doctype html><frameset cols='50%,50%'>"
        "<frame src='inner.html'><frame src='deep/leaf.html'></frameset>\n",
        encoding="utf-8",
    )


def _load_frame_tree(client: TestClient, url: str) -> dict[str, Any]:
    """Fetch ``url`` and every nested frame a browser would load from it."""

    responses: dict[str, Any] = {}
    pending = [url]
    while pending:
        current = pending.pop(0)
        path = urlsplit(current).path
        if path in responses:
            continue
        response = client.get(current)
        responses[path] = response
        if response.status_code != 200:
            continue
        pending.extend(
            reference.resolved
            for reference in document_references(response.text, str(response.url))
            if reference.tag in {"frame", "iframe"}
        )
    return responses


def test_nested_frames_and_a_frameset_load_without_frame_ancestors(tmp_path: Path) -> None:
    """The regression test for the deliberately absent directive.

    ``frame-ancestors 'self'`` reads like free hardening and would break
    this feature. The directive matches every document in the ancestor
    chain, and inside a preview that chain begins with the sandboxed
    preview document, whose origin is opaque and can never equal
    ``'self'``. Framesets and saved pages with iframes — the legacy
    static HTML the preview exists to show — would stop loading.

    What this proves: the policy on each of these responses contains the
    ``sandbox`` directive and no other, so nothing in it constrains who
    may frame the document; and the frame targets a browser derives from
    each parent are served, at 200, with byte-identical trust headers.
    A hardening pass that adds ``frame-ancestors`` fails this test.

    What it cannot prove without a real browser: that the frames paint.
    No engine builds a browsing context here, so this is the header
    precondition for nesting rather than the nesting itself; the DOM
    session in tests/dom/html-preview-session.js covers the frame the
    application itself creates.
    """

    _write_html_tree(tmp_path)
    _write_nested_frame_tree(tmp_path)
    server._set_root_dir(tmp_path)
    with TestClient(app) as client:
        nested = _load_frame_tree(client, "/raw/site/index.html")
        frameset = _load_frame_tree(client, "/raw/site/frameset.html")
        flat = _load_frame_tree(client, "/raw/page.html")
        flat_frameset = _load_frame_tree(client, "/raw/frameset.html")

    # Each parent's relative frame reference resolved under /raw and was
    # served, two levels down for the nested case.
    assert set(nested) == {
        "/raw/site/index.html",
        "/raw/site/inner.html",
        "/raw/site/deep/leaf.html",
    }
    assert set(frameset) == {
        "/raw/site/frameset.html",
        "/raw/site/inner.html",
        "/raw/site/deep/leaf.html",
    }
    assert set(flat) == {"/raw/page.html", "/raw/frame.html"}
    assert set(flat_frameset) == {"/raw/frameset.html", "/raw/frame.html"}

    loaded = {**nested, **frameset, **flat, **flat_frameset}
    for path, response in loaded.items():
        assert response.status_code == 200, path
        _assert_raw_trust_headers(response)
        assert _csp_directive_names(response) == {"sandbox"}, path

    policies = {response.headers["content-security-policy"] for response in loaded.values()}
    assert policies == {_RAW_CSP}


# ── The sandbox is a property of the path, not of one return statement ──


@pytest.mark.parametrize("active_content", [True, False])
def test_every_raw_status_carries_the_sandbox_headers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    active_content: bool,
) -> None:
    """Statuses no ``raw_file`` return produces are sandboxed too.

    Starlette answers a malformed or unsatisfiable ``Range`` itself, the
    router answers a wrong method, and an unhandled exception becomes a
    500 outside every application middleware. None of those pass through
    a handler ``return``, so a wrapper applied there cannot reach them.
    """

    _write_html_tree(tmp_path)
    server._set_root_dir(tmp_path)
    set_capabilities(Capabilities(active_content=active_content, mutations=False))

    def _boom(_request: Request) -> Path | None:
        raise RuntimeError("forced handler failure")

    with TestClient(app, raise_server_exceptions=False) as client:
        ok = client.get("/raw/page.html")
        partial = client.get("/raw/page.html", headers={"range": "bytes=0-3"})
        head = client.head("/raw/page.html")
        missing = client.get("/raw/no-such.html")
        bad_range = client.get("/raw/page.html", headers={"range": "bytes=abc"})
        unsatisfiable = client.get("/raw/page.html", headers={"range": "bytes=9999-99999"})
        wrong_method = client.post("/raw/page.html")
        with monkeypatch.context() as patch:
            patch.setattr(server, "_raw_target_from_request", _boom)
            failure = client.get("/raw/page.html")

    assert ok.status_code == 200
    assert partial.status_code == 206
    assert head.status_code == 200
    assert missing.status_code == 404
    assert bad_range.status_code == 400
    assert unsatisfiable.status_code == 416
    assert wrong_method.status_code == 405
    assert failure.status_code == 500
    for response in (
        ok,
        partial,
        head,
        missing,
        bad_range,
        unsatisfiable,
        wrong_method,
        failure,
    ):
        _assert_raw_trust_headers(response, active_content=active_content)


def test_compressed_raw_branches_are_sandboxed_on_the_wire(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The identity-decompress branch and its two refusals, over HTTP.

    ``.html.gz`` served to a client that refuses gzip is a streaming
    response, and a malformed or over-limit stream is refused before any
    body is sent. All three are content on the application origin.
    """

    from metabrowser import gz_io

    _write_html_tree(tmp_path)
    (tmp_path / "malformed.html.gz").write_bytes(b"not a gzip stream")
    (tmp_path / "oversized.html.gz").write_bytes(gzip.compress(b"<p>payload</p>", mtime=0))
    server._set_root_dir(tmp_path)

    def _raise_limit(_path: Path) -> int:
        raise gz_io.ArtifactDecompressionLimitError("decompressed content exceeds test limit")

    with TestClient(app) as client:
        identity = client.get("/raw/page.html.gz", headers={"accept-encoding": "identity"})
        malformed = client.get("/raw/malformed.html.gz", headers={"accept-encoding": "identity"})
        with monkeypatch.context() as patch:
            patch.setattr(gz_io, "_gzip_uncompressed_size", _raise_limit)
            oversized = client.get(
                "/raw/oversized.html.gz", headers={"accept-encoding": "identity"}
            )

    assert identity.status_code == 200
    assert malformed.status_code == 400
    assert oversized.status_code == 413
    for response in (identity, malformed, oversized):
        _assert_raw_trust_headers(response)


def test_a_new_raw_return_path_cannot_miss_the_sandbox_headers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A handler that returns bytes from somewhere else is still sandboxed.

    This is the guard for the next source of raw bytes: a return added
    at the top of ``raw_file`` that serves an HTML document from a
    revision rather than the working tree. Nothing about it passes
    through the branches below it, so under per-return wrapping it would
    reach a browser on the application origin with no sandbox at all.
    """

    _write_html_tree(tmp_path)
    server._set_root_dir(tmp_path)

    async def _unwrapped(_request: Request) -> Response:
        return Response(b"<script>alert(1)</script>", media_type="text/html")

    patched = 0
    for route in app.routes:
        if isinstance(route, Route) and route.path in _RAW_ROUTE_PATHS:
            monkeypatch.setattr(route, "app", request_response(_unwrapped))
            patched += 1
    assert patched == len(_RAW_ROUTE_PATHS)

    with TestClient(app) as client:
        path_form = client.get("/raw/page.html")
        query_form = client.get("/raw", params={"path": "page.html"})

    assert path_form.status_code == 200
    assert query_form.status_code == 200
    assert path_form.headers["content-type"].startswith("text/html")
    _assert_raw_trust_headers(path_form)
    _assert_raw_trust_headers(query_form)


def test_paths_that_only_look_like_raw_are_untouched(tmp_path: Path) -> None:
    """``/rawfoo`` is a different route space and must not be rewritten."""

    _write_html_tree(tmp_path)
    server._set_root_dir(tmp_path)
    with TestClient(app) as client:
        lookalike = client.get("/rawfoo")
        sibling = client.get("/view/page.html")

    assert lookalike.status_code == 404
    assert "content-security-policy" not in lookalike.headers
    assert "content-security-policy" not in sibling.headers
