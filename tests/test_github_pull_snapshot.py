"""A pull request's revision pairs: which open, the images their rendered Markdown shows,
and the rendered diff that admits them the same way."""

from __future__ import annotations

import errno
import logging
import subprocess
from collections import OrderedDict
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
)
from metabrowser.builtin_plugins.github.pull_snapshot_cache import read_snapshot_bindings
from metabrowser.cache.paths import source_pull_snapshots
from metabrowser.git.tree_source import GitPath, GitTreeSource
from tests.git_pin_harness import git_env
from tests.github_pull_fixture import Origin
from tests.test_github_pulls import (
    _answering_head,  # pyright: ignore[reportPrivateUsage]
    _move_pull_head,  # pyright: ignore[reportPrivateUsage]
    _Stand,
)
from tests.test_github_pulls import pinned_pull as pinned_pull
from tests.test_github_pulls import stand as stand

_PNG = b"\x89PNG\r\n\x1a\nfixture"
_JSON_ONLY = {"accept": "application/json"}


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


def _wire(name: str) -> str:
    return GitPath.from_display(name).to_wire()


def _image_route(client: TestClient, number: int = 7) -> str:
    return client.get("/api/plugin/github/pull", params={"number": number}).json()["image_route"]


def _image(route: str, name: str) -> str:
    return f"{route}&path={_wire(name)}"


def _at_head(stand: _Stand, client: TestClient, head: str) -> str:
    """Publish pull request 7 at *head* as a mirror does; its image route."""
    record = read_pull_record(stand.published.home, stand.published.slug, 7)
    assert isinstance(record, PullRecord)
    write_pull_record(
        stand.published.home,
        stand.published.slug,
        _with_head(record, head),
        store_id=stand.published.store_id,
    )
    return _image_route(client)


def _code(client: TestClient, address: str) -> str:
    """What the image route answers *address* with: ``image``, or its refusal's code.

    A text file of an admitted pair is ``unsupported_image``: the pair opened, and its
    head's tree was read.
    """
    answer = client.get(address, headers=_JSON_ONLY)
    return "image" if answer.status_code == 200 else str(answer.json()["code"])


def _pairs(stand: _Stand) -> list[tuple[str, str, str]]:
    bindings = read_snapshot_bindings(stand.published.home, stand.published.slug, 7)
    assert bindings is not None
    return [(binding.store, binding.reader, binding.head[:4]) for binding in bindings]


def _admits(stand: _Stand, base: str, head: str) -> Admission:
    return _admission(stand.published, Snapshot(7, base, head, "unused"), None)


