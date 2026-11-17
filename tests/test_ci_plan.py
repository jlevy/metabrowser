"""``devtools/ci_plan.sh``, the CI ``plan`` job, run as the workflow runs it.

The API answers are recorded: a stand-in ``gh`` serves them from files, and a file that
is not there is a read that failed. The Git cases use real repositories: an origin, and
a checkout of the merge commit a pull request run tests.

The cases are those of the fast CI plan's Testing Strategy
(``docs/project/specs/active/plan-2026-11-16-fast-ci.md``): each completed answer, each
unfinished run followed by the run behind it, whether a run tested main's red head, the
Chrome tier for each kind of run, and stack-integration by tree.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.required_tools import require_git, require_jq

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "devtools" / "ci_plan.sh"
PYTHONS = ["3.12", "3.13", "3.14", "3.14t"]
PR_CHROME_PYTHON = "3.13"
WIDE = PYTHONS
NARROW = [PR_CHROME_PYTHON]
REPO = "example/project"
Json = dict[str, object]
# Well under the suite's per-test budget (pyproject.toml), as every bound here must be.
RUN_TIMEOUT_S = 30

# `gh api <path>`, answered from $FAKE_GH_DIR: runs.json for the runs listing, and
# attempt-<run>-<n>.json for one attempt. Every call is logged, and a missing file fails
# as an unreachable API does.
FAKE_GH = """#!/usr/bin/env bash
printf '%s\\n' "$*" >>"$FAKE_GH_DIR/calls.log"
[ "$1" = api ] || { echo "fake gh: only api" >&2; exit 2; }
case $2 in
  repos/*/actions/workflows/ci.yml/runs\\?*) file=runs.json ;;
  repos/*/actions/runs/*/attempts/*)
    run=${2#*/actions/runs/}; run=${run%%/*}
    file="attempt-$run-${2##*/}.json" ;;
  *) echo "fake gh: unexpected path $2" >&2; exit 2 ;;
