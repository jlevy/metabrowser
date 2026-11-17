"""Fail the build when a CI workflow could drop a check and still go green.

A workflow is easy to change in a way every remaining job passes: drop an interpreter
from a matrix, a shard from a list, the serial tier from a job, or a whole job from the
verdict. The fast CI plan (``docs/project/specs/active/plan-2026-11-16-fast-ci.md``,
"How Coverage Is Kept") says where each check runs and why. This holds
``.github/workflows/ci.yml`` to it:

- **Triggers.** It runs on a push to ``main`` and on every pull request, with no other
  ``branches``, ``paths``, or ``types`` filter.
- **Jobs.** ``plan``, ``lint`` (``lint-check`` and ``audit``), ``distribution``
  (``build``), ``admitted-git`` (``test-admitted-git``), ``stack-integration`` (``make
  ${{ matrix.part }}`` on the head merged with ``main``), and ``ci-ok`` exist, and the
  four tier targets each run.
- **Interpreters.** ``test-parallel``, ``test-serial``, and ``test-goldens`` run on every
  interpreter: the Python releases ``pyproject.toml``'s classifiers name and the
  free-threaded build of the newest, which is also the ``plan`` job's ``PYTHONS``, and
  ``PR_CHROME_PYTHON`` is one of them. The ``chrome`` matrix is the ``plan`` job's
  ``chrome-pythons``.
- **Shards.** A tier step takes ``SHARD`` only as ``${{ matrix.shard }}/N`` with a shard
  matrix of ``1`` through ``N``, or from a matrix list that deals each part ``1``
  through ``N``; no matrix has ``include`` or ``exclude``.
- **Nothing silenced.** A ``make`` step is that one command, with no shell around it; no
  job or step has ``continue-on-error``; a step's ``if:`` is one of ``STEP_IFS`` and a
  job's one of ``JOB_IFS``; ``ci-ok`` needs every other job and runs ``always()``.
- **Limits.** Every matrix job has ``fail-fast: false``, every job a ``timeout-minutes``,
  and only a pull request's run is cancelled by a newer one. The ``plan`` job checks out
  with ``fetch-depth: 0``, which ``tests-red`` and ``git merge-tree`` need.

It holds ``nightly.yml``'s jobs to ``fail-fast: false``, a ``timeout-minutes``, no
``continue-on-error``, ``PR_CHROME_PYTHON``, and ``ci.yml``'s Chrome limit.

And of every workflow file:

- the shard numbers of each sharded job are ``1`` through ``N``;
- nothing runs on ``pull_request_target`` or ``workflow_run``, which run another
  run's or a pull request's code with the base repository's token;
- every job's permissions are declared, at its own level or the workflow's, and grant
  no ``write`` but ``WRITE_GRANTS``; ``ci.yml`` and ``nightly.yml`` give
  ``contents: read``, and ``actions: read`` only to the jobs ``JOB_PERMISSIONS`` names;
- every checkout sets ``persist-credentials: false``;
- no ``run:`` line, and no string under a step's ``with:`` but ``TRUSTED_WITH``, has an
  expression that reads the event, the head branch, or the whole ``github`` context,
  which a pull request's author can set, in any spelling: ``github.event.``,
  ``github['event']``, ``toJSON(github)``, or inside ``format()``.

``devtools/check_supply_chain.py`` holds the ``admitted-git`` matrix to both Git floors
and ``publish.yml`` to trusted publishing, and ``tests/test_ci_plan.py`` holds that a
push to main, and a pull request while main is red, get all of ``PYTHONS``.

    python -m devtools.check_ci
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Final, cast

import yaml

ROOT: Final = Path(__file__).resolve().parents[1]
WORKFLOWS: Final = Path(".github") / "workflows"
CI: Final = WORKFLOWS / "ci.yml"
NIGHTLY: Final = WORKFLOWS / "nightly.yml"

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
CHROME_JOB: Final = "chrome"
STACK_TARGETS: Final = ("lint-check", *TIER_TARGETS)
STACK_RUN: Final = "make ${{ matrix.part }}"
STACK_REF: Final = "${{ github.event.pull_request.head.sha }}"
STACK_MERGE: Final = 'git merge --no-edit "$MAIN_SHA"'
STACK_MAIN_SHA: Final = "${{ needs.plan.outputs.main-sha }}"
# The jobs besides the tiers that ci.yml keeps, each with the targets it runs.
REQUIRED_JOBS: Final = {
    "lint": frozenset({"lint-check", "audit"}),
    "distribution": frozenset({"build"}),
    "admitted-git": frozenset({"test-admitted-git"}),
}
# The only conditions a ci.yml job or step may carry. A skipped job reads as a failure
# in ci-ok but stack-integration's, whose condition is therefore fixed. A skipped step
# reads as success, so only the serial tier's step (it runs after a failed golden too)
# and the admitted Git build's cache-miss steps may have one.
VERDICT_IF: Final = frozenset({"always()", "${{ always() }}"})
JOB_IFS: Final = {
    STACK_JOB: frozenset({"needs.plan.outputs.integration == 'needed'"}),
    VERDICT_JOB: VERDICT_IF,
}
STEP_IFS: Final = frozenset(
    {"${{ !cancelled() }}", "steps.restore-git.outputs.cache-hit != 'true'"}
)
CI_TRIGGERS: Final = {"push": {"branches": ["main"]}, "pull_request": None}
FORBIDDEN_TRIGGERS: Final = ("pull_request_target", "workflow_run")

WORKFLOW_PERMISSIONS: Final = {"contents": "read"}
READ_RUNS: Final = {"contents": "read", "actions": "read"}
# The workflows whose permissions this holds exactly, and the jobs among them that read
# other runs: the plan job reads main's state, and the nightly report reads job times
# (SUPPLY-CHAIN-SECURITY.md, "CI Workflows").
JOB_PERMISSIONS: Final = {
    "ci.yml": {PLAN_JOB: READ_RUNS},
    "nightly.yml": {"time-limits": READ_RUNS},
}
# The one write any workflow may hold: trusted publishing's OIDC token, which
# check_supply_chain.py holds to a published release and an environment.
WRITE_GRANTS: Final = {("publish.yml", "build-and-publish"): frozenset({"id-token"})}
CANCEL_IN_PROGRESS: Final = "${{ github.event_name == 'pull_request' }}"

CLASSIFIER: Final = re.compile(r"Programming Language :: Python :: (3\.\d+)")
EXPRESSION: Final = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)
MATRIX_SHARD: Final = re.compile(r"SHARD=\$\{\{\s*matrix\.shard\s*\}\}/(\d+)")
LITERAL_SHARD: Final = re.compile(r"(?P<part>.*?)\s*SHARD=(?P<index>\d+)/(?P<count>\d+)")
# What a pull request's author can set: the event (its title, body, branch, and the
# rest), the head branch, and the whole context, which holds the event. It is matched
# in an expression with its spaces removed, so `format('{0}', github.event.x)` is read
# whole; `github.event_name` is not the event.
UNTRUSTED: Final = re.compile(r"github(?:\.event(?:[.\[),]|$)|\.head_ref|\[|\)|,|$)")
# The event fields a step's `with:` may take: a commit, and a release's tag, which only
# a writer creates and checkout reads as a ref.
TRUSTED_WITH: Final = frozenset(
    {"github.event.pull_request.head.sha", "github.event.release.tag_name"}
)
# A shell operator, substitution, or second line around a make step's command.
SHELL: Final = re.compile(r"[;&|<>`$()\n]")

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


def _targets_of(commands: Iterable[str]) -> set[str]:
    found: set[str] = set()
    for command in commands:
        found |= make_targets(command)
    return found


def _needs(job: Json) -> set[str]:
    needs = job.get("needs")
    return {needs} if isinstance(needs, str) else {str(name) for name in _list(needs)}


def _triggers(workflow: Json) -> object:
    # YAML 1.1 reads a bare `on` key as true.
    return workflow.get("on", cast(dict[object, object], workflow).get(True))


def _events(workflow: Json) -> set[str]:
    triggers = _triggers(workflow)
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


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in cast(dict[object, object], value).values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in cast(list[object], value):
            yield from _strings(item)


def untrusted(text: str, trusted: frozenset[str] = frozenset()) -> bool:
    """Whether an expression in *text*, other than one of *trusted*, reads the event."""

    for body in EXPRESSION.findall(text):
        squeezed = re.sub(r"\s+", "", body)
        if squeezed not in trusted and UNTRUSTED.search(squeezed):
            return True
    return False


def _pr_chrome_python(ci: Json) -> object:
    for step in steps(jobs(ci).get(PLAN_JOB, {})):
        if "PR_CHROME_PYTHON" in (variables := _mapping(step.get("env"))):
            return variables["PR_CHROME_PYTHON"]
    return None


def _check_owned(name: str, workflow: Json) -> list[str]:
    """The rules ci.yml and nightly.yml both keep: limits, fail-fast, nothing silenced."""

    errors: list[str] = []
    for job_name, job in sorted(jobs(workflow).items()):
        where = f"{name} job {job_name}"
        if matrix(job) and _mapping(job.get("strategy")).get("fail-fast") is not False:
            errors.append(f"{where} must set fail-fast: false")
        if {"include", "exclude"} & set(matrix(job)):
            errors.append(f"{where}'s matrix must have no include or exclude")
        limit = job.get("timeout-minutes")
        if not isinstance(limit, int) or isinstance(limit, bool):
            errors.append(f"{where} must set timeout-minutes to a number of minutes")
        if "continue-on-error" in job:
            errors.append(f"{where} must not set continue-on-error")
        if any("continue-on-error" in step for step in steps(job)):
            errors.append(f"{where} has a step with continue-on-error")
    return errors


def _check_steps(found: dict[str, Json]) -> list[str]:
    """Each make step is that one command, and each condition is one this allows."""

    errors: list[str] = []
    for name, job in sorted(found.items()):
        condition = job.get("if")
        if condition is not None and str(condition) not in JOB_IFS.get(name, frozenset()):
            errors.append(f"ci.yml job {name} must not run under if: {condition}")
        for step in steps(job):
            condition = step.get("if")
            if condition is not None and str(condition) not in STEP_IFS:
                errors.append(f"ci.yml job {name} has a step under if: {condition}")
            command = step.get("run")
            if not isinstance(command, str) or not make_targets(command):
                continue
            plain = EXPRESSION.sub("EXPR", command.strip())
            if not plain.startswith("make ") or SHELL.search(plain):
                errors.append(f"ci.yml job {name} must run `{command.strip()}` alone")
            tier = bool(make_targets(command) & set(TIER_TARGETS))
            if tier and "SHARD=" in command and not MATRIX_SHARD.search(command):
                errors.append(
                    f"ci.yml job {name} runs a tier with a fixed SHARD; it takes "
                    "SHARD=${{ matrix.shard }}/N"
                )
    return errors


def _check_stack(stack: Json) -> list[str]:
    errors: list[str] = []
    parts = [str(part) for part in _list(matrix(stack).get("part"))]
    if missing := sorted(set(STACK_TARGETS) - _targets_of(f"make {part}" for part in parts)):
        errors.append(f"ci.yml {STACK_JOB} parts run no {', '.join(missing)}")
    if PLAN_JOB not in _needs(stack):
        errors.append(f"ci.yml {STACK_JOB} must need {PLAN_JOB}")
    made = [command.strip() for command in runs(stack) if "make" in command]
    if made != [STACK_RUN]:
        errors.append(f"ci.yml {STACK_JOB} must run `{STACK_RUN}` and no other make")
    refs = [
        _mapping(step.get("with")).get("ref")
        for step in steps(stack)
        if str(step.get("uses", "")).startswith("actions/checkout@")
    ]
    merged = any(
        STACK_MERGE in str(step.get("run", ""))
        and _mapping(step.get("env")).get("MAIN_SHA") == STACK_MAIN_SHA
        for step in steps(stack)
    )
    if refs != [STACK_REF] or not merged:
        errors.append(
            f"ci.yml {STACK_JOB} must check out {STACK_REF} and run {STACK_MERGE} with "
            f"MAIN_SHA: {STACK_MAIN_SHA}"
        )
    return errors


def _check_plan(plan: Json, expected: list[str]) -> list[str]:
    errors: list[str] = []
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
        step for step in steps(plan) if str(step.get("uses", "")).startswith("actions/checkout@")
    ]
    if not checkouts or any(
        _mapping(step.get("with")).get("fetch-depth") != 0 for step in checkouts
    ):
        errors.append(f"ci.yml {PLAN_JOB} job must check out with fetch-depth: 0")
    return errors


def check_ci(workflow: Json, expected: list[str]) -> list[str]:
    """What ``ci.yml`` gets wrong, given the interpreters the classifiers name."""

    errors = _check_owned("ci.yml", workflow)
    found = jobs(workflow)
    if not expected:
        errors.append("pyproject.toml names no Python release in its classifiers")
    if _triggers(workflow) != CI_TRIGGERS:
        errors.append(
            "ci.yml must run on a push to main and on every pull request, with no other "
            f"filter: {CI_TRIGGERS}"
        )
    for name, targets in sorted(REQUIRED_JOBS.items()):
        job = found.get(name)
        if job is None:
            errors.append(f"ci.yml has no {name} job")
        elif missing := sorted(targets - _targets_of(runs(job))):
            errors.append(f"ci.yml job {name} runs no `make {' '.join(missing)}`")
    errors += _check_steps(found)

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

    plan = found.get(PLAN_JOB)
    errors += [f"ci.yml has no {PLAN_JOB} job"] if plan is None else _check_plan(plan, expected)
    stack = found.get(STACK_JOB)
    errors += [f"ci.yml has no {STACK_JOB} job"] if stack is None else _check_stack(stack)

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
    if _mapping(workflow.get("concurrency")).get("cancel-in-progress") != CANCEL_IN_PROGRESS:
        errors.append(f"ci.yml concurrency must cancel in progress only {CANCEL_IN_PROGRESS}")
    return errors


def check_nightly(nightly: Json, ci: Json) -> list[str]:
    """What ``nightly.yml`` gets wrong: its rules, and the values it shares with ``ci.yml``."""

    errors = _check_owned("nightly.yml", nightly)
    chrome_python = _pr_chrome_python(ci)
    found = jobs(nightly)
    for name, job in sorted(found.items()):
        uses = _uv_python(job)
        if {"test-serial", CHROME_TARGET} & _targets_of(runs(job)) and uses != chrome_python:
            errors.append(
                f"nightly.yml job {name} must install PR_CHROME_PYTHON, {chrome_python!r}, "
                f"not {uses!r}"
            )
    limit = found.get(CHROME_JOB, {}).get("timeout-minutes")
    wanted = jobs(ci).get(CHROME_JOB, {}).get("timeout-minutes")
    if limit != wanted:
        errors.append(f"nightly.yml job chrome's timeout-minutes {limit} must be ci.yml's {wanted}")
    return errors


def _writes(permissions: object) -> set[str]:
    if permissions == "write-all":
        return {"all"}
    return {str(scope) for scope, level in _mapping(permissions).items() if str(level) == "write"}


def check_workflow(name: str, workflow: Json) -> list[str]:
    """What any workflow gets wrong: shards, triggers, permissions, and untrusted input."""

    errors: list[str] = []
    events = _events(workflow)
    errors += [f"{name} must not run on {event}" for event in FORBIDDEN_TRIGGERS if event in events]
    allowed = JOB_PERMISSIONS.get(name)
    declared = workflow.get("permissions")
    if allowed is not None and declared != WORKFLOW_PERMISSIONS:
        errors.append(f"{name} permissions must be {WORKFLOW_PERMISSIONS}")
    for job_name, job in sorted(jobs(workflow).items()):
        where = f"{name} job {job_name}"
        granted = job.get("permissions")
        effective = granted if granted is not None else declared
        if effective is None:
            errors.append(f"{where} must declare its permissions, or the workflow its own")
        elif extra := sorted(
            _writes(effective) - WRITE_GRANTS.get((name, job_name), frozenset[str]())
        ):
            errors.append(f"{where} must not have write permission for {', '.join(extra)}")
        if allowed is not None:
            wanted = allowed.get(job_name)
            if wanted is not None and granted != wanted:
                errors.append(f"{where}'s permissions {granted} must be {wanted}")
            elif wanted is None and granted not in (None, WORKFLOW_PERMISSIONS):
                errors.append(f"{where}'s permissions {granted} must be the workflow's")
        values = matrix(job)
        for command in runs(job):
            for count in MATRIX_SHARD.findall(command):
                shards = list(range(1, int(count) + 1))
                if values.get("shard") != shards:
                    errors.append(
                        f"{where} runs SHARD=…/{count}, so its shard matrix must be {shards}"
                    )
            if untrusted(command):
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
        for part, parts in sorted(dealt.items()):
            counts = {count for _, count in parts}
            indices = sorted(index for index, _ in parts)
            if len(counts) != 1 or indices != list(range(1, counts.pop() + 1)):
                errors.append(
                    f"{where} deals {part} into shards {sorted(parts)}, not 1 through N of one N"
                )
        for step in steps(job):
            inputs = step.get("with")
            checkout = str(step.get("uses", "")).startswith("actions/checkout@")
            if checkout and _mapping(inputs).get("persist-credentials") is not False:
                errors.append(f"{where} must check out with persist-credentials: false")
            if any(untrusted(text, TRUSTED_WITH) for text in _strings(inputs)):
                errors.append(
                    f"{where} interpolates the event into a step's with:; pass it through env:"
                )
    return errors


def verify(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for path in sorted((root / WORKFLOWS).glob("*.y*ml")):
        errors += check_workflow(path.name, load(path))
    ci = load(root / CI)
    errors += check_ci(ci, interpreters(root))
    if (root / NIGHTLY).is_file():
        errors += check_nightly(load(root / NIGHTLY), ci)
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
