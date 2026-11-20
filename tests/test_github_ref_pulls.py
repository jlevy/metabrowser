"""The pull requests of a branch, from the cached catalog, for the ref chooser's rows.

``source_refs`` lists them on each row of ``GET /api/source/refs`` and lets the filter find
a branch by its pull request (``tests/test_source_refs.py`` holds the route); this holds
what the GitHub provider answers it with: which pull request is a branch's, which of
several comes first, what a filter matches, and that every answer is read from the cache
alone and kept until the catalog moves.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.github import pull_catalog, pull_list, ref_pulls
from metabrowser.builtin_plugins.github.pull_catalog import catalog_heads, read_catalog
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.ref_pulls import ref_pulls_of
from metabrowser.cache.providers import RefPull
from metabrowser.mirror_refresh import MirrorRef
from metabrowser.source_routes import SourceRef, source_refs
from tests.cache_home_fixture import (  # pyright: ignore[reportPrivateUsage]
    FixtureSource,
    _stage_and_publish_source,
    build_empty_home,
)
from tests.github_pull_fixture import CANONICAL, FETCHED_AT, head_item, seed_catalog
from tests.source_checkout_fixture import admit_installed_git, build_checkout, git

SOURCE = FixtureSource("https", CANONICAL)
STAMP = "2026-10-01T12:00:00Z"


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ListedRepository:
    home = tmp_path / "home"
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    return ListedRepository(home, SOURCE.slug, "octo", "demo")


def _seed(repository: ListedRepository, items: list[dict[str, Any]], **kwargs: Any) -> None:
    seed_catalog(repository, items, fetched_at=STAMP, **kwargs)


def _ref(name: str, *, default: bool = False) -> MirrorRef:
    return MirrorRef(name=name, ref=f"refs/remotes/{name}", commit="a" * 40, default=default)


def _numbers(pulls: Any) -> list[int]:
    return [pull["number"] for pull in pulls]


def _pulls_of(row: SourceRef) -> list[RefPull]:
    """A row's pull requests; the key is absent from a row that has none."""

    return row.get("pulls", [])


def test_a_catalog_not_yet_cached_answers_as_absent_and_is_not_ready(
    repository: ListedRepository,
) -> None:
    waiting = ref_pulls_of(repository, refreshing=True)
    assert (waiting.ready, waiting.complete, waiting.refreshing) == (False, False, True)
    assert waiting.pulls("feature") == ()
    assert waiting.matching("anything") == frozenset()
    # What the answer is kept under says the cache is empty and a job is filling it, so the
    # listing is asked for again when the job has written a page.
    assert waiting.token == "absent:1"
    assert ref_pulls_of(repository).token == "absent:0"


def test_a_branch_is_listed_with_the_pull_requests_it_is_the_head_of(
    repository: ListedRepository,
) -> None:
    _seed(
        repository,
        [
            head_item(12, "topic", "Start the topic", state="closed", merged=True),
            head_item(18, "feature", "Try the first design", state="closed"),
            head_item(21, "feature", "feat(ref): choose among branches"),
            head_item(22, "wip", "WIP: the next page", draft=True),
        ],
    )
    found = ref_pulls_of(repository)
    assert found.ready and found.complete and not found.refreshing
    assert found.pulls("topic") == ({"number": 12, "title": "Start the topic", "state": "merged"},)
    assert found.pulls("wip") == ({"number": 22, "title": "WIP: the next page", "state": "draft"},)
    # Open first, though it is the newer here too, and then the closed one.
    assert found.pulls("feature") == (
        {"number": 21, "title": "feat(ref): choose among branches", "state": "open"},
        {"number": 18, "title": "Try the first design", "state": "closed"},
    )
    assert found.pulls("nowhere") == ()


def test_the_open_pull_request_comes_first_even_when_an_older_one(
    repository: ListedRepository,
) -> None:
    _seed(
        repository,
        [
            head_item(5, "again", "Open, and the oldest"),
            head_item(9, "again", "Closed", state="closed"),
            head_item(8, "again", "Merged", state="closed", merged=True),
            head_item(7, "again", "Draft", draft=True),
        ],
    )
    # Open and draft are both open, newest first among them, then the rest newest first.
    assert _numbers(ref_pulls_of(repository).pulls("again")) == [7, 5, 9, 8]


def test_a_forks_branch_is_not_the_repositorys_branch(repository: ListedRepository) -> None:
    _seed(
        repository,
        [
            head_item(30, "feature", "From a fork", head_repository="forker/demo"),
            head_item(31, "feature", "From a deleted fork", head_repository=None),
            head_item(32, "main", "From a fork's main", head_repository="forker/demo"),
            # GitHub's names are not case-sensitive, and the catalog keeps the spelling it was given.
            head_item(33, "feature", "From the repository itself", head_repository="OCTO/Demo"),
        ],
    )
    found = ref_pulls_of(repository)
    assert _numbers(found.pulls("feature")) == [33]
    assert found.pulls("main") == ()
    assert found.matching("fork") == frozenset()