esac
[ -f "$FAKE_GH_DIR/$file" ] || { echo "HTTP 502: Bad Gateway" >&2; exit 1; }
cat "$FAKE_GH_DIR/$file"
"""


def _run(run_id: int, sha: str, status: str, conclusion: str | None, attempt: int = 1) -> Json:
    return {
        "id": run_id,
        "head_sha": sha,
        "status": status,
        "conclusion": conclusion,
        "run_attempt": attempt,
    }


def _done(run_id: int, sha: str, conclusion: str) -> Json:
    return _run(run_id, sha, "completed", conclusion)


def _going(run_id: int, sha: str, status: str = "in_progress", attempt: int = 1) -> Json:
    return _run(run_id, sha, status, None, attempt)


@dataclass(frozen=True)
class Planned:
    returncode: int
    outputs: dict[str, str]
    summary: str
    log: str
    calls: list[str]

    @property
    def chrome(self) -> list[str]:
        return json.loads(self.outputs["chrome-pythons"])


class Repositories:
    """An origin with a ``main`` branch, and a checkout of the commit a run tests."""

    def __init__(self, root: Path) -> None:
        require_git()
        self.root = root
        self.origin = root / "origin.git"
        self.work = root / "work"
        self.checkout = root / "checkout"
        self.env = {
            name: value for name, value in os.environ.items() if not name.startswith("GIT_")
        }
        absent = str(root / ".gitconfig-absent")
        self.env |= {
            "GIT_CONFIG_GLOBAL": absent,
            "GIT_CONFIG_SYSTEM": absent,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
        root.mkdir(parents=True)
        self.git(root, "init", "--quiet", "--bare", "--initial-branch=main", str(self.origin))
        self.git(root, "init", "--quiet", "--initial-branch=main", str(self.work))
        self.git(self.work, "remote", "add", "origin", str(self.origin))
        self.commit("main", {"shared.txt": "one\n"})

    def git(self, cwd: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
            timeout=RUN_TIMEOUT_S,
        )
        return completed.stdout.strip()

    def commit(self, branch: str, files: dict[str, str], *, start: str | None = None) -> str:
        """Commit *files* on *branch*, made from *start* when it is new, and push it."""

        if start is not None:
            self.git(self.work, "checkout", "--quiet", "-B", branch, start)
        elif self.git(self.work, "branch", "--list", branch):
            self.git(self.work, "checkout", "--quiet", branch)
        for name, text in files.items():
            (self.work / name).write_text(text, encoding="utf-8")
        self.git(self.work, "add", "--all")
        self.git(self.work, "commit", "--quiet", "-m", f"{branch}: {', '.join(files)}")
        self.git(self.work, "push", "--quiet", "--force", "origin", branch)
        return self.git(self.work, "rev-parse", "HEAD")

    def check_out_merge(self, head: str, base: str) -> Path:
        """The checkout a pull request run tests: *head* merged into the branch *base*."""

        if not self.checkout.exists():
            self.git(self.root, "clone", "--quiet", str(self.origin), str(self.checkout))
        self.git(self.checkout, "fetch", "--quiet", "origin")
        self.git(self.checkout, "checkout", "--quiet", "--detach", f"origin/{base}")
        self.git(self.checkout, "merge", "--quiet", "--no-ff", "--no-edit", head)
        return self.checkout


@pytest.fixture
def repos(tmp_path: Path) -> Repositories:
    return Repositories(tmp_path / "git")


def plan(
    tmp_path: Path,
    cwd: Path,
    *,
    event: str = "pull_request",
    base: str = "main",
    head_sha: str = "",
    runs: list[Json] | None = None,
    attempts: dict[tuple[int, int], Json] | None = None,
    pythons: list[str] = PYTHONS,
    pr_chrome_python: str = PR_CHROME_PYTHON,
    env: dict[str, str] | None = None,
) -> Planned:
    """Run the plan job's step; *runs* is the recorded listing, ``None`` a failed read."""

    require_jq()
    answers = tmp_path / "gh"
    answers.mkdir(exist_ok=True)
    if runs is not None:
        (answers / "runs.json").write_text(json.dumps({"workflow_runs": runs}), "utf-8")
    for (run_id, number), answer in (attempts or {}).items():
        (answers / f"attempt-{run_id}-{number}.json").write_text(json.dumps(answer), "utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH, encoding="utf-8")
    gh.chmod(0o755)
    output = tmp_path / "output"
    summary = tmp_path / "summary"
    output.write_text("", encoding="utf-8")
    summary.write_text("", encoding="utf-8")
    environ = dict(env if env is not None else os.environ)
    environ |= {
        "PATH": f"{bin_dir}{os.pathsep}{environ.get('PATH', '')}",
        "FAKE_GH_DIR": str(answers),
        "EVENT": event,
        "BASE": base,
        "HEAD_SHA": head_sha,
        "REPO": REPO,
        "GH_TOKEN": "recorded",
        "PYTHONS": json.dumps(pythons),
        "PR_CHROME_PYTHON": pr_chrome_python,
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(summary),
    }
    completed = subprocess.run(
        ["bash", str(PLAN)],
        cwd=cwd,
        env=environ,
        capture_output=True,
        text=True,
        check=False,
        timeout=RUN_TIMEOUT_S,
    )
    outputs = dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if line
    )
    calls_log = answers / "calls.log"
    calls = calls_log.read_text(encoding="utf-8").splitlines() if calls_log.exists() else []
    return Planned(
        completed.returncode,
        outputs,
        summary.read_text(encoding="utf-8"),
        completed.stdout + completed.stderr,
        calls,
    )


def _pull_request(
    tmp_path: Path,
    repos: Repositories,
    runs: list[Json] | None,
    attempts: dict[tuple[int, int], Json] | None = None,
) -> Planned:
    """A pull request to main whose merge commit contains main's head."""

    head = repos.commit("feature", {"feature.txt": "feature\n"}, start="main")
    checkout = repos.check_out_merge(head, "main")
    result = plan(tmp_path, checkout, runs=runs, attempts=attempts, env=repos.env)
    assert result.returncode == 0, result.log
    return result


# ── Completed answers ──────────────────────────────────────────────────────────────


