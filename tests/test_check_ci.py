"""``devtools/check_ci.py``: each way of dropping a check from the CI workflow is caught.

Each case edits a copy of the real ``ci.yml``, so the rules are tested against the
workflow they hold, and a rule that stopped matching the real file would fail here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from devtools.check_ci import (
    expressions,
    interpreters,
    jobs,
    load,
    make_targets,
    pr_chrome_python,
    verify,
)

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
        ("make test-parallel SHARD=${{ matrix.shard }}", {"test-parallel"}),
        ("make ${{ needs.plan.outputs.target }} SHARD=${{ matrix.shard }}", set()),
        ("make -k test-goldens test-serial", {"test-goldens", "test-serial"}),
        ("make ${{ matrix.part }}", set()),
        ("git config user.name bot\nmake test-goldens", {"test-goldens"}),
        ("echo make test-serial", set()),
    ],
)
def test_make_targets(command: str, targets: set[str]) -> None:
    assert make_targets(command) == targets


# ── Tiers and interpreters ─────────────────────────────────────────────────────────


PLAN_PYTHONS = "python-version: ${{ fromJSON(needs.plan.outputs.pythons) }}"


@pytest.mark.parametrize(
    ("occurrence", "job", "targets"),
    [
        (1, "unit", ["test-parallel"]),
        (2, "goldens", ["test-goldens", "test-serial"]),
        (3, "chrome", ["test-chrome"]),
    ],
)
def test_a_tier_whose_interpreters_are_not_the_plan_s_fails(
    tmp_path: Path, occurrence: int, job: str, targets: list[str]
) -> None:
    """Every interpreter written out would pass on main and cost a pull request its
    short path; one short of them would drop coverage. Only the plan job decides."""

    for written in (EVERY, '["3.12", "3.13", "3.14"]'):
        errors = _errors(
            tmp_path / written,
            PLAN_PYTHONS,
            f"python-version: {written}",
            occurrence=occurrence,
        )

        for target in targets:
            assert f"job {job} runs {target} on [" in errors
            assert "not on the plan job's interpreters" in errors


@pytest.mark.parametrize("target", ["test-serial", "test-goldens", "test-parallel"])
def test_a_tier_no_job_runs_fails(tmp_path: Path, target: str) -> None:
    old = f"make {target} SHARD=${{{{ matrix.shard }}}}"
    errors = _errors(tmp_path, old, "make build", occurrence=1)

    assert f"ci.yml runs no `make {target}`" in errors


def test_a_tier_job_that_installs_another_python_fails(tmp_path: Path) -> None:
    errors = _errors(
        tmp_path,
        "python-version: ${{ matrix.python-version }}",
        'python-version: "3.13"',
        occurrence=2,
    )

    assert "job goldens must need plan and install ${{ matrix.python-version }}" in errors


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

    # The tiers' matrices are the plan job's, so its list is the one that is short.
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


@pytest.mark.parametrize(
    ("job", "after"),
    [
        ("unit", "name: unit ("),
        ("goldens", "name: goldens and serial ("),
        ("chrome", "if: needs.plan.outputs.chrome != 'none'"),
    ],
)
def test_a_tier_job_that_does_not_need_the_plan_fails(tmp_path: Path, job: str, after: str) -> None:
    errors = _errors(tmp_path, f"    needs: plan\n    {after}", f"    needs: lint\n    {after}")

    assert f"job {job} must need plan" in errors


@pytest.mark.parametrize(
    "output",
    ["pythons", "chrome", "admitted-gits", "unit-shards", "chrome-shards"],
)
def test_a_plan_output_that_is_not_the_step_s_own_fails(tmp_path: Path, output: str) -> None:
    errors = _errors(
        tmp_path,
        f"      {output}: ${{{{ steps.decide.outputs.{output} }}}}\n",
        f"      {output}: ${{{{ steps.decide.outputs.path }}}}\n",
    )

    assert f"plan job's output {output} must be ${{{{ steps.decide.outputs.{output} }}}}" in errors


# ── The Chrome tier ────────────────────────────────────────────────────────────────

CHROME_STEP = "run: make test-chrome SHARD=${{ matrix.shard }}"
CHROME_ALONE = "job chrome must run `make test-chrome SHARD=${{ matrix.shard }}` and no other make"


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        # Another target, or one a plan output names, could run less than the whole tier.
        (CHROME_STEP, "run: make test-serial SHARD=${{ matrix.shard }}", CHROME_ALONE),
        (
            CHROME_STEP,
            "run: make ${{ needs.plan.outputs.chrome-target }} SHARD=${{ matrix.shard }}",
            CHROME_ALONE,
        ),
        (CHROME_STEP, "run: make test-chrome", CHROME_ALONE),
        # Any condition but the plan's own could skip the tier on main.
        (
            "    if: needs.plan.outputs.chrome != 'none'\n",
            "    if: github.event_name == 'push'\n",
            "job chrome must not run under if: github.event_name == 'push'",
        ),
        (
            "    if: needs.plan.outputs.chrome != 'none'\n",
            "    if: needs.plan.outputs.chrome == 'whole'\n",
            "job chrome must not run under if: needs.plan.outputs.chrome == 'whole'",
        ),
    ],
    ids=[
        "another target",
        "a target the plan names",
        "no part",
        "another condition",
        "only when whole",
    ],
)
def test_the_chrome_job_runs_the_whole_tier_under_the_plan_s_condition(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    assert message in _errors(tmp_path, old, new)


def test_no_other_job_may_take_its_make_target_from_an_expression(tmp_path: Path) -> None:
    errors = _errors(
        tmp_path,
        "run: make test-parallel SHARD=${{ matrix.shard }}",
        "run: make ${{ needs.plan.outputs.target }} SHARD=${{ matrix.shard }}",
    )

    assert "job unit runs `make ${{ needs.plan.outputs.target }} SHARD=" in errors
    assert "a make with no target named" in errors
    assert "ci.yml runs no `make test-parallel`" in errors


# ── Shards ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        # A list written in is one the plan job's parts can outgrow or fall short of.
        (
            "shard: ${{ fromJSON(needs.plan.outputs.chrome-shards) }}",
            'shard: ["1/4", "2/4", "3/4"]',
            "job chrome's shard matrix must be ${{ fromJSON(needs.plan.outputs.chrome-shards) }}",
        ),
        (
            "shard: ${{ fromJSON(needs.plan.outputs.unit-shards) }}",
            "shard: ${{ fromJSON(needs.plan.outputs.goldens-shards) }}",
            "job unit's shard matrix must be ${{ fromJSON(needs.plan.outputs.unit-shards) }}",
        ),
        (
            "shard: ${{ fromJSON(needs.plan.outputs.admitted-git-shards) }}",
            'shard: ["1/2"]',
            "job admitted-git's shard matrix must be",
        ),
        (
            "git: ${{ fromJSON(needs.plan.outputs.admitted-gits) }}",
            'git: ["2.43.7"]',
            "job admitted-git's git matrix must be",
        ),
        # A step without its part runs the whole tier in every part, or, with the
        # matrix gone too, hides that the parts are no longer dealt.
        (
            "run: make test-serial SHARD=${{ matrix.shard }}",
            "run: make test-serial",
            "job goldens runs `make test-serial` without its part",
        ),
        (
            "run: make test-admitted-git SHARD=${{ matrix.shard }}",
            "run: make test-admitted-git",
            "job admitted-git runs `make test-admitted-git` without its part",
        ),
        ("          - test-chrome SHARD=4/4\n", "", "deals test-chrome into shards"),
        ("test-parallel SHARD=2/2", "test-parallel SHARD=2/3", "deals test-parallel into shards"),
    ],
)
def test_a_missing_shard_fails(tmp_path: Path, old: str, new: str, message: str) -> None:
    assert message in _errors(tmp_path, old, new)


def test_a_static_shard_matrix_elsewhere_still_has_to_be_1_through_n(tmp_path: Path) -> None:
    """The nightly soak deals its parts in its own file, where the count is written."""

    nightly = (ROOT / ".github" / "workflows" / "nightly.yml").read_text(encoding="utf-8")
    assert "shard: [1, 2, 3, 4]" in nightly
    root = _repository(tmp_path, nightly=nightly.replace("shard: [1, 2, 3, 4]", "shard: [1, 2, 3]"))

    assert "SHARD=…/4, so its shard matrix must be" in "\n".join(verify(root))


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


# ── A1 of review A on #504: each edit that drops coverage ──────────────────────────


def _without_job(text: str, name: str, following: str) -> str:
    start = text.index(f"\n  {name}:\n")
    return text[:start] + text[text.index(f"\n  {following}:\n") :]


DROPS = {
    "a fixed SHARD": (
        CI_TEXT.replace(
            "make test-parallel SHARD=${{ matrix.shard }}", "make test-parallel SHARD=1/2"
        ),
        "ci.yml job unit runs `make test-parallel SHARD=1/2`; a make step's words are",
    ),
    "an excluded interpreter": (
        CI_TEXT.replace(
            "        shard: ${{ fromJSON(needs.plan.outputs.unit-shards) }}\n",
            "        shard: ${{ fromJSON(needs.plan.outputs.unit-shards) }}\n"
            '        exclude:\n          - python-version: "3.14t"\n',
        ),
        "ci.yml job unit's matrix must have no include or exclude",
    ),
    "an excluded shard": (
        CI_TEXT.replace(
            "        shard: ${{ fromJSON(needs.plan.outputs.chrome-shards) }}\n",
            "        shard: ${{ fromJSON(needs.plan.outputs.chrome-shards) }}\n"
            '        exclude:\n          - shard: "2/4"\n',
        ),
        "ci.yml job chrome's matrix must have no include or exclude",
    ),
    "a step skipped": (
        CI_TEXT.replace(
            "      - name: Run the parallel tier\n",
            "      - name: Run the parallel tier\n        if: false\n",
        ),
        "ci.yml job unit has a step under if: False",
    ),
    "a step allowed to fail": (
        CI_TEXT.replace(
            "      - name: Run the Chrome tier\n",
            "      - name: Run the Chrome tier\n        continue-on-error: true\n",
        ),
        "ci.yml job chrome has a step with continue-on-error",
    ),
    "a job allowed to fail": (
        CI_TEXT.replace(
            "    name: unit (${{ matrix.python-version }}, ${{ matrix.shard }})\n",
            "    name: unit (${{ matrix.python-version }}, ${{ matrix.shard }})\n"
            "    continue-on-error: true\n",
        ),
        "ci.yml job unit must not set continue-on-error",
    ),
    "the lint job deleted": (
        _without_job(CI_TEXT, "lint", "distribution").replace(
            "needs: [plan, lint, ", "needs: [plan, "
        ),
        "ci.yml has no lint job",
    ),
    "the distribution job deleted": (
        _without_job(CI_TEXT, "distribution", "unit").replace("lint, distribution, ", "lint, "),
        "ci.yml has no distribution job",
    ),
    "the stack-integration job deleted": (
        _without_job(CI_TEXT, "stack-integration", "ci-ok").replace(
            "admitted-git, stack-integration]", "admitted-git]"
        ),
        "ci.yml has no stack-integration job",
    ),
    "the audits dropped": (
        CI_TEXT.replace("run: make lint-check audit", "run: make lint-check"),
        "ci.yml job lint runs no `make audit`",
    ),
    "a stack that runs only lint": (
        CI_TEXT.replace("run: make ${{ matrix.part }}", "run: make lint-check"),
        "ci.yml stack-integration must run `make ${{ matrix.part }}` and no other make",
    ),
    "a stack checked on the merge ref": (
        CI_TEXT.replace("          ref: ${{ github.event.pull_request.head.sha }}\n", ""),
        "ci.yml stack-integration must check out",
    ),
    "a stack never run": (
        CI_TEXT.replace("if: needs.plan.outputs.integration == 'needed'", "if: false"),
        "ci.yml job stack-integration must not run under if: False",
    ),
    "the push trigger dropped": (
        CI_TEXT.replace('  push:\n    branches: ["main"]\n', ""),
        "ci.yml must run on a push to main and on every pull request",
    ),
    "a paths filter on pull requests": (
        CI_TEXT.replace(
            "  pull_request:\n\npermissions",
            "  pull_request:\n    paths: ['src/**']\n\npermissions",
        ),
        "ci.yml must run on a push to main and on every pull request",
    ),
    "a tier whose failure is swallowed": (
        CI_TEXT.replace(
            "run: make test-parallel SHARD=${{ matrix.shard }}",
            "run: make test-parallel SHARD=${{ matrix.shard }} || true",
        ),
        "ci.yml job unit must run `make test-parallel SHARD=${{ matrix.shard }} || true` alone",
    ),
    # C1 of review C on #504: a condition on the wrong step, a make option, and ci-ok's
    # own step.
    "the acceptance tests skipped on a cached Git build": (
        CI_TEXT.replace(
            "      - name: Run acquisition and full-clone acceptance on the admitted Git\n",
            "      - name: Run acquisition and full-clone acceptance on the admitted Git\n"
            "        if: steps.restore-git.outputs.cache-hit != 'true'\n",
        ),
        "ci.yml job admitted-git has a step under if: steps.restore-git.outputs.cache-hit",
    ),
    "the verdict's step skipped": (
        CI_TEXT.replace(
            "      - name: Decide the run's verdict\n",
            "      - name: Decide the run's verdict\n        if: false\n",
        ),
        "ci.yml job ci-ok has a step under if: False",
    ),
    "a tier whose failure make ignores": (
        CI_TEXT.replace("run: make test-goldens", "run: make -i test-goldens"),
        "ci.yml job goldens runs `make -i test-goldens SHARD=${{ matrix.shard }}`; a make step's words are make,",
    ),
    "a tier make only prints": (
        CI_TEXT.replace(
            "run: make test-chrome SHARD=${{ matrix.shard }}",
            "run: make -n test-chrome SHARD=${{ matrix.shard }}",
        ),
        "ci.yml job chrome runs `make -n test-chrome SHARD=${{ matrix.shard }}`; a make step's "
        "words are make,",
    ),
    "a tier whose pytest a make variable replaces": (
        CI_TEXT.replace("run: make test-serial", "run: make test-serial PYTEST=true"),
        "ci.yml job goldens runs `make test-serial PYTEST=true SHARD=${{ matrix.shard }}`; a make step's words are",
    ),
    "a stack part make only prints": (
        CI_TEXT.replace(
            "          - test-chrome SHARD=2/4\n", "          - -n test-chrome SHARD=2/4\n"
        ),
        "ci.yml stack-integration part `-n test-chrome SHARD=2/4`: a part's words are -k,",
    ),
    "a stack part whose failure is swallowed": (
        CI_TEXT.replace("          - lint-check\n", "          - lint-check || true\n"),
        "ci.yml stack-integration part `lint-check || true`: a part's words are -k,",
    ),
    "the verdict replaced": (
        CI_TEXT.replace("run: bash devtools/ci_verdict.sh", "run: echo ok"),
        "ci.yml ci-ok must run `bash devtools/ci_verdict.sh` and no other command",
    ),
    "the verdict's failure swallowed": (
        CI_TEXT.replace(
            "run: bash devtools/ci_verdict.sh", "run: bash devtools/ci_verdict.sh || true"
        ),
        "ci.yml ci-ok must run `bash devtools/ci_verdict.sh` and no other command",
    ),
    "the verdict given one job's result": (
        CI_TEXT.replace(
            "RESULTS: ${{ toJSON(needs) }}", """RESULTS: '{"plan": {"result": "success"}}'"""
        ),
        "ci.yml ci-ok must run `bash devtools/ci_verdict.sh` and no other command, with "
        "RESULTS: ${{ toJSON(needs) }}",
    ),
}


@pytest.mark.parametrize("drop", sorted(DROPS))
def test_an_edit_that_drops_coverage_fails(tmp_path: Path, drop: str) -> None:
    text, message = DROPS[drop]
    assert text != CI_TEXT, drop

    assert message in _errors_of(tmp_path, text)


def _errors_of(tmp_path: Path, text: str) -> str:
    return "\n".join(verify(_repository(tmp_path, text)))


def test_the_cache_miss_condition_stays_in_admitted_git(tmp_path: Path) -> None:
    """In another job it reads a step that is not there and is true, so nothing is dropped
    today; it is refused so that a job that gains a restore-git step cannot skip on a hit.
    """

    errors = _errors(
        tmp_path,
        "      - name: Run the goldens\n",
        "      - name: Run the goldens\n        if: steps.restore-git.outputs.cache-hit != 'true'\n",
    )

    assert "ci.yml job goldens has a step under if: steps.restore-git.outputs.cache-hit" in errors


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


LINUX_UV_SHA256 = "6426a73c3837e6e2483ee344cbc00f36394d179afcba6183cb77437e67db4af0"
INSTALL_UV_STEP = f"      - name: Install uv\n        run: bash devtools/install_uv.sh 0.11.26 {LINUX_UV_SHA256}\n"


@pytest.mark.parametrize(
    ("old", "new", "version"),
    [
        pytest.param(INSTALL_UV_STEP + "\n", "", "0.11.26", id="dropped"),
        pytest.param(
            INSTALL_UV_STEP + "\n",
            INSTALL_UV_STEP + "\n      - name: Between\n        run: true\n\n",
            "0.11.26",
            id="not-just-before",
        ),
        # setup-uv moved on to a release the step before it does not install.
        pytest.param(
            '          version: "0.11.26"\n',
            '          version: "0.11.27"\n',
            "0.11.27",
            id="another-version",
        ),
    ],
)
def test_every_setup_uv_follows_the_install_of_its_own_uv(
    tmp_path: Path, old: str, new: str, version: str
) -> None:
    """Without it setup-uv fetches its manifest once, with a fixed 5 s limit, and can fail."""

    wanted = f"bash devtools/install_uv.sh {version} {LINUX_UV_SHA256}"

    assert _errors(tmp_path, old, new) == (
        f"ci.yml job lint must run `{wanted}` just before setup-uv"
    )


INSTALL_NODE_STEP = (
    "      - name: Install Node\n        run: bash devtools/install_node.sh 24.18.0\n"
)


@pytest.mark.parametrize(
    ("old", "new", "version"),
    [
        pytest.param(INSTALL_NODE_STEP + "\n", "", "24.18.0", id="dropped"),
        pytest.param(
            INSTALL_NODE_STEP + "\n",
            INSTALL_NODE_STEP + "\n      - name: Between\n        run: true\n\n",
            "24.18.0",
            id="not-just-before",
        ),
        # setup-node moved on to a release the step before it does not install.
        pytest.param(
            '          node-version: "24.18.0"\n',
            '          node-version: "24.19.0"\n',
            "24.19.0",
            id="another-version",
        ),
    ],
)
def test_every_setup_node_follows_the_install_of_its_own_node(
    tmp_path: Path, old: str, new: str, version: str
) -> None:
    """Without it setup-node downloads and copies Node itself, and either can stall."""

    wanted = f"bash devtools/install_node.sh {version}"

    assert _errors(tmp_path, old, new) == (
        f"ci.yml job lint must run `{wanted}` just before setup-node"
    )


@pytest.mark.parametrize(
    ("old", "new", "wanted", "action"),
    [
        pytest.param(
            INSTALL_UV_STEP + "\n      - name: Set up uv\n        uses: astral-sh/setup-uv@",
            "      - name: Set up uv\n        uses: Astral-SH/Setup-UV@",
            f"bash devtools/install_uv.sh 0.11.26 {LINUX_UV_SHA256}",
            "setup-uv",
            id="setup-uv",
        ),
        pytest.param(
            INSTALL_NODE_STEP + "\n      - name: Set up Node\n        uses: actions/setup-node@",
            "      - name: Set up Node\n        uses: Actions/Setup-Node@",
            "bash devtools/install_node.sh 24.18.0",
            "setup-node",
            id="setup-node",
        ),
    ],
)
def test_a_setup_action_named_in_another_case_still_follows_its_install(
    tmp_path: Path, old: str, new: str, wanted: str, action: str
) -> None:
    """GitHub runs ``Actions/Setup-Node@`` as ``actions/setup-node@``, so the rule does too."""

    assert _errors(tmp_path, old, new) == (
        f"ci.yml job lint must run `{wanted}` just before {action}"
    )


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


NIGHTLY_TEXT = (ROOT / ".github" / "workflows" / "nightly.yml").read_text(encoding="utf-8")


def test_the_nightly_report_alone_may_read_runs(tmp_path: Path) -> None:
    widened = NIGHTLY_TEXT.replace(
        "  serial:\n", "  serial:\n    permissions:\n      actions: read\n"
    )
    wrote = NIGHTLY_TEXT.replace("      actions: read\n", "      actions: write\n")

    assert verify(_repository(tmp_path / "real", nightly=NIGHTLY_TEXT)) == []
    assert verify(_repository(tmp_path / "widened", nightly=widened)) == [
        "nightly.yml job serial's permissions {'actions': 'read'} must be the workflow's"
    ]
    assert verify(_repository(tmp_path / "wrote", nightly=wrote)) == [
        "nightly.yml job time-limits must not have write permission for actions",
        "nightly.yml job time-limits's permissions {'contents': 'read', 'actions': 'write'} "
        "must be {'contents': 'read', 'actions': 'read'}",
    ]


# B2 of review B on #504: every spelling of the event, and a step's with: inputs.
@pytest.mark.parametrize(
    "expression",
    [
        "format('{0}', github.event.pull_request.title)",
        "github['event'].pull_request.title",
        "github [ 'event' ]",
        "toJSON(github)",
        "toJSON(github.event)",
        "github.event",
        # C2 of review C on #504: the runner reads a context in any case, and ends an
        # expression at the first }} outside a quoted string.
        "GITHUB.EVENT.pull_request.title",
        "github.EVENT.pull_request.title",
        "GitHub.Head_Ref",
        "format('{{}} {0}', github.event.pull_request.title)",
        "'}}' && github.event.pull_request.title",
        "'it''s }}' && github.event.pull_request.title",
    ],
)
def test_every_spelling_of_the_event_is_untrusted(tmp_path: Path, expression: str) -> None:
    workflow = _workflow("pull_request", run=f'echo "${{{{ {expression} }}}}"')

    assert verify(_repository(tmp_path, other=workflow)) == [
        "other.yml job job interpolates the event into a run: line; pass it through env:"
    ]


@pytest.mark.parametrize(
    ("text", "bodies"),
    [
        ("${{ a }} and ${{ b }}", [" a ", " b "]),
        ("${{ format('{{}} {0}', a) }}", [" format('{{}} {0}', a) "]),
        ("${{ 'x''}}' }} ${{ b }}", [" 'x''}}' ", " b "]),
        ("${{}}", [""]),
        ("${{ a", [" a"]),
    ],
)
def test_an_expression_ends_where_the_runner_ends_it(text: str, bodies: list[str]) -> None:
    assert expressions(text) == bodies


# C2 of review C on #504: env in a run: line is pasted into the script, as the event is.
@pytest.mark.parametrize(
    "expression", ["env.TITLE", "ENV.TITLE", "env['TITLE']", "toJSON(env)", "format('{0}', env.X)"]
)
def test_no_run_line_interpolates_env(tmp_path: Path, expression: str) -> None:
    workflow = _workflow("pull_request", run=f'echo "${{{{ {expression} }}}}"')

    assert verify(_repository(tmp_path, other=workflow)) == [
        'other.yml job job interpolates env into a run: line; read it as "$NAME"'
    ]


def test_a_property_named_env_and_env_read_by_the_shell_are_fine(tmp_path: Path) -> None:
    workflow = _workflow(
        "pull_request",
        run='echo "$TITLE ${{ github.env }} ${{ steps.x.outputs.env }} ${{ matrix.environment }}"',
    )

    assert verify(_repository(tmp_path, other=workflow)) == []


def test_the_event_name_and_the_repository_are_trusted(tmp_path: Path) -> None:
    workflow = _workflow(
        "pull_request", run='echo "${{ github.event_name }} ${{ github.repository }}"'
    )

    assert verify(_repository(tmp_path, other=workflow)) == []


def test_a_step_input_that_reads_the_event_is_untrusted(tmp_path: Path) -> None:
    workflow = _workflow("pull_request") + (
        "      - uses: actions/github-script@" + "1" * 40 + "\n"
        "        with:\n          script: console.log('${{ github.event.pull_request.title }}')\n"
    )

    assert verify(_repository(tmp_path, other=workflow)) == [
        "other.yml job job interpolates the event into a step's with:; pass it through env:"
    ]


@pytest.mark.parametrize(
    "expression",
    [
        "github.event.pull_request.head.sha",
        "GitHub.Event.Pull_Request.Head.Sha",
        "github.event.release.tag_name",
    ],
)
def test_a_commit_or_a_release_tag_is_a_trusted_step_input(tmp_path: Path, expression: str) -> None:
    workflow = _workflow("pull_request", checkout=f"ref: ${{{{ {expression} }}}}").replace(
        "        with:\n", "        with:\n          persist-credentials: false\n"
    )

    assert verify(_repository(tmp_path, other=workflow)) == []


def test_no_workflow_may_run_on_workflow_run(tmp_path: Path) -> None:
    workflow = _workflow("{workflow_run: {workflows: [CI]}}")

    assert verify(_repository(tmp_path, other=workflow)) == [
        "other.yml must not run on workflow_run"
    ]


@pytest.mark.parametrize(
    ("permissions", "message"),
    [
        ("permissions:\n  contents: write\n", "must not have write permission for contents"),
        ("permissions: write-all\n", "must not have write permission for all"),
        ("", "must declare its permissions, or the workflow its own"),
    ],
)
def test_no_unregistered_workflow_may_write_or_leave_its_permissions_undeclared(
    tmp_path: Path, permissions: str, message: str
) -> None:
    workflow = _workflow("push").replace("permissions:\n  contents: read\n", permissions)

    assert verify(_repository(tmp_path, other=workflow)) == [f"other.yml job job {message}"]


def test_a_job_may_write_only_where_the_grant_is_registered(tmp_path: Path) -> None:
    workflow = _workflow("push").replace(
        "    runs-on: ubuntu-latest\n",
        "    runs-on: ubuntu-latest\n    permissions:\n      pull-requests: write\n",
    )

    assert verify(_repository(tmp_path, other=workflow)) == [
        "other.yml job job must not have write permission for pull-requests"
    ]


# A5 of review A on #504: the nightly keeps the values it shares with ci.yml. Each case
# edits the value the files hold now, so a re-measured limit changes ci.yml and
# nightly.yml and not this test (C6 of review C on #504).
CI = load(ROOT / ".github" / "workflows" / "ci.yml")
NIGHTLY_JOBS = jobs(load(ROOT / ".github" / "workflows" / "nightly.yml"))
PR_CHROME_PYTHON = pr_chrome_python(CI)
CHROME_LIMIT = jobs(CI)["chrome"]["timeout-minutes"]
SERIAL_LIMIT = NIGHTLY_JOBS["serial"]["timeout-minutes"]


@pytest.mark.parametrize(
    ("job", "old", "new", "message"),
    [
        (
            "serial",
            f'python-version: "{PR_CHROME_PYTHON}"',
            'python-version: "3.11"',
            f"nightly.yml job serial must install PR_CHROME_PYTHON, '{PR_CHROME_PYTHON}', "
            "not '3.11'",
        ),
        (
            "chrome",
            f"    timeout-minutes: {CHROME_LIMIT}\n",
            "    timeout-minutes: 99\n",
            f"nightly.yml job chrome's timeout-minutes 99 must be ci.yml's {CHROME_LIMIT}",
        ),
        (
            "serial",
            "      fail-fast: false\n",
            "      fail-fast: true\n",
            "nightly.yml job serial must set fail-fast: false",
        ),
        (
            "serial",
            f"    timeout-minutes: {SERIAL_LIMIT}\n",
            "",
            "nightly.yml job serial must set timeout-minutes to a number of minutes",
        ),
        (
            "serial",
            "      - name: Run the serial tier\n",
            "      - name: Run the serial tier\n        continue-on-error: true\n",
            "nightly.yml job serial has a step with continue-on-error",
        ),
    ],
)
def test_the_nightly_keeps_ci_yml_s_interpreter_and_limit(
    tmp_path: Path, job: str, old: str, new: str, message: str
) -> None:
    start = NIGHTLY_TEXT.index(f"\n  {job}:\n")
    at = NIGHTLY_TEXT.index(old, start)
    nightly = NIGHTLY_TEXT[:at] + new + NIGHTLY_TEXT[at + len(old) :]

    assert message in verify(_repository(tmp_path, nightly=nightly))
