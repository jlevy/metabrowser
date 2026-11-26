"""``devtools/ci_verdict.sh``, the CI ``ci-ok`` job, over recorded job results.

It fails unless every needed job succeeded, accepts a skipped stack-integration only
where the plan job found none to run, and while main is red writes the one verdict line
AGENTS.md (Git) merges by. That line's format is pinned here.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.required_tools import require_jq

ROOT = Path(__file__).resolve().parents[1]
VERDICT = ROOT / "devtools" / "ci_verdict.sh"
JOBS = ("plan", "lint", "distribution", "unit", "goldens", "chrome", "admitted-git")
RED_HEAD = "4" * 40
# The fixed format of A Red main in the fast CI plan; nothing else may be on the line.
VERDICT_LINE = re.compile(
    r"main-red run=(?:[0-9]+|none) head=(?:[0-9a-f]{40}|none) tested=(?:yes|no)"
)
CONFLICT = "::error::This branch conflicts with main, so the stack cannot merge as it stands."
# Well under the suite's per-test budget (pyproject.toml).
RUN_TIMEOUT_S = 30


@dataclass(frozen=True)
class Verdict:
    returncode: int
    lines: list[str]
    summary: str


def results(integration: str = "none", **overrides: str) -> dict[str, dict[str, object]]:
    """``toJSON(needs)`` for a run whose jobs all succeeded, but for *overrides*."""

    found: dict[str, dict[str, object]] = {
        job: {"result": "success", "outputs": {}} for job in JOBS
    }
    found["stack-integration"] = {
        "result": "success" if integration == "needed" else "skipped",
        "outputs": {},
    }
    for job, result in overrides.items():
        found[job.replace("_", "-")]["result"] = result
    return found


def verdict(
    tmp_path: Path,
    needs: dict[str, dict[str, object]],
    *,
    integration: str = "none",
    chrome: str = "whole",
    main_state: str = "green",
    main_run: str = "",
    main_run_sha: str = "",
    tests_red: str = "no",
) -> Verdict:
    require_jq()
    summary = tmp_path / "summary"
    summary.write_text("", encoding="utf-8")
    environ = dict(os.environ) | {
        "RESULTS": json.dumps(needs),
        "INTEGRATION": integration,
        "CHROME": chrome,
        "MAIN_STATE": main_state,
        "MAIN_RUN": main_run,
        "MAIN_RUN_SHA": main_run_sha,
        "TESTS_RED": tests_red,
        "GITHUB_STEP_SUMMARY": str(summary),
    }
    completed = subprocess.run(
        ["bash", str(VERDICT)],
        env=environ,
        capture_output=True,
        text=True,
        check=False,
        timeout=RUN_TIMEOUT_S,
    )
    return Verdict(
        completed.returncode,
        (completed.stdout + completed.stderr).splitlines(),
        summary.read_text(encoding="utf-8"),
    )


def _verdict_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if "main-red" in line]


@pytest.mark.parametrize("integration", ["none", "identical", "contained"])
def test_every_job_green_passes_with_no_verdict_line_while_main_is_green(
    tmp_path: Path, integration: str
) -> None:
    result = verdict(tmp_path, results(integration), integration=integration)

    assert result.returncode == 0, result.lines
    assert _verdict_lines(result.lines) == []
    assert not any(line.startswith("::notice::") for line in result.lines)
    assert "| stack-integration | skipped |" in result.summary
    # A8 of review A on #504: the required check says why it accepted the skip.
    accepted = (
        f"stack-integration skipped: integration={integration} (the plan job's summary says why)"
    )
    assert accepted in result.lines
    assert accepted in result.summary


def test_a_needed_integration_that_ran_passes(tmp_path: Path) -> None:
    result = verdict(tmp_path, results("needed"), integration="needed")

    assert result.returncode == 0, result.lines


def test_a_needed_integration_that_was_skipped_fails(tmp_path: Path) -> None:
    needs = results("needed", stack_integration="skipped")
    result = verdict(tmp_path, needs, integration="needed")

    assert result.returncode == 1
    assert "::error::Not every job succeeded: stack-integration (skipped)" in result.lines


def test_a_chrome_job_skipped_because_the_plan_decided_none_is_accepted_and_said(
    tmp_path: Path,
) -> None:
    result = verdict(tmp_path, results(chrome="skipped"), chrome="none")

    assert result.returncode == 0, result.lines
    accepted = (
        "chrome skipped: chrome=none, the pull request touches no browser path "
        "(the plan job's summary says why)"
    )
    # Both skips are said, each on its own line.
    assert accepted in result.lines and accepted in result.summary
    assert any(line.startswith("stack-integration skipped: ") for line in result.lines)


@pytest.mark.parametrize("chrome", ["whole", ""])
def test_a_chrome_job_skipped_when_the_plan_decided_to_run_it_fails(
    tmp_path: Path, chrome: str
) -> None:
    """The whole tier, or no decision at all, as when the plan
    job failed: a Chrome job that did not run is a check that did not happen."""

    result = verdict(tmp_path, results(chrome="skipped"), chrome=chrome)

    assert result.returncode == 1
    assert "::error::Not every job succeeded: chrome (skipped)" in result.lines


@pytest.mark.parametrize("outcome", ["failure", "cancelled"])
def test_a_chrome_job_that_ran_and_did_not_pass_fails_whatever_the_plan_decided(
    tmp_path: Path, outcome: str
) -> None:
    result = verdict(tmp_path, results(chrome=outcome), chrome="none")

    assert result.returncode == 1
    assert f"::error::Not every job succeeded: chrome ({outcome})" in result.lines


def test_a_conflict_with_main_fails_with_the_stack_message(tmp_path: Path) -> None:
    result = verdict(tmp_path, results("conflict"), integration="conflict")

    assert result.returncode == 1
    assert CONFLICT in result.lines


@pytest.mark.parametrize("outcome", ["failure", "cancelled", "skipped"])
def test_any_other_job_short_of_success_fails_and_is_named(tmp_path: Path, outcome: str) -> None:
    result = verdict(tmp_path, results(chrome=outcome, admitted_git="failure"))

    assert result.returncode == 1
    assert (
        f"::error::Not every job succeeded: chrome ({outcome}), admitted-git (failure)"
        in result.lines
    )


def test_a_failed_plan_fails_even_with_no_integration_named(tmp_path: Path) -> None:
    result = verdict(tmp_path, results(plan="failure"), integration="")

    assert result.returncode == 1
    # With no integration named, a skipped stack-integration is not accepted either.
    assert (
        "::error::Not every job succeeded: plan (failure), stack-integration (skipped)"
        in result.lines
    )


def test_no_results_at_all_fail(tmp_path: Path) -> None:
    result = verdict(tmp_path, {})

    assert result.returncode == 1
    assert "::error::Not every job succeeded: no job results" in result.lines


@pytest.mark.parametrize("tests_red", ["yes", "no"])
def test_a_red_main_writes_the_verdict_line_and_never_fails_the_run_by_itself(
    tmp_path: Path, tests_red: str
) -> None:
    result = verdict(
        tmp_path,
        results(),
        main_state="red",
        main_run="44007745684",
        main_run_sha=RED_HEAD,
        tests_red=tests_red,
    )

    line = f"main-red run=44007745684 head={RED_HEAD} tested={tests_red}"
    assert result.returncode == 0, result.lines
    assert _verdict_lines(result.lines) == [line, f"::notice::{line}"]
    assert VERDICT_LINE.fullmatch(line)
    assert line in result.summary


def test_a_red_main_that_could_not_be_read_names_no_run(tmp_path: Path) -> None:
    result = verdict(tmp_path, results(), main_state="red", tests_red="no")

    line = "main-red run=none head=none tested=no"
    assert _verdict_lines(result.lines) == [line, f"::notice::{line}"]
    assert VERDICT_LINE.fullmatch(line)


def test_only_tests_red_yes_says_tested(tmp_path: Path) -> None:
    result = verdict(
        tmp_path, results(), main_state="red", main_run="7", main_run_sha=RED_HEAD, tests_red=""
    )

    assert _verdict_lines(result.lines)[0].endswith("tested=no")


def test_a_red_main_still_writes_the_line_when_a_job_fails(tmp_path: Path) -> None:
    result = verdict(
        tmp_path,
        results(unit="failure"),
        main_state="red",
        main_run="9",
        main_run_sha=RED_HEAD,
        tests_red="yes",
    )

    assert result.returncode == 1
    assert _verdict_lines(result.lines) == [
        f"main-red run=9 head={RED_HEAD} tested=yes",
        f"::notice::main-red run=9 head={RED_HEAD} tested=yes",
    ]


@pytest.mark.parametrize("main_state", ["green", "none", ""])
def test_no_verdict_line_unless_main_is_red(tmp_path: Path, main_state: str) -> None:
    result = verdict(
        tmp_path, results(), main_state=main_state, main_run="9", main_run_sha=RED_HEAD
    )

    assert _verdict_lines(result.lines) == []
