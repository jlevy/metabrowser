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
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import kpress_adapter, server
from metabrowser.capabilities import (
    DEFAULT_CAPABILITIES,
    Capabilities,
    set_capabilities,
    untrusted_shell_csp,
)
from metabrowser.server import app
from metabrowser.settings import BLOCK_REMOTE_IMAGES_COOKIE
from tests.git_pin_harness import fast_import_store, pinned_client
from tests.github_pull_fixture import allowlist_violations
from tests.required_tools import needs_git
from tests.test_inert_html import HOSTILE_README

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    *sorted((REPO_ROOT / "src/metabrowser/static").glob("*.js")),
    *sorted((REPO_ROOT / "src/metabrowser/builtin_plugins").glob("*/*.js")),
]
README_WIRE = "g1-UkVBRE1FLm1k"

pytestmark = needs_git


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
    assert '<img loading="lazy" src="docs/diagram.png" alt="diagram">' in html
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
    diagram_scripts = tuple(
        kpress_adapter.kpress_static_url(module) for module in kpress_adapter.DIAGRAM_MODULES
    )
    assert policy == untrusted_shell_csp(
        nonce.group(1), "http://testserver", diagram_scripts, remote_images=True
    )
    assert first.headers["x-frame-options"] == "DENY"
    # No address of the page reaches an image's host, from an image the allowlist did not write.
    assert first.headers["referrer-policy"] == "no-referrer"
    # A fresh nonce per response, carried by every inline script of the shell.
    assert nonce.group(1) not in second.headers["content-security-policy"]
    inline = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>", first.text)
    assert inline and all(f'nonce="{nonce.group(1)}"' in attrs for attrs in inline)
    # Code only from the application's own static paths, and KPress's diagram modules
    # by exact path: never /raw, never inline, never the rest of KPress's tree.
    assert (
        f"script-src 'nonce-{nonce.group(1)}' http://testserver/static/"
        " http://testserver/plugin-static/ "
        + " ".join(f"http://testserver{path}" for path in diagram_scripts)
        + ";"
    ) in policy
    assert all(path.startswith("/kpress-static/") for path in diagram_scripts)
    assert "http://testserver/kpress-static/ " not in policy.split("script-src", 1)[1].split(";")[0]
    assert "'unsafe-hashes'" not in policy and "script-src 'self'" not in policy
    for directive in (
        "style-src http://testserver/static/ http://testserver/plugin-static/"
        " http://testserver/kpress-static/",
        "img-src 'self' data: https:",
        "connect-src 'self'",
        "worker-src http://testserver/plugin-static/",
        "frame-src http://testserver/raw;",
        "frame-ancestors 'none'",
        # Frames and objects only from `/raw` itself, by exact path: never a prefix
        # (`/raw/`), and never another route of this origin. The PDF view embeds a
        # file's bytes there, and Chrome checks the frame it draws them in as well.
        "object-src http://testserver/raw;",
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
        assert "avatars.githubusercontent.com" not in page.headers["content-security-policy"]


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


def _img_src(shell: Any) -> str:
    return next(
        part.strip()
        for part in shell.headers["content-security-policy"].split(";")
        if part.strip().startswith("img-src ")
    )


def _settings(shell: Any) -> dict[str, Any]:
    found = re.search(r"window\.METABROWSER_SETTINGS=(\{.*?\});</script>", shell.text, re.DOTALL)
    assert found is not None
    return json.loads(found.group(1))  # type: ignore[no-any-return]


def test_an_untrusted_render_shows_images_from_the_web_over_https_with_no_referrer(
    tmp_path: Path, untrusted: None
) -> None:
    (tmp_path / "README.md").write_text(
        "[![Follow](https://img.shields.io/badge/follow-x-black)](https://x.com/ojoshe)\n\n"
        "![outside](https://avatars.githubusercontent.com/u/123?s=40)\n\n"
        "![insecure](http://example.com/a.png)\n"
    )
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        rendered = client.get(
            "/api/kpress/render", params={"path": "README.md", "view": "document"}
        ).json()
        shell = client.get("/view/")
    html = rendered["html"]
    # The link keeps its destination around the image; the image is fetched under
    # a policy that sends no referrer, from https alone.
    assert (
        '<a href="https://x.com/ojoshe" target="_blank" rel="noopener noreferrer">'
        '<img loading="lazy" referrerpolicy="no-referrer"'
        ' src="https://img.shields.io/badge/follow-x-black" alt="Follow"></a>'
    ) in html
    assert 'src="https://avatars.githubusercontent.com/u/123?s=40"' in html
    assert 'src="http://example.com/a.png"' not in html
    assert 'data-tip-text="http://example.com/a.png"' in html
    # The page's policy admits https images and no other address.
    assert _img_src(shell) == "img-src 'self' data: https:"
    assert _settings(shell)["BLOCK_REMOTE_IMAGES"] is False


def test_the_reader_who_blocks_remote_images_gets_the_narrow_policy(
    tmp_path: Path, untrusted: None
) -> None:
    """Their cookie, read from the page request, narrows ``img-src`` and is the page's setting.

    The browser itself then refuses an image from the web, whatever the page's code does,
    so a page that built one would show nothing and send nothing. Only the exact cookie
    value turns it on.
    """

    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    narrow = "img-src 'self' data: https://avatars.githubusercontent.com"
    with TestClient(app) as client:
        client.cookies.set(BLOCK_REMOTE_IMAGES_COOKIE, "1")
        blocked = client.get("/view/")
        for value in ("0", "", "true", "yes", "11"):
            client.cookies.set(BLOCK_REMOTE_IMAGES_COOKIE, value)
            other = client.get("/view/")
            assert _img_src(other) == "img-src 'self' data: https:", value
            assert _settings(other)["BLOCK_REMOTE_IMAGES"] is False, value
    assert _img_src(blocked) == narrow
    assert _settings(blocked)["BLOCK_REMOTE_IMAGES"] is True
    # The menu's box is drawn as the server read the cookie: ticked only when blocking.
    box = r'<input class="menu-check" id="block-remote-images-input" type="checkbox"( checked)?'
    assert re.search(box, blocked.text).group(1) == " checked"  # type: ignore[union-attr]
    assert re.search(box, other.text).group(1) is None  # type: ignore[union-attr]
    # Everything else the policy says is the same as without the cookie.
    assert untrusted_shell_csp("n", "http://testserver", (), remote_images=False) == (
        untrusted_shell_csp("n", "http://testserver", (), remote_images=True).replace(
            "img-src 'self' data: https:", narrow
        )
    )
    assert blocked.headers["referrer-policy"] == "no-referrer"
    with pytest.raises(TypeError):
        untrusted_shell_csp("n", "http://testserver", ())  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]


