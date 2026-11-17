"""Fail the build when the CI workflow could drop a check and still go green.

A workflow is easy to change in a way every remaining job passes: drop an interpreter
from a matrix, a shard from a list, or the serial tier from a job. The fast CI plan
(``docs/project/specs/active/plan-2026-11-16-fast-ci.md``, "How Coverage Is Kept") says
where each check runs and why; this holds ``.github/workflows/ci.yml`` to it:

- the workflow runs each of the four tier targets, and ``test-parallel``,
  ``test-serial``, and ``test-goldens`` on every interpreter;
- every interpreter list (the ``unit`` and ``goldens`` matrices and the ``plan`` job's
  ``PYTHONS``) is the Python releases ``pyproject.toml``'s classifiers name and the
  free-threaded build of the newest, and ``PR_CHROME_PYTHON`` is one of them;
- the ``chrome`` matrix is the ``plan`` job's ``chrome-pythons`` output;
- the ``plan`` job checks out with ``fetch-depth: 0``, which ``tests-red`` and
  ``git merge-tree`` need;
- the stack-integration parts run lint and the four tiers;
- ``ci-ok`` needs every other job and runs whatever they did, every matrix job has
  ``fail-fast: false``, every job has a ``timeout-minutes``, and only a pull request's
  run is cancelled by a newer one.

And of every workflow file:

- the shard numbers of each sharded job are ``1`` through ``N``;
- nothing runs on ``pull_request_target``, which would run with the base repository's
  token; every checkout sets ``persist-credentials: false``; and no ``run:`` line
  interpolates the event or the head branch, which a pull request's author controls;
- ``ci.yml`` and ``nightly.yml`` give ``contents: read``, and ``actions: read`` only to
  the jobs ``JOB_PERMISSIONS`` names.

``devtools/check_supply_chain.py`` holds the ``admitted-git`` matrix to both Git floors,
and ``tests/test_ci_plan.py`` holds that a push to main, and a pull request while main is
red, get all of ``PYTHONS``.

    python -m devtools.check_ci
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Final, cast

import yaml

ROOT: Final = Path(__file__).resolve().parents[1]
WORKFLOWS: Final = Path(".github") / "workflows"
CI: Final = WORKFLOWS / "ci.yml"

TIER_TARGETS: Final = ("test-parallel", "test-serial", "test-chrome", "test-goldens")
# The tiers a pull request checks on every interpreter. Only the Chrome tier may run on
# one interpreter before the merge (the plan's Q3), and only through the plan job.
EVERY_INTERPRETER: Final = ("test-parallel", "test-serial", "test-goldens")
CHROME_TARGET: Final = "test-chrome"
CHROME_MATRIX: Final = "${{ fromJSON(needs.plan.outputs.chrome-pythons) }}"
MATRIX_PYTHON: Final = "${{ matrix.python-version }}"
PLAN_JOB: Final = "plan"
VERDICT_JOB: Final = "ci-ok"
STACK_JOB: Final = "stack-integration"
STACK_TARGETS: Final = ("lint-check", *TIER_TARGETS)
WORKFLOW_PERMISSIONS: Final = {"contents": "read"}
READ_RUNS: Final = {"contents": "read", "actions": "read"}
# The workflows whose permissions this holds, and the jobs among them that read other
# runs: the plan job reads main's state, and the nightly report reads job times
# (SUPPLY-CHAIN-SECURITY.md, "CI Workflows"). publish.yml's are check_supply_chain.py's.
JOB_PERMISSIONS: Final = {
    "ci.yml": {PLAN_JOB: READ_RUNS},
    "nightly.yml": {"time-limits": READ_RUNS},
}
CANCEL_IN_PROGRESS: Final = "${{ github.event_name == 'pull_request' }}"
VERDICT_IF: Final = frozenset({"always()", "${{ always() }}"})

CLASSIFIER: Final = re.compile(r"Programming Language :: Python :: (3\.\d+)")
EXPRESSION: Final = re.compile(r"\$\{\{.*?\}\}")
MATRIX_SHARD: Final = re.compile(r"SHARD=\$\{\{\s*matrix\.shard\s*\}\}/(\d+)")
LITERAL_SHARD: Final = re.compile(r"(?P<part>.*?)\s*SHARD=(?P<index>\d+)/(?P<count>\d+)")
# An expression a pull request's author can set: its title, body, branch, and the rest
# of the event. Pass one through `env:` and quote it in the shell instead.
UNTRUSTED: Final = re.compile(r"\$\{\{[^}]*\b(?:github\.event\.|github\.head_ref)")

Json = dict[str, object]


def _mapping(value: object) -> Json:
    return cast(Json, value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def load(path: Path) -> Json:
    try:
        document: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RuntimeError(f"cannot read {path}: {error}") from error
    if not isinstance(document, dict):
        raise RuntimeError(f"{path} is not a workflow")
    return cast(Json, document)


def interpreters(root: Path) -> list[str]:
    """The classifiers' Python releases, oldest first, then the newest's free-threaded build."""

    project = _mapping(tomllib.loads((root / "pyproject.toml").read_text("utf-8")).get("project"))
    versions = sorted(
        {
            match[1]
            for line in _list(project.get("classifiers"))
            if (match := CLASSIFIER.fullmatch(str(line)))
        },
        key=lambda version: tuple(int(part) for part in version.split(".")),
    )
    return [*versions, f"{versions[-1]}t"] if versions else []


def jobs(workflow: Json) -> dict[str, Json]:
    return {str(name): _mapping(job) for name, job in _mapping(workflow.get("jobs")).items()}


def steps(job: Json) -> list[Json]:
    return [_mapping(step) for step in _list(job.get("steps"))]


def runs(job: Json) -> Iterator[str]:
    for step in steps(job):
        if isinstance(run := step.get("run"), str):
            yield run


def matrix(job: Json) -> Json:
    return _mapping(_mapping(job.get("strategy")).get("matrix"))


def make_targets(command: str) -> set[str]:
    """The targets each ``make`` line of a ``run:`` names; an expression names none."""

    found: set[str] = set()
    for line in command.splitlines():
        words = EXPRESSION.sub("$", line).split()
        if words[:1] == ["make"]:
            found |= {
                word
                for word in words[1:]
                if not word.startswith("-") and not {"=", "$"} & set(word)
            }
    return found


def _targets_of(commands: Iterator[str] | list[str]) -> set[str]:
    found: set[str] = set()
    for command in commands:
        found |= make_targets(command)
    return found


def _needs(job: Json) -> set[str]:
    needs = job.get("needs")
    return {needs} if isinstance(needs, str) else {str(name) for name in _list(needs)}


def _events(workflow: Json) -> set[str]:
    # YAML 1.1 reads a bare `on` key as true.
    triggers = workflow.get("on", cast(dict[object, object], workflow).get(True))
    if isinstance(triggers, str):
        return {triggers}
    if isinstance(triggers, list):
        return {str(event) for event in cast(list[object], triggers)}
    return {str(event) for event in _mapping(triggers)}


def _uv_python(job: Json) -> object:
    for step in steps(job):
        if str(step.get("uses", "")).startswith("astral-sh/setup-uv@"):
            return _mapping(step.get("with")).get("python-version")
    return None


def check_ci(workflow: Json, expected: list[str]) -> list[str]:
    """What ``ci.yml`` gets wrong, given the interpreters the classifiers name."""

    errors: list[str] = []
    found = jobs(workflow)
    if not expected:
        errors.append("pyproject.toml names no Python release in its classifiers")

    # The tiers, and the interpreters each runs on.
    tiered = {name: _targets_of(runs(job)) for name, job in found.items() if name != STACK_JOB}
    for target in TIER_TARGETS:
        if not any(target in targets for targets in tiered.values()):
            errors.append(f"ci.yml runs no `make {target}`")
    for name, targets in sorted(tiered.items()):
        job = found[name]
        for target in sorted(targets & set(EVERY_INTERPRETER)):
            pythons = matrix(job).get("python-version")
            if pythons != expected:
                errors.append(
                    f"ci.yml job {name} runs {target} on {pythons}, not on every interpreter "
                    f"{expected}"
                )
            elif _uv_python(job) != MATRIX_PYTHON:
                errors.append(f"ci.yml job {name} must install {MATRIX_PYTHON} for {target}")
        if CHROME_TARGET in targets:
            if matrix(job).get("python-version") != CHROME_MATRIX:
                errors.append(f"ci.yml job {name}'s python-version matrix must be {CHROME_MATRIX}")
            if PLAN_JOB not in _needs(job) or _uv_python(job) != MATRIX_PYTHON:
                errors.append(f"ci.yml job {name} must need {PLAN_JOB} and install {MATRIX_PYTHON}")

    # The plan job: the interpreter lists, its history, and its permission.
    plan = found.get(PLAN_JOB)
    if plan is None:
        errors.append(f"ci.yml has no {PLAN_JOB} job")
    else:
        environment: Json = {}
        for step in steps(plan):
            if "PYTHONS" in (variables := _mapping(step.get("env"))):
                environment = variables
        try:
            pythons: object = json.loads(str(environment.get("PYTHONS", "")))
        except json.JSONDecodeError:
            pythons = None
        if pythons != expected:
            errors.append(f"ci.yml {PLAN_JOB} job's PYTHONS {pythons} must be {expected}")
        chrome_python = environment.get("PR_CHROME_PYTHON")
        if not isinstance(pythons, list) or chrome_python not in cast(list[object], pythons):
            errors.append(f"ci.yml PR_CHROME_PYTHON {chrome_python!r} must be one of PYTHONS")
        checkouts = [
            step
            for step in steps(plan)
            if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        if not checkouts or any(
            _mapping(step.get("with")).get("fetch-depth") != 0 for step in checkouts
        ):
            errors.append(f"ci.yml {PLAN_JOB} job must check out with fetch-depth: 0")

    # stack-integration: lint and every tier, on the head merged with main.
    stack = found.get(STACK_JOB)
    if stack is not None:
        parts = [str(part) for part in _list(matrix(stack).get("part"))]
        covered = _targets_of([f"make {part}" for part in parts])
        if missing := sorted(set(STACK_TARGETS) - covered):
            errors.append(f"ci.yml {STACK_JOB} parts run no {', '.join(missing)}")
        if PLAN_JOB not in _needs(stack):
            errors.append(f"ci.yml {STACK_JOB} must need {PLAN_JOB}")

    # The verdict, the matrices, the limits, and cancellation.
    verdict = found.get(VERDICT_JOB)
    if verdict is None:
        errors.append(f"ci.yml has no {VERDICT_JOB} job")
    else:
        if missing := sorted(set(found) - {VERDICT_JOB} - _needs(verdict)):
            errors.append(
                f"ci.yml {VERDICT_JOB} must need every other job; it leaves out {missing}"
            )
        if verdict.get("if") not in VERDICT_IF:
            errors.append(f"ci.yml {VERDICT_JOB} must run if: always()")
    for name, job in sorted(found.items()):
        if matrix(job) and _mapping(job.get("strategy")).get("fail-fast") is not False:
            errors.append(f"ci.yml job {name} must set fail-fast: false")
        limit = job.get("timeout-minutes")
        if not isinstance(limit, int) or isinstance(limit, bool):
            errors.append(f"ci.yml job {name} must set timeout-minutes to a number of minutes")
    if _mapping(workflow.get("concurrency")).get("cancel-in-progress") != CANCEL_IN_PROGRESS:
        errors.append(f"ci.yml concurrency must cancel in progress only {CANCEL_IN_PROGRESS}")
    return errors


def check_workflow(name: str, workflow: Json) -> list[str]:
    """What any workflow gets wrong: shards, triggers, checkouts, and untrusted input."""

    errors: list[str] = []
    if "pull_request_target" in _events(workflow):
        errors.append(f"{name} must not run on pull_request_target")
    allowed = JOB_PERMISSIONS.get(name)
    if allowed is not None and workflow.get("permissions") != WORKFLOW_PERMISSIONS:
        errors.append(f"{name} permissions must be {WORKFLOW_PERMISSIONS}")
    for job_name, job in sorted(jobs(workflow).items()):
        where = f"{name} job {job_name}"
        if allowed is not None:
            granted = job.get("permissions")
            wanted = allowed.get(job_name)
            if wanted is not None and granted != wanted:
                errors.append(f"{where}'s permissions {granted} must be {wanted}")
            elif wanted is None and granted not in (None, WORKFLOW_PERMISSIONS):
                errors.append(f"{where}'s permissions {granted} must be the workflow's")
        values = matrix(job)
        for command in runs(job):
            for count in MATRIX_SHARD.findall(command):
                wanted = list(range(1, int(count) + 1))
                if values.get("shard") != wanted:
                    errors.append(
                        f"{where} runs SHARD=…/{count}, so its shard matrix must be {wanted}"
                    )
            if UNTRUSTED.search(command):
                errors.append(
                    f"{where} interpolates the event into a run: line; pass it through env:"
                )
        dealt: dict[str, list[tuple[int, int]]] = {}
        for value in values.values():
            for item in _list(value):
                if isinstance(item, str) and (shard := LITERAL_SHARD.fullmatch(item)):
                    dealt.setdefault(shard["part"], []).append(
                        (int(shard["index"]), int(shard["count"]))
                    )
        for part, shards in sorted(dealt.items()):
            counts = {count for _, count in shards}
            indices = sorted(index for index, _ in shards)
            if len(counts) != 1 or indices != list(range(1, counts.pop() + 1)):
                errors.append(
                    f"{where} deals {part} into shards {sorted(shards)}, not 1 through N of one N"
                )
        for step in steps(job):
            checkout = str(step.get("uses", "")).startswith("actions/checkout@")
            if checkout and _mapping(step.get("with")).get("persist-credentials") is not False:
                errors.append(f"{where} must check out with persist-credentials: false")
    return errors


def verify(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for path in sorted((root / WORKFLOWS).glob("*.y*ml")):
        errors += check_workflow(path.name, load(path))
    errors += check_ci(load(root / CI), interpreters(root))
    return errors


def main() -> int:
    errors = verify()
    if errors:
        print("CI workflow checks failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print("CI workflow checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
