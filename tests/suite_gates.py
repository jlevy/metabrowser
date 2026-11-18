"""Hooks that stop a test from being silently absent; ``tests/conftest.py`` registers them.

A skipped test is judged against the tier it belongs to (``docs/e2e-testing.md``):

- a ``macos_tier`` test may not skip where ``make test-macos`` requires the tier;
- a ``live_github`` test may skip, once the live tier is selected, only for what
  github.com holds today;
- in strict mode, which ``make test`` turns on in CI, any other skip must be the
  admitted-Git tier's. A reason outside the tiers means a test the suite is believed
  to run did not;
- where ``METABROWSER_STRICT_SKIPS=all``, which ``make golden-update`` sets, no test may
  skip, whatever its tier or reason: a recorder or driver that skipped regenerated
  nothing, and the update would report that it had.

A test is also judged on what it asked for: a module that reaches the Git floor has to
be in ``ADMITTED_GIT_TESTS``, or the admitted-git job never runs it unpatched.

And each tier marker is held to its meaning (``tests/suite_tiers.py``), so that no test
runs beside other workers when it should not, and none reaches one interpreter by being
marked:

- a test that asks for Chrome through ``require_chrome`` has to be ``chrome``;
- a ``chrome`` test has to use ``chrome_profile``, the marker's only source;
- a ``serial`` marker has to give its reason;
- no test in an ``ADMITTED_GIT_TESTS`` module may be ``serial`` or ``chrome``:
  ``make test-admitted-git`` runs that list beside other workers with no marker filter,
  so a module there that fails beside them is fixed, not marked.
"""

from __future__ import annotations

import os
import re
from collections.abc import Collection, Generator, Mapping, Sequence
from functools import cache
from pathlib import Path

import pytest

from tests.admitted_git import take_floor_request
from tests.required_tools import take_chrome_request
from tests.suite_tiers import CHROME_FIXTURE, CHROME_MARKER, SERIAL_MARKER

REQUIRE_MACOS_TIER_ENV = "METABROWSER_REQUIRE_MACOS_TIER"
LIVE_GITHUB_ENV = "METABROWSER_LIVE_GITHUB"
STRICT_SKIPS_ENV = "METABROWSER_STRICT_SKIPS"
# The value under which no skip stands at all; ``devtools/golden_update.py`` sets it.
STRICT_SKIPS_ALL = "all"

# What a live test may still skip for once its tier is selected: github.com's data.
LIVE_DATA_SKIPS = ("has no branch with a slash today", "has no open pull request today")
# The admitted-Git tier's skip, where the installed Git is below the floor.
ADMITTED_GIT_SKIP = "needs a Git the acquisition floor admits"


def refused_skip(markers: Collection[str], reason: str, environ: Mapping[str, str]) -> str | None:
    """Why this skip has to fail instead, or ``None`` when it may stand."""

    if environ.get(STRICT_SKIPS_ENV) == STRICT_SKIPS_ALL:
        return (
            f"{STRICT_SKIPS_ENV}={STRICT_SKIPS_ALL}, so no test may skip: what this one "
            f"writes was not regenerated on this machine: {reason}"
        )
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


def unmarked_chrome_request(markers: Collection[str]) -> str | None:
    """Why a test that asked for Chrome has to fail, or ``None`` when it is ``chrome``."""

    if CHROME_MARKER in markers:
        return None
    return (
        "this test asks for Chrome through require_chrome but is not in the Chrome tier, "
        f"so it would run beside other workers. Use the {CHROME_FIXTURE} fixture, which "
        f"gives it the {CHROME_MARKER} marker (tests/suite_tiers.py)."
    )


def misused_tier_marker(
    markers: Collection[str], serial_reasons: Sequence[object], fixtures: Collection[str]
) -> str | None:
    """Why a test's tier markers contradict their meaning, or ``None``.

    *serial_reasons* holds the ``reason`` of each ``serial`` marker the test carries,
    ``None`` where one gives none, and *fixtures* every fixture the test uses.
    """

    if CHROME_MARKER in markers and CHROME_FIXTURE not in fixtures:
        return (
            f"this test is marked {CHROME_MARKER} but does not use the {CHROME_FIXTURE} "
            f"fixture. The marker takes a test to one interpreter on a pull request, so it "
            f"comes from that fixture alone: drop the marker, or drive Chrome through the "
            f"fixture (tests/suite_tiers.py)."
        )
    if any(not isinstance(reason, str) or not reason.strip() for reason in serial_reasons):
        return (
            f"this test is marked {SERIAL_MARKER} without a reason. Write "
            f"pytest.mark.{SERIAL_MARKER}(reason=...) with the measurement that showed it "
            "needs the machine to itself, or fix what made it need that "
            "(tests/suite_tiers.py)."
        )
    return None


def tiered_admitted_git_test(
    module: str, markers: Collection[str], listed: Collection[str] | None
) -> str | None:
    """Why a ``serial`` or ``chrome`` test in an ``ADMITTED_GIT_TESTS`` module fails, or ``None``.

    ``make test-admitted-git`` runs the list beside other workers and selects no tier, so
    such a test would not have the machine to itself there.
    """

    tiers = sorted({SERIAL_MARKER, CHROME_MARKER} & set(markers))
    if listed is None or module not in listed or not tiers:
        return None
    return (
        f"{module} is in ADMITTED_GIT_TESTS, which make test-admitted-git runs beside "
        f"other workers with no marker filter, so a {' and '.join(tiers)} test there "
        "would not have the machine to itself. Fix what makes it need the machine, or "
        "move it to a module the list leaves out."
    )


def _serial_reasons(item: pytest.Item) -> list[object]:
    return [mark.kwargs.get("reason") for mark in item.iter_markers(name=SERIAL_MARKER)]


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
    listed = admitted_git_tests(item.config.rootpath)
    asked = take_floor_request()
    if asked and verdict is None and not report.failed and module not in _unlisted_reported:
        verdict = unlisted_floor_request(module, markers, listed)
        if verdict is not None:
            _unlisted_reported.add(module)
    if take_chrome_request() and verdict is None and not report.failed:
        verdict = unmarked_chrome_request(markers)
    # A test's markers are judged once: on its call, or on its setup where that skipped
    # and no call follows. A test that already failed keeps its own failure.
    once = report.when == "call" or (report.when == "setup" and report.skipped)
    if once and verdict is None and not report.failed:
        fixtures = getattr(item, "fixturenames", ())
        verdict = misused_tier_marker(markers, _serial_reasons(item), fixtures)
        verdict = verdict or tiered_admitted_git_test(module, markers, listed)
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