def test_a_green_main_keeps_the_chrome_tier_on_one_interpreter(
    tmp_path: Path, repos: Repositories
) -> None:
    main = repos.git(repos.work, "rev-parse", "main")
    result = _pull_request(tmp_path, repos, [_done(101, main, "success")])

    assert result.outputs["main-state"] == "green"
    assert result.outputs["main-run"] == "101"
    assert result.outputs["main-run-sha"] == ""
    assert result.outputs["tests-red"] == "no"
    assert result.chrome == NARROW
    assert result.outputs["integration"] == "none"
    assert "| main | green, run 101; tests-red=no |" in result.summary


@pytest.mark.parametrize(
    "conclusion",
    ["failure", "cancelled", "timed_out", "startup_failure", "action_required", "neutral"],
)
def test_every_completed_answer_but_success_is_red_and_widens_the_chrome_tier(
    tmp_path: Path, repos: Repositories, conclusion: str
) -> None:
    main = repos.git(repos.work, "rev-parse", "main")
    result = _pull_request(tmp_path, repos, [_done(102, main, conclusion)])

    assert result.outputs["main-state"] == "red"
    assert result.outputs["main-run"] == "102"
    assert result.outputs["main-run-sha"] == main
    assert result.chrome == WIDE


def test_no_run_on_main_is_red(tmp_path: Path, repos: Repositories) -> None:
    result = _pull_request(tmp_path, repos, [])

    assert result.outputs["main-state"] == "red"
    assert result.outputs["main-run"] == ""
    assert result.outputs["main-run-sha"] == ""
    assert result.outputs["tests-red"] == "no"
    assert result.chrome == WIDE
    assert "has a completed attempt" in result.summary


def test_a_failed_read_is_red_and_says_so(tmp_path: Path, repos: Repositories) -> None:
    result = _pull_request(tmp_path, repos, None)

    assert result.outputs["main-state"] == "red"
    assert result.outputs["main-run"] == ""
    assert result.outputs["tests-red"] == "no"
    assert result.chrome == WIDE
    assert "main's state could not be read" in result.summary
    assert "::warning::main's state could not be read" in result.log


def test_an_answer_that_is_not_runs_is_a_failed_read(tmp_path: Path, repos: Repositories) -> None:
    head = repos.commit("feature", {"feature.txt": "feature\n"}, start="main")
    checkout = repos.check_out_merge(head, "main")
    (tmp_path / "gh").mkdir()
    (tmp_path / "gh" / "runs.json").write_text('{"message": "Not Found"}', "utf-8")
    result = plan(tmp_path, checkout, env=repos.env)

    assert result.returncode == 0, result.log
    assert result.outputs["main-state"] == "red"
    assert "could not be read" in result.summary


@pytest.mark.parametrize(
    ("run_id", "sha"),
    [("12; echo main-state=green", "c" * 40), ("601", "-" + "c" * 39), ("602", "C" * 40)],
    ids=["an id that is not a number", "a head that starts with a dash", "an uppercase head"],
)
def test_an_answer_with_a_malformed_id_or_head_is_a_failed_read(
    tmp_path: Path, repos: Repositories, run_id: str, sha: str
) -> None:
    """B3 of review B on #504: the id goes into a path and the outputs, the head to git."""

    head = repos.commit("feature", {"feature.txt": "feature\n"}, start="main")
    checkout = repos.check_out_merge(head, "main")
    runs: list[Json] = [
        {
            "id": run_id,
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 1,
        }
    ]
    result = plan(tmp_path, checkout, runs=runs, env=repos.env)

    assert result.returncode == 0, result.log
    assert result.outputs["main-state"] == "red"
    assert result.outputs["main-run"] == ""
    assert result.chrome == WIDE
    assert "could not be read" in result.summary


# ── Unfinished runs, each followed by the run behind it ────────────────────────────


def test_a_first_attempt_in_progress_then_success_is_green(
    tmp_path: Path, repos: Repositories
) -> None:
    main = repos.git(repos.work, "rev-parse", "main")
    result = _pull_request(tmp_path, repos, [_going(202, "a" * 40), _done(201, main, "success")])

    assert result.outputs["main-state"] == "green"
    assert result.outputs["main-run"] == "201"
    assert result.chrome == NARROW


