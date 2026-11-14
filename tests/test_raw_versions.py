"""Versioned ``/raw`` addresses: a replaced file is a new address.

The render route answers ``raw_versions``, the version of each served file a document
embeds, by the identity the page's link enhancer resolves it to, and the enhancer puts
the version in the image's address. So a browser that reuses an image by its address --
Chrome's list of available images on a return to a document, a reload's cache -- asks
again when the file was replaced. ``/raw`` keeps an answer for a year only for a raster
image at the version the file has now, whose execution policy is the same in both trust
profiles, and revalidates every other (``SECURITY.md``):
``tests/test_raw_profile_cache_chrome.py`` follows an SVG's old address across a switch to
``--untrusted`` in Chrome.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser import http_caching, server
from metabrowser.capabilities import DEFAULT_CAPABILITIES, Capabilities, set_capabilities
from metabrowser.embedded_resources import embedded_raw_paths, resolve_embedded_path
from tests.required_tools import require_node

PNG = b"\x89PNG\r\n\x1a\n"
IMMUTABLE = "private, max-age=31536000, immutable"
SOURCE = "docs/guide/readme.md"
RESOLVER = Path(__file__).resolve().parent / "dom" / "embedded-resource-resolution.js"
# links.js MAX_AUTHORED_TARGET_LENGTH: a longer address is refused.
LIMIT = 16384
# Enough `./` that `ab.png` after them is exactly LIMIT units long.
PAD = (LIMIT - 6) // 2

# Authored addresses, each with the identity the enhancer asks /raw for, or None.
ADDRESSES: list[tuple[str, str | None]] = [
    ("images/a.png", "docs/guide/images/a.png"),
    ("./images/./a.png", "docs/guide/images/a.png"),
    ("../top.png", "docs/top.png"),
    ("../../top.png", "top.png"),
    ("../../../escape.png", None),
    ("/assets/logo.png", "assets/logo.png"),
    ("/../escape.png", None),
    ("images/a.png?raw=1#frag", "docs/guide/images/a.png"),
    ("my%20image.png", "docs/guide/my image.png"),
    # The inventory spells a `%` in a name as `%25`.
    ("100%25.png", "docs/guide/100%25.png"),
    ("na%C3%AFve.png", "docs/guide/naïve.png"),
    # A folder, the root, and the document itself: /raw finds no regular file there.
    ("images/", "docs/guide/images"),
    ("images/..", "docs/guide"),
    ("/", ""),
    ("", SOURCE),
    ("#frag", SOURCE),
    ("?query", SOURCE),
    # Every address links.js refuses, or that is not a served file's.
    ("a%2Fb.png", None),
    ("a%zz.png", None),
    ("a%E9.png", None),
    ("a.png?bad=%zz", None),
    ("a.png#%00", None),
    ("a\\b.png", None),
    ("a//b.png", None),
    ("https://example.com/badge.png", None),
    ("//example.com/badge.png", None),
    (" //example.com/badge.png", None),
    ("data:image/png;base64,AAAA", None),
    (" javascript:alert(1)", None),
    ("c:image.png", None),
    # At links.js's bound, `./` repeated before a short name; one unit more is refused.
    ("./" * PAD + "ab.png", "docs/guide/ab.png"),
    ("./" * PAD + "abc.png", None),
    # The bound counts UTF-16 units: an astral character is two.
    ("./" * PAD + "\U0001f600.png", "docs/guide/\U0001f600.png"),
    ("./" * PAD + "a\U0001f600.png", None),
]


@pytest.mark.parametrize(("authored", "expected"), ADDRESSES)
def test_an_embedded_address_resolves_as_the_link_enhancer_resolves_it(
    authored: str, expected: str | None
) -> None:
    assert resolve_embedded_path(authored, SOURCE) == expected


def test_the_prediction_is_the_production_resolvers() -> None:
    """Review A of #426, A3: each address, its bound included, through links.js itself."""

    cases = [{"authored": authored, "source": SOURCE} for authored, _ in ADDRESSES]
    result = subprocess.run(
        [require_node(), str(RESOLVER)],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [expected for _, expected in ADDRESSES]


def test_the_bound_cases_sit_on_the_bound() -> None:
    lengths = [len(authored.encode("utf-16-le")) // 2 for authored, _ in ADDRESSES[-4:]]
    assert lengths == [LIMIT, LIMIT + 1, LIMIT, LIMIT + 1]


def test_a_render_names_each_resource_once_in_order_and_within_its_bound() -> None:
    html = (
        '<p><img loading="lazy" src="b.png" alt="x > y"> <img src=\'a.png\'>'
        '<IMG SRC=c.png><img src="b.png"><video src="v.mp4"></video>'
        '<object data="o.svg"></object><object src="not-data.svg"></object>'
        '<a href="link.png">l</a><img alt="no address"><img src="a&amp;b.png"></p>'
    )
    assert embedded_raw_paths(html, "readme.md", limit=100) == [
        "b.png",
        "a.png",
        "c.png",
        "v.mp4",
        "o.svg",
        "a&b.png",
    ]
    assert embedded_raw_paths(html, "readme.md", limit=2) == ["b.png", "a.png"]


@pytest.fixture
def served(tmp_path: Path) -> TestClient:
    (tmp_path / "docs" / "images").mkdir(parents=True)
    (tmp_path / "docs" / "images" / "a.png").write_bytes(PNG + b"a" * 32)
    (tmp_path / "docs" / ".hidden").mkdir()
    (tmp_path / "docs" / ".hidden" / "h.png").write_bytes(PNG + b"h" * 32)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(PNG + b"l" * 32)
    (tmp_path / "logo.png").symlink_to("assets/logo.png")
    (tmp_path / "docs" / "readme.md").write_text(
        "# Readme\n\n"
        "![a](images/a.png) ![h](.hidden/h.png) ![logo](../logo.png)\n"
        "![missing](images/missing.png) ![folder](images) ![badge](https://example.com/b.png)\n"
        "![up](../../escape.png)\n"
    )
    server._set_root_dir(tmp_path)
    return TestClient(server.app)


def _versions(client: TestClient) -> dict[str, str]:
    response = client.get("/api/kpress/render", params={"path": "docs/readme.md"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    return response.json()["raw_versions"]


def test_a_render_versions_each_served_file_it_embeds(served: TestClient) -> None:
    """A hidden file and a link's target are versioned too: the version is read, not heard."""

    versions = _versions(served)
    assert sorted(versions) == ["docs/.hidden/h.png", "docs/images/a.png", "logo.png"]
    for identity, version in versions.items():
        answer = served.get("/raw", params={"path": identity, "v": version})
        assert answer.status_code == 200
        assert answer.headers["cache-control"] == IMMUTABLE
        assert "sandbox" in answer.headers["content-security-policy"]
        # The same tag answers with a 304 that keeps the address immutable.
        again = served.get(
            "/raw",
            params={"path": identity, "v": version},
            headers={"if-none-match": answer.headers["etag"]},
        )
        assert again.status_code == 304
        assert again.headers["cache-control"] == IMMUTABLE


def test_a_replaced_file_is_a_new_address_and_its_old_one_is_revalidated(
    tmp_path: Path, served: TestClient
) -> None:
    """A same-size replacement that restores the modification time still moves the version."""

    image = tmp_path / "docs" / "images" / "a.png"
    os.utime(image, ns=(499_187_700_000_000_000, 499_187_700_000_000_000))
    before = _versions(served)["docs/images/a.png"]
    image.write_bytes(PNG + b"b" * 32)
    os.utime(image, ns=(499_187_700_000_000_000, 499_187_700_000_000_000))
    after = _versions(served)["docs/images/a.png"]
    assert after != before
    old = served.get("/raw", params={"path": "docs/images/a.png", "v": before})
    assert old.content == PNG + b"b" * 32
    assert old.headers["cache-control"] == "no-cache"
    new = served.get("/raw", params={"path": "docs/images/a.png", "v": after})
    assert new.headers["cache-control"] == IMMUTABLE


def test_only_the_current_version_of_the_query_form_is_kept(served: TestClient) -> None:
    version = _versions(served)["docs/images/a.png"]
    for params in ({"path": "docs/images/a.png"}, {"path": "docs/images/a.png", "v": "0" * 16}):
        assert served.get("/raw", params=params).headers["cache-control"] == "no-cache"
    # The path form is a document's address, for its relative references.
    path_form = served.get("/raw/docs/images/a.png", params={"v": version})
    assert path_form.status_code == 200
    assert path_form.headers["cache-control"] == "no-cache"


def test_a_version_names_the_trust_profile(served: TestClient) -> None:
    """Review C of #372, C1: an answer kept under one profile must not be reused under
    another, so the version under --untrusted differs, and the default profile's is
    revalidated there."""

    trusted = _versions(served)["docs/images/a.png"]
    set_capabilities(Capabilities(active_content=False, mutations=False))
    try:
        untrusted = _versions(served)["docs/images/a.png"]
        assert untrusted != trusted
        stale = served.get("/raw", params={"path": "docs/images/a.png", "v": trusted})
        assert stale.headers["cache-control"] == "no-cache"
        assert "allow-scripts" not in stale.headers["content-security-policy"]
        current = served.get("/raw", params={"path": "docs/images/a.png", "v": untrusted})
        assert current.headers["cache-control"] == IMMUTABLE
    finally:
        set_capabilities(DEFAULT_CAPABILITIES)


def test_a_version_names_the_build(served: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    before = _versions(served)["docs/images/a.png"]
    monkeypatch.setattr(http_caching, "BUILD_TAG", "0" * len(http_caching.BUILD_TAG))
    assert _versions(served)["docs/images/a.png"] != before


# Execution headers: what decides whether, and as what, a browser runs an answer.
EXECUTION_HEADERS = ("content-type", "content-security-policy", "x-content-type-options")


def _answers(client: TestClient, identity: str) -> dict[str, object]:
    """The answer at *identity*'s current version, under the profile serving now."""

    target = server._safe_path(identity)
    assert target is not None
    version = server._raw_version(target, target.stat())
    answer = client.get("/raw", params={"path": identity, "v": version})
    assert answer.status_code == 200
    return {
        "cache-control": answer.headers["cache-control"],
        "execution": {name: answer.headers.get(name) for name in EXECUTION_HEADERS},
    }


def test_only_a_raster_image_is_kept_and_its_policy_is_every_profiles(tmp_path: Path) -> None:
    """Reviews A and B of #426, A1 and B1: an answer a browser keeps is replayed without
    reaching the server, under whichever profile serves the origin by then. So only an
    answer whose execution headers are the same under both profiles is kept: a raster
    image's. An SVG or an HTML document runs scripts under the trusted profile, and is
    revalidated at its current version too."""

    raster = ["a.png", "a.jpg", "a.jpeg", "a.gif", "a.webp", "a.avif", "upper.PNG"]
    documents = ["a.svg", "a.html", "a.js", "a.css", "a.txt", "a.bmp", "a.ico", "a.pdf"]
    for name in raster + documents:
        (tmp_path / name).write_bytes(PNG + b"x" * 16)
    server._set_root_dir(tmp_path)
    client = TestClient(server.app)
    trusted = {name: _answers(client, name) for name in raster + documents}
    set_capabilities(Capabilities(active_content=False, mutations=False))
    try:
        untrusted = {name: _answers(client, name) for name in raster + documents}
    finally:
        set_capabilities(DEFAULT_CAPABILITIES)
    for name in raster:
        assert trusted[name]["cache-control"] == IMMUTABLE, name
        assert untrusted[name]["cache-control"] == IMMUTABLE, name
        assert trusted[name]["execution"] == untrusted[name]["execution"], name
        assert "allow-scripts" not in str(trusted[name]["execution"]), name
    for name in documents:
        assert trusted[name]["cache-control"] == "no-cache", name
        assert untrusted[name]["cache-control"] == "no-cache", name
    assert "allow-scripts" in str(trusted["a.svg"]["execution"])
    assert "allow-scripts" not in str(untrusted["a.svg"]["execution"])


def test_a_looping_link_is_left_unversioned_and_the_document_renders(tmp_path: Path) -> None:
    """Review B of #426, B2: on Python 3.12 resolving a link to itself raised
    RuntimeError, which failed the whole render; now the link names no file."""

    (tmp_path / "a.png").write_bytes(PNG)
    (tmp_path / "loop.png").symlink_to("loop.png")
    (tmp_path / "readme.md").write_text("# Loop\n\n![x](loop.png) ![a](a.png)\n")
    server._set_root_dir(tmp_path)
    client = TestClient(server.app)
    response = client.get("/api/kpress/render", params={"path": "readme.md"})
    assert response.status_code == 200
    assert "<h1" in response.json()["html"]
    assert sorted(response.json()["raw_versions"]) == ["a.png"]
    assert client.get("/raw", params={"path": "loop.png"}).status_code == 404
