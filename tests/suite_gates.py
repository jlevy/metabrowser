"""Hooks that stop a test from being silently absent; ``tests/conftest.py`` registers them.

A skipped test is judged against the tier it belongs to (``docs/e2e-testing.md``):

- a ``macos_tier`` test may not skip where ``make test-macos`` requires the tier;
- a ``live_github`` test may skip, once the live tier is selected, only for what
  github.com holds today;
- in strict mode, which ``make test`` turns on in CI, any other skip must be the
  admitted-Git tier's. A reason outside the tiers means a test the suite is believed
  to run did not.

A test is also judged on what it asked for: a module that reaches the Git floor has to
be in ``ADMITTED_GIT_TESTS``, or the admitted-git job never runs it unpatched.
"""

from __future__ import annotations

import os
import re
from collections.abc import Collection, Generator, Mapping
from functools import cache
from pathlib import Path

import pytest

from tests.admitted_git import take_floor_request

REQUIRE_MACOS_TIER_ENV = "METABROWSER_REQUIRE_MACOS_TIER"
LIVE_GITHUB_ENV = "METABROWSER_LIVE_GITHUB"
STRICT_SKIPS_ENV = "METABROWSER_STRICT_SKIPS"

# What a live test may still skip for once its tier is selected: github.com's data.
LIVE_DATA_SKIPS = ("has no branch with a slash today", "has no open pull request today")
# The admitted-Git tier's skip, where the installed Git is below the floor.
ADMITTED_GIT_SKIP = "needs a Git the acquisition floor admits"


def refused_skip(markers: Collection[str], reason: str, environ: Mapping[str, str]) -> str | None:
    """Why this skip has to fail instead, or ``None`` when it may stand."""

    if "macos_tier" in markers:
        if environ.get(REQUIRE_MACOS_TIER_ENV) == "1":
            return f"{REQUIRE_MACOS_TIER_ENV}=1, so a macOS-tier test may not skip: {reason}"
        return None
    if "live_github" in markers:
        selected = environ.get(LIVE_GITHUB_ENV) == "1"
        if selected and not any(known in reason for known in LIVE_DATA_SKIPS):
            return (
                f"{LIVE_GITHUB_ENV}=1 selected the live tier, so a live test may skip "
                f"only for what github.com holds today: {reason}"
            )
        return None
    if environ.get(STRICT_SKIPS_ENV) == "1" and ADMITTED_GIT_SKIP not in reason:
        return (
            f"{STRICT_SKIPS_ENV}=1, and this skip belongs to no tier that "
            f"docs/e2e-testing.md names: {reason}"
        )
    return None


def unlisted_floor_request(
    module: str, markers: Collection[str], listed: Collection[str] | None
) -> str | None:
    """Why a test that asked for the Git floor has to fail, or ``None``.

    The live tier asks too, but it needs the network, so the admitted-git job does not
    run it. *listed* is ``None`` where there is no ``Makefile`` to read.
    """

    if listed is None or module in listed or "live_github" in markers:
        return None
    return (
        f"{module} asks for the Git floor but is not in ADMITTED_GIT_TESTS in the "
        "Makefile, so the admitted-git job never runs it unpatched. Add it there."
    )


@cache
def admitted_git_tests(root: Path) -> frozenset[str] | None:
    """The modules ``make test-admitted-git`` runs, as the ``Makefile`` lists them."""

    makefile = root / "Makefile"
    if not makefile.is_file():
        return None
    listing = makefile.read_text(encoding="utf-8").split("ADMITTED_GIT_TESTS :=", 1)[1]
    return frozenset(re.findall(r"tests/test_\w+\.py", listing.split("\n\n", 1)[0]))


def _skip_reason(report: pytest.TestReport | pytest.CollectReport) -> str:
    reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
    return reason.removeprefix("Skipped: ")


# One failure names an unlisted module; its other tests need not repeat it.
_unlisted_reported: set[str] = set()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    markers = {mark.name for mark in item.iter_markers()}
    verdict = None
    # An expected failure is reported as a skip that carries ``wasxfail``; it ran.
    if report.skipped and not hasattr(report, "wasxfail"):
        verdict = refused_skip(markers, _skip_reason(report), os.environ)
    module = item.nodeid.split("::", 1)[0]
    asked = take_floor_request()
    if asked and verdict is None and not report.failed and module not in _unlisted_reported:
        verdict = unlisted_floor_request(module, markers, admitted_git_tests(item.config.rootpath))
        if verdict is not None:
            _unlisted_reported.add(module)
    if verdict is not None:
        report.outcome = "failed"
        report.longrepr = verdict
    return report


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, pytest.CollectReport, pytest.CollectReport]:
    """A module that skips itself at import has no test to judge, so judge it here."""

    report = yield
    if report.skipped:
        verdict = refused_skip((), _skip_reason(report), os.environ)
        if verdict is not None:
            report.outcome = "failed"
            report.longrepr = verdict
    return report