def test_a_first_attempt_in_progress_then_failure_is_red_at_the_failed_head(
    tmp_path: Path, repos: Repositories
) -> None:
    failed = repos.git(repos.work, "rev-parse", "main")
    result = _pull_request(tmp_path, repos, [_going(204, "a" * 40), _done(203, failed, "failure")])

    assert result.outputs["main-state"] == "red"
    assert result.outputs["main-run"] == "203"
    assert result.outputs["main-run-sha"] == failed
    assert result.chrome == WIDE


def test_two_first_attempts_in_progress_then_success_is_green(
    tmp_path: Path, repos: Repositories
) -> None:
    main = repos.git(repos.work, "rev-parse", "main")
    runs = [_going(207, "a" * 40), _going(206, "b" * 40), _done(205, main, "success")]
    result = _pull_request(tmp_path, repos, runs)

    assert result.outputs["main-state"] == "green"
    assert result.outputs["main-run"] == "205"
    assert result.chrome == NARROW


@pytest.mark.parametrize("status", ["queued", "waiting", "requested", "pending"])
def test_a_run_not_started_then_success_is_green(
    tmp_path: Path, repos: Repositories, status: str
) -> None:
    main = repos.git(repos.work, "rev-parse", "main")
    result = _pull_request(
        tmp_path, repos, [_going(209, "a" * 40, status), _done(208, main, "success")]
    )

    assert result.outputs["main-state"] == "green"
    assert result.outputs["main-run"] == "208"
    assert result.chrome == NARROW


def test_a_rerun_in_progress_whose_earlier_attempt_failed_is_red_at_its_own_head(
    tmp_path: Path, repos: Repositories
) -> None:
    rerun = repos.git(repos.work, "rev-parse", "main")
    runs = [_going(211, rerun, attempt=2), _done(210, "c" * 40, "success")]
    attempts = {(211, 1): _done(211, rerun, "failure")}
    result = _pull_request(tmp_path, repos, runs, attempts)

    assert result.outputs["main-state"] == "red"
    assert result.outputs["main-run"] == "211"
    assert result.outputs["main-run-sha"] == rerun
    assert result.chrome == WIDE
    assert any(call.endswith("/actions/runs/211/attempts/1") for call in result.calls)


def test_a_rerun_in_progress_whose_earlier_attempt_passed_is_green(
    tmp_path: Path, repos: Repositories
) -> None:
    rerun = repos.git(repos.work, "rev-parse", "main")
    runs = [_going(213, rerun, attempt=3), _done(212, "c" * 40, "failure")]
    attempts = {(213, 2): _done(213, rerun, "success")}
    result = _pull_request(tmp_path, repos, runs, attempts)

    assert result.outputs["main-state"] == "green"
    assert result.outputs["main-run"] == "213"
    assert result.chrome == NARROW


def test_a_rerun_whose_earlier_attempt_cannot_be_read_is_red(
    tmp_path: Path, repos: Repositories
) -> None:
    rerun = repos.git(repos.work, "rev-parse", "main")
    result = _pull_request(tmp_path, repos, [_going(215, rerun, attempt=2)])

    assert result.outputs["main-state"] == "red"
    assert "could not be read" in result.summary


def test_no_completed_attempt_in_the_page_is_red(tmp_path: Path, repos: Repositories) -> None:
    result = _pull_request(tmp_path, repos, [_going(217, "a" * 40), _going(216, "b" * 40)])

    assert result.outputs["main-state"] == "red"
    assert result.outputs["main-run"] == ""
    assert result.chrome == WIDE
    assert "has a completed attempt" in result.summary


# ── Whether the run tested main's red head ─────────────────────────────────────────


def test_a_merge_commit_that_contains_the_red_head_tests_it(
    tmp_path: Path, repos: Repositories
) -> None:
    red = repos.commit("main", {"main.txt": "red\n"})
    result = _pull_request(tmp_path, repos, [_done(301, red, "failure")])

    assert result.outputs["main-run-sha"] == red
    assert result.outputs["tests-red"] == "yes"
    assert f"| main | red, run 301, head {red}; tests-red=yes |" in result.summary


