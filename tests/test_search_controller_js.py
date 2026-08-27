"""Behavioral checks for the headless browser search runtime."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SEARCH_CONTROLLER_TEST_JS = (
    Path(__file__).resolve().parent / "dom" / "search-controller-behavior.js"
)
SEARCH_CONTROLLER_PROFILE_JS = (
    Path(__file__).resolve().parent / "dom" / "search-controller-profile.js"
)


def test_search_controller_js_assertions_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SEARCH_CONTROLLER_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        "search-controller assertions failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"


def test_search_controller_profile_stays_bounded_and_responsive() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SEARCH_CONTROLLER_PROFILE_JS)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"search-controller profile failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("PROFILE "), f"unexpected stdout: {result.stdout!r}"
    report = json.loads(result.stdout.removeprefix("PROFILE "))

    assert report["shallow"]["candidateCount"] == 50
    assert report["recent"]["candidateCount"] == 2_000
    assert report["expanded"]["candidateCount"] == 50_000
    assert report["shallow"]["resultCount"] == 50
    assert report["recent"]["resultCount"] == 100
    assert report["expanded"]["resultCount"] == 100
    assert report["recent"]["timerBeforeCompletion"] is True
    assert report["expanded"]["timerBeforeCompletion"] is True
    assert report["cancellation"]["obsoleteResultWasDiscarded"] is True
    assert report["cancellation"]["publishedObsoleteCompletion"] is False
