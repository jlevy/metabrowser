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
    returned = stand.refresh(7)
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
    assert companion.last == {
        "outcome": _WINNER_STAMP.outcome,
        "message": _WINNER_STAMP.message,
        "reset_at": _WINNER_STAMP.reset_at,
        "at": _WINNER_STAMP.at,
    }