def test_a_merge_commit_that_predates_the_red_head_does_not(
    tmp_path: Path, repos: Repositories
) -> None:
    head = repos.commit("feature", {"feature.txt": "feature\n"}, start="main")
    checkout = repos.check_out_merge(head, "main")
    red = repos.commit("main", {"main.txt": "red\n"})
    # A rerun of a run planned before main turned red: the clone has every branch as it
    # is now, and the commit it tests is the one it tested then.
    repos.git(checkout, "fetch", "--quiet", "origin")
    result = plan(tmp_path, checkout, runs=[_done(302, red, "failure")], env=repos.env)

    assert result.returncode == 0, result.log
    assert result.outputs["tests-red"] == "no"
    assert f"predates {red}" in result.summary
    assert "::warning::" not in result.log


def test_a_red_head_the_clone_lacks_is_named_with_a_warning(
    tmp_path: Path, repos: Repositories
) -> None:
    missing = "d" * 40
    result = _pull_request(tmp_path, repos, [_done(303, missing, "failure")])

    assert result.outputs["tests-red"] == "no"
    assert f"{missing} is missing from the clone" in result.summary
    assert "git merge-base exited 128" in result.summary
    assert f"::warning::tests-red is no because git merge-base exited 128: {missing}" in (
        result.log
    )


# ── The Chrome tier by kind of run ─────────────────────────────────────────────────


def test_a_push_to_main_runs_the_chrome_tier_on_every_interpreter_without_reading_main(
    tmp_path: Path, repos: Repositories
) -> None:
    result = plan(tmp_path, repos.work, event="push", base="", runs=None, env=repos.env)

    assert result.returncode == 0, result.log
    assert result.chrome == WIDE
    assert result.outputs["main-state"] == "none"
    assert result.outputs["integration"] == "none"
    assert result.calls == []


def test_an_unknown_pull_request_interpreter_fails_the_plan(
    tmp_path: Path, repos: Repositories
) -> None:
    result = plan(tmp_path, repos.work, event="push", pr_chrome_python="3.11", env=repos.env)

    assert result.returncode == 1
    assert "::error::PR_CHROME_PYTHON (3.11) must be one of PYTHONS" in result.log


# ── A stacked pull request: stack-integration by tree ──────────────────────────────


def _stack(repos: Repositories) -> tuple[str, str]:
    """A lower branch off main, and an upper one on it; returns the upper head and base."""

    repos.commit("lower", {"lower.txt": "lower\n"}, start="main")
    upper = repos.commit("upper", {"upper.txt": "upper\n"}, start="lower")
    return upper, "lower"


def test_a_stack_whose_tested_commit_contains_main_reads_main_and_needs_nothing_more(
    tmp_path: Path, repos: Repositories
) -> None:
    """A formal stack's merge ref holds main: the owner's decision on A3 of #504."""

    upper, base = _stack(repos)
    checkout = repos.check_out_merge(upper, base)
    main = repos.git(repos.work, "rev-parse", "main")
    runs = [_done(501, main, "success")]
    result = plan(tmp_path, checkout, base="lower", head_sha=upper, runs=runs, env=repos.env)

    assert result.returncode == 0, result.log
    tree = repos.git(checkout, "rev-parse", "HEAD^{tree}")
    assert result.outputs["integration"] == "contained"
    assert result.outputs["main-sha"] == main
    assert result.outputs["main-state"] == "green"
    assert result.chrome == NARROW
    assert f"the commit this run tests (tree {tree}) already contains main ({main})" in (
        result.summary
    )


def test_a_stack_that_contains_main_s_red_head_tests_it(
    tmp_path: Path, repos: Repositories
) -> None:
    upper, base = _stack(repos)
    checkout = repos.check_out_merge(upper, base)
    red = repos.git(repos.work, "rev-parse", "main")
    runs = [_done(502, red, "failure")]
    result = plan(tmp_path, checkout, base="lower", head_sha=upper, runs=runs, env=repos.env)

    assert result.returncode == 0, result.log
    assert result.outputs["main-state"] == "red"
    assert result.outputs["main-run-sha"] == red
    assert result.outputs["tests-red"] == "yes"
    assert result.chrome == WIDE


