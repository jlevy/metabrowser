"""Repository Markdown and the page under the untrusted profile.

A served mirror always runs with active content off, and a fork's author controls its
README. These tests serve a pin whose README carries every payload of the hostile corpus
and check what the page is sent: the Markdown route's HTML reduced to the inert
allowlist with no KPress script in its assets, and the shell's Content-Security-Policy,
under which only this server's scripts run. A trusted folder keeps its rich rendering
and no policy.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.capabilities import (
    DEFAULT_CAPABILITIES,
    Capabilities,
    set_capabilities,
    untrusted_shell_csp,
)
from metabrowser.server import app
from tests.git_pin_harness import fast_import_store, pinned_client
from tests.github_pull_fixture import allowlist_violations
from tests.test_inert_html import HOSTILE_README

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    *sorted((REPO_ROOT / "src/metabrowser/static").glob("*.js")),
    *sorted((REPO_ROOT / "src/metabrowser/builtin_plugins").glob("*/*.js")),
]
README_WIRE = "g1-UkVBRE1FLm1k"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")


@pytest.fixture
def untrusted() -> Iterator[None]:
    set_capabilities(Capabilities(active_content=False, mutations=False))
    try:
        yield
    finally:
        set_capabilities(DEFAULT_CAPABILITIES)


def test_a_mirrored_readme_renders_inert(tmp_path: Path, untrusted: None) -> None:
    store, commit = fast_import_store(
        tmp_path,
        {b"README.md": HOSTILE_README.encode(), b"docs/diagram.png": b"\x89PNG\r\n"},
    )

    async def fetch() -> Any:
        async with pinned_client(store, commit) as (client, _subject):
            return await client.get(
                "/api/kpress/render", params={"path": README_WIRE, "view": "document"}
            )

    answer = asyncio.run(fetch())
    assert answer.status_code == 200
    rendered = answer.json()
    assert rendered["inert"] is True
    html = rendered["html"]
    assert allowlist_violations(html, images=True) == []
    assert '<img src="docs/diagram.png" alt="diagram">' in html
    for gone in ("url(", "javascript:", "dQw4w9WgXcQ", "modal-overlay", "evil.css"):
        assert gone not in html, gone
    # KPress adds script entry points for what a document contains; none are sent.
    loads = {asset["loading"] for asset in rendered["assets"]["assets"]}
    assert loads <= {"stylesheet", "resource"} and "stylesheet" in loads
    assert "import_map" not in rendered["assets"]
    assert rendered["widgets"] == {}


def test_a_trusted_folder_keeps_the_rich_render_and_no_policy(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Title\n\n<span class='x'>kept</span>\n")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        rendered = client.get(
            "/api/kpress/render", params={"path": "README.md", "view": "document"}
        ).json()
        shell = client.get("/view/")
    assert "inert" not in rendered
    assert 'class="kpress' in rendered["html"]
    assert "content-security-policy" not in shell.headers


def test_the_untrusted_shell_runs_only_this_servers_scripts(untrusted: None) -> None:
    with TestClient(app) as client:
        first = client.get("/view/")
        second = client.get("/view/")
    policy = first.headers["content-security-policy"]
    nonce = re.search(r"'nonce-([^']+)'", policy)
    assert nonce is not None
    assert policy == untrusted_shell_csp(nonce.group(1), "http://testserver")
    assert first.headers["x-frame-options"] == "DENY"
    # A fresh nonce per response, carried by every inline script of the shell.
    assert nonce.group(1) not in second.headers["content-security-policy"]
    inline = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>", first.text)
    assert inline and all(f'nonce="{nonce.group(1)}"' in attrs for attrs in inline)
    # Code only from the application's own static paths: never /raw, never inline.
    assert (
        f"script-src 'nonce-{nonce.group(1)}' http://testserver/static/"
        " http://testserver/plugin-static/;"
    ) in policy
    assert "'unsafe-hashes'" not in policy and "script-src 'self'" not in policy
    for directive in (
        "style-src http://testserver/static/ http://testserver/plugin-static/"
        " http://testserver/kpress-static/",
        "img-src 'self' data:",
        "connect-src 'self'",
        "worker-src http://testserver/plugin-static/",
        "frame-src 'none'",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ):
        assert directive in policy


def test_raw_never_serves_a_browsed_file_as_code_when_untrusted(
    tmp_path: Path, untrusted: None
) -> None:
    (tmp_path / "evil.js").write_text("alert(1)\n")
    (tmp_path / "evil.css").write_text("body{display:none}\n")
    (tmp_path / "page.html").write_text("<p>x</p>\n")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        for path, destination in (
            ("evil.js", "script"),
            ("evil.css", "style"),
            ("evil.js", "worker"),
            ("evil.js", "serviceworker"),
        ):
            refused = client.get(
                "/raw", params={"path": path}, headers={"sec-fetch-dest": destination}
            )
            assert refused.status_code == 403, (path, destination)
            assert "sandbox" in refused.headers["content-security-policy"]
        # Read as a document, or by a browser that names no destination, it is text.
        for path in ("evil.js", "evil.css"):
            text = client.get("/raw", params={"path": path})
            assert text.status_code == 200
            assert text.headers["content-type"].startswith("text/plain")
            assert text.headers["x-content-type-options"] == "nosniff"
        page = client.get(
            "/raw", params={"path": "page.html"}, headers={"sec-fetch-dest": "document"}
        )
        assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")


def test_a_trusted_folders_raw_scripts_are_unchanged(tmp_path: Path) -> None:
    (tmp_path / "tool.js").write_text("console.log(1)\n")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        answer = client.get(
            "/raw", params={"path": "tool.js"}, headers={"sec-fetch-dest": "script"}
        )
    assert answer.status_code == 200
    assert "javascript" in answer.headers["content-type"]


def test_the_application_writes_no_inline_handler() -> None:
    """The page policy for an untrusted source runs no inline handler, so none may exist.

    It catches handler attributes written into markup, set with ``setAttribute``, or
    assigned a string; a function assigned to a handler property is not inline code.
    """

    found: list[str] = []
    for path in SOURCES:
        if "vendor" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        for pattern in (
            r"\son[a-z]+=[\"'\\]",
            r"setAttribute\(\s*[\"'`]on[a-z]+",
            r"\.on[a-z]+\s*=\s*[\"'`]",
        ):
            found += [f"{path.name}: {match}" for match in re.findall(pattern, source)]
    assert found == []