def test_a_filter_matches_a_number_by_its_start_and_a_title_by_every_word(
    repository: ListedRepository,
) -> None:
    _seed(
        repository,
        [
            head_item(12, "alpha", "Draw the Branch list"),
            head_item(120, "beta", "Something else"),
            head_item(21, "gamma", "Branch names in a LIST"),
            head_item(1200, "delta", "Fix #12 in the tab"),
        ],
    )
    found = ref_pulls_of(repository)
    # `#` and digits: the numbers that start with them, and the page's own words are not read.
    assert found.matching("#12") == {"alpha", "beta", "delta"}
    assert found.matching(" #2 ") == {"gamma"}
    # `#` alone is the start of every number: the branches that have a pull request.
    assert found.matching("#") == {"alpha", "beta", "gamma", "delta"}
    # Words: every one of them, in any order, ignoring case.
    assert found.matching("list branch") == {"alpha", "gamma"}
    assert found.matching("LIST") == {"alpha", "gamma"}
    assert found.matching("12") == {"delta"}
    assert found.matching("   ") == frozenset()
    assert found.matching("absent word") == frozenset()


def test_a_filter_puts_the_pull_request_it_matched_first(repository: ListedRepository) -> None:
    _seed(
        repository,
        [
            head_item(40, "feature", "The newest, which says nothing of it"),
            head_item(30, "feature", "Draw the picker"),
            head_item(20, "feature", "Closed picker", state="closed"),
        ],
    )
    found = ref_pulls_of(repository)
    assert _numbers(found.pulls("feature")) == [40, 30, 20]
    assert _numbers(found.pulls("feature", "picker")) == [30, 20, 40]
    assert _numbers(found.pulls("feature", "#4")) == [40, 30, 20]
    assert _numbers(found.pulls("feature", "no such words")) == [40, 30, 20]


