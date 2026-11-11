"""Exercise the exact revision viewer through the served PR and private cache."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser.builtin_plugins.github.pull_record import write_pull_record
from metabrowser.builtin_plugins.github.pull_snapshot import Snapshot, _render_markdown
from metabrowser.git.tree_source import GitPath
from tests.git_pin_harness import git_env
from tests.github_pull_fixture import Origin
from tests.test_github_pulls import _Stand
from tests.test_github_pulls import pinned_pull as pinned_pull
from tests.test_github_pulls import stand as stand


def test_revision_file_link_stays_on_its_side_after_the_record_advances(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    envelope = client.get("/api/plugin/github/pull", params={"number": 7}).json()
    route = envelope["comparison_route"]
    query = route.split("?", 1)[1]
    address = "/api/plugin/github/pull-snapshot?" + query
    path = GitPath.from_display("src/app.txt").to_wire()
    stand.calls()
    head = client.get(f"{address}&side=head&path={path}")
    base = client.get(f"{address}&side=base&path={path}")
    assert head.status_code == base.status_code == 200, (head.text, base.text)
    assert head.text != base.text
    assert envelope["pin"] in head.text
    assert "default-src 'none'" in head.headers["content-security-policy"]
    assert head.headers["cache-control"] == "no-store"
    assert "/plugin-static/github/pull-snapshot.css" in head.text
    assert client.get("/plugin-static/github/pull-snapshot.css").status_code == 200
    latest = stand.refresh(7)
    assert latest.comparison is not None
    from metabrowser.builtin_plugins.github.pull_snapshot_cache import (
        _path,  # pyright: ignore[reportPrivateUsage]
    )

    (stand.published.home / _path(stand.published.slug, 7)).unlink()
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
            "store": query.split("store=", 1)[1],
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
    address = f"{route}&rendered_file={file['id']}"

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
    route = client.get("/api/plugin/github/pull?number=7").json()["comparison_route"]
    address = "/api/plugin/github/pull-snapshot?" + route.split("?", 1)[1] + "&side=head&path="
    picture = address + GitPath.from_display("image.png").to_wire()
    source = address + GitPath.from_display("payload.bin").to_wire()
    preview = client.get(picture)
    assert preview.status_code == 200 and "<img src=" in preview.text
    asset = client.get(picture + "&mode=image")
    assert asset.headers["content-type"] == "image/png" and asset.content == image
    assert "Binary file." in client.get(source).text
    download = client.get(source + "&mode=download")
    assert download.headers["content-disposition"] == "attachment"
    assert download.content == binary
    outside = client.get(
        source + "&mode=source&offset=100000000", headers={"accept": "application/json"}
    )
    assert outside.status_code == 416


def test_revision_source_offset_is_bounded_below_eof(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.git.tree_source import GitTreeSource

    _, client = pinned_pull
    route = client.get("/api/plugin/github/pull?number=7").json()["comparison_route"]
    query = route.split("?", 1)[1]
    path = GitPath.from_display("src/app.txt").to_wire()
    address = f"/api/plugin/github/pull-snapshot?{query}&side=head&mode=source&path={path}"
    monkeypatch.setattr(GitTreeSource, "max_blob_bytes", property(lambda _source: 4))
    preview = client.get(address)
    assert preview.status_code == 200 and "Next bytes" not in preview.text
    refused = client.get(address + "&offset=5", headers={"accept": "application/json"})
    assert refused.status_code == 416 and refused.json()["code"] == "invalid_offset"


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
    route = _after(fetched)["comparison_route"]
    manifest = run_metab([str(checkout), "--api", route]).payload()["manifest"]
    draft = next(
        change
        for change in manifest["files"]
        if (change["new"] or {}).get("path") == "docs/draft.md"
    )
    rendered = run_metab([str(checkout), "--api", f"{route}&rendered_file={draft['id']}"])
    assert rendered.exit_code == 0, rendered.stderr
    answer = rendered.payload()
    assert answer["status"] == "ready", answer
    assert [block["kind"] for block in answer["blocks"]] == ["added"]
    assert answer["blocks"][0]["html"].startswith("<h1 ")
    assert "Draft" in answer["blocks"][0]["html"]
    assert "working tree" not in json.dumps(answer)
    assert live.read_bytes() == b"# Draft\n\nOnly the working tree says this.\n"
