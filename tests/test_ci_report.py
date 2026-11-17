"""``devtools/ci_report.py``: job times, push to green, and reruns, from recorded run data."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from devtools import ci_report
from devtools.check_goldens import recipe
from devtools.ci_report import CHECK_FRACTION, GITHUB_DEFAULT_TIMEOUT_MINUTES, WORKFLOW

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_TEXT = """
jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 3
  test:
    strategy:
      matrix:
        python-version: ["3.13"]
    timeout-minutes: 12
  admitted-git:
    name: admitted-git (${{ matrix.git }})
    timeout-minutes: ${{ inputs.limit }}
  build:
    runs-on: ubuntu-latest
"""

Json = dict[str, object]


def _at(minutes: float) -> str:
    """A time *minutes* after 2026-11-16 00:00 UTC, as the API writes it."""

    hours, rest = divmod(round(minutes * 60), 3600)
    return f"2026-11-16T{hours:02d}:{rest // 60:02d}:{rest % 60:02d}Z"


def _job(id: int, name: str, start: float, end: float | None, conclusion: str = "success") -> Json:
    return {
        "id": id,
        "name": name,
        "status": "completed" if end is not None else "in_progress",
        "conclusion": conclusion if end is not None else None,
        "started_at": _at(start),
        "completed_at": _at(end) if end is not None else None,
        "steps": [
            {
                "name": "Set up job",
                "conclusion": "success",
                "started_at": _at(start),
                "completed_at": _at(start + 0.5),
            },
            {
                "name": "Run",
                "conclusion": conclusion,
                "started_at": _at(start + 0.5),
                "completed_at": _at(end) if end is not None else None,
            },
        ],
    }


def _run(id: int, created: float, attempts: int, event: str, branch: str, base: str | None) -> Json:
    pulls = [] if base is None else [{"number": id, "base": {"ref": base}}]
    return {
        "id": id,
        "event": event,
        "head_branch": branch,
        "run_attempt": attempts,
        "created_at": _at(created),
        "pull_requests": pulls,
    }


# Six runs, newest first as the API lists them. Times are minutes after midnight.
RUNS: list[Json] = [
    _run(6, 500, 1, "pull_request", "feature-6", "main"),
    _run(5, 400, 2, "pull_request", "feature-5", "main"),
    _run(4, 300, 1, "pull_request", "layer-2", "layer-1"),
    _run(3, 200, 1, "pull_request", "feature-3", "main"),
    _run(2, 100, 1, "pull_request", "feature-2", "main"),
    _run(1, 0, 1, "push", "main", None),
]
JOBS: dict[tuple[int, int], list[Json]] = {
    # Green: 10.5 minutes from the push, 11.5 runner minutes.
    (1, 1): [_job(11, "lint", 0.5, 2.0), _job(12, "test (3.13)", 0.5, 10.5)],
    # Green: 13, and 14.
    (2, 1): [_job(21, "lint", 101, 103), _job(22, "test (3.13)", 101, 113)],
    # Red: a test failed.
    (3, 1): [_job(31, "lint", 201, 202), _job(32, "test (3.13)", 201, 206, "failure")],
    # Cancelled, with nothing failed.
    (4, 1): [_job(41, "lint", 301, 302), _job(42, "test (3.13)", 301, 305, "cancelled")],
    # Red, then green on a rerun of the failed job alone; lint is carried over.
    (5, 1): [_job(51, "lint", 401, 402), _job(52, "test (3.13)", 401, 409, "failure")],
    (5, 2): [_job(51, "lint", 401, 402), _job(53, "test (3.13)", 420, 429)],
    # Still going.
    (6, 1): [_job(61, "lint", 501, 502), _job(62, "test (3.13)", 501, None)],
}


def _record(directory: Path) -> Path:
    ci_report.save(directory, RUNS, JOBS)
    return directory


@pytest.fixture
def workflow(tmp_path: Path) -> Path:
    path = tmp_path / "ci.yml"
    path.write_text(WORKFLOW_TEXT, encoding="utf-8")
    return path


def test_a_percentile_interpolates_between_ranks() -> None:
    assert ci_report.percentile([4.0, 1.0, 3.0, 2.0], 0.5) == 2.5
    assert ci_report.percentile([1.0, 2.0, 3.0, 4.0], 0.9) == pytest.approx(3.7)
    assert ci_report.percentile([7.0], 0.9) == 7.0


def test_a_job_s_limit_is_found_by_its_display_name(workflow: Path) -> None:
    known = ci_report.limits(workflow)

    assert ci_report.limit_of("lint", known) == 3
    assert ci_report.limit_of("test (3.13)", known) == 12
    # A limit given by an expression cannot be read, and a job that gives none has
    # GitHub's default.
    assert ci_report.limit_of("admitted-git (2.43.7)", known) is None
    assert ci_report.limit_of("build", known) == GITHUB_DEFAULT_TIMEOUT_MINUTES
    assert ci_report.limit_of("test", known) is None


def test_every_job_of_this_repository_s_workflow_has_its_limit_found() -> None:
    known = ci_report.limits(WORKFLOW)

    for name in ("lint", "distribution", "test (3.13)", "admitted-git (2.50.1)"):
        assert ci_report.limit_of(name, known) is not None, name


def test_the_report_gives_push_to_green_jobs_and_reruns(
    tmp_path: Path, workflow: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _record(tmp_path / "runs")

    assert ci_report.main(["--from", str(source), "--workflow", str(workflow), "--steps"]) == 0

    report = capsys.readouterr().out
    assert report.startswith("6 runs, 7 attempts, 13 job executions, created 2026-11-16 00:00")
    # By kind and outcome; the run still going is left out.
    assert "| pull request to main | green | 1 | 13.0 | 13.0 | 14.0 |" in report
    assert "| pull request to main | red | 2 | 7.5 | 8.7 | 7.5 |" in report
    assert "| push to main | green | 1 | 10.5 | 10.5 | 11.5 |" in report
    assert "| stacked pull request | cancelled | 1 | 5.0 | 5.0 | 5.0 |" in report
    assert "1 run(s) still going or without jobs are left out." in report
    # Run 5 ended green on its second attempt, 29 minutes after its push.
    assert "1 of 6 runs had more than one attempt; push to green for the 1 that ended" in report
    assert "median 29.0 min" in report
    # Each successful execution once: lint 1.5, 2, 1, 1, 1, and 1 in the run still going,
    # with the one the rerun carried over not counted again; test 10, 12, and 9.
    assert "| lint | 6 | 1.0 | 1.8 | 2.0 | 3 |" in report
    assert "| test (3.13) | 3 | 10.0 | 11.6 | 12.0 | 12 |" in report
    assert "| test (3.13) | Set up job | 0.50 | 0.50 |" in report


def test_check_fails_on_a_job_whose_90th_percentile_nears_its_limit(
    tmp_path: Path, workflow: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _record(tmp_path / "runs")

    assert ci_report.main(["--from", str(source), "--workflow", str(workflow), "--check"]) == 1

    errors = capsys.readouterr().err.splitlines()
    assert errors == [
        f"ci-report: test (3.13)'s 90th percentile, 11.6 min, passes {CHECK_FRACTION:.0%} "
        "of its 12-minute limit: add a shard, or make its slowest tests cheaper"
    ]


def _fake_gh(directory: Path, runs: Sequence[Json], jobs: Mapping[tuple[int, int], object]) -> Path:
    """A ``gh`` that answers ``gh api`` from *runs* and *jobs*, and logs each path."""

    directory.mkdir()
    (directory / "runs.json").write_text(json.dumps(runs), encoding="utf-8")
    (directory / "jobs.json").write_text(
        json.dumps({f"{run}/{number}": listed for (run, number), listed in jobs.items()}),
        encoding="utf-8",
    )
    script = directory / "gh"
    script.write_text(
        f"#!{sys.executable}\n"
        + """
