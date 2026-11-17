"""``devtools/check_ci.py``: each way of dropping a check from the CI workflow is caught.

Each case edits a copy of the real ``ci.yml``, so the rules are tested against the
workflow they hold, and a rule that stopped matching the real file would fail here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from devtools.check_ci import interpreters, make_targets, verify

ROOT = Path(__file__).resolve().parents[1]
CI_TEXT = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
EVERY = '["3.12", "3.13", "3.14", "3.14t"]'


def _repository(tmp_path: Path, ci: str = CI_TEXT, **workflows: str) -> Path:
    root = tmp_path / "repository"
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text(ci, encoding="utf-8")
    for name, text in workflows.items():
        (root / ".github" / "workflows" / f"{name}.yml").write_text(text, encoding="utf-8")
    shutil.copy(ROOT / "pyproject.toml", root / "pyproject.toml")
    return root


def _edited(old: str, new: str, *, occurrence: int = 1) -> str:
    """The real ci.yml with the *occurrence*-th copy of *old* replaced by *new*."""

    parts = CI_TEXT.split(old)
    assert len(parts) > occurrence, f"ci.yml has fewer than {occurrence} of {old!r}"
    return old.join(parts[:occurrence]) + new + old.join(parts[occurrence:])


def _errors(tmp_path: Path, old: str, new: str, *, occurrence: int = 1) -> str:
    return "\n".join(verify(_repository(tmp_path, _edited(old, new, occurrence=occurrence))))


def test_the_real_workflows_pass() -> None:
    assert verify() == []


def test_a_copy_of_the_real_workflow_passes(tmp_path: Path) -> None:
    assert verify(_repository(tmp_path)) == []


def test_the_interpreters_are_the_classifiers_and_the_newest_free_threaded_build() -> None:
    assert interpreters(ROOT) == ["3.12", "3.13", "3.14", "3.14t"]


@pytest.mark.parametrize(
    ("command", "targets"),
    [
        ("make lint-check audit", {"lint-check", "audit"}),
        ("make test-chrome SHARD=${{ matrix.shard }}/4", {"test-chrome"}),
        ("make -k test-goldens test-serial", {"test-goldens", "test-serial"}),
        ("make ${{ matrix.part }}", set()),
        ("git config user.name bot\nmake test-goldens", {"test-goldens"}),
        ("echo make test-serial", set()),
    ],
)
def test_make_targets(command: str, targets: set[str]) -> None:
    assert make_targets(command) == targets


# ── Tiers and interpreters ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("occurrence", "job", "targets"),
    [(1, "unit", ["test-parallel"]), (2, "goldens", ["test-goldens", "test-serial"])],
)
def test_a_matrix_short_of_an_interpreter_fails(
    tmp_path: Path, occurrence: int, job: str, targets: list[str]
) -> None:
    errors = _errors(
        tmp_path,
        f"python-version: {EVERY}",
        'python-version: ["3.12", "3.13", "3.14"]',
        occurrence=occurrence,
    )

    for target in targets:
        assert f"job {job} runs {target} on ['3.12', '3.13', '3.14'], not on every" in errors


@pytest.mark.parametrize("target", ["test-serial", "test-goldens", "test-parallel"])
def test_a_tier_no_job_runs_fails(tmp_path: Path, target: str) -> None:
    old = (
        f"make {target} SHARD=${{{{ matrix.shard }}}}/2"
        if target == "test-parallel"
        else f"make {target}\n"
    )
    errors = _errors(tmp_path, old, "make build\n" if old.endswith("\n") else "make build")

    assert f"ci.yml runs no `make {target}`" in errors


def test_a_tier_job_that_installs_another_python_fails(tmp_path: Path) -> None:
    errors = _errors(
        tmp_path,
        "python-version: ${{ matrix.python-version }}",
        'python-version: "3.13"',
        occurrence=2,
    )

    assert "job goldens must install ${{ matrix.python-version }}" in errors


def test_a_new_classifier_is_missing_from_every_list(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(
        text.replace(
            '"Programming Language :: Python :: 3.14",',
            '"Programming Language :: Python :: 3.14",\n    "Programming Language :: Python :: 3.15",',
        ),
        encoding="utf-8",
    )
    errors = "\n".join(verify(root))

    assert "job unit runs test-parallel on" in errors
    assert "job goldens runs test-serial on" in errors
    assert "plan job's PYTHONS" in errors
    assert "'3.15t'" in errors


def test_plan_pythons_short_of_an_interpreter_fails(tmp_path: Path) -> None:
    errors = _errors(
        tmp_path,
        """PYTHONS: '["3.12", "3.13", "3.14", "3.14t"]'""",
        """PYTHONS: '["3.12", "3.13", "3.14"]'""",
    )

    assert "plan job's PYTHONS ['3.12', '3.13', '3.14'] must be" in errors


def test_a_pull_request_chrome_python_outside_pythons_fails(tmp_path: Path) -> None:
    errors = _errors(tmp_path, 'PR_CHROME_PYTHON: "3.13"', 'PR_CHROME_PYTHON: "3.11"')

    assert "PR_CHROME_PYTHON '3.11' must be one of PYTHONS" in errors


def test_a_chrome_matrix_that_is_not_the_plan_output_fails(tmp_path: Path) -> None:
    errors = _errors(
        tmp_path,
        "python-version: ${{ fromJSON(needs.plan.outputs.chrome-pythons) }}",
        'python-version: ["3.13"]',
    )

    assert "job chrome's python-version matrix must be" in errors


def test_a_chrome_job_that_does_not_need_the_plan_fails(tmp_path: Path) -> None:
    errors = _errors(
        tmp_path, "    needs: plan\n    name: chrome", "    needs: lint\n    name: chrome"
    )

    assert "job chrome must need plan" in errors


# ── Shards ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("shard: [1, 2, 3, 4]", "shard: [1, 2, 3]", "SHARD=…/4, so its shard matrix must be"),
        ("shard: [1, 2]", "shard: [1]", "SHARD=…/2, so its shard matrix must be"),
        ("          - test-chrome SHARD=4/4\n", "", "deals test-chrome into shards"),
        ("test-parallel SHARD=2/2", "test-parallel SHARD=2/3", "deals test-parallel into shards"),
    ],
)
def test_a_missing_shard_fails(tmp_path: Path, old: str, new: str, message: str) -> None:
    assert message in _errors(tmp_path, old, new)


def test_the_stack_parts_must_run_lint_and_every_tier(tmp_path: Path) -> None:
    errors = _errors(tmp_path / "goldens", "          - -k test-goldens test-serial\n", "")
    lint = _errors(tmp_path / "lint", "          - lint-check\n", "")

    assert "stack-integration parts run no test-goldens, test-serial" in errors
    assert "stack-integration parts run no lint-check" in lint


# ── The plan job, permissions, and the verdict ─────────────────────────────────────


def test_the_plan_job_needs_its_whole_history(tmp_path: Path) -> None:
    errors = _errors(tmp_path, "fetch-depth: 0", "fetch-depth: 1")

    assert "plan job must check out with fetch-depth: 0" in errors


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("      actions: read\n", "      actions: write\n", "ci.yml job plan's permissions"),
        (
            "  lint:\n    runs-on: ubuntu-latest\n",
            "  lint:\n    permissions:\n      actions: read\n    runs-on: ubuntu-latest\n",
            "ci.yml job lint's permissions",
        ),
        (
            "permissions:\n  contents: read\n",
            "permissions:\n  contents: write\n",
            "ci.yml permissions",
        ),
    ],
)
def test_a_permission_beyond_the_plan_jobs_read_fails(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    assert message in _errors(tmp_path, old, new)


def test_the_verdict_must_need_every_job(tmp_path: Path) -> None:
    errors = _errors(tmp_path, "chrome, admitted-git, stack-integration]", "chrome]")

    assert (
        "ci-ok must need every other job; it leaves out ['admitted-git', 'stack-integration']"
        in (errors)
    )


def test_the_verdict_must_run_whatever_the_jobs_did(tmp_path: Path) -> None:
    assert "ci-ok must run if: always()" in _errors(tmp_path, "if: always()", "if: success()")


def test_fail_fast_must_be_off(tmp_path: Path) -> None:
    errors = _errors(tmp_path, "fail-fast: false", "fail-fast: true", occurrence=2)

    assert "job goldens must set fail-fast: false" in errors


def test_every_job_needs_a_time_limit(tmp_path: Path) -> None:
    errors = _errors(tmp_path, "    timeout-minutes: 2\n    steps:", "    steps:")

    assert "must set timeout-minutes" in errors


def test_main_runs_are_never_cancelled(tmp_path: Path) -> None:
    errors = _errors(
        tmp_path,
        "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
        "cancel-in-progress: true",
    )

    assert "concurrency must cancel in progress only" in errors


# ── Every workflow ─────────────────────────────────────────────────────────────────

CHECKOUT = "actions/checkout@" + "0" * 40


def _workflow(on: str, run: str = "make test", checkout: str = "persist-credentials: false") -> str:
    return (
        f"on: {on}\npermissions:\n  contents: read\njobs:\n  job:\n    runs-on: ubuntu-latest\n"
        f"    steps:\n      - uses: {CHECKOUT}\n        with:\n          {checkout}\n"
        f"      - run: {run}\n"
    )


def test_no_workflow_may_run_on_pull_request_target(tmp_path: Path) -> None:
    errors = verify(_repository(tmp_path, other=_workflow("[push, pull_request_target]")))

    assert errors == ["other.yml must not run on pull_request_target"]


def test_every_checkout_drops_its_credentials(tmp_path: Path) -> None:
    errors = verify(_repository(tmp_path, other=_workflow("push", checkout="fetch-depth: 1")))

    assert errors == ["other.yml job job must check out with persist-credentials: false"]


@pytest.mark.parametrize(
    "expression", ["github.event.pull_request.title", "github.head_ref", "github.event.issue.body"]
)
def test_no_run_line_interpolates_untrusted_input(tmp_path: Path, expression: str) -> None:
    workflow = _workflow("pull_request", run=f'echo "${{{{ {expression} }}}}"')
    errors = verify(_repository(tmp_path, other=workflow))

    assert errors == [
        "other.yml job job interpolates the event into a run: line; pass it through env:"
    ]


def test_a_trusted_expression_in_a_run_line_is_fine(tmp_path: Path) -> None:
    workflow = _workflow("push", run='echo "${{ github.sha }} ${{ matrix.shard }}"')

    assert verify(_repository(tmp_path, other=workflow)) == []
