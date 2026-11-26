"""``GET /api/source/refs`` and the pin route's ``view``: what the ref selector reads and posts.

The listing is read from a real mirror of a ``file://`` origin: every branch and tag, the
default branch first and then newest first by the commit each names, a case-insensitive
name filter, the served ref marked, and an answer kept until a ref moves. A switch that names the page's ``/view/`` address
answers where that page goes on the new pin: the same entry when the revision has it,
else the root. ``tests/golden/cli-api-source.tryscript.md`` pins the envelopes.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.cache import served_mirror
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.paths import store_directory
from metabrowser.cache.providers import RefPull
from metabrowser.cache.repository_store import open_revision
from metabrowser.git.tree_source import GitPath, GitRevisionSubject
from metabrowser.mirror_refresh import mirror_session, serve_mirror
from metabrowser.source import serve_subject_opener
from metabrowser.source_routes import REFS_MAX_QUERY_CHARS
from tests.required_tools import needs_git
from tests.test_cache_acquire import _file_source, _git, _git_env
from tests.test_serve_pin import _home, _Origin, _origin, _serve, posix_only

pytestmark = [
    posix_only,
    needs_git,
]

_JSON = {"content-type": "application/json"}
_PATCH = "--- a/x.txt\n+++ b/x.txt\n@@ -0,0 +1 @@\n+x\n"


def _wire(display: str) -> str:
    return GitPath.from_display(display).to_wire()


@pytest.fixture(autouse=True)
def _no_interrupt_handler(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)


def _tag_later(work: Path, name: str, target: str) -> None:
    """An annotated tag dated after every commit, so tags list in a known order."""

    env = _git_env(work) | {"GIT_COMMITTER_DATE": "2099-01-01T00:00:00Z"}
    subprocess.run(
        ["git", "-C", str(work), "tag", "-a", name, "-m", name, target],
        check=True,
        capture_output=True,
        env=env,
    )


@pytest.fixture
def origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Origin:
    """``topic`` (default) and ``first``/``second`` from the pin fixture, plus more refs.

    ``feature`` and ``Release/v1`` are branches, and ``patches`` adds a patch file,
    a container, to the second commit; ``v1`` is an annotated tag of the second commit
    dated later than every commit, ``light`` a lightweight tag of the first,
    ``nested`` an annotated tag of ``v1``, and ``tree-tag`` names a tree, which no pin
    can serve.
    """

    _home(tmp_path, monkeypatch)
    made = _origin(tmp_path)
    work = tmp_path / "work"
    _git(work, "branch", "feature", made.first)
    _git(work, "branch", "Release/v1", made.second)
    _tag_later(work, "v1", made.second)
    _git(work, "tag", "light", made.first)
    _git(work, "update-ref", "refs/tags/tree-tag", f"{made.second}^{{tree}}")
    _git(work, "tag", "-a", "nested", "-m", "nested", "v1")
    _git(work, "switch", "-q", "-c", "patches", made.second)
    (work / "change.patch").write_text(_PATCH, encoding="utf-8")
    _git(work, "add", "change.patch")
    _git(work, "commit", "-qm", "patch")
    _git(work, "switch", "-q", "topic")
    _git(work, "push", "-q", str(made.path), "feature", "Release/v1", "patches", "--tags")
    _git(work, "push", "-q", str(made.path), "refs/tags/tree-tag")
    return made


@pytest.fixture
def served(origin: _Origin) -> Iterator[TestClient]:
    result = _serve(origin.url)
    assert result.exit_code == 0, result.output
    with TestClient(server.app) as client:
        yield client


def _refs(client: TestClient, **params: str) -> Any:
    response = client.get("/api/source/refs", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _reads_newest_first(rows: list[dict[str, Any]]) -> bool:
    """Whether *rows* are newest first by ``committed_at``, equal dates by name."""

    keys = [(-row["committed_at"], row["name"]) for row in rows]
    return keys == sorted(keys)


def test_branches_list_the_default_first_and_mark_the_served_one(
    served: TestClient, origin: _Origin
) -> None:
    listing = _refs(served)
    assert listing["kind"] == "branch"
    # Every ref is listed: there is no page, so nothing says where one stops.
    assert not {"limit", "total", "truncated"} & listing.keys()
    assert (listing["pin"], listing["ref"]) == (origin.second, "refs/remotes/origin/topic")
    # The default first, then newest first: this fixture's commits are made in real time,
    # so equal dates read by name. test_every_list_reads_newest_first holds the order
    # with dates set apart.
    assert listing["refs"][0]["name"] == "topic"
    assert sorted(row["name"] for row in listing["refs"][1:]) == [
        "Release/v1",
        "feature",
        "patches",
    ]
    assert _reads_newest_first(listing["refs"][1:])
    by_name = {row["name"]: row for row in listing["refs"]}
    topic, release, feature = by_name["topic"], by_name["Release/v1"], by_name["feature"]
    # Each row's commit and the date it was committed, as the origin has it.
    committed = subprocess.run(
        ["git", "-C", str(origin.path), "log", "-1", "--format=%ct", origin.second],
        check=True,
        capture_output=True,
        text=True,
        env=_git_env(origin.path),
    ).stdout
    assert topic.pop("committed_at") == float(committed)
    assert topic == {
        "name": "topic",
        "ref": "refs/remotes/origin/topic",
        "commit": origin.second,
        "default": True,
        "checked_out": False,
        "current": True,
    }
    assert (release["default"], release["current"]) == (False, False)
    assert feature["commit"] == origin.first


def test_tags_list_newest_first_and_peel_to_the_commit(served: TestClient, origin: _Origin) -> None:
    listing = _refs(served, kind="tag")
    rows = {row["name"]: row["commit"] for row in listing["refs"]}
    # The tag of a tree names no commit, and the tag of a tag is not peeled, on any
    # Git version, so neither is offered.
    assert rows == {"v1": origin.second, "light": origin.first}
    # Dated by the commit each names, not by v1's own later tagger date.
    assert _reads_newest_first(listing["refs"])
    assert not any(row["default"] or row["current"] for row in listing["refs"])


def test_a_tag_of_a_tag_is_not_listed_but_pins_by_name(served: TestClient, origin: _Origin) -> None:
    assert "nested" not in [row["name"] for row in _refs(served, kind="tag", q="nest")["refs"]]
    pinned = served.post("/api/source/pin", json={"ref": "nested"}, headers=_JSON)
    assert pinned.status_code == 200
    assert pinned.json()["status"]["pin"] == origin.second


def test_the_filter_is_a_case_insensitive_name_fragment(served: TestClient) -> None:
    assert [row["name"] for row in _refs(served, q="RELEASE")["refs"]] == ["Release/v1"]
    assert _refs(served, q="nothing-matches")["refs"] == []
    # A page size is no input: every match is listed.
    assert len(_refs(served, limit="1")["refs"]) == 4


def _dated_origin(root: Path, branches: int) -> _Origin:
    """A bare origin whose refs' commits are dated apart, and far more branches than a page.

    ``main``, the default, is committed in 2021; ``alpha`` in 2022; ``beta`` and ``zeta``
    on the same second of 2024, so their names decide; and *branches* more, ``bulk-NNN``,
    name ``zeta``'s commit. ``v2`` is a lightweight tag of ``zeta``'s commit, ``v1`` an
    annotated tag of ``alpha``'s, and ``retro`` an annotated tag of the 2020 root commit
    dated after every commit, as a release tagged after the fact is.
    """

    work = root / "dated"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")

    def commit(message: str, date: str) -> str:
        env = _git_env(work) | {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        subprocess.run(
            ["git", "-C", str(work), "commit", "-q", "--allow-empty", "-m", message],
            check=True,
            capture_output=True,
            env=env,
        )
        return subprocess.run(
            ["git", "-C", str(work), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            env=_git_env(work),
        ).stdout.strip()

    (work / "README.md").write_text("# Dated\n", encoding="utf-8")
    _git(work, "add", "README.md")
    root_commit = commit("root", "2020-01-01T00:00:00Z")
    alpha = commit("alpha", "2022-01-01T00:00:00Z")
    late = commit("late", "2024-01-01T00:00:00Z")
    _git(work, "switch", "-q", "--detach", root_commit)
    main = commit("main", "2021-01-01T00:00:00Z")
    lines = [f"update refs/heads/main {main}", f"create refs/heads/alpha {alpha}"]
    lines += [f"create refs/heads/{name} {late}" for name in ("beta", "zeta")]
    lines += [f"create refs/heads/bulk-{at:03d} {late}" for at in range(branches)]
    lines.append(f"create refs/tags/v2 {late}")
    subprocess.run(
        ["git", "-C", str(work), "update-ref", "--stdin"],
        input="\n".join(lines) + "\n",
        check=True,
        capture_output=True,
        text=True,
        env=_git_env(work),
    )
    _git(work, "switch", "-q", "main")
    tagger = _git_env(work) | {"GIT_COMMITTER_DATE": "2022-06-01T00:00:00Z"}
    subprocess.run(
        ["git", "-C", str(work), "tag", "-a", "v1", "-m", "v1", alpha],
        check=True,
        capture_output=True,
        env=tagger,
    )
    _tag_later(work, "retro", root_commit)
    bare = root / "dated.git"
    _git(work, "clone", "--bare", "--template=", "--", str(work), str(bare))
    return _Origin(path=bare, first=root_commit, second=main)


def test_every_list_reads_newest_first_by_the_commit_each_ref_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home(tmp_path, monkeypatch)
    dated = _dated_origin(tmp_path, branches=150)
    result = _serve(dated.url)
    assert result.exit_code == 0, result.output
    with TestClient(server.app) as client:
        branches = [row["name"] for row in _refs(client)["refs"]]
        tags = [row["name"] for row in _refs(client, kind="tag")["refs"]]
        filtered = [row["name"] for row in _refs(client, q="ETA")["refs"]]
    bulk = [f"bulk-{at:03d}" for at in range(150)]
    # The default branch first though it is older; then 2024's commit, whose branches
    # read by name; then 2022's. Every one of 154 branches, more than a page held.
    assert branches == ["main", "beta", *bulk, "zeta", "alpha"]
    # v2 names 2024's commit, v1 2022's, and retro, tagged after every commit, the root
    # of 2020: a tag lists by the commit its row dates, not by when it was made.
    assert tags == ["v2", "v1", "retro"]
    assert filtered == ["beta", "zeta"]


def _store_repository(mirror: object) -> Path:
    assert isinstance(mirror, served_mirror.StoreMirror)
    return mirror.home / store_directory(mirror.store_key) / "repository.git"


def test_a_listing_is_kept_until_a_ref_moves(
    served: TestClient, origin: _Origin, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The listing is one ``for-each-ref``, asked again only once the refs' state moves."""

    listed = served_mirror.list_mirror_refs
    calls: list[str] = []

    async def counted(*args: Any, **kwargs: Any) -> Any:
        calls.append(args[1])
        return await listed(*args, **kwargs)

    monkeypatch.setattr(served_mirror, "list_mirror_refs", counted)
    first = served.get("/api/source/refs")
    again = served.get("/api/source/refs")
    assert (first.status_code, again.status_code, again.content) == (200, 200, first.content)
    assert calls == ["branch"]
    # The entity tag is the Git routes' memo's, so a client that holds it is answered 304.
    tag = again.headers["etag"]
    assert served.get("/api/source/refs", headers={"if-none-match": tag}).status_code == 304
    # Another filter and another list are their own answers.
    _refs(served, q="feat")
    _refs(served, kind="tag")
    assert calls == ["branch", "branch", "tag"]
    # A ref the store moves, as a fetch does, is listed at once.
    mirror = mirror_session(server.app)
    assert mirror is not None
    store = _store_repository(mirror.mirror)
    subprocess.run(
        ["git", "--git-dir", str(store), "update-ref", "refs/remotes/origin/moved", origin.first],
        check=True,
        capture_output=True,
        env=_git_env(store),
    )
    assert "moved" in [row["name"] for row in _refs(served)["refs"]]
    assert calls == ["branch", "branch", "tag", "branch"]


