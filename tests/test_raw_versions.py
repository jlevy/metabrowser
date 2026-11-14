"""Versioned ``/raw`` addresses: a replaced file is a new address, kept only while current.

The render route answers ``raw_versions``, the version of each served file a document
embeds, by the identity the page's link enhancer resolves it to, and the enhancer puts
the version in the image's address. So a browser that reuses an image by its address --
Chrome's list of available images on a return to a document, a reload's cache -- asks
again when the file was replaced. ``/raw`` keeps an answer for a year only at the
version the file has now, which names the trust profile as well, and revalidates every
other (``SECURITY.md``).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser import http_caching, server
from metabrowser.capabilities import DEFAULT_CAPABILITIES, Capabilities, set_capabilities
from metabrowser.embedded_resources import embedded_raw_paths, resolve_embedded_path

PNG = b"\x89PNG\r\n\x1a\n"
IMMUTABLE = "private, max-age=31536000, immutable"


@pytest.mark.parametrize(
    ("authored", "expected"),
    [
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
        # Every address links.js refuses, or that is not a served file's.
        ("a%2Fb.png", None),
        ("a%zz.png", None),
        ("a%E9.png", None),
        ("a\\b.png", None),
        ("a//b.png", None),
        ("images/", None),
        ("", None),
        ("#frag", None),
        ("?query", None),
        ("https://example.com/badge.png", None),
        ("//example.com/badge.png", None),
        ("data:image/png;base64,AAAA", None),
        (" javascript:alert(1)", None),
    ],
)
def test_an_embedded_address_resolves_as_the_link_enhancer_resolves_it(
    authored: str, expected: str | None
) -> None:
    assert resolve_embedded_path(authored, "docs/guide/readme.md") == expected


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
