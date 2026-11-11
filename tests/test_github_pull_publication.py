"""A refresh that loses its record's publication adopts the winner, and keeps its stamp.

Review A6: each caller of a guarded record write handles
:class:`~metabrowser.builtin_plugins.github.pull_record.PullObservationSuperseded`. These
let a second writer publish while the refresh's own write waits, as two servers of one
source would, and check what each caller then keeps.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    PullRefreshStamp,
    read_pull_refresh,
    write_pull_record,
    write_pull_refresh,
)
from metabrowser.builtin_plugins.github.served_pull import ServedPulls
from tests.test_github_pulls import _Stand  # pyright: ignore[reportPrivateUsage]
from tests.test_github_pulls import stand as stand

_WINNER_STAMP = PullRefreshStamp(
    outcome="rate_limited",
    message="GitHub's API rate limit was reached",
    reset_at="2026-09-17T13:00:00Z",
    at="2026-09-17T12:00:05Z",
)


def _lose_the_next_write(stand: _Stand, monkeypatch: pytest.MonkeyPatch, number: int) -> list[Any]:
    """Publish a newer record and its stamp just before the refresh's own write."""
    winners: list[PullRecord] = []
    real = pulls.write_pull_record

    def first_writer_wins(home: Any, slug: str, record: PullRecord, **kwargs: Any) -> Any:
        if record.number == number and not winners:
            winner = record.model_copy(
                update={"fetched_at": "2026-09-17T12:00:05Z", "comparison": None}
            )
            write_pull_record(home, slug, winner, store_id=kwargs.get("store_id"))
            write_pull_refresh(home, slug, number, _WINNER_STAMP, expected=winner)
            winners.append(winner)
        return real(home, slug, record, **kwargs)

    monkeypatch.setattr(pulls, "write_pull_record", first_writer_wins)
    return winners


