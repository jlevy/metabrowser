"""The rate-limit governor: what a response's headers say, the floor, expiry, and holds."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from metabrowser.builtin_plugins.github import gh_budget
from metabrowser.builtin_plugins.github.gh_budget import (
    BACKGROUND_FLOOR,
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

    def hosts(login: str) -> bytes:
        account = {"state": "success", "active": True, "host": "github.com", "login": login}
        return json.dumps({"hosts": {"github.com": [account]}}).encode()

    logins = ["octo-reader", "someone-else"]

    async def run(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(stdout=hosts(logins.pop(0)), stderr=b"", returncode=0)

    monkeypatch.setattr(gh, "_run", run)
    assert asyncio.run(gh.gh_account()) == "octo-reader"
    hold("2026-09-17T12:10:00Z", now=NOW)
    assert asyncio.run(gh.gh_account()) == "someone-else"
    assert held_until(NOW) is None