def test_a_formal_stack_planned_after_main_moved_is_read_as_an_informal_chain(
    tmp_path: Path, repos: Repositories
) -> None:
    """A rerun once main has moved reads no main state (C7 of review C on #504).

    ci_verdict.sh writes a verdict line only for a red main-state, so this run gives none,
    and a red main still refuses the merge.
    """

    upper, base = _stack(repos)
    checkout = repos.check_out_merge(upper, base)  # holds main as it was
    main = repos.commit("main", {"main.txt": "newer\n"})
    runs = [_done(503, main, "failure")]
    result = plan(tmp_path, checkout, base="lower", head_sha=upper, runs=runs, env=repos.env)

    assert result.returncode == 0, result.log
    assert result.outputs["main-sha"] == main
    assert result.outputs["main-state"] == "none"
    assert result.outputs["main-run-sha"] == ""
    assert result.outputs["tests-red"] == "no"
    assert result.outputs["integration"] == "needed"
    assert result.chrome == NARROW
    assert result.calls == []


def test_a_stack_level_with_main_by_content_needs_no_integration(
    tmp_path: Path, repos: Repositories
) -> None:
    """An informal chain whose merge with main changes nothing: main made the same change."""

    upper, base = _stack(repos)
    repos.commit("main", {"upper.txt": "upper\n"})
    checkout = repos.check_out_merge(upper, base)
    result = plan(tmp_path, checkout, base="lower", head_sha=upper, runs=None, env=repos.env)

    assert result.returncode == 0, result.log
    tree = repos.git(checkout, "rev-parse", "HEAD^{tree}")
    assert result.outputs["integration"] == "identical"
    assert result.outputs["main-state"] == "none"
    assert result.chrome == NARROW
    assert result.calls == []
    assert f"leaves tree {tree}, which the other jobs check" in result.summary


def test_a_stack_behind_main_needs_the_integration_jobs(
    tmp_path: Path, repos: Repositories
) -> None:
    upper, base = _stack(repos)
    main = repos.commit("main", {"main.txt": "newer\n"})
    checkout = repos.check_out_merge(upper, base)
    result = plan(tmp_path, checkout, base="lower", head_sha=upper, env=repos.env)

    assert result.returncode == 0, result.log
    assert result.outputs["integration"] == "needed"
    assert result.outputs["main-sha"] == main
    assert "so the stack-integration jobs check it" in result.summary
    # An informal chain's run tests no main, so it does not read main's state.
    assert result.outputs["main-state"] == "none"
    assert result.calls == []
    assert f"not read: the commit this run tests does not contain main's head ({main})" in (
        result.summary
    )


def test_a_stack_that_conflicts_with_main_names_the_file(
    tmp_path: Path, repos: Repositories
) -> None:
    repos.commit("lower", {"lower.txt": "lower\n"}, start="main")
    upper = repos.commit("upper", {"shared.txt": "upper\n"}, start="lower")
    repos.commit("main", {"shared.txt": "main\n"})
    checkout = repos.check_out_merge(upper, "lower")
    result = plan(tmp_path, checkout, base="lower", head_sha=upper, env=repos.env)

    assert result.returncode == 0, result.log
    assert result.outputs["integration"] == "conflict"
    assert "conflicts in: shared.txt" in result.summary
    assert result.calls == []


def test_a_head_that_is_not_a_commit_fails_the_plan(tmp_path: Path, repos: Repositories) -> None:
    upper, base = _stack(repos)
    checkout = repos.check_out_merge(upper, base)
    result = plan(tmp_path, checkout, base="lower", head_sha="--upload-pack=x", env=repos.env)

    assert result.returncode == 1
    assert "::error::HEAD_SHA (--upload-pack=x) is not a commit" in result.log


def test_a_pull_request_to_main_needs_no_integration(tmp_path: Path, repos: Repositories) -> None:
    main = repos.git(repos.work, "rev-parse", "main")
    result = _pull_request(tmp_path, repos, [_done(401, main, "success")])

    assert result.outputs["integration"] == "none"
    assert result.outputs["main-sha"] == ""
    assert "| stack-integration | none: not a stacked pull request |" in result.summary