def test_an_image_link_survives_a_record_without_a_comparison(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    envelope = client.get("/api/plugin/github/pull", params={"number": 7}).json()
    route = envelope["image_route"]
    assert route.startswith("/api/plugin/github/pull-image?number=7&")
    assert "snapshot_route" not in envelope
    address = _image(route, "src/app.txt")
    stand.calls()
    answer = client.get(address)
    assert answer.status_code == 415, answer.text
    assert answer.json()["code"] == "unsupported_image"
    assert answer.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert answer.headers["cache-control"] == "no-store"
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
    assert _code(client, address) == "unsupported_image"
    assert (
        client.get("/api/plugin/github/pull", params={"number": 7}).json()["pin"] == envelope["pin"]
    )
    store = route.split("store=", 1)[1].split("&", 1)[0]
    refused = client.get(
        "/api/plugin/github/pull-image",
        params={
            "number": 7,
            "left": "0" * 40,
            "right": envelope["pin"],
            "store": store,
            "path": _wire("src/app.txt"),
        },
    )
    assert refused.status_code == 410
    assert refused.json()["code"] == "snapshot_expired"
    assert stand.calls() == []


def test_references_stay_in_the_heads_tree() -> None:
    """A rendered file's image is on the image route; its link is the head's ``/view/``
    address, which the page keeps only while it shows the head; nothing leaves the tree."""

    snapshot = Snapshot(7, "a" * 40, "b" * 40, "test")
    source = GitPath.from_display("docs/readme.md")
    route = "/api/plugin/github/pull-image?number=7&left=" + "a" * 40 + "&right=" + "b" * 40
    assert snapshot.reference(source, "../assets/image.png", True) == (
        f"{route}&store=test&path={_wire('assets/image.png').replace('/', '%2F')}"
    )
    assert snapshot.reference(source, "../guide.md", False) == "/view/" + _wire("guide.md")
    assert snapshot.reference(source, "notes.md#Setup Steps", False) == (
        "/view/" + _wire("docs/notes.md") + "#user-content-Setup%20Steps"
    )
    assert snapshot.reference(source, "#topic", False) == "#topic"
    assert snapshot.reference(source, "?plain=1", False) == "/view/" + _wire("docs/readme.md")
    for href, image in (
        ("../../outside.md", False),
        ("../", False),
        ("diagram.svg", True),
        ("https://example.org/x.png", True),
        ("//example.org/x", False),
    ):
        assert snapshot.reference(source, href, image) is None, href


def test_an_image_keeps_its_type_and_nothing_else_is_served(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    record = stand.refresh(7)
    assert record.comparison is not None
    png = _blob(stand, _PNG)
    svg = _blob(stand, b"<svg xmlns='http://www.w3.org/2000/svg'/>")
    binary = _blob(stand, b"\0\xffbytes")
    head = _commit(
        stand,
        record.comparison.head,
        [
            ("100644", "blob", png, "image.png"),
            ("100644", "blob", svg, "diagram.svg"),
            ("100644", "blob", binary, "payload.bin"),
        ],
    )
    route = _at_head(stand, client, head)
    asset = client.get(_image(route, "image.png"))
    assert asset.headers["content-type"] == "image/png" and asset.content == _PNG
    assert asset.headers["x-content-type-options"] == "nosniff"
    assert asset.headers["referrer-policy"] == "no-referrer"
    for name in ("diagram.svg", "payload.bin"):
        assert _code(client, _image(route, name)) == "unsupported_image", name
    for address in (
        route + "&path=",
        # A segment that names the parent, `..`, in its wire form.
        route + "&path=" + _wire("a") + "/g1-Li4",
        route.replace("number=7", "number=x") + "&path=" + _wire("image.png"),
        route.replace(f"right={head}", "right=HEAD") + "&path=" + _wire("image.png"),
    ):
        refused = client.get(address)
        assert refused.status_code == 400, address
        assert refused.json() == {
            "code": "invalid_image",
            "message": "This image address is invalid.",
        }
        assert refused.headers["cache-control"] == "no-store"


# ── History and admission ───────────────────────────────────────


def test_a_new_head_keeps_the_old_link_until_sixteen_newer_pairs(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    home, slug, store = stand.published.home, stand.published.slug, stand.published.store_id
    first = stand.refresh(7)
    assert first.comparison is not None
    old = _image(_image_route(client), "src/app.txt")
    assert _code(client, old) == "unsupported_image"
    # The pull request's head moves on GitHub and a refresh reads it.
    earlier = stand.origin["fork_earlier"]
    _move_pull_head(stand, earlier)
    stand.answer(_answering_head(stand, earlier))
    moved = stand.refresh(7)
    assert moved.comparison is not None and moved.comparison.head == earlier
    stand.calls()
    new = _image(_image_route(client), "src/app.txt")
    assert new != old
    assert _code(client, old) == _code(client, new) == "unsupported_image"
    # Fifteen more pairs fill the history with the old one as its oldest of sixteen.
    for index in range(1, 15):
        write_pull_record(home, slug, _with_head(moved, f"{index:040x}"), store_id=store)
    assert len(_pairs(stand)) == 16 and _code(client, old) == "unsupported_image"
    write_pull_record(home, slug, _with_head(moved, f"{15:040x}"), store_id=store)
    expired = client.get(old)
    assert expired.status_code == 410 and expired.json()["code"] == "snapshot_expired"
    assert _code(client, new) == "unsupported_image"
    # Another store's token never opens the pair.
    other = new.replace("store=", "store=0000000000000000&ignored=")
    assert client.get(other).status_code == 410
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
    address = _image(_image_route(client), "src/app.txt")
    with monkeypatch.context() as patch:
        patch.setattr(pull_snapshot, "_ADMITTED", OrderedDict())
        patch.setattr(pull_snapshot, "read_pull_record", lambda *_a, **_k: "unreadable")
        unknown = client.get(address)
    assert unknown.status_code == 409 and unknown.json()["code"] == "snapshot_unavailable"
    assert "Reload the page" in unknown.json()["message"]
    assert unknown.headers["cache-control"] == "no-store"
    assert _code(client, address) == "unsupported_image"
    # A commit the store does not have: the current pair may come back, a retained one not.
    lost = _image(_at_head(stand, client, "1" * 40), "src/app.txt")
    missing = client.get(lost)
    assert missing.status_code == 409 and missing.json()["code"] == "snapshot_objects_unavailable"
    write_pull_record(home, slug, record, store_id=store)
    gone = client.get(lost)
    assert gone.status_code == 410 and gone.json()["code"] == "snapshot_objects_expired"
    assert _code(client, address) == "unsupported_image"


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
            ("120000", "blob", target, "link.png"),
            ("160000", "commit", record.comparison.head, "module"),
        ],
    )
    route = _at_head(stand, client, head)
    said = {}
    for name in ("folder", "link.png", "module", "absent.png"):
        answer = client.get(_image(route, name))
        assert answer.status_code == 404
        said[name] = (answer.json()["code"], answer.json()["message"])
    assert said == {
        "folder": ("not_a_file", "This path is a folder at this revision."),
        "link.png": (
            "not_a_file",
            "This path is a symbolic link, which images do not follow at this revision.",
        ),
        "module": ("not_a_file", "This path is a submodule at this revision."),
        "absent.png": ("file_not_found", "This file is absent at this revision."),
    }


def test_an_image_past_the_blob_bound_is_not_served(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    stand, client = pinned_pull
    record = stand.refresh(7)
    assert record.comparison is not None
    head = _commit(stand, record.comparison.head, [("100644", "blob", _blob(stand, _PNG), "a.png")])
    address = _image(_at_head(stand, client, head), "a.png")
    monkeypatch.setattr(GitTreeSource, "max_blob_bytes", property(lambda _source: 4))
    assert _code(client, address) == "unsupported_image"


def test_a_pages_images_repeat_no_record_read_or_revision_resolution(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review B1 and A15: the images of one page pay admission and resolution once."""
    stand, client = pinned_pull
    record = stand.refresh(7)
    assert record.comparison is not None
    png = _blob(stand, _PNG)
    head = _commit(stand, record.comparison.head, [("100644", "blob", png, "logo.png")])
    image = _image(_at_head(stand, client, head), "logo.png")
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
        assert answer.status_code == 200 and answer.content == _PNG
    assert (len(reads), len(opens)) == (1, 1)


# ── The rendered diff, which admits its pair the same way ────────


def test_rendered_markdown_uses_the_admitted_comparison_and_exact_hunks(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_rendered_diff
    from metabrowser.diff.adapters.base import DiffSourceError
    from metabrowser.git.process import GitError

    stand, client = pinned_pull
    stand.refresh(8)
    envelope = client.get("/api/plugin/github/pull", params={"number": 8}).json()
    route = envelope["comparison_route"]
    source = client.get(route).json()
    file = next(
        change for change in source["manifest"]["files"] if change["new"]["path"] == "docs/guide.md"
    )
    stand.calls()
    assert envelope["rendered_route"].startswith("/api/plugin/github/pull-rendered-diff?number=8&")
    address = f"{envelope['rendered_route']}&file={file['id']}"

    async def missing_object(*_args: object) -> None:
        raise DiffSourceError("unresolved revision") from GitError("object unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(pull_rendered_diff, "_project", missing_object)
        temporary = client.get(address)
    assert temporary.status_code == 409
    assert temporary.json()["code"] == "rendered_objects_unavailable"

    rendered = client.get(address)
    assert rendered.status_code == 200, rendered.text
    answer = rendered.json()
    assert answer["status"] == "ready", answer
    assert answer["version"] == "markdown-diff-v1"
    assert any(block["kind"] == "added" and "More." in block["html"] for block in answer["blocks"])
    assert answer["assets"]["assets"]
    assert stand.calls() == []


def test_rendered_markdown_in_a_checkout_reads_the_head_blob_not_the_working_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """A served checkout's comparison renders the admitted head, whatever is on disk."""

    import json

    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.builtin_plugins.github import pulls
    from metabrowser.cache.urls import GitSource
    from tests.github_pull_fixture import (
        CANONICAL,
        FETCHED_AT,
        clone_checkout,
        files_scenario,
        install_fake_gh,
    )
    from tests.golden_harness import isolate_cli, run_metab
    from tests.test_cli_github_checkout_golden import _after  # pyright: ignore[reportPrivateUsage]

    isolate_cli(tmp_path, monkeypatch)
    checkout_module._RESOLVED.clear()  # pyright: ignore[reportPrivateUsage]
    checkout_module._PULLS.clear()  # pyright: ignore[reportPrivateUsage]
    for name, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)

    def remote_url_for(source: GitSource) -> str:
        return pull_origin.url if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote_url_for)
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    live = checkout / "docs" / "draft.md"
    assert live.read_bytes() == b"# Draft\n", "the checkout is on pull request 10's head"
    live.write_bytes(b"# Draft\n\nOnly the working tree says this.\n")
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"number": 10, "retry": True, "comparison": True}) + "\n")
    fetched = run_metab(
        [str(checkout), "--api", "/api/plugin/github/pull-refresh", "--data", str(request)]
    )
    assert fetched.exit_code == 0, fetched.stderr
    envelope = _after(fetched)
    route = envelope["comparison_route"]
    manifest = run_metab([str(checkout), "--api", route]).payload()["manifest"]
    draft = next(
        change
        for change in manifest["files"]
        if (change["new"] or {}).get("path") == "docs/draft.md"
    )
    rendered = run_metab(
        [str(checkout), "--api", f"{envelope['rendered_route']}&file={draft['id']}"]
    )
    assert rendered.exit_code == 0, rendered.stderr
    answer = rendered.payload()
    assert answer["status"] == "ready", answer
    assert [block["kind"] for block in answer["blocks"]] == ["added"]
    assert answer["blocks"][0]["html"].startswith("<h1 ")
    assert "Draft" in answer["blocks"][0]["html"]
    assert "working tree" not in json.dumps(answer)
    assert live.read_bytes() == b"# Draft\n\nOnly the working tree says this.\n"


