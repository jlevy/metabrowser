"""Content-stamped asset addresses and the cache policy they earn.

Every reload used to revalidate 33 to 84 assets (research 2026-11-11, H87): ``/static``
was fresh only by the Last-Modified heuristic, and plugin and KPress scripts were
``no-cache`` at addresses that did not name their content. An address that names its
content is answered ``immutable``, and only while it names what the server has now: a
page rendered before an edit must not keep the edited bytes under the old address.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import kpress_adapter, server
from metabrowser.asset_stamps import StampedTree, split_stamp
from metabrowser.capabilities import DEFAULT_CAPABILITIES, Capabilities, set_capabilities
from metabrowser.plugin_loader.discovery import LoadedPlugin
from metabrowser.plugin_loader.manifest import PLUGIN_SDK_VERSION, PluginManifest
from metabrowser.plugin_loader.static_assets import (
    build_plugin_routes,
    plugin_asset_prefix,
    plugin_tree_is_live,
)

IMMUTABLE = "public, max-age=31536000, immutable"
STAMPED_MODULE = re.compile(r'"module": "(/plugin-static/[a-z_-]+/@[0-9a-f]{16}/index\.js)"')


def _shell(client: TestClient) -> str:
    response = client.get("/view/")
    assert response.status_code == 200
    return response.text


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    (tmp_path / "a.md").write_text("# A\n")
    server._set_root_dir(tmp_path)
    return TestClient(server.app)


# ── /static ────────────────────────────────────────────────────


def test_a_static_file_at_its_current_stamp_is_immutable(client: TestClient) -> None:
    stamped = re.search(r'src="(/static/app\.js\?v=[^"]+)"', _shell(client))
    assert stamped is not None
    url = stamped.group(1)

    answer = client.get(url)
    assert answer.status_code == 200
    assert answer.headers["cache-control"] == IMMUTABLE

    # A revalidation's answer carries the policy too, since it refreshes what is held.
    again = client.get(url, headers={"if-none-match": answer.headers["etag"]})
    assert again.status_code == 304
    assert again.headers["cache-control"] == IMMUTABLE


@pytest.mark.parametrize("query", ["", "?v=app_js_1_2_stale"], ids=["unstamped", "stale"])
def test_a_static_file_without_its_current_stamp_is_revalidated(
    client: TestClient, query: str
) -> None:
    """An older page, or a hand-written URL, must not pin today's bytes for a year."""
    answer = client.get(f"/static/app.js{query}")
    assert answer.status_code == 200
    assert answer.headers["cache-control"] == "no-cache"


# ── /plugin-static ─────────────────────────────────────────────


def test_every_plugin_url_the_shell_names_is_stamped_and_immutable(client: TestClient) -> None:
    html = _shell(client)
    modules = STAMPED_MODULE.findall(html)
    assert len(modules) >= 8, "every built-in plugin's module carries its tree's stamp"
    assert "/plugin-static/markdown/index.js" not in html
    for url in modules:
        answer = client.get(url)
        assert answer.status_code == 200, url
        assert answer.headers["cache-control"] == IMMUTABLE, url
    # The same file at its unstamped address is still served, and revalidated.
    unstamped = re.sub(r"/@[0-9a-f]{16}/", "/", modules[0])
    answer = client.get(unstamped)
    assert answer.status_code == 200
    assert answer.headers["cache-control"] == "no-cache"


def _fixture_plugin(root: Path, *, source: str = "local:fixture") -> LoadedPlugin:
    (root / "index.js").write_text('import "./part.js";\n')
    (root / "part.js").write_text("export const part = 1;\n")
    (root / "worker.js").write_text("self.onmessage = () => {};\n")
    manifest = PluginManifest.model_validate(
        {
            "plugin": {"name": "fixture", "sdk_version": PLUGIN_SDK_VERSION},
            "kind": [{"id": "fixture-kind", "match": {"ext": ".fixture"}}],
        }
    )
    return LoadedPlugin(name="fixture", static_root=root, manifest=manifest, source=source)


def _plugin_client(plugin: LoadedPlugin, tree: StampedTree) -> TestClient:
    routes = build_plugin_routes([plugin], asset_trees={plugin.name: tree})
    return TestClient(Starlette(routes=routes))


