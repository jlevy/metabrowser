"""``make golden-update`` cannot pass by skipping.

It claims to regenerate everything. A skipped recorder regenerates nothing, so
``devtools/golden_update.py`` runs its modules with ``METABROWSER_STRICT_SKIPS=all``, the
level of the suite's own skip judgement (``tests/suite_gates.py``) at which no skip
stands. The probes below are collected only by the nested runs, which name ``probe_*``
as their tests, so they go through ``tests/conftest.py`` as a real update does.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from devtools import golden_update
from devtools.check_goldens import UPDATE_ENV
from tests.suite_gates import (
    ADMITTED_GIT_SKIP,
    STRICT_SKIPS_ALL,
    STRICT_SKIPS_ENV,
    refused_skip,
)

ROOT = Path(__file__).resolve().parent.parent
PROBE_OUT_ENV = "METABROWSER_TEST_PROBE_OUT"
MAX_INNER_BOUND_S = 50


def probe_a_recorder_that_writes() -> None:
    assert os.environ[UPDATE_ENV] == "1"
    Path(os.environ[PROBE_OUT_ENV]).write_text("regenerated\n", encoding="utf-8")


def probe_a_recorder_below_the_git_floor() -> None:
    pytest.skip(f"{ADMITTED_GIT_SKIP}; found 'git version 2.39.5'")


def probe_a_recorder_without_node() -> None:
    pytest.skip("node is not on PATH, and METABROWSER_ALLOW_MISSING_TOOLS allows that")


@pytest.mark.macos_tier
def probe_a_macos_tier_recorder_that_skips() -> None:
    pytest.skip("the file system is case-sensitive")


@pytest.mark.xfail(reason="a known failure is not a skip", strict=True)
def probe_an_expected_failure() -> None:
    raise AssertionError("expected")


def _update(tmp_path: Path, *selection: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    out = tmp_path / "written.txt"
    this = str(Path(__file__).relative_to(ROOT))
    options = ["-v", "-p", "no:cacheprovider", "-p", "no:sugar", "-o", "python_functions=probe_*"]
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {UPDATE_ENV, STRICT_SKIPS_ENV}
    }
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "devtools.golden_update",
            *options,
            f"--basetemp={tmp_path / 'nested'}",
            *selection,
            this,
        ],
        cwd=ROOT,
        env={**environment, PROBE_OUT_ENV: str(out)},
        capture_output=True,
        text=True,
        timeout=MAX_INNER_BOUND_S,
        check=False,
    )
    return completed, out


def test_an_update_that_skips_nothing_writes_and_passes(tmp_path: Path) -> None:
    completed, out = _update(tmp_path, "-k", "writes or expected_failure")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert out.read_text(encoding="utf-8") == "regenerated\n"


def test_any_skip_fails_the_update_and_is_named(tmp_path: Path) -> None:
    completed, out = _update(tmp_path)
    report = completed.stdout
    outcomes = dict(re.findall(r"::(probe_\w+) ([A-Z]+)", report))
    assert outcomes == {
        "probe_a_recorder_that_writes": "PASSED",
        # The admitted-Git tier's skip stands in strict mode, and not in an update.
        "probe_a_recorder_below_the_git_floor": "FAILED",
        "probe_a_recorder_without_node": "FAILED",
        "probe_a_macos_tier_recorder_that_skips": "FAILED",
        "probe_an_expected_failure": "XFAIL",
    }, report + completed.stderr
    assert completed.returncode == 1
    assert report.count(f"{STRICT_SKIPS_ENV}={STRICT_SKIPS_ALL}, so no test may skip") >= 3
    assert "needs a Git the acquisition floor admits" in report
    # What could be regenerated was: the failure is about what was not.
    assert out.is_file()


def test_the_update_uses_the_suites_own_skip_judgement() -> None:
    """One place says which skips are allowed, and an update asks it for none."""

    assert (golden_update.STRICT_SKIPS_ENV, golden_update.STRICT_SKIPS_ALL) == (
        STRICT_SKIPS_ENV,
        STRICT_SKIPS_ALL,
    )
    everything = {STRICT_SKIPS_ENV: STRICT_SKIPS_ALL}
    for markers, reason in [
        ((), f"{ADMITTED_GIT_SKIP}; found 'git 2.39'"),
        ({"macos_tier"}, "the file system is case-sensitive"),
        ({"live_github"}, "set METABROWSER_LIVE_GITHUB=1 to run"),
        ((), "root is never denied by modes"),
    ]:
        refusal = refused_skip(markers, reason, everything)
        assert refusal is not None and reason in refusal


def test_no_module_is_a_usage_error() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "devtools.golden_update"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=MAX_INNER_BOUND_S,
        check=False,
    )
    assert completed.returncode == 2 and "usage:" in completed.stderr