import json, pathlib, re, sys
here = pathlib.Path(__file__).parent
path = sys.argv[2]
with open(here / "calls.log", "a", encoding="utf-8") as log:
    log.write(path + "\\n")
if "/workflows/" in path:
    runs = json.loads((here / "runs.json").read_text())
    page = int(re.search(r"[?&]page=(\\d+)", path).group(1))
    print(json.dumps({"workflow_runs": runs[(page - 1) * 100 : page * 100]}))
elif found := re.search(r"/runs/(\\d+)/attempts/(\\d+)/jobs", path):
    listed = json.loads((here / "jobs.json").read_text())[f"{found[1]}/{found[2]}"]
    print(json.dumps({"total_count": len(listed), "jobs": listed}))
else:
    sys.exit(f"unknown path {path}")
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return directory


def test_runs_are_read_through_gh_and_saved_as_they_were_read(
    tmp_path: Path,
    workflow: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    gh = _fake_gh(tmp_path / "gh", RUNS, JOBS)
    monkeypatch.setenv("PATH", f"{gh}{os.pathsep}{os.environ['PATH']}")
    saved = tmp_path / "saved"

    arguments = ["--runs", "3", "--branch", "main", "--workflow", str(workflow)]
    assert ci_report.main([*arguments, "--save", str(saved)]) == 0

    calls = (gh / "calls.log").read_text(encoding="utf-8").splitlines()
    assert calls[0] == (
        "repos/{owner}/{repo}/actions/workflows/ci.yml/runs?per_page=100&page=1&branch=main"
    )
    # The three newest runs, and both attempts of the one that had two.
    assert sorted(calls[1:]) == [
        f"repos/{{owner}}/{{repo}}/actions/runs/{run}/attempts/{number}/jobs?per_page=100"
        for run, number in [(4, 1), (5, 1), (5, 2), (6, 1)]
    ]
    first = capsys.readouterr().out
    assert first.startswith("3 runs, 4 attempts")
    # A branch's `&`, `#`, and `/` reach GitHub as part of its value, not of the query.
    assert ci_report.main(["--runs", "1", "--branch", "a/b&c#d", "--workflow", str(workflow)]) == 0
    calls = (gh / "calls.log").read_text(encoding="utf-8").splitlines()
    assert calls[-2].endswith("runs?per_page=100&page=1&branch=a%2Fb%26c%23d")
    capsys.readouterr()
    assert ci_report.main(["--from", str(saved), "--workflow", str(workflow)]) == 0
    assert capsys.readouterr().out == first


def test_a_failed_read_is_reported_without_a_traceback(
    tmp_path: Path, workflow: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ci_report.main(["--from", str(tmp_path / "nothing"), "--workflow", str(workflow)]) == 1
    assert capsys.readouterr().err.startswith(f"ci-report: {tmp_path / 'nothing'} holds no")


def test_the_make_target_passes_its_flags() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert recipe(makefile, "ci-report") == (
        "\t$(UV_RUN) python -m devtools.ci_report $(CI_REPORT_FLAGS)"
    )
