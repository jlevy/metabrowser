"""The rate-limit governor: what a response's headers say, the floor, expiry, and holds."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import gh_budget
from metabrowser.builtin_plugins.github.gh_budget import (
    AUTOMATIC_CORE_PER_HOUR,
    BACKGROUND_FLOOR,
    CEILING_FULL_READ_S,
    SPECULATIVE_CORE_PER_HOUR,
    Admission,
    admission,
    held_until,
    hold,
    observations,
    observe,
)

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
RESET = int((NOW + timedelta(minutes=30)).timestamp())


@pytest.fixture(autouse=True)
def fresh_process() -> Iterator[None]:
    gh_budget.forget()
    yield
    gh_budget.forget()


def _headers(remaining: int, *, limit: int = 5000, resource: str | None = "core") -> dict[str, str]:
    headers = {
        "x-ratelimit-limit": str(limit),
        "x-ratelimit-remaining": str(remaining),
        "x-ratelimit-reset": str(RESET),
        "x-ratelimit-used": str(limit - remaining),
    }
    if resource is not None:
        headers["x-ratelimit-resource"] = resource
    return headers


def test_nothing_observed_admits_and_the_first_response_is_kept() -> None:
    assert admission(("core",), now=NOW) == Admission(True)
    observe(_headers(4999), resource="core")
    assert observations(NOW) == {
        "core": {"limit": 5000, "remaining": 4999, "reset_at": "2026-09-17T12:30:00Z"}
    }


def test_background_stops_at_the_floor_of_each_resource_it_spends() -> None:
    floor = int(BACKGROUND_FLOOR * 5000)
    observe(_headers(floor + 1), resource="core")
    observe(_headers(floor, resource="graphql"), resource="graphql")
    assert admission(("core",), now=NOW).admitted
    assert admission(("core", "graphql"), now=NOW) == Admission(False, "below_floor")
    observe(_headers(floor), resource="core")
    assert admission(("core",), now=NOW) == Admission(False, "below_floor")


def test_a_response_that_names_no_resource_is_kept_under_the_callers() -> None:
    # The fake gh, like an older GitHub, sends no x-ratelimit-resource.
    observe(_headers(100, resource=None), resource="graphql")
    assert set(observations(NOW)) == {"graphql"}
    assert admission(("core",), now=NOW).admitted
    assert not admission(("graphql",), now=NOW).admitted


def test_an_observation_expires_at_its_reset() -> None:
    observe(_headers(0), resource="core")
    assert not admission(("core",), now=NOW).admitted
    after = NOW + timedelta(minutes=30)
    assert admission(("core",), now=after).admitted and observations(after) == {}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"x-ratelimit-limit": "0", "x-ratelimit-remaining": "0", "x-ratelimit-reset": str(RESET)},
        {"x-ratelimit-limit": "5000", "x-ratelimit-remaining": "-1", "x-ratelimit-reset": "1"},
        {"x-ratelimit-limit": "5000", "x-ratelimit-remaining": "9", "x-ratelimit-reset": "soon"},
        {**_headers(9), "x-ratelimit-resource": "Core; drop"},
    ],
    ids=["none", "no limit", "negative", "no reset", "odd resource"],
)
def test_headers_that_say_nothing_usable_are_ignored(headers: dict[str, str]) -> None:
    observe(headers, resource="core")
    assert observations(NOW) == {}


def test_the_resources_kept_are_bounded() -> None:
    for index in range(20):
        observe(_headers(10, resource=f"r{chr(ord('a') + index)}"), resource="core")
    assert len(observations(NOW)) == 8


def test_a_hold_stops_everything_until_it_lifts_and_is_never_shortened() -> None:
    hold("2026-09-17T12:10:00Z", now=NOW)
    hold("2026-09-17T12:05:00Z", now=NOW)
    assert held_until(NOW) == "2026-09-17T12:10:00Z"
    assert admission((), now=NOW) == Admission(False, "rate_hold")
    assert admission((), now=datetime(2026, 9, 17, 12, 10, tzinfo=UTC)).admitted


def test_a_hold_without_a_reset_lasts_a_window() -> None:
    hold(None, now=NOW)
    assert held_until(NOW) == "2026-09-17T12:01:00Z"
    hold("garbled", now=NOW)
    assert held_until(NOW) == "2026-09-17T12:01:00Z"


def test_another_account_forgets_the_last_ones_budget_and_hold() -> None:
    """Review A7: the budget is the token's account's; a switch to another starts afresh."""

    gh_budget.note_account("octo-reader")
    observe(_headers(int(BACKGROUND_FLOOR * 5000)), resource="core")
    hold("2026-09-17T12:10:00Z", now=NOW)
    gh_budget.note_account("octo-reader")
    assert admission(("core",), now=NOW) == Admission(False, "rate_hold")
    gh_budget.note_account("someone-else")
    assert observations(NOW) == {} and held_until(NOW) is None
    assert admission(("core",), now=NOW) == Admission(True)


def test_the_account_check_names_the_account_to_the_governor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import json
    from types import SimpleNamespace

    from metabrowser.builtin_plugins.github import gh

    def named(login: str) -> bytes:
        body = json.dumps({"login": login}).encode()
        return b'HTTP/2.0 200 OK\nEtag: "' + login.encode() + b'"\r\n\r\n' + body

    logins = ["octo-reader", "someone-else"]

    async def run(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(stdout=named(logins.pop(0)), stderr=b"", returncode=0)

    monkeypatch.setattr(gh, "_run_in", run)
    assert asyncio.run(gh.gh_account()) == "octo-reader"
    hold("2026-09-17T12:10:00Z", now=NOW)
    assert asyncio.run(gh.gh_account()) == "someone-else"
    assert held_until(NOW) is None


# ── The self-ceiling ────────────────────────────────────────────


def test_automatic_work_is_counted_from_what_the_process_spends_itself() -> None:
    assert gh_budget.automatic_spent(NOW) == 0 and not gh_budget.over_ceiling(NOW)
    gh_budget.spent(1, now=NOW)
    gh_budget.spent(3, now=NOW + timedelta(seconds=90))
    # A ``304`` costs nothing, and is counted as nothing.
    gh_budget.spent(0, now=NOW + timedelta(seconds=91))
    assert gh_budget.automatic_spent(NOW + timedelta(seconds=120)) == 4
    # The account's counter, which every other client moves, says nothing here.
    observe(_headers(100), resource="core")
    assert gh_budget.automatic_spent(NOW + timedelta(seconds=120)) == 4


def test_the_hour_rolls_a_minute_at_a_time_and_keeps_sixty_counts() -> None:
    for minute in range(180):
        gh_budget.spent(1, now=NOW + timedelta(minutes=minute))
    last = NOW + timedelta(minutes=179)
    assert gh_budget.automatic_spent(last) == 60
    assert len(gh_budget._SPENT) == 60  # pyright: ignore[reportPrivateUsage]
    assert gh_budget.automatic_spent(last + timedelta(minutes=30)) == 30
    assert gh_budget.automatic_spent(last + timedelta(minutes=60)) == 0


def test_past_the_ceiling_background_work_stops_and_full_reads_slow_until_the_hour_rolls() -> None:
    gh_budget.spent(AUTOMATIC_CORE_PER_HOUR - 1, now=NOW)
    assert admission(("core",), now=NOW) == Admission(True)
    assert gh_budget.full_read_interval(90.0, now=NOW) == 90.0
    gh_budget.spent(1, now=NOW)
    assert gh_budget.over_ceiling(NOW)
    assert admission(("core",), now=NOW) == Admission(False, "self_ceiling")
    # A periodic full read of what is visible is slowed, not stopped.
    assert admission(("core",), now=NOW, ceiling=False) == Admission(True)
    assert gh_budget.full_read_interval(90.0, now=NOW) == CEILING_FULL_READ_S
    assert gh_budget.full_read_interval(600.0, now=NOW) == 600.0
    later = NOW + timedelta(minutes=60)
    assert not gh_budget.over_ceiling(later)
    assert admission(("core",), now=later) == Admission(True)
    assert gh_budget.full_read_interval(90.0, now=later) == 90.0


def test_the_floor_and_a_hold_are_named_before_the_ceiling() -> None:
    gh_budget.spent(AUTOMATIC_CORE_PER_HOUR, now=NOW)
    observe(_headers(int(BACKGROUND_FLOOR * 5000)), resource="core")
    assert admission(("core",), now=NOW) == Admission(False, "below_floor")
    assert admission(("core",), now=NOW, ceiling=False) == Admission(False, "below_floor")
    hold("2026-09-17T12:10:00Z", now=NOW)
    assert admission(("core",), now=NOW) == Admission(False, "rate_hold")


def test_a_readers_own_action_is_never_counted_nor_is_the_job_it_starts() -> None:
    import asyncio

    async def job() -> None:
        gh_budget.spent(5, now=NOW)

    async def click() -> asyncio.Task[None]:
        with gh_budget.readers_own():
            gh_budget.spent(AUTOMATIC_CORE_PER_HOUR, now=NOW)
            # The job's task copies the context it is created in.
            started = asyncio.create_task(job())
        # Automatic work the same request does after it is counted again.
        gh_budget.spent(2, now=NOW)
        return started

    async def run() -> None:
        await (await click())
        # And a job started outside it is automatic.
        await asyncio.create_task(job())

    asyncio.run(run())
    assert gh_budget.automatic_spent(NOW) == 7 and not gh_budget.over_ceiling(NOW)


def test_another_account_starts_its_hour_afresh() -> None:
    gh_budget.note_account("octo-reader")
    gh_budget.spent(AUTOMATIC_CORE_PER_HOUR, now=NOW)
    gh_budget.note_account("octo-reader")
    assert gh_budget.over_ceiling(NOW)
    gh_budget.note_account("someone-else")
    assert gh_budget.automatic_spent(NOW) == 0


@pytest.mark.parametrize(
    ("status", "cost"),
    [(200, 1), (304, 0), (404, 1)],
)
def test_a_rest_answer_costs_one_unless_it_is_a_304(
    monkeypatch: pytest.MonkeyPatch, status: int, cost: int
) -> None:
    import asyncio
    from types import SimpleNamespace

    from metabrowser.builtin_plugins.github import gh

    reason = {200: "OK", 304: "Not Modified", 404: "Not Found"}[status]
    body = b"" if status == 304 else b'{"message": "x"}'
    out = f'HTTP/2.0 {status} {reason}\r\nEtag: W/"a"\r\n\r\n'.encode() + body

    async def run(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(stdout=out, stderr=b"gh: HTTP 404", returncode=0)

    monkeypatch.setattr(gh, "_run_in", run)

    async def ask() -> None:
        try:
            await gh.gh_api("repos/octo/demo/pulls/7", etag='W/"a"', now=NOW)
        except gh.GhError:
            assert status == 404

    asyncio.run(ask())
    assert gh_budget.automatic_spent(NOW) == cost


@pytest.mark.parametrize(
    ("data", "cost"),
    [
        ({"viewer": {"login": "octo"}}, 1),
        ({"viewer": {"login": "octo"}, "rateLimit": {"cost": 3}}, 3),
        ({"viewer": {"login": "octo"}, "rateLimit": {"cost": "many"}}, 1),
    ],
)
def test_a_graphql_query_costs_what_github_reports_and_one_when_it_reports_nothing(
    monkeypatch: pytest.MonkeyPatch, data: dict[str, object], cost: int
) -> None:
    import asyncio
    import json
    from types import SimpleNamespace

    from metabrowser.builtin_plugins.github import gh

    out = b"HTTP/2.0 200 OK\r\n\r\n" + json.dumps({"data": data}).encode()

    async def run(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(stdout=out, stderr=b"", returncode=0)

    monkeypatch.setattr(gh, "_run_in", run)
    asyncio.run(gh.gh_graphql("query Fixed { viewer { login } rateLimit { cost } }", {}, now=NOW))
    assert gh_budget.automatic_spent(NOW) == cost


@pytest.mark.parametrize(
    ("status", "reason", "headers"),
    [
        (401, "Unauthorized", ""),
        (403, "Forbidden", f"X-Ratelimit-Remaining: 0\r\nX-Ratelimit-Reset: {RESET}\r\n"),
        (502, "Bad Gateway", ""),
    ],
)
def test_a_graphql_query_github_refused_costs_one(
    monkeypatch: pytest.MonkeyPatch, status: int, reason: str, headers: str
) -> None:
    """A refusal is charged as a ``200`` is, rate-limited or not (A9 of review A on #737)."""

    import asyncio
    from types import SimpleNamespace

    from metabrowser.builtin_plugins.github import gh

    out = f"HTTP/2.0 {status} {reason}\r\n{headers}\r\n".encode() + b'{"message": "no"}'

    async def run(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(stdout=out, stderr=b"", returncode=0)

    monkeypatch.setattr(gh, "_run_in", run)
    with pytest.raises(gh.GhError):
        asyncio.run(gh.gh_graphql("query Fixed { viewer { login } }", {}, now=NOW))
    assert gh_budget.automatic_spent(NOW) == 1


def test_a_job_the_coordinator_starts_for_a_readers_click_is_the_readers_too() -> None:
    import asyncio

    from metabrowser.mirror_refresh import RefreshCoordinator

    async def job() -> None:
        gh_budget.spent(9, now=NOW)

    async def run() -> None:
        coordinator = RefreshCoordinator(limit=1)
        with gh_budget.readers_own():
            coordinator.start("a reader's refresh", job, network=False)
        coordinator.start("an automatic refresh", job, network=False)
        await coordinator.drain(timeout_s=2)
        await coordinator.aclose()

    asyncio.run(run())
    assert gh_budget.automatic_spent(NOW) == 9


def test_the_account_check_is_counted_as_any_other_answer_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A conditional ``gh api user``: a ``200`` costs one, and the ``304`` after it nothing."""

    import asyncio
    from types import SimpleNamespace

    from metabrowser.builtin_plugins.github import gh

    answers = [
        b'HTTP/2.0 200 OK\r\nEtag: W/"user"\r\n\r\n{"login": "octo-reader"}',
        b'HTTP/2.0 304 Not Modified\r\nEtag: W/"user"\r\n\r\n',
    ]

    async def run(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(stdout=answers.pop(0), stderr=b"", returncode=0)

    monkeypatch.setattr(gh, "_run_in", run)
    gh.forget_account()
    try:
        before = gh_budget.automatic_spent(datetime.now(UTC))
        assert asyncio.run(gh.gh_account()) == "octo-reader"
        assert gh_budget.automatic_spent(datetime.now(UTC)) == before + 1
        assert asyncio.run(gh.gh_account()) == "octo-reader"
        assert gh_budget.automatic_spent(datetime.now(UTC)) == before + 1
    finally:
        gh.forget_account()


# ── Speculative work's share of the ceiling ─────────────────────


def test_speculative_work_stops_at_its_share_and_what_is_on_screen_keeps_the_rest() -> None:
    """A1 of review A on #737: the prefetch could spend the ceiling the screen then paid for."""

    with gh_budget.speculative():
        gh_budget.spent(SPECULATIVE_CORE_PER_HOUR - 1, now=NOW)
    assert admission(("core",), now=NOW, speculative=True) == Admission(True)
    with gh_budget.speculative():
        gh_budget.spent(1, now=NOW)
    assert gh_budget.speculative_spent(NOW) == SPECULATIVE_CORE_PER_HOUR
    assert admission(("core",), now=NOW, speculative=True) == Admission(False, "self_ceiling")
    # What is on screen is admitted, and neither its probes nor its full reads slow.
    assert not gh_budget.over_ceiling(NOW)
    assert admission(("graphql",), now=NOW) == Admission(True)
    assert gh_budget.full_read_interval(90.0, now=NOW) == 90.0
    # It keeps the rest of the ceiling, to the point.
    rest = AUTOMATIC_CORE_PER_HOUR - SPECULATIVE_CORE_PER_HOUR
    gh_budget.spent(rest - 1, now=NOW)
    assert admission(("core",), now=NOW) == Admission(True)
    gh_budget.spent(1, now=NOW)
    assert admission(("core",), now=NOW) == Admission(False, "self_ceiling")
    # The share rolls with the hour, as the ceiling does.
    later = NOW + timedelta(minutes=60)
    assert gh_budget.speculative_spent(later) == 0
    assert admission(("core",), now=later, speculative=True) == Admission(True)


def test_what_is_on_screen_spends_none_of_speculative_works_share() -> None:
    gh_budget.spent(SPECULATIVE_CORE_PER_HOUR, now=NOW)
    assert gh_budget.speculative_spent(NOW) == 0
    assert admission(("core",), now=NOW, speculative=True) == Admission(True)
    # The ceiling stops speculative work as it stops any background work.
    gh_budget.spent(AUTOMATIC_CORE_PER_HOUR - SPECULATIVE_CORE_PER_HOUR, now=NOW)
    assert admission(("core",), now=NOW, speculative=True) == Admission(False, "self_ceiling")


def test_the_share_leaves_what_is_on_screen_more_than_one_busy_page_spends() -> None:
    """The arithmetic beside the constants: 160 points an hour for one busy visible page."""

    assert AUTOMATIC_CORE_PER_HOUR - SPECULATIVE_CORE_PER_HOUR >= 160
    assert 0 < SPECULATIVE_CORE_PER_HOUR < AUTOMATIC_CORE_PER_HOUR


def test_a_job_started_inside_speculative_work_is_speculative_and_a_readers_own_is_uncounted() -> (
    None
):
    import asyncio

    from metabrowser.mirror_refresh import RefreshCoordinator

    async def job() -> None:
        gh_budget.spent(4, now=NOW)

    async def run() -> None:
        coordinator = RefreshCoordinator(limit=1)
        with gh_budget.speculative():
            coordinator.start("a prefetch", job, network=False)
            with gh_budget.readers_own():
                coordinator.start("a reader's refresh", job, network=False)
        coordinator.start("a visible page's refresh", job, network=False)
        await coordinator.drain(timeout_s=2)
        await coordinator.aclose()

    asyncio.run(run())
    assert gh_budget.speculative_spent(NOW) == 4 and gh_budget.automatic_spent(NOW) == 8


def test_another_account_starts_its_share_afresh() -> None:
    gh_budget.note_account("octo-reader")
    with gh_budget.speculative():
        gh_budget.spent(SPECULATIVE_CORE_PER_HOUR, now=NOW)
    gh_budget.note_account("someone-else")
    assert gh_budget.speculative_spent(NOW) == 0


def test_the_hours_spending_is_read_from_a_copy_while_the_loop_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A6 of review A on #737: a worker thread summed the buckets the loop was adding to.

    The stand-in dictionary lets another thread count a new minute's spending in the
    middle of a read's iteration, which is the switch the lock rules out.
    """

    import threading

    counting = threading.Thread(
        target=gh_budget.spent, args=(1,), kwargs={"now": NOW + timedelta(minutes=5)}
    )

    class Interrupted(dict[int, int]):
        def items(self) -> Any:
            for pair in tuple(super().items()):
                if not counting.is_alive() and len(self) == 1:
                    counting.start()
                    # Under the lock the count waits for this read; without it, it lands.
                    counting.join(0.2)
                    if len(self) != 1:
                        raise RuntimeError("dictionary changed size during iteration")
                yield pair

    monkeypatch.setattr(gh_budget, "_SPENT", Interrupted({gh_budget._minute(NOW): 2}))  # pyright: ignore[reportPrivateUsage]
    assert gh_budget.automatic_spent(NOW + timedelta(minutes=5)) == 2
    counting.join(5)
    assert gh_budget.automatic_spent(NOW + timedelta(minutes=5)) == 3