def test_a_relative_import_under_a_stamp_is_served_immutable(tmp_path: Path) -> None:
    """A module's imports and worker resolve against its path, so they inherit the stamp."""
    plugin = _fixture_plugin(tmp_path)
    tree = StampedTree(tmp_path, live=True)
    prefix = plugin_asset_prefix("fixture", tree)
    assert re.fullmatch(r"/plugin-static/fixture/@[0-9a-f]{16}", prefix)
    client = _plugin_client(plugin, tree)
    for name in ("index.js", "part.js", "worker.js"):
        answer = client.get(f"{prefix}/{name}")
        assert answer.status_code == 200, name
        assert answer.headers["cache-control"] == IMMUTABLE, name
        again = client.get(f"{prefix}/{name}", headers={"if-none-match": answer.headers["etag"]})
        assert again.status_code == 304
        assert again.headers["cache-control"] == IMMUTABLE


def test_an_edit_after_the_stamp_is_revalidated_and_moves_the_next_stamp(
    tmp_path: Path,
) -> None:
    plugin = _fixture_plugin(tmp_path)
    tree = StampedTree(tmp_path, live=True)
    prefix = plugin_asset_prefix("fixture", tree)
    client = _plugin_client(plugin, tree)

    # A page rendered before the edit asks with the old stamp after it.
    (tmp_path / "part.js").write_text("export const part = 2;\n")
    stale = client.get(f"{prefix}/part.js")
    assert stale.status_code == 200
    assert stale.text == "export const part = 2;\n"
    assert stale.headers["cache-control"] == "no-cache", "new bytes under the old stamp"
    # An unedited file under the same stamp is still the one the stamp names.
    assert client.get(f"{prefix}/index.js").headers["cache-control"] == IMMUTABLE

    # The next page names the edited tree, and its answers are immutable again.
    after = plugin_asset_prefix("fixture", tree)
    assert after != prefix
    assert client.get(f"{after}/part.js").headers["cache-control"] == IMMUTABLE
    # And the page that still holds the old stamp is revalidated for every file.
    assert client.get(f"{prefix}/index.js").headers["cache-control"] == "no-cache"


def test_a_stamp_this_process_never_gave_is_revalidated(tmp_path: Path) -> None:
    """A page from an earlier server process asks with a stamp this one has not taken."""
    plugin = _fixture_plugin(tmp_path)
    tree = StampedTree(tmp_path, live=True)
    client = _plugin_client(plugin, tree)
    answer = client.get("/plugin-static/fixture/@0123456789abcdef/index.js")
    assert answer.status_code == 200
    assert answer.headers["cache-control"] == "no-cache"
    plugin_asset_prefix("fixture", tree)
    answer = client.get("/plugin-static/fixture/@0123456789abcdef/index.js")
    assert answer.headers["cache-control"] == "no-cache"


def test_routes_without_trees_revalidate_every_answer(tmp_path: Path) -> None:
    plugin = _fixture_plugin(tmp_path)
    prefix = plugin_asset_prefix("fixture", StampedTree(tmp_path, live=True))
    client = TestClient(Starlette(routes=build_plugin_routes([plugin])))
    answer = client.get(f"{prefix}/index.js")
    assert answer.status_code == 200
    assert answer.headers["cache-control"] == "no-cache"


def test_who_stamps_once_and_who_stamps_every_page(tmp_path: Path) -> None:
    local = _fixture_plugin(tmp_path)
    assert plugin_tree_is_live(local), "an operator's directory can change at any time"
    assert not plugin_tree_is_live(
        LoadedPlugin(local.name, tmp_path, local.manifest, "entry-point:not-installed-dist")
    )


# ── The stamp ──────────────────────────────────────────────────


def _digest(tree: StampedTree) -> str:
    stamp = tree.stamp()
    assert stamp is not None
    return stamp.digest