def test_the_answer_is_kept_until_the_catalog_moves(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(repository, [head_item(3, "feature", "First")])
    reads: list[Any] = []
    real = pull_catalog.catalog_heads

    def counted(repo: ListedRepository, **kwargs: Any) -> Any:
        found = real(repo, **kwargs)
        reads.append(found.pulls is not None)
        return found

    monkeypatch.setattr(ref_pulls, "catalog_heads", counted)
    first = ref_pulls_of(repository)
    again = ref_pulls_of(repository)
    # The second ask found the revision it held, and read no row.
    assert reads == [True, False]
    assert again.token == first.token
    assert _numbers(again.pulls("feature")) == [3]
    # A page a job writes moves the revision, and the answer follows it.
    _seed(repository, [head_item(3, "feature", "First"), head_item(4, "feature", "Second")])
    moved = ref_pulls_of(repository)
    assert moved.token != first.token
    assert _numbers(moved.pulls("feature")) == [4, 3]
    assert reads == [True, False, True]
    # Whether a job is filling the catalog is part of what the answer is kept under.
    assert ref_pulls_of(repository, refreshing=True).token != moved.token


def test_a_catalog_still_filling_is_not_complete(repository: ListedRepository) -> None:
    _seed(repository, [head_item(3, "feature", "First")], complete=False)
    found = ref_pulls_of(repository, refreshing=True)
    assert (found.ready, found.complete, found.refreshing) == (True, False, True)
    assert _numbers(found.pulls("feature")) == [3]


def test_only_the_newest_rows_are_looked_through(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pull_catalog, "_HEADS_SCAN_ROWS", 3)
    _seed(
        repository,
        [head_item(number, f"branch-{number}", f"Pull {number}") for number in range(1, 6)],
    )
    found = ref_pulls_of(repository)
    assert [(head, bool(found.pulls(head))) for head in ("branch-5", "branch-3", "branch-2")] == [
        ("branch-5", True),
        ("branch-3", True),
        ("branch-2", False),
    ]
    # The oldest were not read, so a branch with none is not known to have none.
    assert found.ready and not found.complete


def test_a_catalog_of_another_repository_is_no_answer(repository: ListedRepository) -> None:
    _seed(repository, [head_item(3, "feature", "First")])
    other = ListedRepository(repository.home, repository.slug, "octo", "other")
    assert catalog_heads(other).state is None
    assert not ref_pulls_of(other).ready


def test_a_catalog_that_cannot_be_read_answers_as_absent(repository: ListedRepository) -> None:
    _seed(repository, [head_item(3, "feature", "First")])
    state = read_catalog(repository.home, repository.slug)
    assert state is not None
    path = repository.home / f"sources/{repository.slug}/pulls/catalog.sqlite3"
    path.write_bytes(b"not a database")
    assert not ref_pulls_of(repository).ready


# The listing joins what the provider answers with the refs the mirror holds.


def test_a_listing_names_a_branchs_pull_requests_and_lets_the_filter_find_it(
    repository: ListedRepository,
) -> None:
    _seed(
        repository,
        [
            head_item(21, "feature", "feat(ref): choose among branches"),
            head_item(18, "feature", "Try the first design", state="closed"),
            head_item(12, "topic", "Start the topic", state="closed", merged=True),
        ],
    )
    found = ref_pulls_of(repository)
    listed = (_ref("topic", default=True), _ref("feature"), _ref("plain"))
    everything = source_refs(listed, None, kind="branch", query="", pulls=found)
    by_name = {row["name"]: row for row in everything["refs"]}
    assert _numbers(_pulls_of(by_name["feature"])) == [21, 18]
    assert _numbers(_pulls_of(by_name["topic"])) == [12]
    # A row with none has no key, so ten thousand branches cost no more for them.
    assert "pulls" not in by_name["plain"]
    assert everything["pull_requests"] == {"state": "ready", "complete": True, "refreshing": False}
    # A name matches as it did; a pull request's number or title matches too, and its row
    # lists the pull request that matched first.
    assert [
        row["name"]
        for row in source_refs(listed, None, kind="branch", query="feat", pulls=found)["refs"]
    ] == ["feature"]
    by_number = source_refs(listed, None, kind="branch", query="#1", pulls=found)
    assert [row["name"] for row in by_number["refs"]] == ["topic", "feature"]
    assert _numbers(_pulls_of(by_number["refs"][1])) == [18, 21]
    by_title = source_refs(listed, None, kind="branch", query="start the", pulls=found)
    assert [row["name"] for row in by_title["refs"]] == ["topic"]
    nothing = source_refs(listed, None, kind="branch", query="zzz", pulls=found)
    assert nothing["refs"] == []


def test_a_checkouts_remote_branches_are_origins_alone(repository: ListedRepository) -> None:
    _seed(repository, [head_item(21, "feature", "From origin's own branch")])
    found = ref_pulls_of(repository)
    listed = (_ref("origin/feature"), _ref("upstream/feature"), _ref("origin/other"))
    remotes = source_refs(listed, None, kind="remote", query="", pulls=found)
    assert [(row["name"], "pulls" in row) for row in remotes["refs"]] == [
        ("origin/feature", True),
        ("upstream/feature", False),
        ("origin/other", False),
    ]
    # A tag is no pull request's head, whatever it is named.
    tags = source_refs((_ref("feature"),), None, kind="tag", query="", pulls=found)
    assert "pulls" not in tags["refs"][0]


def test_a_checkouts_branches_list_the_pull_requests_of_its_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A folder that is a GitHub repository's root lists them as a mirror does."""

    admit_installed_git(monkeypatch)
    sandbox = tmp_path.resolve()
    checkout = build_checkout(sandbox)
    git(checkout, "remote", "set-url", "origin", CANONICAL)
    home = sandbox / "cache-home"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
    monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(sandbox / "config"))
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    seed_catalog(
        ListedRepository(home, SOURCE.slug, "octo", "demo"),
        [
            head_item(21, "feature", "Draw the picker"),
            head_item(30, "topic", "From a fork", head_repository="forker/demo"),
        ],
        fetched_at=STAMP,
    )
    server._set_root_dir(checkout)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:

        def pulls_of(**params: str) -> dict[str, list[int]]:
            listing = client.get("/api/source/refs", params=params).json()
            assert listing["pull_requests"]["state"] == "ready", listing
            return {
                row["name"]: _numbers(row["pulls"]) for row in listing["refs"] if "pulls" in row
            }

        # Its own branch, and origin's remote-tracking one; the fork's `topic` is no one's.
        assert pulls_of() == {"feature": [21]}
        assert pulls_of(kind="remote") == {"origin/feature": [21]}
        assert pulls_of(q="picker") == {"feature": [21]}
        # Served as a revision of itself, the folder is no checkout the plugin resolves, and
        # has no Pulls tab either ("Revisions of a Checkout" in arch-source-sessions-and-pins.md),
        # so its listing has no pull requests, and says so.
        switched = client.post(
            "/api/source/pin",
            json={"ref": "refs/heads/topic"},
            headers={"content-type": "application/json"},
        )
        assert switched.status_code == 200, switched.text
        on_revision = client.get("/api/source/refs").json()
        assert on_revision["pull_requests"] is None
        assert not any("pulls" in row for row in on_revision["refs"])
