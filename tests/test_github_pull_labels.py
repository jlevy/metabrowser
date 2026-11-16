"""The repository's cached label set: when it is asked for, what it keeps, and its use.

``pull_labels`` keeps one bounded snapshot of ``repos/<owner>/<repo>/labels``. These
hold when a refresh is wanted (absent, past :data:`LABEL_FRESHNESS_S`, or a reader's
retry), that GitHub's limit holds it, that a failure or a refused write keeps the
preceding set and backs off, that a superseded writer is refused, that the page loop
follows GitHub's continuation, conditional answers included, within its bounds, that the
index is parsed once a file, and that ``labels_for`` fills only a label a record names
without a color. The CLI transcript is ``tests/golden/cli-github-labels.txt``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_labels, pull_list, repository_snapshot
from metabrowser.builtin_plugins.github.gh import GhResponse
from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
from metabrowser.builtin_plugins.github.pull_labels import (
    LABEL_FRESHNESS_S,
    LabelCache,
    LabelPage,
    LabelSnapshot,
    RepositoryLabel,
    label_index,
    labels_for,
    last_refresh,
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


def _cached(repository: ListedRepository) -> LabelCache:
    cache = read_labels(repository.home, repository.slug, repository.source)
    assert cache is not None
    return cache


def _names(repository: ListedRepository) -> list[str]:
    snapshot = _cached(repository).snapshot
    assert snapshot is not None
    return [label.name for label in snapshot.labels()]


class _GitHub:
    """The label pages as GitHub answers them, in process: by name, a page at a time.

    As a probe of github.com's own label pages found: a page's ETag is its body's, so it
    is the same whatever ``Link`` says; a ``304`` carries the ``Link``; a set of one page
    has no ``Link`` at all, and every other page names its ``next`` but the last.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch, names: Sequence[str]) -> None:
        self.names = list(names)
        self.calls: list[str] = []
        self.readers = [READER]

        async def active() -> str:
            return self.readers.pop(0) if len(self.readers) > 1 else self.readers[0]

        monkeypatch.setattr(pull_labels, "active_account", active)
        monkeypatch.setattr(pull_labels, "gh_api", self.api)

    async def api(self, path: str, *, etag: str | None = None) -> GhResponse:
        size = pull_labels.LABEL_PAGE_SIZE
        assert path.startswith(f"repos/octo/demo/labels?per_page={size}&page="), path
        page = int(path.rsplit("=", 1)[1])
        body = [
            {"name": name, "color": "d73a4a", "description": None}
            for name in self.names[(page - 1) * size : page * size]
        ]
        pages = max(1, -(-len(self.names) // size))
        base = f"https://api.github.com/repositories/1/labels?per_page={size}"
        links: list[str] = []
        if page < pages:
            links += [f'<{base}&page={page + 1}>; rel="next"', f'<{base}&page={pages}>; rel="last"']
        if page > 1:
            links += [f'<{base}&page={page - 1}>; rel="prev"', f'<{base}&page=1>; rel="first"']
        digest = hashlib.sha256(json.dumps(body).encode()).hexdigest()[:16]
        headers = {"etag": f'W/"{digest}"'}
        if links:
            headers["link"] = ", ".join(links)
        self.calls.append(f"page {page}" + (" (If-None-Match)" if etag else ""))
        if etag == headers["etag"]:
            return GhResponse(304, headers, b"")
        return GhResponse(200, headers, json.dumps(body).encode())


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
    # The failure backs off for the set's age, as every refresh outcome does.
    assert not refresh_wanted(repository)


def test_the_account_is_asked_before_and_after_the_pages(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A snapshot's reader read every page of it; an account switch keeps the set."""

    github = _GitHub(monkeypatch, ["a", "b"])
    asyncio.run(refresh_labels(repository))
    kept = _cached(repository)
    assert kept.snapshot is not None and kept.snapshot.reader == f"gh:{READER}"
    github.readers = [READER, "someone-else"]
    asyncio.run(refresh_labels(repository, retry=True))
    switched = _cached(repository)
    assert switched.last_refresh.outcome == "account_changed"
    assert switched.snapshot == kept.snapshot


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


def test_a_refresh_parses_the_set_once_and_checks_its_hold_by_stat(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each page's rate-limit check, under the network slot, reads the set's stat-gated index."""

    names = [f"label-{n}" for n in range(5)]
    monkeypatch.setattr(pull_labels, "LABEL_PAGE_SIZE", 1)
    _GitHub(monkeypatch, names)
    asyncio.run(refresh_labels(repository))
    parsed: list[int] = []
    real = pull_labels.LabelCache.model_validate_json

    def counted(data: bytes | str) -> Any:
        parsed.append(len(data))
        return real(data)

    monkeypatch.setattr(pull_labels.LabelCache, "model_validate_json", counted)
    asyncio.run(refresh_labels(repository, retry=True))
    # The set this read starts from, and the one it publishes over, under the lock: two
    # parses for five pages and their seven hold checks.
    assert len(parsed) == 2
    assert _names(repository) == names


def test_only_a_label_named_without_a_color_takes_the_sets(
    repository: ListedRepository,
) -> None:
    lookup = labels_for(
        repository.home,
        repository.slug,
        repository.source,
        [{"name": "bug", "color": None, "description": None}],
    )
    assert (lookup.entries, lookup.missing) == ([], ("bug",))
    _seed(repository, "bug", "docs")
    labels: list[object] = [
        {"name": "bug", "color": None, "description": None},
        {"name": "docs", "color": "0075ca", "description": "own"},
        {"name": "gone", "color": None, "description": None},
        {"name": "bug", "color": None, "description": None},
        {"name": "gone", "color": None, "description": None},
        "not a label",
    ]
    lookup = labels_for(repository.home, repository.slug, repository.source, labels)
    assert lookup.entries == [{"name": "bug", "color": "d73a4a", "description": "about bug"}]
    # Each name the set does not hold, once.
    assert lookup.missing == ("gone",)
    # A set another source wrote colors nothing.
    other = labels_for(repository.home, repository.slug, "https://github.com/o/r", labels)
    assert (other.entries, other.missing) == ([], ("bug", "gone"))


def test_a_name_past_its_bound_is_refused_and_the_set_reads_as_none(
    repository: ListedRepository,
) -> None:
    _seed(repository, "bug")
    path = repository.home / f"sources/{repository.slug}/pulls/labels.json"
    cache = json.loads(path.read_bytes())
    cache["snapshot"]["pages"][0]["labels"][0]["name"] = "x" * 1000
    path.write_text(json.dumps(cache))
    assert read_labels(repository.home, repository.slug, repository.source) is None
    assert label_index(repository.home, repository.slug, repository.source) is None


def test_a_refresh_stops_at_its_page_bound_and_keeps_its_pages(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pull_labels, "LABEL_PAGE_SIZE", 2)
    monkeypatch.setattr(pull_labels, "MAX_LABEL_PAGES", 2)
    github = _GitHub(monkeypatch, ["a", "b", "c", "d", "e"])
    asyncio.run(refresh_labels(repository))
    snapshot = _cached(repository).snapshot
    assert snapshot is not None and not snapshot.complete
    assert _names(repository) == ["a", "b", "c", "d"]
    assert github.calls == ["page 1", "page 2"]


def test_a_refresh_stops_at_its_byte_bound_and_keeps_the_pages_before_it(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pull_labels, "LABEL_PAGE_SIZE", 2)
    one = LabelPage(
        etag='W/"0123456789abcdef"',
        has_next=True,
        labels=(
            RepositoryLabel(name="a", color="d73a4a", description=None),
            RepositoryLabel(name="b", color="d73a4a", description=None),
        ),
    )
    room = pull_labels._ENVELOPE_BYTES + len(one.model_dump_json().encode()) + 10  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(pull_labels, "MAX_LABELS_BYTES", room)
    github = _GitHub(monkeypatch, ["a", "b", "c", "d"])
    asyncio.run(refresh_labels(repository))
    cache = _cached(repository)
    assert cache.last_refresh.outcome == "succeeded"
    assert cache.snapshot is not None and not cache.snapshot.complete
    assert _names(repository) == ["a", "b"]
    assert github.calls == ["page 1", "page 2"]


def test_a_refused_cache_write_still_backs_off(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    _GitHub(monkeypatch, ["a"])

    def refused(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(repository_snapshot, "write_private_file_atomic", refused)
    asyncio.run(refresh_labels(repository))
    assert read_labels(repository.home, repository.slug, repository.source) is None
    stamp = last_refresh(repository.home, repository.source, None)
    assert stamp is not None and stamp.outcome == "cache_unwritable"
    # Remembered in this process, so the next ask waits out the set's age.
    assert not refresh_wanted(repository)
    _later(monkeypatch, LABEL_FRESHNESS_S)
    assert refresh_wanted(repository)


def test_a_stale_writer_is_refused_and_the_newer_set_kept(
    repository: ListedRepository,
) -> None:
    _seed(repository, "old")
    stale = _cached(repository)
    _seed(repository, "newer")
    assert stale.snapshot is not None
    assert not publish_labels(repository, stale, stale.snapshot, stale.last_refresh)
    assert _names(repository) == ["newer"]


def test_a_success_cannot_replace_a_rate_limit_that_holds(
    repository: ListedRepository,
) -> None:
    _seed(repository, "bug")
    held = PullRefreshStamp(
        outcome="rate_limited",
        at=utc_stamp(FETCHED_AT),
        reset_at=utc_stamp(FETCHED_AT + timedelta(hours=1)),
    )
    assert publish_labels(repository, _cached(repository), None, held)
    limited = _cached(repository)
    succeeded = PullRefreshStamp(outcome="succeeded", at=utc_stamp(FETCHED_AT), reader="gh:o")
    assert limited.snapshot is not None
    assert not publish_labels(repository, limited, limited.snapshot, succeeded)
    assert _cached(repository).last_refresh == held


def test_a_publish_into_another_sources_cache_is_refused(
    repository: ListedRepository,
) -> None:
    """The cache must still be this repository's, as the native stack snapshot's must."""

    elsewhere = ListedRepository(repository.home, repository.slug, "octo", "elsewhere")
    stamp = PullRefreshStamp(outcome="succeeded", at=utc_stamp(FETCHED_AT))
    with pytest.raises(ValueError, match="source identity changed"):
        publish_labels(elsewhere, None, None, stamp)
    assert read_labels(repository.home, repository.slug, elsewhere.source) is None
