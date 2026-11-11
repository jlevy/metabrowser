"""Publishing a pull-request record while another writer may publish first.

``write_pull_record`` compares what a writer read before its work with the record under
the publication lock. These tests race a second writer into that gap on the ``stand``
fixture: a checkout's refresh merges what it meets, a mirror's refresh adopts the record
that won, an open never pins a head its store lacks, a read that failed observes
nothing, and a record that had to be fitted is still deepened.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_record, pulls
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_record import (
    PullObservationSuperseded,
    PullRecord,
    read_pull_record,
    read_pull_refresh,
    write_pull_record,
)
from metabrowser.cache.pull_refs import BaseUncertainError, has_commit
from tests.test_github_pulls import _Stand
from tests.test_github_pulls import stand as stand


def _titled(record: PullRecord, title: str) -> PullRecord:
    return record.model_copy(update={"pull": record.pull.model_copy(update={"title": title})})


def _record(stand: _Stand) -> PullRecord:
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    return record


def test_an_expectation_is_only_what_was_observed_on_disk(stand: _Stand) -> None:
    home, slug = stand.published.home, stand.published.slug
    record = stand.refresh(7)
    newer = record.model_copy(update={"fetched_at": "2026-09-17T12:00:01Z"})
    assert write_pull_record(home, slug, newer, expected=record) == newer
    with pytest.raises(PullObservationSuperseded) as superseded:
        write_pull_record(home, slug, record, expected=record)
    assert superseded.value.current == newer == _record(stand)
    # A writer that saw no file loses to one that published one meanwhile.
    with pytest.raises(PullObservationSuperseded):
        write_pull_record(home, slug, record, expected="not_cached")
    # A read that failed saw nothing of the disk, so it expects nothing.
    for failed in ("unreadable", "schema_mismatch"):
        assert write_pull_record(home, slug, record, expected=failed) == record
        assert _record(stand) == record
        write_pull_record(home, slug, newer)


def test_a_checkout_refresh_merges_a_comparison_published_during_its_read(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review A2: the checkout's fresh metadata wins, and the mirror's comparison stays."""

    home, slug = stand.published.home, stand.published.slug
    shared = stand.refresh(7)
    assert shared.comparison is not None
    metadata = shared.model_copy(update={"comparison": None, "unavailable": {}})
    write_pull_record(home, slug, _titled(metadata, "stale"))
    read_api = pulls._read_api  # pyright: ignore[reportPrivateUsage]

    async def read_then_mirror_publishes(*args: Any, **kwargs: Any) -> PullRecord:
        fresh = await read_api(*args, **kwargs)
        # The mirror publishes its comparison for the same reader and inputs.
        await asyncio.to_thread(write_pull_record, home, slug, _titled(shared, "mirror"))
        return _titled(fresh, "fresh")

    monkeypatch.setattr(pulls, "_read_api", read_then_mirror_publishes)
    listed = ListedRepository(home, slug, "octo", "demo")
    saved = asyncio.run(pulls.refresh_pull_request(listed, 7))
    assert saved == _record(stand)
    assert saved.pull.title == "fresh"
    assert saved.comparison == shared.comparison
    assert "comparison" not in saved.unavailable


