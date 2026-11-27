"""The list's automatic reads under the budget: the floor, and the process's own ceiling.

The probe and its cadence are ``tests/test_github_pull_list_probe.py``'s, whose stand-in
for GitHub these use.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from metabrowser.builtin_plugins.github import gh_budget
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_list_probe import LIST_PROBE_S, ListProbe
from metabrowser.builtin_plugins.github.pull_list_route import RefreshRequest, refresh_wanted
from metabrowser.builtin_plugins.github.served_pull import FULL_REFRESH_S
from tests.github_pull_fixture import generated_item, seed_catalog
from tests.test_github_pull_list_probe import (  # pyright: ignore[reportPrivateUsage]
    STAMP,
    _changed,
    _GitHub,
    _probe,
    _succeeded,
    _view,
)
from tests.test_github_pull_list_probe import repository as repository


def _low(resource: str, now: datetime) -> None:
    gh_budget.observe(
        {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "1000",
            "x-ratelimit-reset": str(int((now + timedelta(minutes=30)).timestamp())),
        },
        resource=resource,
    )


def test_below_the_floor_the_periodic_scan_stops_and_a_change_a_probe_finds_is_still_scanned(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _succeeded(repository)
    github = _GitHub(monkeypatch, generated_item(2))
    ask = RefreshRequest("all", background=True)
    probe = ListProbe()
    github.later(FULL_REFRESH_S + 1)
    assert refresh_wanted(_view(repository, probe), ask) == "scan"
    _low("graphql", github.now)
    try:
        # The scan every FULL_REFRESH_S is automatic work; the probe still runs.
        assert refresh_wanted(_view(repository, probe), ask) == "probe"
        _probe(probe, repository)
        assert refresh_wanted(_view(repository, probe), ask) is False
        # A reader's Refresh never asks the budget.
        assert refresh_wanted(_view(repository, probe), RefreshRequest("all", retry=True)) is True
        # And a change the probe finds is scanned for, below the floor as above it.
        github.update(_changed(2, minutes=5))
        github.later(LIST_PROBE_S)
        _probe(probe, repository)
        assert refresh_wanted(_view(repository, probe), ask) == "changed"
    finally:
        gh_budget.forget()


def test_over_the_process_ceiling_list_probes_and_scans_slow_until_the_hour_rolls(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _succeeded(repository)
    github = _GitHub(monkeypatch, generated_item(2))
    ask = RefreshRequest("all", background=True)
    probe = ListProbe()
    _probe(probe, repository)
    gh_budget.spent(gh_budget.AUTOMATIC_CORE_PER_HOUR, now=github.now)
    try:
        github.later(LIST_PROBE_S)
        assert not probe.due(github.now)
        github.later(FULL_REFRESH_S - LIST_PROBE_S)
        assert probe.due(github.now)
        # The scan, due every window with no probe vouching, waits five minutes.
        github.later(60)
        assert refresh_wanted(_view(repository, None), ask) is False
        github.later(gh_budget.CEILING_FULL_READ_S - FULL_REFRESH_S - 60 + 1)
        assert refresh_wanted(_view(repository, None), ask) == "scan"
        # An hour after the spending, everything is as it was.
        github.later(3600)
        assert not gh_budget.over_ceiling(github.now)
    finally:
        gh_budget.forget()
