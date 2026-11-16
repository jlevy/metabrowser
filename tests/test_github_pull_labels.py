"""The repository's cached label set: when it is asked for, what it keeps, and its use.

``pull_labels`` keeps one bounded snapshot of ``repos/<owner>/<repo>/labels``. These
hold when a refresh is wanted (absent, past :data:`LABEL_FRESHNESS_S`, or a name it does
not hold once a window), that GitHub's limit holds it, that a failure keeps the preceding
set, that the index is parsed once a file, and that ``labels_for`` fills only a label a
record names without a color. The CLI transcript is ``tests/golden/cli-github-labels.txt``.
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_labels, pull_list
from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
from metabrowser.builtin_plugins.github.pull_labels import (
    LABEL_FRESHNESS_S,
    UNKNOWN_LABEL_HOLD_S,
    LabelPage,
    LabelSnapshot,
    RepositoryLabel,
    label_index,
    labels_for,
    publish_labels,
    read_labels,
    refresh_labels,
    refresh_wanted,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
from tests.cache_home_fixture import (  # pyright: ignore[reportPrivateUsage]
    FixtureSource,
    _stage_and_publish_source,
    build_empty_home,
)
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    READER,
    account,
    install_fake_gh,
    label_entries,
    next_link,
    ok,
)

SOURCE = FixtureSource("https", CANONICAL)
PAGE = "repos/octo/demo/labels?per_page=100&page=1"


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ListedRepository:
    home = tmp_path / "home"
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    return ListedRepository(home, SOURCE.slug, "octo", "demo")


def _gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, api: dict[str, Any]) -> None:
    answers = {"auth": account(), "api": api, "api_failure": None}
    for key, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(key, value)


def _seed(repository: ListedRepository, *names: str, at: str | None = None) -> None:
    stamp_at = at or utc_stamp(FETCHED_AT)
    labels = tuple(
        RepositoryLabel(name=name, color="d73a4a", description=f"about {name}") for name in names
    )
    snapshot = LabelSnapshot(
        source=repository.source,
        reader=f"gh:{READER}",
        fetched_at=stamp_at,
        complete=True,
        pages=(LabelPage(etag=None, has_next=False, labels=labels),),
    )
    stamp = PullRefreshStamp(outcome="succeeded", at=stamp_at, reader=f"gh:{READER}")
    assert publish_labels(
        repository,
        read_labels(repository.home, repository.slug, repository.source),
        snapshot,
        stamp,
    )


def _later(monkeypatch: pytest.MonkeyPatch, seconds: float) -> None:
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(seconds=seconds))


def test_a_set_is_wanted_absent_then_by_its_age(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert refresh_wanted(repository)
    _seed(repository, "bug")
    assert not refresh_wanted(repository)
    assert refresh_wanted(repository, retry=True)
    _later(monkeypatch, LABEL_FRESHNESS_S - 1)
    assert not refresh_wanted(repository)
    _later(monkeypatch, LABEL_FRESHNESS_S)
    assert refresh_wanted(repository)


def test_a_name_it_does_not_hold_asks_again_once_a_window(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(repository, "bug")
    assert not refresh_wanted(repository, names=("bug",))
    # A name it does not hold, as a label created since, or one deleted on GitHub.
    assert not refresh_wanted(repository, names=("bug", "new"))
    _later(monkeypatch, UNKNOWN_LABEL_HOLD_S)
    assert refresh_wanted(repository, names=("bug", "new"))
    assert not refresh_wanted(repository, names=("bug",))
    assert not refresh_wanted(repository)


def test_githubs_rate_limit_holds_it(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    held = PullRefreshStamp(
        outcome="rate_limited",
        at=utc_stamp(FETCHED_AT),
        reset_at=utc_stamp(FETCHED_AT + timedelta(hours=1)),
    )
    pull_list.write_list_refresh(repository.home, repository.slug, "all", held)
    assert not refresh_wanted(repository)
    assert not refresh_wanted(repository, retry=True)


def test_a_refresh_reads_every_page_and_a_failure_keeps_the_set(
    repository: ListedRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    second = "repos/octo/demo/labels?per_page=100&page=2"
    first = label_entries()[PAGE]
    _gh(
        tmp_path,
        monkeypatch,
        {
            PAGE: {**first, "headers": {**first["headers"], **next_link(PAGE, 1)}},
            second: ok(second, [{"name": "late", "color": "0E8A16", "description": ""}]),
        },
    )
    asyncio.run(refresh_labels(repository))
    index = label_index(repository.home, repository.slug, repository.source)
    assert index is not None and index.cache.snapshot is not None
    assert index.cache.snapshot.complete and len(index.cache.snapshot.pages) == 2
    late = index.get("late")
    assert late == RepositoryLabel(name="late", color="0e8a16", description=None)
    # Another case finds it too, as GitHub's names are unique in any case.
    assert index.get("ENHANCEMENT") == index.get("enhancement")
    _later(monkeypatch, LABEL_FRESHNESS_S)
    _gh(tmp_path, monkeypatch, {})
    asyncio.run(refresh_labels(repository))
    failed = label_index(repository.home, repository.slug, repository.source)
    assert failed is not None and failed.cache.last_refresh.outcome != "succeeded"
    assert failed.cache.snapshot == index.cache.snapshot
    # The failure backs off for a window, as every refresh outcome does.
    assert not refresh_wanted(repository)


def test_the_index_is_parsed_once_a_file(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(repository, "bug")
    first = label_index(repository.home, repository.slug, repository.source)
    parsed: list[bytes] = []
    real = pull_labels.LabelCache.model_validate_json

    def counted(data: bytes | str) -> Any:
        parsed.append(data if isinstance(data, bytes) else data.encode())
        return real(data)

    monkeypatch.setattr(pull_labels.LabelCache, "model_validate_json", counted)
    assert label_index(repository.home, repository.slug, repository.source) is first
    assert parsed == []
    _seed(repository, "bug", "docs")
    second = label_index(repository.home, repository.slug, repository.source)
    assert second is not None and second is not first and second.get("docs") is not None
    assert len(parsed) >= 1


def test_only_a_label_named_without_a_color_takes_the_sets(
    repository: ListedRepository,
) -> None:
    assert labels_for(repository.home, repository.slug, repository.source, ["bug"]) == []
    _seed(repository, "bug", "docs")
    labels: list[object] = [
        {"name": "bug", "color": None, "description": None},
        {"name": "docs", "color": "0075ca", "description": "own"},
        {"name": "gone", "color": None, "description": None},
        {"name": "bug", "color": None, "description": None},
        "not a label",
    ]
    assert labels_for(repository.home, repository.slug, repository.source, labels) == [
        {"name": "bug", "color": "d73a4a", "description": "about bug"}
    ]
    # A set another source wrote colors nothing.
    assert labels_for(repository.home, repository.slug, "https://github.com/o/r", labels) == []


def test_a_set_past_its_bound_is_refused_and_reads_as_none(
    repository: ListedRepository,
) -> None:
    _seed(repository, "bug")
    path = repository.home / f"sources/{repository.slug}/pulls/labels.json"
    cache = json.loads(path.read_bytes())
    cache["snapshot"]["pages"][0]["labels"][0]["name"] = "x" * 1000
    path.write_text(json.dumps(cache))
    assert read_labels(repository.home, repository.slug, repository.source) is None
    assert label_index(repository.home, repository.slug, repository.source) is None


def test_a_read_notes_a_label_the_set_lacks_for_the_catalogs_next_refresh(
    repository: ListedRepository,
) -> None:
    """A pull read never asks GitHub; it notes the names, and the catalog's job takes them."""

    known: list[pull_labels.LabelEntry] = [{"name": "bug", "color": "d73a4a", "description": None}]
    pull_labels.note_unknown(repository.source, ("bug", "gone", "gone"), known)
    pull_labels.note_unknown(repository.source, ("new",), [])
    assert pull_labels.take_unknown(repository.source) == ("gone", "new")
    assert pull_labels.take_unknown(repository.source) == ()