def test_a_refresh_that_loses_publication_returns_the_winner_and_its_stamp(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    stand.refresh(7)
    winners = _lose_the_next_write(stand, monkeypatch, 7)
    returned = asyncio.run(pulls.refresh_pull_request(stand.published, 7, adopt_current=True))
    assert winners and returned == winners[0] == stand.record(7)
    published = stand.published
    assert read_pull_refresh(published.home, published.slug, 7) == _WINNER_STAMP


def test_a_caller_that_keeps_its_own_outcome_receives_the_winner(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    stand.refresh(7)
    winners = _lose_the_next_write(stand, monkeypatch, 7)
    with pytest.raises(pulls.PullObservationSuperseded) as lost:
        asyncio.run(pulls.refresh_pull_request(stand.published, 7, adopt_current=False))
    assert lost.value.current == winners[0]
    published = stand.published
    assert read_pull_refresh(published.home, published.slug, 7) == _WINNER_STAMP


def test_the_served_pull_request_adopts_the_winner_and_its_stamp(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    stand.refresh(7)
    winners = _lose_the_next_write(stand, monkeypatch, 7)

    async def run() -> Any:
        served = ServedPulls(stand.published)
        companion = await served.companion(7)
        await companion.refresh()
        return companion

    companion = asyncio.run(run())
    assert companion.fetched_at == winners[0].fetched_at
    assert companion.outcome() == {
        "outcome": _WINNER_STAMP.outcome,
        "message": _WINNER_STAMP.message,
        "reset_at": _WINNER_STAMP.reset_at,
        "at": _WINNER_STAMP.at,
    }


def test_an_open_with_no_usable_record_refuses_a_winner_whose_head_it_lacks(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The third outcome of ``open_pull_request``'s lost publication: ``head_mismatch``.

    #347's swap tests pin the other two: the winner when the store has its head, and the
    usable cached record when it does not.
    """
    real = pulls.write_pull_record
    winners: list[PullRecord] = []

    def first_writer_wins(home: Any, slug: str, record: PullRecord, **kwargs: Any) -> Any:
        if record.number == 7 and not winners:
            head = record.pull.head.model_copy(update={"sha": "e" * 40})
            winner = record.model_copy(
                update={"pull": record.pull.model_copy(update={"head": head}), "comparison": None}
            )
            write_pull_record(home, slug, winner, store_id=kwargs.get("store_id"))
            winners.append(winner)
        return real(home, slug, record, **kwargs)

    monkeypatch.setattr(pulls, "write_pull_record", first_writer_wins)
    assert stand.record(7) == "not_cached"
    with pytest.raises(pulls.PullDataError) as refused:
        asyncio.run(pulls.open_pull_request(stand.published, 7, fetch="always"))
    assert winners and refused.value.state == "head_mismatch"


def test_a_refresh_failing_after_its_own_pending_write_stamps_that_failure(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review B3 on #348: the failure stamp describes the record this refresh wrote.

    An uncertain merge base is written first, then deepening fails in Git. Before, the
    stamp expected the record from before the refresh, so it was refused and the stamp
    kept the previous success.
    """
    from datetime import timedelta

    from metabrowser.cache.pull_refs import BaseUncertainError
    from metabrowser.git.process import GitCommandError
    from tests.github_pull_fixture import FETCHED_AT

    first = stand.refresh(7)

    async def uncertain(*_args: Any, **_kwargs: Any) -> Any:
        raise BaseUncertainError(base_commit=first.pull.base.sha, base_from="base_sha")

    async def offline(*_args: Any, **_kwargs: Any) -> Any:
        raise GitCommandError(["fetch"], 128, "could not resolve host")

    monkeypatch.setattr(pulls, "comparison_endpoints", uncertain)
    monkeypatch.setattr(pulls, "deepen_until_certain", offline)
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT + timedelta(minutes=10))
    with pytest.raises(pulls.PullDataError) as failed:
        asyncio.run(pulls.refresh_pull_request(stand.published, 7))
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    assert record.unavailable["comparison"] == "base_uncertain"
    stamp = read_pull_refresh(stand.published.home, stand.published.slug, 7)
    assert stamp is not None and stamp.outcome == failed.value.state == "git_failed"


def test_a_comparison_of_an_older_read_does_not_discard_a_newer_refresh(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review E2 on #348: a comparison added to a record is not a newer observation.

    During a reader's 12:10 refresh, another server prepares the comparison of the record it
    read at 12:00. Before, the refresh's write was refused as superseded, and the 12:10
    read was discarded for the 12:00 one.
    """
    from datetime import timedelta

    from tests.github_pull_fixture import FETCHED_AT

    first = stand.refresh(7)
    published = stand.published
    observed = first.model_copy(
        update={"comparison": None, "unavailable": {**first.unavailable, "comparison": "no_store"}}
    )
    write_pull_record(published.home, published.slug, observed)
    real_read = pulls._read_api  # pyright: ignore[reportPrivateUsage]
    raced: list[Any] = []

    async def read_while_another_server_prepares(*args: Any, **kwargs: Any) -> Any:
        if not raced:
            raced.append(await pulls.prepare_pull_comparison(published, observed))
        return await real_read(*args, **kwargs)

    later = FETCHED_AT + timedelta(minutes=10)
    monkeypatch.setattr(pulls, "_read_api", read_while_another_server_prepares)
    monkeypatch.setattr(pulls, "utc_now", lambda: later)

    async def reader_refresh() -> Any:
        served = ServedPulls(published)
        companion = await served.companion(7)
        await companion.refresh()
        return companion

    companion = asyncio.run(reader_refresh())
    stamp = later.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert raced and raced[0] is not None and raced[0].fetched_at == first.fetched_at
    on_disk = stand.record(7)
    assert isinstance(on_disk, PullRecord) and on_disk.fetched_at == stamp
    assert companion.fetched_at == stamp
    assert companion.last is not None and companion.last["at"] == stamp