def test_the_stamp_names_content_not_times(tmp_path: Path) -> None:
    """The same release has the same addresses on every machine and after a restart."""
    (tmp_path / "a.js").write_text("a\n")
    (tmp_path / "css").mkdir()
    (tmp_path / "css" / "b.css").write_text("b\n")
    # Not browser assets: a server-side edit must not refetch the scripts.
    (tmp_path / "sidekick.py").write_text("x = 1\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "sidekick.cpython-314.pyc").write_bytes(b"\0")
    (tmp_path / ".DS_Store").write_bytes(b"\0")
    first = StampedTree(tmp_path, live=True).stamp()
    assert first is not None
    assert set(first.files) == {"a.js", "css/b.css"}

    os.utime(tmp_path / "a.js", ns=(1, 1_000_000_000))
    (tmp_path / "sidekick.py").write_text("x = 2\n")
    assert _digest(StampedTree(tmp_path, live=True)) == first.digest

    (tmp_path / "a.js").write_text("A\n")
    assert _digest(StampedTree(tmp_path, live=True)) != first.digest


def test_a_released_tree_is_stamped_once(tmp_path: Path) -> None:
    (tmp_path / "a.js").write_text("a\n")
    released = StampedTree(tmp_path, live=False)
    stamp = released.stamp()
    assert released.settled
    (tmp_path / "a.js").write_text("b\n")
    assert released.stamp() is stamp, "nothing under an installed release changes"
    live = StampedTree(tmp_path, live=True)
    assert not live.settled
    assert live.stamp() != stamp


def test_a_live_tree_rehashes_only_after_a_stat_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser import asset_stamps

    (tmp_path / "a.js").write_text("a\n")
    hashed = 0
    real = asset_stamps._hash_tree  # pyright: ignore[reportPrivateUsage]

    def counted(root: Path, signature: tuple[tuple[str, tuple[int, int, int, int]], ...]) -> object:
        nonlocal hashed
        hashed += 1
        return real(root, signature)

    monkeypatch.setattr(asset_stamps, "_hash_tree", counted)
    tree = StampedTree(tmp_path, live=True)
    first = tree.stamp()
    assert tree.stamp() is first and hashed == 1
    (tmp_path / "a.js").write_text("aa\n")
    assert tree.stamp() is not first and hashed == 2


def test_a_tree_past_the_bound_is_not_stamped(tmp_path: Path) -> None:
    for index in range(4):
        (tmp_path / f"{index}.js").write_text("x\n")
    plugin = _fixture_plugin(tmp_path)
    tree = StampedTree(tmp_path, live=True, max_files=3)
    assert tree.stamp() is None
    prefix = plugin_asset_prefix("fixture", tree)
    assert prefix == "/plugin-static/fixture"
    answer = _plugin_client(plugin, tree).get(f"{prefix}/index.js")
    assert answer.headers["cache-control"] == "no-cache"
    assert StampedTree(tmp_path, live=True, max_bytes=4).stamp() is None


def test_a_rewrite_that_restores_size_and_time_is_not_the_stamped_file(tmp_path: Path) -> None:
    """Review C of #372, C2: a same-size replacement with its modification time restored,
    as npm's fixed 1985 time gives, still moves the change time, so it is revalidated and
    the next stamp names its bytes."""
    plugin = _fixture_plugin(tmp_path)
    tree = StampedTree(tmp_path, live=True)
    prefix = plugin_asset_prefix("fixture", tree)
    client = _plugin_client(plugin, tree)
    part = tmp_path / "part.js"
    times = (499_187_700_000_000_000, 499_187_700_000_000_000)
    os.utime(part, ns=times)
    prefix = plugin_asset_prefix("fixture", tree)
    part.write_text("export const part = 9;\n")  # the same size as before
    os.utime(part, ns=times)
    answer = client.get(f"{prefix}/part.js")
    assert answer.text == "export const part = 9;\n"
    assert answer.headers["cache-control"] == "no-cache"
    assert plugin_asset_prefix("fixture", tree) != prefix


def test_tooling_under_a_plugin_directory_is_not_part_of_its_stamp(tmp_path: Path) -> None:
    (tmp_path / "index.js").write_text("x\n")
    (tmp_path / "node_modules" / "dep").mkdir(parents=True)
    (tmp_path / "node_modules" / "dep" / "index.js").write_text("y\n")
    stamp = StampedTree(tmp_path, live=True).stamp()
    assert stamp is not None and set(stamp.files) == {"index.js"}


def test_a_live_tree_past_the_bound_is_walked_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review B of #372, B5: it used to be walked, and given up on, for every page."""
    from metabrowser import asset_stamps

    for index in range(4):
        (tmp_path / f"{index}.js").write_text("x\n")
    walks = 0
    real = asset_stamps._signature  # pyright: ignore[reportPrivateUsage]

    def counted(root: Path, max_files: int) -> object:
        nonlocal walks
        walks += 1
        return real(root, max_files)

    monkeypatch.setattr(asset_stamps, "_signature", counted)
    tree = StampedTree(tmp_path, live=True, max_files=3)
    assert tree.stamp() is None and tree.stamp() is None
    assert walks == 1 and tree.settled


def test_a_static_file_is_stamped_by_its_bytes(tmp_path: Path) -> None:
    """Review C of #372, C3: a name, size, and time token gave two releases one address
    when a packager normalizes times; the digest of the bytes cannot."""
    from metabrowser.asset_stamps import StampedStaticFiles

    (tmp_path / "app.js").write_text("one();\n")
    tree = StampedTree(tmp_path, live=True)
    stamp = tree.stamp()
    assert stamp is not None
    client = TestClient(StampedStaticFiles(directory=tmp_path, tree=tree))
    digest = stamp.digests["app.js"]
    assert client.get(f"/app.js?v={digest}").headers["cache-control"] == IMMUTABLE
    times = (499_187_700_000_000_000, 499_187_700_000_000_000)
    (tmp_path / "app.js").write_text("two();\n")  # same size, same name
    os.utime(tmp_path / "app.js", ns=times)
    stale = client.get(f"/app.js?v={digest}")
    assert stale.text == "two();\n"
    assert stale.headers["cache-control"] == "no-cache"
    fresh = tree.stamp()
    assert fresh is not None and fresh.digests["app.js"] != digest
    assert client.get(f"/app.js?v={fresh.digests['app.js']}").headers["cache-control"] == IMMUTABLE


def test_only_a_well_formed_stamp_segment_is_a_stamp() -> None:
    assert split_stamp("@0123456789abcdef/js/a.js") == ("0123456789abcdef", "js/a.js")
    assert split_stamp("js/a.js") == (None, "js/a.js")
    assert split_stamp("@0123456789ABCDEF/a.js") == (None, "@0123456789ABCDEF/a.js")
    assert split_stamp("@0123/a.js") == (None, "@0123/a.js")


# ── /kpress-static ─────────────────────────────────────────────


def test_kpress_css_and_js_under_the_current_stamp_are_immutable(client: TestClient) -> None:
    prefix = kpress_adapter.kpress_asset_url_prefix()
    assert re.fullmatch(r"/kpress-static/@[0-9a-f]{16}/", prefix)
    for rel in ("css/document.css", "js/toc.js", "fonts/pt-serif-latin-400-normal.woff2"):
        url = kpress_adapter.kpress_static_url(rel)
        assert url.startswith(prefix)
        answer = client.get(url)
        assert answer.status_code == 200, url
        assert answer.headers["cache-control"] == IMMUTABLE, url


def test_kpress_css_off_the_current_stamp_is_revalidated(client: TestClient) -> None:
    version = kpress_adapter.kpress_static_url("css/document.css").split("/")[3]
    for url in (
        f"/kpress-static/{version}/css/document.css",
        f"/kpress-static/@0123456789abcdef/{version}/css/document.css",
    ):
        answer = client.get(url)
        assert answer.status_code == 200, url
        assert answer.headers["cache-control"] == "no-cache", url
    # A font at the version-keyed address, with no stamp, is kept hard as it always was;
    # under a stamp that is not current it is revalidated like the rest (review C, C4).
    font = client.get(f"/kpress-static/{version}/fonts/pt-serif-latin-400-normal.woff2")
    assert font.headers["cache-control"] == IMMUTABLE
    old_stamp = client.get(
        f"/kpress-static/@0123456789abcdef/{version}/fonts/pt-serif-latin-400-normal.woff2"
    )
    assert old_stamp.status_code == 200
    assert old_stamp.headers["cache-control"] == "no-cache"


def test_the_shell_and_kpress_renders_name_the_same_stamped_assets(client: TestClient) -> None:
    """One download per asset: the shell's preload and link match what a render lists."""
    html = _shell(client)
    rendered = client.get("/api/kpress/render", params={"path": "a.md"}).json()
    listed = {asset["public_url"] for asset in rendered["assets"]["assets"]}
    shell_urls = re.findall(r'href="(/kpress-static/[^"]+)"', html)
    assert len(shell_urls) == 2
    assert set(shell_urls) <= listed
    prefix = kpress_adapter.kpress_asset_url_prefix()
    assert all(url.startswith(prefix) for url in listed)


# ── /raw ───────────────────────────────────────────────────────


def _raw_fixture(tmp_path: Path) -> TestClient:
    (tmp_path / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    (tmp_path / "x.js").write_text("alert(1);\n")
    server._set_root_dir(tmp_path)
    return TestClient(server.app)


def test_raw_answers_its_tag_with_304_and_is_always_revalidated(tmp_path: Path) -> None:
    """A revalidated image used to be sent again whole; now a 304, never a fresh copy."""
    client = _raw_fixture(tmp_path)
    first = client.get("/raw", params={"path": "pic.png"})
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-cache"
    etag = first.headers["etag"]
    again = client.get("/raw", params={"path": "pic.png"}, headers={"if-none-match": etag})
    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["etag"] == etag
    assert again.headers["cache-control"] == "no-cache"
    # A date cannot name the trust profile the headers came from, so it earns no 304.
    since = {"if-modified-since": first.headers["last-modified"]}
    assert client.get("/raw", params={"path": "pic.png"}, headers=since).status_code == 200
    # No address of a reader's file is kept without asking, whatever it carries.
    for query in ({"path": "pic.png", "v": "anything"}, {"path": "pic.png"}):
        assert client.get("/raw", params=query).headers["cache-control"] == "no-cache"


def test_raw_never_answers_one_trust_profile_with_anothers_response(tmp_path: Path) -> None:
    """Review C of #372, C1: a response stored under one profile must not be revalidated
    under another, or its headers -- the sandbox policy and, for a script, the type --
    are the other profile's."""
    client = _raw_fixture(tmp_path)
    trusted = client.get("/raw", params={"path": "x.js"})
    assert trusted.headers["content-type"].startswith("text/javascript")
    assert "allow-scripts" in trusted.headers["content-security-policy"]
    set_capabilities(Capabilities(active_content=False, mutations=False))
    try:
        held = {"if-none-match": trusted.headers["etag"]}
        untrusted = client.get("/raw", params={"path": "x.js"}, headers=held)
        assert untrusted.status_code == 200, "a 304 would keep the trusted type and policy"
        assert untrusted.headers["content-type"].startswith("text/plain")
        assert "allow-scripts" not in untrusted.headers["content-security-policy"]
        assert untrusted.headers["etag"] != trusted.headers["etag"]
        assert untrusted.headers["cache-control"] == "no-cache"
        # The other direction is refused as well.
        set_capabilities(DEFAULT_CAPABILITIES)
        back = {"if-none-match": untrusted.headers["etag"]}
        assert client.get("/raw", params={"path": "x.js"}, headers=back).status_code == 200
    finally:
        set_capabilities(DEFAULT_CAPABILITIES)


def test_raw_moves_its_tag_when_a_rewrite_keeps_size_and_modification_time(
    tmp_path: Path,
) -> None:
    """Review C of #372, C2: npm unpacks every file at one fixed time, so a same-size
    replacement keeps name, size, and mtime; its change time still moves the tag."""
    client = _raw_fixture(tmp_path)
    logo = tmp_path / "logo.svg"
    logo.write_text("<svg>version 1</svg>")
    os.utime(logo, ns=(499_187_700_000_000_000, 499_187_700_000_000_000))
    first = client.get("/raw", params={"path": "logo.svg"})
    logo.write_text("<svg>version 2</svg>")
    os.utime(logo, ns=(499_187_700_000_000_000, 499_187_700_000_000_000))
    held = {"if-none-match": first.headers["etag"]}
    answer = client.get("/raw", params={"path": "logo.svg"}, headers=held)
    assert answer.status_code == 200
    assert answer.text == "<svg>version 2</svg>"