def test_rendered_markdown_past_the_html_cap_is_too_large(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_rendered_diff

    stand, client = pinned_pull
    stand.refresh(8)
    envelope = client.get("/api/plugin/github/pull", params={"number": 8}).json()
    file = next(
        change
        for change in client.get(envelope["comparison_route"]).json()["manifest"]["files"]
        if change["new"]["path"] == "docs/guide.md"
    )
    monkeypatch.setattr(pull_rendered_diff, "_MAX_HTML_BYTES", 8)
    answer = client.get(f"{envelope['rendered_route']}&file={file['id']}").json()
    assert answer == {
        "version": "markdown-diff-v1",
        "status": "too_large",
        "blocks": [],
        "source_only": False,
    }


def _guide_address(stand: _Stand, client: TestClient) -> str:
    """The rendered route's address for ``docs/guide.md`` of pull request 8."""

    stand.refresh(8)
    envelope = client.get("/api/plugin/github/pull", params={"number": 8}).json()
    file = next(
        change
        for change in client.get(envelope["comparison_route"]).json()["manifest"]["files"]
        if change["new"]["path"] == "docs/guide.md"
    )
    return f"{envelope['rendered_route']}&file={file['id']}"


def test_a_markdown_pair_past_the_read_bound_is_too_large(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The route reads a Markdown pair past what a thread projects, up to its own bound."""

    from metabrowser.builtin_plugins.github import pull_rendered_diff
    from metabrowser.diff.markdown_projection import MARKDOWN_DIFF_MAX_BYTES

    assert pull_rendered_diff._MARKDOWN_PAIR_MAX_BYTES > MARKDOWN_DIFF_MAX_BYTES  # pyright: ignore[reportPrivateUsage]
    stand, client = pinned_pull
    address = _guide_address(stand, client)
    monkeypatch.setattr(pull_rendered_diff, "_MARKDOWN_PAIR_MAX_BYTES", 8)
    assert client.get(address).json() == {
        "version": "markdown-diff-v1",
        "status": "too_large",
        "blocks": [],
        "source_only": False,
    }


def test_a_file_whose_content_did_not_change_says_so(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_rendered_diff
    from metabrowser.diff.format import FilePatch

    async def no_hunks(_self: object, *_args: object) -> FilePatch:
        # What a rename or a mode change hydrates to.
        return FilePatch(file_id="renamed", hunks=(), truncated=False)

    stand, client = pinned_pull
    address = _guide_address(stand, client)
    monkeypatch.setattr(pull_rendered_diff._Patches, "get", no_hunks)  # pyright: ignore[reportPrivateUsage]
    assert client.get(address).json() == {
        "version": "markdown-diff-v1",
        "status": "unsupported",
        "blocks": [],
        "source_only": False,
        "reason": "no_changes",
    }


def test_a_projection_the_child_could_not_finish_is_not_kept_as_the_files_answer(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pair no child could run is asked again at once, and one the child was stopped on
    after a while: neither is the pair's own answer, which the route keeps (mb-rm40)."""

    from metabrowser.builtin_plugins.github import pull_rendered_diff
    from metabrowser.diff.markdown_projection import (
        MarkdownRefusal,
        PreparedMarkdownDiff,
        unavailable_markdown_diff,
    )
    from metabrowser.diff.markdown_projection_worker import ProjectionWorker

    refusing: list[MarkdownRefusal | None] = []
    asked: list[str] = []

    class Scripted(ProjectionWorker):
        async def prepare(self, **pair: Any) -> PreparedMarkdownDiff:
            asked.append("asked")
            if refusing:
                return unavailable_markdown_diff("too_large", refusing.pop(0))
            return await super().prepare(**pair)

    now = [1_000.0]
    monkeypatch.setattr(pull_rendered_diff, "monotonic", lambda: now[0])
    stand, client = pinned_pull
    address = _guide_address(stand, client)
    application: Any = client.app
    monkeypatch.setattr(
        application.state, "pull_rendered_diff_worker", Scripted(processes=False), raising=False
    )

    # Process peak RSS includes earlier requests: even this same pair can succeed on retry.
    refusing.append("memory")
    assert client.get(address).json()["reason"] == "memory"

    # No child could run it: the thread's budget refuses, and the next request asks again.
    refusing.append(None)
    unavailable = client.get(address).json()
    assert (unavailable["status"], "reason" in unavailable) == ("too_large", False)
    assert client.get(address).json()["status"] == "ready"
    assert asked == ["asked", "asked", "asked"]
    asked.clear()

    # Stopped at the deadline: refused without asking the child again, for a while. The
    # answer kept above is dropped first, as a server that had none would stand.
    monkeypatch.setattr(application.state, "pull_rendered_diff_cache", None, raising=False)
    refusing.append("deadline")
    stopped = {
        "version": "markdown-diff-v1",
        "status": "too_large",
        "blocks": [],
        "source_only": False,
        "reason": "deadline",
    }
    assert client.get(address).json() == stopped
    now[0] += pull_rendered_diff._STOPPED_TTL_S - 1  # pyright: ignore[reportPrivateUsage]
    assert client.get(address).json() == stopped
    assert asked == ["asked"], "the child is not asked again yet"
    now[0] += 2
    assert client.get(address).json()["status"] == "ready"
    assert asked == ["asked", "asked"]


def test_one_git_diff_hydrates_the_markdown_files_after_the_one_asked_for() -> None:
    import asyncio
    from types import SimpleNamespace
    from typing import cast

    from metabrowser.builtin_plugins.github import pull_rendered_diff
    from metabrowser.diff.format import Availability, ContentRefKind, EntryType, FilePatch

    def change(file_id: str, path: str, changed: int | None = 4) -> Any:
        side = SimpleNamespace(
            entry_type=EntryType.file,
            content=SimpleNamespace(kind=ContentRefKind.git_object),
            path=path,
            path_b64=None,
        )
        return SimpleNamespace(
            id=file_id,
            availability=Availability.ready,
            binary=False,
            old=side,
            new=side,
            additions=changed,
            deletions=None if changed is None else 0,
        )

    files = [change(f"f{index}", f"docs/{index}.md") for index in range(20)]
    files.insert(3, change("code", "src/app.py"))
    # A rewrite past what a projection answers, and a file whose lines nobody counted.
    files.insert(5, change("rewrite", "docs/rewrite.md", changed=8_000))
    files.insert(6, change("uncounted", "docs/uncounted.md", changed=None))
    asked: list[list[str]] = []

    class Source:
        async def hydrate(self, _resolved: object, ids: list[str], *, manifest: object) -> Any:
            asked.append(list(ids))
            return SimpleNamespace(
                patches={each: FilePatch(file_id=each, hunks=(), truncated=False) for each in ids}
            )

    patches = pull_rendered_diff._Patches()  # pyright: ignore[reportPrivateUsage]
    manifest = cast("Any", SimpleNamespace(files=files))

    async def run() -> None:
        for file_id in ("f0", "f1", "f5", "f15", "f16"):
            patch = await patches.get(
                ("store", "a", "b"), cast("Any", Source()), None, manifest, file_id
            )
            assert patch is not None and patch.file_id == file_id

    asyncio.run(run())
    assert asked[0] == [f"f{index}" for index in range(16)], (
        "sixteen small Markdown files; code, a large rewrite and an uncounted file skipped"
    )
    assert asked[1:] == [["f16", "f17", "f18", "f19"]]
    assert "rewrite" not in {file_id for batch in asked for file_id in batch}


def test_a_request_ahead_of_changes_starts_the_projection_process(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.diff.markdown_projection_worker import ProjectionWorker

    starts: list[str] = []

    class Recording(ProjectionWorker):
        def start(self, *, renders: bool = False) -> None:
            starts.append("renders" if renders else "start")

    stand, client = pinned_pull
    stand.refresh(8)
    envelope = client.get("/api/plugin/github/pull", params={"number": 8}).json()
    file = next(
        change
        for change in client.get(envelope["comparison_route"]).json()["manifest"]["files"]
        if change["new"]["path"] == "docs/guide.md"
    )
    application: Any = client.app
    # The served app is the process's own, so a worker set on it without monkeypatch
    # would answer every later in-process request on this xdist worker, `metab --api`
    # runs included, with a child that never starts.
    monkeypatch.setattr(
        application.state, "pull_rendered_diff_worker", Recording(processes=False), raising=False
    )
    address = f"{envelope['rendered_route']}&file={file['id']}"
    assert client.get(address).json()["status"] == "ready"
    assert starts == [], "one request does not start a child"
    assert client.get(f"{address}&prefetch=1").json()["status"] == "ready"
    assert starts == ["start"]


def test_the_rendered_route_answers_an_undecided_pair_and_a_busy_slot(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_rendered_diff

    stand, client = pinned_pull
    stand.refresh(8)
    envelope = client.get("/api/plugin/github/pull", params={"number": 8}).json()
    file = next(
        change
        for change in client.get(envelope["comparison_route"]).json()["manifest"]["files"]
        if change["new"]["path"] == "docs/guide.md"
    )
    address = f"{envelope['rendered_route']}&file={file['id']}"
    with monkeypatch.context() as patch:
        patch.setattr(pull_snapshot, "_ADMITTED", OrderedDict())
        patch.setattr(pull_snapshot, "read_pull_record", lambda *_a, **_k: "unreadable")
        undecided = client.get(address)
    assert undecided.status_code == 409
    assert undecided.json() == {"code": "snapshot_unavailable"}
    assert undecided.headers["cache-control"] == "no-store"

    class Busy:
        async def run(self, _load: object) -> object:
            raise pull_rendered_diff._Busy  # pyright: ignore[reportPrivateUsage]

    application: Any = client.app
    # The app outlives this test, so the stand-in slot is removed after it.
    monkeypatch.setattr(application.state, "pull_rendered_diff_slot", Busy(), raising=False)
    busy = client.get(address)
    assert busy.status_code == 429
    assert busy.json() == {"code": "rendered_diff_busy"}


def test_the_projection_slot_runs_one_load_keeps_four_waiting_and_refuses_the_rest() -> None:
    import asyncio

    from metabrowser.builtin_plugins.github import pull_rendered_diff

    slot = pull_rendered_diff._Slot()  # pyright: ignore[reportPrivateUsage]
    busy = pull_rendered_diff._Busy  # pyright: ignore[reportPrivateUsage]

    async def run() -> None:
        gate = asyncio.Event()
        running: list[int] = []
        finished: list[int] = []

        async def load(index: int) -> int:
            running.append(index)
            assert len(running) - len(finished) == 1, "one load at a time"
            await gate.wait()
            finished.append(index)
            return index

        tasks = [
            asyncio.create_task(slot.run(lambda index=index: load(index))) for index in range(5)
        ]
        await asyncio.sleep(0.01)
        assert running == [0], "one runs and four wait"
        with pytest.raises(busy):
            await slot.run(lambda: load(99))
        tasks[2].cancel()
        await asyncio.sleep(0.01)
        late = asyncio.create_task(slot.run(lambda: load(5)))
        await asyncio.sleep(0.01)
        assert not late.done(), "a cancelled waiter's place goes to the next"
        gate.set()
        results = await asyncio.gather(*tasks, late, return_exceptions=True)
        assert results[:2] == [0, 1] and results[3:] == [3, 4, 5]
        assert isinstance(results[2], asyncio.CancelledError)
        assert finished == [0, 1, 3, 4, 5]

    asyncio.run(run())


def test_kept_patches_are_bounded_by_their_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    from metabrowser.builtin_plugins.github import pull_rendered_diff
    from metabrowser.diff.format import FilePatch, Hunk, LineOp, LineRecord

    monkeypatch.setattr(pull_rendered_diff, "_KEPT_LINES", 10)
    patches = pull_rendered_diff._Patches()  # pyright: ignore[reportPrivateUsage]

    def patch(lines: int) -> FilePatch:
        records = tuple(LineRecord(op=LineOp.add, text="x") for _ in range(lines))
        hunk = Hunk(old_start=0, old_count=0, new_start=1, new_count=lines, lines=records)
        return FilePatch(file_id="f", hunks=(hunk,), truncated=False)

    for index in range(5):
        patches._keep(("k", str(index)), patch(4))  # pyright: ignore[reportPrivateUsage]
    assert list(patches._kept) == [("k", "3"), ("k", "4")]  # pyright: ignore[reportPrivateUsage]
    assert patches._lines == 8  # pyright: ignore[reportPrivateUsage]