@dataclass
class _Pulls:
    """What a provider answers a listing with: pull requests by head branch, as it holds them."""

    by_head: dict[str, tuple[RefPull, ...]]
    token: str = "one"
    ready: bool = True
    complete: bool = True
    refreshing: bool = False
    asked: list[str] = field(default_factory=list[str])

    def pulls(self, head: str, needle: str = "") -> tuple[RefPull, ...]:
        self.asked.append(head)
        return self.by_head.get(head, ())

    def matching(self, needle: str) -> frozenset[str]:
        return frozenset(
            head
            for head, pulls in self.by_head.items()
            if any(needle.casefold() in pull["title"].casefold() for pull in pulls)
        )


def _provide(monkeypatch: pytest.MonkeyPatch, pulls: _Pulls | None) -> None:
    async def provided(app: object) -> _Pulls | None:
        return pulls

    monkeypatch.setattr("metabrowser.cache.providers.ref_pulls_for", provided)


def test_a_branch_lists_the_pull_requests_it_is_the_head_of(
    served: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pulls = _Pulls(
        {
            "feature": (
                {"number": 21, "title": "Draw the picker", "state": "open"},
                {"number": 18, "title": "An earlier try", "state": "closed"},
            ),
            "Release/v1": ({"number": 9, "title": "Cut the release", "state": "merged"},),
        }
    )
    _provide(monkeypatch, pulls)
    listing = _refs(served)
    by_name = {row["name"]: row for row in listing["refs"]}
    assert [pull["number"] for pull in by_name["feature"]["pulls"]] == [21, 18]
    assert by_name["Release/v1"]["pulls"] == [
        {"number": 9, "title": "Cut the release", "state": "merged"}
    ]
    # A branch that is the head of none has no key, so the listing costs it nothing.
    assert "pulls" not in by_name["topic"]
    assert listing["pull_requests"] == {"state": "ready", "complete": True, "refreshing": False}
    # A tag is no pull request's head: nothing is asked of the provider for one.
    pulls.asked.clear()
    tags = _refs(served, kind="tag")
    assert tags["pull_requests"] is None and not pulls.asked
    assert all("pulls" not in row for row in tags["refs"])


def test_the_filter_finds_a_branch_by_its_pull_request(
    served: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _provide(
        monkeypatch,
        _Pulls({"feature": ({"number": 21, "title": "Draw the picker", "state": "open"},)}),
    )
    # `patches` matches by name and `feature` by its pull request's title: both are listed,
    # in the listing's order, with no name in common.
    assert [row["name"] for row in _refs(served, q="picker")["refs"]] == ["feature"]
    assert [row["name"] for row in _refs(served, q="patch")["refs"]] == ["patches"]
    assert _refs(served, q="nothing-matches")["refs"] == []


def test_a_provider_with_pull_requests_is_asked_for_a_listing_that_follows_its_token(
    served: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pulls = _Pulls({"feature": ({"number": 21, "title": "Draw the picker", "state": "open"},)})
    _provide(monkeypatch, pulls)
    first = served.get("/api/source/refs")
    again = served.get("/api/source/refs")
    assert again.content == first.content
    # Kept: the second ask read no pull request of a row.
    asked = len(pulls.asked)
    assert asked > 0
    served.get("/api/source/refs", headers={"if-none-match": first.headers["etag"]})
    assert len(pulls.asked) == asked
    # The provider's own cache moved, so the listing is made again, from what it holds now.
    pulls.by_head["feature"] = (
        {"number": 22, "title": "Draw the picker", "state": "open"},
        *pulls.by_head["feature"],
    )
    pulls.token = "two"
    moved = served.get("/api/source/refs")
    assert moved.headers["etag"] != first.headers["etag"]
    rows = {row["name"]: row for row in moved.json()["refs"]}
    assert [pull["number"] for pull in rows["feature"]["pulls"]] == [22, 21]
    # And whether the provider is still filling its cache is part of what it was kept under.
    pulls.refreshing = True
    pulls.token = "three"
    assert served.get("/api/source/refs").json()["pull_requests"]["refreshing"] is True


def test_a_provider_that_fails_shows_no_pull_requests_and_the_branches_still_list(
    served: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The pull requests are an addition: a provider that cannot read its cache costs the
    list nothing but them, and the server says why in its log (mb-tjbm review A10)."""

    async def broken(app: object) -> None:
        raise RuntimeError("the catalog is on fire")

    monkeypatch.setattr("metabrowser.cache.providers.ref_pulls_for", broken)
    with caplog.at_level("WARNING", logger="metabrowser.source_routes"):
        listing = _refs(served)
    assert listing["pull_requests"] is None
    assert listing["refs"][0]["name"] == "topic"
    assert "the catalog is on fire" in caplog.text


def test_a_provider_with_nothing_cached_says_so(
    served: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _provide(monkeypatch, _Pulls({}, ready=False, complete=False, refreshing=True))
    listing = _refs(served)
    assert listing["pull_requests"] == {"state": "absent", "complete": False, "refreshing": True}
    assert all("pulls" not in row for row in listing["refs"])


@pytest.mark.parametrize(
    "params",
    [{"kind": "commit"}, {"q": "x" * (REFS_MAX_QUERY_CHARS + 1)}],
)
def test_a_bad_listing_request_is_refused(served: TestClient, params: dict[str, str]) -> None:
    response = served.get("/api/source/refs", params=params)
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


def test_a_mirrors_page_fetch_that_names_no_commit_is_answered(served: TestClient) -> None:
    """The refusal of a nameless page fetch is a checkout's server's, not a mirror's.

    A mirror has no working-tree page whose guard has yet to arrive, so its requests are
    checked only by the commit they name: a worker's, a frame's, or an event stream's,
    which can carry none, is answered as it always was.
    """

    page_fetch = {"sec-fetch-site": "same-origin", "sec-fetch-dest": "empty"}
    assert served.get("/api/tree", headers=page_fetch).status_code == 200
    stale = served.get("/api/tree", headers={**page_fetch, "x-metabrowser-pin": "0" * 40})
    assert (stale.status_code, stale.json()["code"]) == (409, "pin_changed")


def test_a_folder_has_no_refs_to_list(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    with TestClient(server.app) as client:
        response = client.get("/api/source/refs")
    assert response.status_code == 409
    assert response.json()["capability"] == "refs"


def test_a_switch_keeps_the_page_where_the_new_pin_has_it(
    served: TestClient, origin: _Origin
) -> None:
    kept = served.post(
        "/api/source/pin",
        json={"ref": "refs/remotes/origin/feature", "view": f"/view/{_wire('README.md')}"},
        headers=_JSON,
    )
    assert kept.status_code == 200
    assert kept.json()["view_href"] == f"/view/{_wire('README.md')}"
    assert kept.json()["status"]["pin"] == origin.first
    # The listing follows the switch.
    current = [row["name"] for row in _refs(served)["refs"] if row["current"]]
    assert current == ["feature"]
    # A directory keeps its trailing slash; the page's own spelling need not have one.
    folder = served.post(
        "/api/source/pin",
        json={"ref": "topic", "view": f"/view/{_wire('images')}"},
        headers=_JSON,
    )
    assert folder.json()["view_href"] == f"/view/{_wire('images')}/"


@pytest.mark.parametrize(
    "view",
    [
        # data.json arrives in the second commit, so the first does not have it.
        "/view/" + GitPath.from_display("data.json").to_wire(),
        "/view/",
        "/view/not-a-wire",
        "/view/%zz",
    ],
)
def test_a_switch_goes_to_the_root_when_the_new_pin_lacks_the_page(
    served: TestClient, view: str
) -> None:
    response = served.post("/api/source/pin", json={"ref": "feature", "view": view}, headers=_JSON)
    assert response.status_code == 200
    assert response.json()["view_href"] == "/view/"


@pytest.mark.parametrize("view", ["/raw/README.md", 7, "https://example.invalid/view/x"])
def test_a_view_that_is_not_a_view_address_is_refused(served: TestClient, view: object) -> None:
    response = served.post("/api/source/pin", json={"ref": "feature", "view": view}, headers=_JSON)
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_selection"


@pytest.mark.parametrize("view", ["/view/\ud800", "/view/calf\u00e9"])
def test_a_view_that_is_not_a_page_address_is_refused_before_the_switch(
    served: TestClient, origin: _Origin, view: str
) -> None:
    """A page sends percent-encoded ASCII; nothing else may switch and then fail."""

    # Escaped JSON, as a client would send a lone surrogate.
    body = json.dumps({"ref": "feature", "view": view})
    response = served.post("/api/source/pin", content=body, headers=_JSON)
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_selection"
    assert served.get("/api/source/status").json()["pin"] == origin.second


def test_a_query_or_fragment_is_not_kept(served: TestClient) -> None:
    readme = f"/view/{_wire('README.md')}"
    response = served.post(
        "/api/source/pin", json={"ref": "feature", "view": f"{readme}?x=1#L3"}, headers=_JSON
    )
    assert response.json()["view_href"] == readme


def _container_view(inner: str) -> str:
    return f"/view/{_wire('change.patch')}/{inner}"


def test_an_inner_path_is_kept_where_the_new_pin_has_its_container(served: TestClient) -> None:
    kept = served.post(
        "/api/source/pin",
        json={"ref": "patches", "view": _container_view("x%20y.txt") + "?q=1"},
        headers=_JSON,
    )
    assert kept.status_code == 200
    assert kept.json()["view_href"] == _container_view("x%20y.txt")


@pytest.mark.parametrize(
    "view",
    [
        # feature has no change.patch.
        _container_view("x.txt"),
        # A folder is not a container file.
        f"/view/{_wire('images')}/logo.png",
        # Deeper than a container inner path may go.
        _container_view("/".join(["d"] * 17)),
    ],
)
def test_an_inner_path_goes_to_the_root_without_its_container(
    served: TestClient, view: str
) -> None:
    response = served.post("/api/source/pin", json={"ref": "feature", "view": view}, headers=_JSON)
    assert response.status_code == 200
    assert response.json()["view_href"] == "/view/"


def test_a_switch_without_a_view_answers_no_href(served: TestClient) -> None:
    response = served.post("/api/source/pin", json={"ref": "feature"}, headers=_JSON)
    assert response.status_code == 200
    assert "view_href" not in response.json()


# ── The shell ────────────────────────────────────────────────────────


def test_a_mirror_pin_shell_has_the_selector_loaded_on_demand(served: TestClient) -> None:
    shell = served.get("/view/").text
    # First paint reserves a branch chip and a separate chooser above the usual filters.
    assert (
        '<div class="nav-source-ref" id="nav-source-ref">'
        '<div class="source-ref-selector" id="source-ref-selector">'
        '<span class="source-ref-selector-button">'
        '<span class="source-ref-selector-label"><span class="git-ref git-ref-remote">'
        '<span class="git-ref-label">topic</span></span></span>'
        '<button type="button" class="icon-btn source-ref-selector-toggle disclosure-toggle"'
        ' aria-label="Switch branch or tag" aria-haspopup="dialog" aria-expanded="false"'
        ' data-tip-text="Switch branch or tag"></button></span></div></div>'
    ) in shell
    assert shell.index('class="tab-bar nav-tab-bar"') < shell.index('id="nav-source-ref"')
    assert shell.index('id="nav-source-ref"') < shell.index('id="nav-filter-bar"')
    bundles = shell[shell.index("window.METABROWSER_ASSET_BUNDLES=") :]
    bundles = bundles[: bundles.index("</script>")]
    assert '"source-ref-selector": [{"src": "/static/source-ref-selector.js' in bundles
    # On demand, never eager: no blocking script tag names it.
    assert '<script src="/static/source-ref-selector.js' not in shell


def test_a_pin_without_a_mirror_and_a_folder_have_no_selector(
    tmp_path: Path, origin: _Origin
) -> None:
    published = asyncio.run(acquire_source(_file_source(origin.path), home=tmp_path / "home"))

    async def opener() -> GitRevisionSubject:
        return await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=published.default_revision,
            store_identity=published.store_id,
            ref=published.default_remote_ref,
        )

    serve_mirror(None)
    serve_subject_opener(opener)
    with TestClient(server.app) as client:
        pin_shell = client.get("/view/").text
        refs = client.get("/api/source/refs")
    assert 'id="source-freshness"' in pin_shell
    assert 'id="source-ref-selector"' not in pin_shell
    assert refs.status_code == 409
    server._set_root_dir(tmp_path)
    with TestClient(server.app) as client:
        assert 'id="source-ref-selector"' not in client.get("/view/").text
