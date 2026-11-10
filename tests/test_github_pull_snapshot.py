"""Exercise the exact revision viewer through the served PR and private cache."""

from __future__ import annotations

from starlette.testclient import TestClient

from metabrowser.builtin_plugins.github.pull_record import write_pull_record
from metabrowser.builtin_plugins.github.pull_snapshot import Snapshot, _render_markdown
from metabrowser.git.tree_source import GitPath
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
    latest = stand.refresh(7)
    assert latest.comparison is not None
    write_pull_record(
        stand.published.home,
        stand.published.slug,
        latest.model_copy(update={"comparison": None}),
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
