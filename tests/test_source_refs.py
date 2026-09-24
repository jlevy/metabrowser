"""``GET /api/source/refs`` and the pin route's ``view``: what the ref selector reads and posts.

The listing is read from a real mirror of a ``file://`` origin: branches in name order
with the default first, tags newest first, a case-insensitive name filter, a clamped
limit, and the served ref marked. A switch that names the page's ``/view/`` address
answers where that page goes on the new pin: the same entry when the revision has it,
else the root. ``tests/golden/cli-api-source.tryscript.md`` pins the envelopes.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.repository_store import open_revision
from metabrowser.git.tree_source import GitPath, GitRevisionSubject
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.source import reset_source_session, serve_subject_opener
from metabrowser.source_routes import REFS_DEFAULT_LIMIT, REFS_MAX_QUERY_CHARS
from tests.test_cache_acquire import _file_source, _git, _git_env
from tests.test_serve_pin import _home, _Origin, _origin, _serve, posix_only

pytestmark = [
    posix_only,
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]

_JSON = {"content-type": "application/json"}


def _wire(display: str) -> str:
    return GitPath.from_display(display).to_wire()


@pytest.fixture(autouse=True)
def _isolated_session(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    yield
    reset_source_session()


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

    ``feature`` and ``Release/v1`` are branches; ``v1`` is an annotated tag of the
    second commit dated later than every commit, ``light`` a lightweight tag of the
    first, and ``tree-tag`` names a tree, which no pin can serve.
    """

    _home(tmp_path, monkeypatch)
    made = _origin(tmp_path)
    work = tmp_path / "work"
    _git(work, "branch", "feature", made.first)
    _git(work, "branch", "Release/v1", made.second)
    _tag_later(work, "v1", made.second)
    _git(work, "tag", "light", made.first)
    _git(work, "update-ref", "refs/tags/tree-tag", f"{made.second}^{{tree}}")
    _git(work, "push", "-q", str(made.path), "feature", "Release/v1", "--tags")
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


def test_branches_list_the_default_first_and_mark_the_served_one(
    served: TestClient, origin: _Origin
) -> None:
    listing = _refs(served)
    assert listing["kind"] == "branch"
    assert listing["limit"] == REFS_DEFAULT_LIMIT
    assert (listing["pin"], listing["ref"]) == (origin.second, "refs/remotes/origin/topic")
    assert [row["name"] for row in listing["refs"]] == ["topic", "Release/v1", "feature"]
    assert (listing["total"], listing["truncated"]) == (3, False)
    topic, release, feature = listing["refs"]
    assert topic == {
        "name": "topic",
        "ref": "refs/remotes/origin/topic",
        "commit": origin.second,
        "default": True,
        "current": True,
    }
    assert (release["default"], release["current"]) == (False, False)
    assert feature["commit"] == origin.first


def test_tags_list_newest_first_and_peel_to_the_commit(served: TestClient, origin: _Origin) -> None:
    listing = _refs(served, kind="tag")
    rows = [(row["name"], row["commit"]) for row in listing["refs"]]
    # The tag of a tree names no commit, so it is not offered.
    assert rows == [("v1", origin.second), ("light", origin.first)]
    assert not any(row["default"] or row["current"] for row in listing["refs"])


def test_the_filter_is_a_case_insensitive_name_fragment_and_the_limit_is_clamped(
    served: TestClient,
) -> None:
    assert [row["name"] for row in _refs(served, q="RELEASE")["refs"]] == ["Release/v1"]
    assert _refs(served, q="nothing-matches")["refs"] == []
    page = _refs(served, limit="1")
    assert ([row["name"] for row in page["refs"]], page["total"], page["truncated"]) == (
        ["topic"],
        3,
        True,
    )
    assert _refs(served, limit="0")["limit"] == 1
    assert _refs(served, limit="many")["limit"] == REFS_DEFAULT_LIMIT


@pytest.mark.parametrize(
    "params",
    [{"kind": "commit"}, {"q": "x" * (REFS_MAX_QUERY_CHARS + 1)}],
)
def test_a_bad_listing_request_is_refused(served: TestClient, params: dict[str, str]) -> None:
    response = served.get("/api/source/refs", params=params)
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


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


def test_a_switch_without_a_view_answers_no_href(served: TestClient) -> None:
    response = served.post("/api/source/pin", json={"ref": "feature"}, headers=_JSON)
    assert response.status_code == 200
    assert "view_href" not in response.json()


# ── The shell ────────────────────────────────────────────────────────


def test_a_mirror_pin_shell_has_the_selector_loaded_on_demand(served: TestClient) -> None:
    shell = served.get("/view/").text
    assert '<div class="source-ref-selector" id="source-ref-selector" hidden></div>' in shell
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