def test_a_trusted_folders_page_has_the_setting_and_no_policy_either_way(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Title\n")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        client.cookies.set(BLOCK_REMOTE_IMAGES_COOKIE, "1")
        shell = client.get("/view/")
    assert "content-security-policy" not in shell.headers
    assert _settings(shell)["BLOCK_REMOTE_IMAGES"] is True


def test_inert_pin_keeps_only_real_fences_addressable(tmp_path: Path, untrusted: None) -> None:
    source = (
        '<pre class="kpress-code"><code class="language-json">{}</code></pre>\n\n```json\n{}\n```\n'
    )
    store, commit = fast_import_store(tmp_path, {b"README.md": source.encode()})

    async def fetch() -> Any:
        async with pinned_client(store, commit) as (client, _subject):
            return await client.get(
                "/api/kpress/render", params={"path": README_WIRE, "view": "document"}
            )

    answer = asyncio.run(fetch())
    assert answer.status_code == 200
    rendered = answer.json()
    (placement,) = rendered["structured_fences"]
    assert rendered["inert"] and placement["opening_line"] == 3
    assert re.fullmatch(r"[0-9a-f]{40}", rendered["fence_revision"])
    assert allowlist_violations(rendered["html"], images=True) == []
    assert f'<pre><code>{{}}\n<a href="#{placement["id"]}"></a></code></pre>' in rendered["html"]