def test_a_mirror_refresh_that_loses_adopts_the_winner_without_a_success_stamp(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, slug = stand.published.home, stand.published.slug
    first = stand.refresh(7)
    stamp = read_pull_refresh(home, slug, 7)
    assert stamp is not None and stamp.outcome == "succeeded"
    later = pulls.utc_now() + timedelta(hours=2)
    monkeypatch.setattr(pulls, "utc_now", lambda: later)
    winners = [
        _titled(first, title).model_copy(update={"fetched_at": "2026-09-17T13:00:00Z"})
        for title in ("winner", "another winner")
    ]
    fetch = pulls.fetch_pull_head

    async def fetch_then_another_writer(*args: Any, **kwargs: Any) -> str | None:
        fetched = await fetch(*args, **kwargs)
        await asyncio.to_thread(write_pull_record, home, slug, winners.pop(0))
        return fetched

    monkeypatch.setattr(pulls, "fetch_pull_head", fetch_then_another_writer)
    winner = winners[0]
    assert asyncio.run(pulls.refresh_pull_request(stand.published, 7)) == winner
    assert _record(stand) == winner
    # Nothing claims this refresh succeeded at the winner's time.
    assert read_pull_refresh(home, slug, 7) == stamp
    # A caller that keeps its own outcome is told instead.
    with pytest.raises(PullObservationSuperseded) as superseded:
        asyncio.run(pulls.refresh_pull_request(stand.published, 7, adopt_current=False))
    assert superseded.value.current.pull.title == "another winner"


def test_a_failed_pre_read_does_not_turn_a_refresh_into_a_no_op(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review C1 (R7): one unreadable read before the network read observes nothing."""

    old = stand.refresh(7)
    later = pulls.utc_now() + timedelta(hours=2)
    monkeypatch.setattr(pulls, "utc_now", lambda: later)
    real = pulls.read_pull_record
    calls = 0

    def unreadable_once(*args: Any, **kwargs: Any) -> object:
        nonlocal calls
        calls += 1
        return "unreadable" if calls == 1 else real(*args, **kwargs)

    monkeypatch.setattr(pulls, "read_pull_record", unreadable_once)
    returned = asyncio.run(pulls.refresh_pull_request(stand.published, 7))
    assert returned.fetched_at == "2026-09-17T14:00:00Z" != old.fetched_at
    assert _record(stand) == returned
    stamp = read_pull_refresh(stand.published.home, stand.published.slug, 7)
    assert stamp is not None and (stamp.outcome, stamp.at) == ("succeeded", returned.fetched_at)


def test_an_open_that_loses_never_pins_a_head_its_store_lacks(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review C2 (R9): another writer publishes a head this store never fetched."""

    home, slug = stand.published.home, stand.published.slug
    first = stand.refresh(7)
    fetch = pulls.fetch_pull_head

    async def fetch_then_another_writer(*args: Any, **kwargs: Any) -> str | None:
        fetched = await fetch(*args, **kwargs)
        moved = first.pull.model_copy(
            update={"head": first.pull.head.model_copy(update={"sha": "e" * 40})}
        )
        other = first.model_copy(update={"pull": moved, "comparison": None})
        await asyncio.to_thread(write_pull_record, home, slug, other)
        return fetched

    monkeypatch.setattr(pulls, "fetch_pull_head", fetch_then_another_writer)
    pin = asyncio.run(pulls.open_pull_request(stand.published, 7, fetch="always"))
    assert pin.head == first.pull.head.sha
    assert asyncio.run(has_commit(stand.published, pin.head))


def test_a_lost_open_pins_the_winner_when_the_store_has_its_head(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, slug = stand.published.home, stand.published.slug
    first = stand.refresh(7)
    winner = _titled(first, "winner")
    fetch = pulls.fetch_pull_head

    async def fetch_then_another_writer(*args: Any, **kwargs: Any) -> str | None:
        fetched = await fetch(*args, **kwargs)
        await asyncio.to_thread(write_pull_record, home, slug, winner)
        return fetched

    monkeypatch.setattr(pulls, "fetch_pull_head", fetch_then_another_writer)
    pin = asyncio.run(pulls.open_pull_request(stand.published, 7, fetch="always"))
    assert pin.head == winner.pull.head.sha and _record(stand) == winner


def test_an_uncertain_base_is_deepened_when_its_record_was_fitted(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review A3: the first write's own fitted record is what the second write expects."""

    record = stand.refresh(7)
    comparison = record.comparison
    assert comparison is not None
    deepened: list[int] = []

    async def uncertain(*_args: Any, **_kwargs: Any) -> Any:
        raise BaseUncertainError(base_commit=comparison.base_commit, base_from="base_branch")

    async def deepen(*_args: Any, **_kwargs: Any) -> Any:
        deepened.append(1)
        raise BaseUncertainError(base_commit=comparison.base_commit, base_from="base_branch")

    monkeypatch.setattr(pulls, "comparison_endpoints", uncertain)
    monkeypatch.setattr(pulls, "deepen_until_certain", deepen)
    # A record whose text exceeds the budget, as a long discussion's does.
    monkeypatch.setattr(pull_record, "MAX_TEXT_BYTES", 8)
    large = record.model_copy(
        update={"pull": record.pull.model_copy(update={"body": "x" * 64}), "comparison": None}
    )
    written = asyncio.run(pulls._with_comparison(stand.published, large, expected=record))  # pyright: ignore[reportPrivateUsage]
    assert deepened == [1]
    assert written.unavailable["comparison"] == "base_uncertain"
    assert written.pull.body != large.pull.body and _record(stand) == written


def test_a_prepared_comparison_publishes_once_and_never_over_a_newer_record(
    stand: _Stand,
) -> None:
    """``prepare_pull_comparison`` computes Files changed for an observation already read.

    Its scheduler lands in #348; here it is the same compare-and-swap's other writer.
    """

    home, slug = stand.published.home, stand.published.slug
    record = stand.refresh(7)
    observed = record.model_copy(update={"comparison": None})
    write_pull_record(home, slug, observed)
    stand.calls()
    prepared = asyncio.run(pulls.prepare_pull_comparison(stand.published, observed))
    assert prepared is not None and prepared.comparison is not None
    assert record.comparison is not None
    # This layer compares a cached observation from its observed base commit, not the
    # base branch a refresh fetched, so only the endpoints agree.
    pair = (prepared.comparison.base, prepared.comparison.head)
    assert pair == (record.comparison.base, record.comparison.head)
    assert prepared.comparison.base_from == "base_sha"
    assert _record(stand) == prepared
    assert asyncio.run(pulls.prepare_pull_comparison(stand.published, prepared)) is prepared
    newer = observed.model_copy(update={"fetched_at": "2026-09-17T12:00:01Z"})
    write_pull_record(home, slug, newer)
    with pytest.raises(PullObservationSuperseded):
        asyncio.run(pulls.prepare_pull_comparison(stand.published, observed))
    assert read_pull_record(home, slug, 7) == newer
    assert stand.calls() == []
