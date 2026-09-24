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
    SHELL_INLINE_HANDLERS,
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
    assert policy == untrusted_shell_csp(nonce.group(1))
    # A fresh nonce per response, carried by every inline script of the shell.
    assert nonce.group(1) not in second.headers["content-security-policy"]
    inline = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>", first.text)
    assert inline and all(f'nonce="{nonce.group(1)}"' in attrs for attrs in inline)
    for directive in (
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "style-src 'self'",
    ):
        assert directive in policy


def test_the_policy_allows_exactly_the_inline_handlers_the_application_writes() -> None:
    """Every inline handler in the browser sources is one the policy hashes, and each is used.

    A new inline handler would be refused under the untrusted profile; this names it.
    """

    written: set[str] = set()
    for path in SOURCES:
        if "vendor" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        written |= set(re.findall(r'\son[a-z]+="([^"$]+)"', source))
        # The partial-content notice writes its handler from a default action.
        written |= set(re.findall(r'onclick="\$\{action \|\| "([^"]+)"\}"', source))
    assert written == set(SHELL_INLINE_HANDLERS)
