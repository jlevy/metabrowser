"""Exercise the exact revision viewer through the served PR and private cache."""

from __future__ import annotations

import base64
import errno
import hashlib
import json
import logging
import re
import subprocess
from collections import OrderedDict
from html import escape, unescape
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser.builtin_plugins.github import pull_snapshot, pull_snapshot_cache
from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    read_pull_record,
    write_pull_record,
)
from metabrowser.builtin_plugins.github.pull_snapshot import (
    Admission,
    Snapshot,
    _admission,  # pyright: ignore[reportPrivateUsage]
    _render_markdown,  # pyright: ignore[reportPrivateUsage]
)
from metabrowser.builtin_plugins.github.pull_snapshot_cache import read_snapshot_bindings
from metabrowser.cache.paths import source_pull_snapshots
from metabrowser.git.tree_source import GitPath, GitTreeSource
from tests.git_pin_harness import git_env
from tests.required_tools import needs_node
from tests.test_github_pulls import (
    _answering_head,  # pyright: ignore[reportPrivateUsage]
    _move_pull_head,  # pyright: ignore[reportPrivateUsage]
    _Stand,
)
from tests.test_github_pulls import pinned_pull as pinned_pull
from tests.test_github_pulls import stand as stand


def test_revision_file_link_survives_a_record_without_a_comparison(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    envelope = client.get("/api/plugin/github/pull", params={"number": 7}).json()
    address = envelope["snapshot_route"]
    query = address.split("?", 1)[1]
    path = GitPath.from_display("src/app.txt").to_wire()
    stand.calls()
    head = client.get(f"{address}&side=head&path={path}")
    base = client.get(f"{address}&side=base&path={path}")
    assert head.status_code == base.status_code == 200, (head.text, base.text)
    assert head.text != base.text
    assert envelope["pin"] in head.text
    assert "default-src 'none'" in head.headers["content-security-policy"]
    assert head.headers["cache-control"] == "no-store"
    latest = stand.refresh(7)
    assert latest.comparison is not None
    (stand.published.home / source_pull_snapshots(stand.published.slug, 7)).unlink()
    write_pull_record(
        stand.published.home,
        stand.published.slug,
        latest.model_copy(update={"comparison": None}),
        store_id=stand.published.store_id,
    )
    stand.calls()
    assert client.get(f"{address}&side=head&path={path}").text == head.text
    assert (
        client.get("/api/plugin/github/pull", params={"number": 7}).json()["pin"] == envelope["pin"]
    )
    refused = client.get(
        "/api/plugin/github/pull-snapshot",
        params={
            "number": 7,
            "left": "0" * 40,
            "right": envelope["pin"],
            "store": query.split("store=", 1)[1].split("&", 1)[0],
            "side": "head",
            "path": path,
        },
        headers={"accept": "application/json"},
    )
    assert refused.status_code == 410
    assert refused.json()["code"] == "snapshot_expired"
    assert stand.calls() == []


def test_document_references_are_inert_and_use_the_same_snapshot() -> None:
    snapshot = Snapshot(7, "a" * 40, "b" * 40, "test", "head")
    path = GitPath.from_display("docs/readme.md")
    html = _render_markdown(
        b"# Topic\n\n[Topic](#topic) [Guide](../guide.md) ![Image](../assets/image.png)\n\n"
        b"<script>alert(1)</script>\n\n[Local API](/api/file) [Outside](https://example.org)",
        path,
        "c" * 40,
        snapshot,
    )
    assert 'id="user-content-topic"' in html
    assert 'href="#user-content-topic"' in html
    assert GitPath.from_display("guide.md").to_wire() in html
    assert "mode=image" in html
    assert 'href="/api/file"' not in html
    assert "<script" not in html
    assert 'href="https://example.org"' in html


def test_snapshot_images_and_binary_files_keep_their_type(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    record = stand.refresh(7)
    assert record.comparison is not None
    store = stand.published.git_dir

    def git(*args: str, data: bytes = b"") -> str:
        result = subprocess.run(
            ["git", "--git-dir", str(store), *args],
            env=git_env(stand.tmp_path),
            input=data,
            capture_output=True,
            check=True,
        )
        return result.stdout.decode().strip()

    image = b"\x89PNG\r\n\x1a\nfixture"
    binary = b"\0\xffbytes"
    png_oid = git("hash-object", "-w", "--stdin", data=image)
    binary_oid = git("hash-object", "-w", "--stdin", data=binary)
    tree = git(
        "mktree",
        data=f"100644 blob {png_oid}\timage.png\n100644 blob {binary_oid}\tpayload.bin\n".encode(),
    )
    head = git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.com",
        "commit-tree",
        tree,
        "-p",
        record.comparison.head,
        data=b"Snapshot images\n",
    )
    write_pull_record(
        stand.published.home,
        stand.published.slug,
        record.model_copy(
            update={"comparison": record.comparison.model_copy(update={"head": head})}
        ),
    )
    address = client.get("/api/plugin/github/pull?number=7").json()["snapshot_route"]
    address += "&side=head&path="
    picture = address + GitPath.from_display("image.png").to_wire()
    source = address + GitPath.from_display("payload.bin").to_wire()
    preview = client.get(picture)
    assert preview.status_code == 200 and "<img src=" in preview.text
    asset = client.get(picture + "&mode=image")
    assert asset.headers["content-type"] == "image/png" and asset.content == image
    assert "Binary file." in client.get(source).text
    download = client.get(source + "&mode=download")
    assert download.headers["content-disposition"] == (
        "attachment; filename=\"payload.bin\"; filename*=UTF-8''payload.bin"
    )
    assert download.content == binary
    outside = client.get(
        source + "&mode=source&offset=100000000", headers={"accept": "application/json"}
    )
    assert outside.status_code == 416


def test_revision_source_offset_is_bounded_below_eof(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, client = pinned_pull
    route = client.get("/api/plugin/github/pull?number=7").json()["snapshot_route"]
    path = GitPath.from_display("src/app.txt").to_wire()
    address = f"{route}&side=head&mode=source&path={path}"
    monkeypatch.setattr(GitTreeSource, "max_blob_bytes", property(lambda _source: 4))
    preview = client.get(address)
    assert preview.status_code == 200 and "Next bytes" not in preview.text
    # The file is 8 bytes; the page says where its preview stops.
    assert "<pre><code>one\n</code></pre>" in preview.text
    assert "This preview ends at 4 of 8 bytes" in preview.text
    refused = client.get(address + "&offset=5", headers={"accept": "application/json"})
    assert refused.status_code == 416 and refused.json()["code"] == "invalid_offset"


# ── History, admission, and every page over HTTP ───────────────


def _git(stand: _Stand, *args: str, data: bytes = b"") -> str:
    result = subprocess.run(
        ["git", "--git-dir", str(stand.published.git_dir), *args],
        env=git_env(stand.tmp_path),
        input=data,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode().strip()


def _blob(stand: _Stand, data: bytes) -> str:
    return _git(stand, "hash-object", "-w", "--stdin", data=data)


def _commit(stand: _Stand, parent: str, entries: list[tuple[str, str, str, str]]) -> str:
    """A commit on *parent* whose root tree is *entries*: (mode, type, oid, name)."""
    listing = "".join(f"{mode} {kind} {oid}\t{name}\n" for mode, kind, oid, name in entries)
    tree = _git(stand, "mktree", data=listing.encode())
    return _git(
        stand,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.com",
        "commit-tree",
        tree,
        "-p",
        parent,
        data=b"fixture\n",
    )


def _with_head(record: PullRecord, head: str, reader: str | None = None) -> PullRecord:
    assert record.comparison is not None
    update: dict[str, object] = {"comparison": record.comparison.model_copy(update={"head": head})}
    if reader is not None:
        update["reader"] = reader
    return record.model_copy(update=update)


def _at_head(stand: _Stand, client: TestClient, head: str) -> str:
    """Publish pull request 7 at *head* as a mirror does; its snapshot route's head side."""
    record = read_pull_record(stand.published.home, stand.published.slug, 7)
    assert isinstance(record, PullRecord)
    write_pull_record(
        stand.published.home,
        stand.published.slug,
        _with_head(record, head),
        store_id=stand.published.store_id,
    )
    route = client.get("/api/plugin/github/pull?number=7").json()["snapshot_route"]
    return f"{route}&side=head&path="


def _wire(name: str) -> str:
    return GitPath.from_display(name).to_wire()


def _pairs(stand: _Stand) -> list[tuple[str, str, str]]:
    bindings = read_snapshot_bindings(stand.published.home, stand.published.slug, 7)
    assert bindings is not None
    return [(binding.store, binding.reader, binding.head[:4]) for binding in bindings]


def _admits(stand: _Stand, base: str, head: str) -> Admission:
    return _admission(stand.published, Snapshot(7, base, head, "unused", "head"), None)


def test_a_new_head_keeps_the_old_link_until_sixteen_newer_pairs(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    home, slug, store = stand.published.home, stand.published.slug, stand.published.store_id
    first = stand.refresh(7)
    assert first.comparison is not None
    old = client.get("/api/plugin/github/pull?number=7").json()["snapshot_route"]
    old += "&side=head&path=" + _wire("src/app.txt")
    assert client.get(old).status_code == 200
    # The pull request's head moves on GitHub and a refresh reads it.
    earlier = stand.origin["fork_earlier"]
    _move_pull_head(stand, earlier)
    stand.answer(_answering_head(stand, earlier))
    moved = stand.refresh(7)
    assert moved.comparison is not None and moved.comparison.head == earlier
    stand.calls()
    new = client.get("/api/plugin/github/pull?number=7").json()["snapshot_route"]
    new += "&side=head&path=" + _wire("src/app.txt")
    assert new != old
    assert client.get(old).status_code == client.get(new).status_code == 200
    assert client.get(old).text != client.get(new).text
    # Fifteen more pairs fill the history with the old one as its oldest of sixteen.
    for index in range(1, 15):
        write_pull_record(home, slug, _with_head(moved, f"{index:040x}"), store_id=store)
    assert len(_pairs(stand)) == 16 and client.get(old).status_code == 200
    write_pull_record(home, slug, _with_head(moved, f"{15:040x}"), store_id=store)
    expired = client.get(old, headers={"accept": "application/json"})
    assert expired.status_code == 410 and expired.json()["code"] == "snapshot_expired"
    assert client.get(new).status_code == 200
    # Another store's token never opens the pair.
    other = new.replace("store=", "store=0000000000000000&ignored=")
    assert client.get(other, headers={"accept": "application/json"}).status_code == 410
    assert stand.calls() == []


def test_a_reader_change_starts_the_history_over_whatever_its_write_holds(
    stand: _Stand,
) -> None:
    """Review C4: both paths of R2 now end with the old reader's pair refused."""
    home, slug, store = stand.published.home, stand.published.slug, stand.published.store_id
    first = stand.refresh(7)
    assert first.comparison is not None
    base, p0, alice = first.comparison.base, first.comparison.head, first.reader
    assert _admits(stand, base, p0) == "current"
    # Another reader's record without a comparison, then alice's new pair.
    write_pull_record(
        home,
        slug,
        first.model_copy(update={"reader": "gh:bob", "comparison": None}),
        store_id=store,
    )
    assert _pairs(stand) == []
    write_pull_record(home, slug, _with_head(first, "a" * 40, alice), store_id=store)
    assert _pairs(stand) == [(store, alice, "aaaa")]
    assert _admits(stand, base, p0) == "refused"
    # Another reader's record with a comparison, then alice's again.
    write_pull_record(home, slug, first, store_id=store)
    assert _admits(stand, base, "a" * 40) == "retained"
    write_pull_record(home, slug, _with_head(first, "b" * 40, "gh:bob"), store_id=store)
    assert _pairs(stand) == [(store, "gh:bob", "bbbb")]
    write_pull_record(home, slug, _with_head(first, "c" * 40, alice), store_id=store)
    assert _pairs(stand) == [(store, alice, "cccc")]
    assert _admits(stand, base, p0) == "refused"


def test_a_checkout_write_by_another_reader_starts_the_history_over(stand: _Stand) -> None:
    """Review D4: a metadata write, which has no store, also drops another reader's pairs."""
    home, slug, store = stand.published.home, stand.published.slug, stand.published.store_id
    first = stand.refresh(7)
    assert first.comparison is not None
    base, p0, alice = first.comparison.base, first.comparison.head, first.reader
    assert _pairs(stand) == [(store, alice, p0[:4])]
    bob = first.model_copy(update={"reader": "gh:bob", "comparison": None})
    write_pull_record(home, slug, bob, metadata_only=True)
    assert _pairs(stand) == []
    write_pull_record(home, slug, _with_head(first, "a" * 40, alice), store_id=store)
    assert _pairs(stand) == [(store, alice, "aaaa")]
    assert _admits(stand, base, p0) == "refused"
    # The same reader's metadata write keeps them.
    write_pull_record(home, slug, _with_head(first, "a" * 40, alice), metadata_only=True)
    assert _pairs(stand) == [(store, alice, "aaaa")]


def test_a_replaced_pair_stays_with_the_store_that_computed_it(stand: _Stand) -> None:
    """Review C5 (R3): the next store's write does not adopt an earlier store's pair."""
    home, slug = stand.published.home, stand.published.slug
    first = stand.refresh(7)
    assert first.comparison is not None
    (home / source_pull_snapshots(slug, 7)).unlink()
    write_pull_record(home, slug, first, store_id="old-store")
    write_pull_record(home, slug, _with_head(first, "d" * 40), store_id="new-store")
    head = first.comparison.head[:4]
    assert _pairs(stand) == [("old-store", first.reader, head), ("new-store", first.reader, "dddd")]
    # The pair was computed in another store than this server's, so it does not open here.
    assert _admits(stand, first.comparison.base, first.comparison.head) == "refused"


def test_history_is_kept_through_a_transient_failure_and_restarted_from_a_foreign_file(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Review C3 (R1) and A18: a read that fails now changes nothing, and says so."""
    home, slug, store = stand.published.home, stand.published.slug, stand.published.store_id
    first = stand.refresh(7)
    assert first.comparison is not None
    base, p0 = first.comparison.base, first.comparison.head
    for head in ("1" * 40, "2" * 40):
        write_pull_record(home, slug, _with_head(first, head), store_id=store)
    real = pull_snapshot_cache.read_bytes_bounded
    calls = 0

    def failing_once(*args: Any, **kwargs: Any) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError(errno.EIO, "transient I/O error")
        return real(*args, **kwargs)

    caplog.set_level(logging.DEBUG, logger="metabrowser.builtin_plugins.github")
    with monkeypatch.context() as patch:
        patch.setattr(pull_snapshot_cache, "read_bytes_bounded", failing_once)
        write_pull_record(home, slug, _with_head(first, "3" * 40), store_id=store)
    assert [pair[2] for pair in _pairs(stand)] == [p0[:4], "1111", "2222", "3333"]
    assert _admits(stand, base, p0) == "retained"
    assert "could not keep pull request 7's revision history" in caplog.text
    # A file this format never writes is started over, with the pair it replaces.
    (home / source_pull_snapshots(slug, 7)).write_text('{"version": 2, "pairs": []}')
    write_pull_record(home, slug, _with_head(first, "4" * 40), store_id=store)
    assert [pair[2] for pair in _pairs(stand)] == ["3333", "4444"]
    assert "discarding pull request 7's revision history" in caplog.text
    # One that cannot be opened now, such as a symbolic link, stays as it is.
    history = home / source_pull_snapshots(slug, 7)
    kept = history.with_name("kept.json")
    history.rename(kept)
    history.symlink_to(kept.name)
    write_pull_record(home, slug, _with_head(first, "5" * 40), store_id=store)
    assert history.is_symlink()
    assert read_snapshot_bindings(home, slug, 7) is None
    assert _admits(stand, base, "4" * 40) == "unknown"
    assert read_pull_record(home, slug, 7) == _with_head(first, "5" * 40)


def test_undecided_admission_and_lost_objects_answer_what_the_reader_can_do(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review C7: retry for a check that could not run; gone for a lost earlier commit."""
    stand, client = pinned_pull
    home, slug, store = stand.published.home, stand.published.slug, stand.published.store_id
    record = stand.refresh(7)
    route = client.get("/api/plugin/github/pull?number=7").json()["snapshot_route"]
    address = f"{route}&side=head&path={_wire('src/app.txt')}"
    json_only = {"accept": "application/json"}
    with monkeypatch.context() as patch:
        patch.setattr(pull_snapshot, "_ADMITTED", OrderedDict())
        patch.setattr(pull_snapshot, "read_pull_record", lambda *_a, **_k: "unreadable")
        unknown = client.get(address, headers=json_only)
    assert unknown.status_code == 409 and unknown.json()["code"] == "snapshot_unavailable"
    assert client.get(address).status_code == 200
    # A commit the store does not have: the current pair may come back, a retained one not.
    lost = _at_head(stand, client, "1" * 40) + _wire("src/app.txt")
    missing = client.get(lost, headers=json_only)
    assert missing.status_code == 409 and missing.json()["code"] == "snapshot_objects_unavailable"
    write_pull_record(home, slug, record, store_id=store)
    gone = client.get(lost, headers=json_only)
    assert gone.status_code == 410 and gone.json()["code"] == "snapshot_objects_expired"
    assert client.get(address).status_code == 200


def test_every_response_carries_the_page_policy(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review B2: one exit adds the policy to each status and mode the route answers."""
    stand, client = pinned_pull
    record = stand.refresh(7)
    assert record.comparison is not None
    png = _blob(stand, b"\x89PNG\r\n\x1a\nfixture")
    text = _blob(stand, b"# Notes\n\nPlain.\n")
    binary = _blob(stand, b"\0\xffbytes")
    head = _commit(
        stand,
        record.comparison.head,
        [
            ("100644", "blob", png, "image.png"),
            ("100644", "blob", text, "notes.md"),
            ("100644", "blob", binary, "payload.bin"),
        ],
    )
    at = _at_head(stand, client, head)
    expired = at.replace("store=", "store=0000000000000000&ignored=")
    cases = {
        200: [at + _wire("notes.md"), at + _wire("notes.md") + "&mode=source"],
        400: [at.replace("side=head", "side=middle") + _wire("notes.md")],
        404: [at + _wire("absent.md")],
        410: [expired + _wire("notes.md")],
        415: [at + _wire("notes.md") + "&mode=image"],
        416: [at + _wire("notes.md") + "&mode=source&offset=999"],
    }
    cases[200] += [at + _wire("image.png") + mode for mode in ("", "&mode=image")]
    cases[200] += [at + _wire("payload.bin") + mode for mode in ("", "&mode=download")]
    for status, addresses in cases.items():
        for address in addresses:
            for accept in ("text/html", "application/json"):
                response = client.get(address, headers={"accept": accept})
                assert response.status_code == status, (address, response.text)
                headers = response.headers
                assert headers["content-security-policy"].startswith(
                    "default-src 'none'; script-src 'sha256-"
                ), address
                assert headers["x-content-type-options"] == "nosniff"
                assert headers["cache-control"] == "no-store"
                assert headers["referrer-policy"] == "no-referrer"
    page = client.get(at + _wire("notes.md"))
    scripts = re.findall(r"<script>(.*?)</script>", page.text, re.DOTALL)
    hashes = [
        "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"
        for script in scripts
    ]
    assert len(scripts) == 3 and all(
        value in page.headers["content-security-policy"] for value in hashes
    )
    # The reader's theme, type, and width scripts are the shell's own, after the default
    # the width script reads.
    assert scripts[0].startswith("window.METABROWSER_SETTINGS=")
    assert "MetabrowserDocumentWidth" in scripts[1] and "metabrowser.themeMode" in scripts[2]
    with monkeypatch.context() as patch:
        patch.setattr(GitTreeSource, "max_blob_bytes", property(lambda _source: 4))
        too_large = client.get(at + _wire("payload.bin") + "&mode=download")
    assert too_large.status_code == 413
    assert too_large.headers["content-security-policy"].startswith("default-src 'none'")
    with monkeypatch.context() as patch:
        patch.setattr(pull_snapshot, "_ADMITTED", OrderedDict())
        patch.setattr(pull_snapshot, "read_pull_record", lambda *_a, **_k: "unreadable")
        undecided = client.get(at + _wire("notes.md"))
    assert undecided.status_code == 409 and "Reload the page" in undecided.text
    assert undecided.headers["content-security-policy"].startswith("default-src 'none'")


def test_a_markdown_document_keeps_its_references_in_its_tree(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review A11 and A7, over HTTP: navigation, stylesheets, images, and links."""
    stand, client = pinned_pull
    record = stand.refresh(7)
    assert record.comparison is not None
    png = _blob(stand, b"\x89PNG\r\n\x1a\nfixture")
    svg = _blob(stand, b"<svg xmlns='http://www.w3.org/2000/svg'/>")
    readme = _blob(
        stand,
        b"# Readme\n\nSee [the notes](notes.txt), [the folder](src/), and"
        b" [a section](#readme).\n\n![logo](logo.png) ![again](logo.png)"
        b" ![diagram](diagram.svg)\n",
    )
    notes = _blob(stand, b"notes\n")
    head = _commit(
        stand,
        record.comparison.head,
        [
            ("100644", "blob", readme, "README.md"),
            ("100644", "blob", png, "logo.png"),
            ("100644", "blob", svg, "diagram.svg"),
            ("100644", "blob", notes, "notes.txt"),
        ],
    )
    at = _at_head(stand, client, head)
    monkeypatch.setattr(pull_snapshot, "_DOCUMENT_IMAGES", 1)
    page = client.get(at + _wire("README.md"))
    assert page.status_code == 200, page.text
    html = page.text
    nav = html.split('<nav aria-label="Revision file">', 1)[1].split("</nav>", 1)[0]
    assert ">Document</a>" in nav and 'aria-current="page">Document' in nav
    assert "mode=source" in nav and "Pull request #7 Changes" in nav
    stylesheets = re.findall(r'<link rel="stylesheet" href="([^"]+)"', html)
    assert stylesheets[:2] == ["/static/styles.css", "/plugin-static/github/pull-snapshot.css"]
    assert stylesheets[2:] and all(href.startswith("/kpress-static/") for href in stylesheets[2:])
    content = html.split('<article class="pull-snapshot-content">', 1)[1]
    logo = escape(
        Snapshot(7, record.comparison.base, head, "", "head")
        .href(GitPath.from_display("logo.png"), "image")
        .split("&side=", 1)[1]
    )
    # The first image stays an image; the second, past the cap, is a link to its page.
    assert content.count("<img ") == 1 and logo in content
    assert re.search(
        r'<a href="[^"]*path=' + _wire("logo.png") + r'&amp;mode=document">again</a>', content
    )
    # An SVG is a document, so it is a link to its own page, not a picture.
    assert re.search(
        r'<a href="[^"]*path=' + _wire("diagram.svg") + r'&amp;mode=document">diagram</a>', content
    )
    assert "mode=document" in content and _wire("notes.txt") in content
    # A folder's link keeps its text and names nothing this route could open.
    assert "<a>the folder</a>" in content
    assert 'href="#user-content-readme"' in content
    source = client.get(at + _wire("README.md") + "&mode=source").text
    assert 'aria-current="page">Source' in source and "![logo](logo.png)" in source
    # A document with more `[` than the render budget opens as its Source.
    monkeypatch.setattr(pull_snapshot, "_DOCUMENT_OPENERS", 5)
    over = client.get(at + _wire("README.md")).text
    assert "<pre><code># Readme" in over and ">Document</a>" not in over


def test_folders_links_and_submodules_say_what_they_are(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    """Review A7: only a missing path is absent."""
    stand, client = pinned_pull
    record = stand.refresh(7)
    assert record.comparison is not None
    target = _blob(stand, b"src/app.txt")
    folder = _git(stand, "rev-parse", f"{record.comparison.head}^{{tree}}")
    head = _commit(
        stand,
        record.comparison.head,
        [
            ("040000", "tree", folder, "folder"),
            ("120000", "blob", target, "link"),
            ("160000", "commit", record.comparison.head, "module"),
        ],
    )
    at = _at_head(stand, client, head)
    said = {}
    for name in ("folder", "link", "module", "absent"):
        answer = client.get(at + _wire(name), headers={"accept": "application/json"})
        assert answer.status_code == 404
        said[name] = (answer.json()["code"], answer.json()["message"])
    assert said == {
        "folder": ("not_a_file", "This path is a folder at this revision."),
        "link": (
            "not_a_file",
            "This path is a symbolic link, which revision files do not follow at this revision.",
        ),
        "module": ("not_a_file", "This path is a submodule at this revision."),
        "absent": ("file_not_found", "This file is absent at this revision."),
    }


def test_source_windows_end_on_characters_and_say_where_a_preview_stops(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review A13 (R4, R5), at the real window size, and C6 (R6)."""
    stand, client = pinned_pull
    record = stand.refresh(7)
    assert record.comparison is not None
    window = pull_snapshot._SOURCE_BYTES  # pyright: ignore[reportPrivateUsage]
    accented = _blob(stand, b"a" * (window - 1) + "é".encode() + b"b" * 10)
    lines = _blob(stand, b"".join(b"line %04d\n" % index for index in range(20)))
    binary = _blob(stand, b"\0\xff" * 40000)
    head = _commit(
        stand,
        record.comparison.head,
        [
            ("100644", "blob", accented, "accented.txt"),
            ("100644", "blob", lines, "lines.txt"),
            ("100644", "blob", binary, "payload.bin"),
            ("100644", "blob", binary, "résumé.bin"),
        ],
    )
    at = _at_head(stand, client, head) + _wire("accented.txt") + "&mode=source"

    def body(page: str) -> str:
        return unescape(page.split("<pre><code>", 1)[1].split("</code></pre>", 1)[0])

    first = client.get(at).text
    assert body(first) == "a" * (window - 1)
    assert f"offset={window - 1}" in first
    second = client.get(f"{at}&offset={window - 1}").text
    assert body(second) == "é" + "b" * 10 and "Next bytes" not in second
    # An address inside a character opens at the character's first byte.
    assert body(client.get(f"{at}&offset={window}").text) == "é" + "b" * 10
    # A window that is not the file's last ends after a line.
    monkeypatch.setattr(pull_snapshot, "_SOURCE_BYTES", 25)
    lined = client.get(_at_head(stand, client, head) + _wire("lines.txt") + "&mode=source").text
    assert body(lined) == "line 0000\nline 0001\n" and "offset=20" in lined
    # What a file is follows from its first bytes, at every offset.
    binary_at = _at_head(stand, client, head) + _wire("payload.bin") + "&mode=source"
    assert "Binary file." in client.get(binary_at).text
    assert "Binary file." in client.get(binary_at + "&offset=2").text
    # A download is saved under the file's name.
    download = client.get(_at_head(stand, client, head) + _wire("résumé.bin") + "&mode=download")
    assert download.headers["content-disposition"] == (
        "attachment; filename=\"r_sum_.bin\"; filename*=UTF-8''r%C3%A9sum%C3%A9.bin"
    )


def test_a_pages_images_repeat_no_record_read_or_revision_resolution(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review B1 and A15: the images of one page pay admission and resolution once."""
    stand, client = pinned_pull
    record = stand.refresh(7)
    assert record.comparison is not None
    png = _blob(stand, b"\x89PNG\r\n\x1a\nfixture")
    head = _commit(stand, record.comparison.head, [("100644", "blob", png, "logo.png")])
    image = _at_head(stand, client, head) + _wire("logo.png") + "&mode=image"
    reads, opens = [], []
    read, open_revision = pull_snapshot.read_pull_record, pull_snapshot.open_revision

    def counted_read(*args: Any, **kwargs: Any) -> Any:
        reads.append(1)
        return read(*args, **kwargs)

    async def counted_open(**kwargs: Any) -> Any:
        opens.append(1)
        return await open_revision(**kwargs)

    monkeypatch.setattr(pull_snapshot, "read_pull_record", counted_read)
    monkeypatch.setattr(pull_snapshot, "open_revision", counted_open)
    for _ in range(8):
        answer = client.get(image)
        assert answer.status_code == 200 and answer.content.startswith(b"\x89PNG")
    assert (len(reads), len(opens)) == (1, 1)


_PREFERENCES_RUNNER = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const { scripts, cookie, dark } = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const attributes = {};
const style = {};
const documentElement = {
  setAttribute: (name, value) => { attributes[name] = String(value); },
  style: { setProperty: (name, value) => { style[name] = String(value); } },
};
const sandbox = { document: { cookie, documentElement }, matchMedia: () => ({ matches: dark }) };
sandbox.window = sandbox;
vm.createContext(sandbox);
for (const script of scripts) {
  vm.runInContext(script, sandbox);
}
process.stdout.write(JSON.stringify({ attributes, style }));
"""


@needs_node
def test_the_revision_page_scripts_apply_the_readers_preferences(
    pinned_pull: tuple[_Stand, TestClient], tmp_path: Path
) -> None:
    """Review D1: the page's scripts run in order, without the shell, and set every hook."""
    _, client = pinned_pull
    route = client.get("/api/plugin/github/pull?number=7").json()["snapshot_route"]
    page = client.get(f"{route}&side=head&path={_wire('docs/new.md')}")
    assert page.status_code == 200, page.text
    scripts = re.findall(r"<script>(.*?)</script>", page.text, re.DOTALL)
    # The Markdown sits in the frame whose classes carry the measure and reading font.
    assert '<div class="metabrowser-kpress-host"><article class="kpress kpress-doc' in page.text
    assert '<div class="kpress-prose kpress-long-text">' in page.text
    runner = tmp_path / "preferences.js"
    runner.write_text(_PREFERENCES_RUNNER, encoding="utf-8")
    cases = {
        "defaults": ("", False),
        "system dark": ("", True),
        "chosen": (
            "metabrowser.themeMode=dark; metabrowser.proseFont=sans; "
            "metabrowser.interfaceFont=system; metabrowser.docMaxChars=80",
            False,
        ),
    }
    seen = {}
    for name, (cookie, dark) in cases.items():
        given = tmp_path / f"{name}.json"
        given.write_text(json.dumps({"scripts": scripts, "cookie": cookie, "dark": dark}))
        result = subprocess.run(
            ["node", str(runner), str(given)], capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, result.stderr
        seen[name] = json.loads(result.stdout)
    assert seen["defaults"]["attributes"] == {
        "data-theme-mode": "system",
        "data-theme": "light",
        "data-kpress-resolved-theme": "light",
        "data-prose-font": "serif",
        "data-app-font": "clean",
    }
    assert seen["defaults"]["style"] == {"--doc-max-chars": "102"}
    assert seen["system dark"]["attributes"]["data-theme"] == "dark"
    assert seen["chosen"]["attributes"] == {
        "data-theme-mode": "dark",
        "data-theme": "dark",
        "data-kpress-resolved-theme": "dark",
        "data-prose-font": "sans",
        "data-app-font": "system",
    }
    assert seen["chosen"]["style"] == {"--doc-max-chars": "80"}
