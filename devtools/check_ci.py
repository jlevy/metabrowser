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
- **Interpreters.** Every tier's ``python-version`` matrix is the ``plan`` job's
  ``pythons`` output, and that job's ``PYTHONS`` is every interpreter: the Python
  releases ``pyproject.toml``'s classifiers name and the free-threaded build of the
  newest. ``PR_CHROME_PYTHON`` is one of them. ``devtools/ci_plan.sh`` gives a push to
  ``main``, and a pull request while ``main`` is red, all of ``PYTHONS`` and a pull
  request while it is green ``PR_CHROME_PYTHON`` alone (the owner's direction of
  2026-11-22, in the plan).
- **Shards.** A tier step, and ``test-admitted-git``, takes ``SHARD`` only as
  ``${{ matrix.shard }}``, with the job's ``shard`` matrix the ``plan`` output
  ``SHARD_OUTPUTS`` names for it, which ``devtools/ci_plan.sh`` writes as ``1/N``
  through ``N/N``; a ``stack-integration`` matrix list deals each part ``1`` through
  ``N``; no matrix has ``include`` or ``exclude``.
- **The Chrome tier.** The ``chrome`` job's one ``make`` step is ``CHROME_RUN``, the
  whole tier, and its only condition is ``CHROME_IF``: a run has every Chrome test or
  no Chrome job, never some of the tier. ``devtools/ci_plan.sh`` never gives a push to
  ``main`` ``none``.
- **Nothing silenced.** A ``make`` step is that one command, with no shell around it,
  and its words are ``make``, target names, and ``SHARD=${{ matrix.shard }}``, so no
  option ignores a failure or runs nothing; a ``stack-integration`` part's are ``-k``,
  target names, and ``SHARD=I/N``. No other ``make`` step takes an expression. No job
  or step has ``continue-on-error``. A job's ``if:`` is one of ``JOB_IFS``. A step's is ``SERIAL_IF`` on the step that runs ``make
  test-serial``, or ``CACHE_MISS_IF`` on an ``admitted-git`` step that runs no ``make``,
  and no other. ``ci-ok`` needs every other job, runs ``always()``, and runs only
  ``VERDICT_RUN`` with ``RESULTS: ${{ toJSON(needs) }}``.
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
  which a pull request's author can set, in any spelling or case: ``github.event.``,
  ``github['event']``, ``toJSON(github)``, ``GitHub.Head_Ref``, or inside ``format()``.
  An expression ends where the runner ends it, so a ``}}`` in a quoted string does not
  hide the rest;
- no ``run:`` line has an expression that reads ``env``: the shell reads a variable as
  ``"$NAME"``, which the runner does not paste into the script;
- every setup-uv step comes just after ``INSTALL_UV`` with its own version and
  checksum, which puts that uv where setup-uv finds it without fetching anything.
- every setup-node step comes just after ``INSTALL_NODE`` with its own version, which
  unpacks that Node where setup-node finds it without downloading or copying it.
  Both rules read the action's name in any case, as GitHub does.

``devtools/check_supply_chain.py`` holds the ``plan`` job's ``ADMITTED_GITS`` to both
Git floors and ``publish.yml`` to trusted publishing, and ``tests/test_ci_plan.py``
holds what this file leaves to ``devtools/ci_plan.sh``: that a push to main, and a pull
request while main is red, get all of ``PYTHONS``, every part of every tier, the whole
Chrome tier, and every admitted Git.

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
CHROME_TARGET: Final = "test-chrome"
# The targets a job's shard matrix deals: the tiers, and the admitted Git's tests.
SHARDED_TARGETS: Final = frozenset(
    {"test-parallel", "test-serial", "test-chrome", "test-goldens", "test-admitted-git"}
)
# Every tier's interpreters: the plan job's decision, which is PYTHONS for main.
PLAN_PYTHONS: Final = "${{ fromJSON(needs.plan.outputs.pythons) }}"
# The plan output that holds each sharded job's parts, and the Gits of admitted-git.
SHARD_OUTPUTS: Final = {
    "unit": "unit-shards",
    "goldens": "goldens-shards",
    "chrome": "chrome-shards",
    "admitted-git": "admitted-git-shards",
}
PLAN_LIST: Final = "${{{{ fromJSON(needs.plan.outputs.{output}) }}}}"
PLAN_GITS: Final = PLAN_LIST.format(output="admitted-gits")
# The outputs the tier jobs read, each of which the plan job passes on by its own name.
PLAN_OUTPUTS: Final = (
    "pythons",
    "chrome",
    "admitted-gits",
    *SHARD_OUTPUTS.values(),
)
STEP_OUTPUT: Final = "${{{{ steps.decide.outputs.{output} }}}}"
# The Chrome job's one make step: the whole tier on every path, a target written out so
# that no plan output can name a narrower one. And the one condition it may carry,
# under which ci-ok accepts its skip (devtools/ci_verdict.sh).
CHROME_RUN: Final = "make test-chrome SHARD=${{ matrix.shard }}"
CHROME_IF: Final = "needs.plan.outputs.chrome != 'none'"
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
# ci-ok's one command, and the job results it reads: what every other job's half of
# these rules ends in.
VERDICT_RUN: Final = "bash devtools/ci_verdict.sh"
VERDICT_RESULTS: Final = "${{ toJSON(needs) }}"
# The jobs besides the tiers that ci.yml keeps, each with the targets it runs.
REQUIRED_JOBS: Final = {
    "lint": frozenset({"lint-check", "audit"}),
    "distribution": frozenset({"build"}),
    "admitted-git": frozenset({"test-admitted-git"}),
}
# The only conditions a ci.yml job or step may carry. A skipped job reads as a failure
# in ci-ok but stack-integration's, whose condition is therefore fixed. A skipped step
# reads as success, so only two kinds may have one: the serial tier's make step, which
# runs after a failed golden too, and the admitted Git build's cache-miss steps, which
# run no make. A step of ci-ok has none.
VERDICT_IF: Final = frozenset({"always()", "${{ always() }}"})
JOB_IFS: Final = {
    STACK_JOB: frozenset({"needs.plan.outputs.integration == 'needed'"}),
    CHROME_JOB: frozenset({CHROME_IF}),
    VERDICT_JOB: VERDICT_IF,
}
SERIAL_IF: Final = "${{ !cancelled() }}"
SERIAL_TARGET: Final = "test-serial"
CACHE_MISS_IF: Final = "steps.restore-git.outputs.cache-hit != 'true'"
CACHE_JOB: Final = "admitted-git"
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
OPEN_EXPRESSION: Final = "${{"
MATRIX_SHARD: Final = re.compile(r"SHARD=\$\{\{\s*matrix\.shard\s*\}\}/(\d+)")
# A part from the job's shard matrix, which the plan job writes as I/N.
PLAN_SHARD: Final = re.compile(r"SHARD=\$\{\{\s*matrix\.shard\s*\}\}(?![/\w])")
LITERAL_SHARD: Final = re.compile(r"(?P<part>.*?)\s*SHARD=(?P<index>\d+)/(?P<count>\d+)")
# The words of a make step and of a stack-integration part, beside `make` itself: a
# target's name, a shard the matrix deals, and, in a part, make's `-k`. Any other word,
# such as `-i`, `-n`, or `VARIABLE=value`, can turn a failing tier green.
TARGET: Final = re.compile(r"[a-z][a-z0-9-]*")
DEALT_SHARD: Final = re.compile(r"SHARD=\d+/\d+")
KEEP_GOING: Final = "-k"
# What a pull request's author can set: the event (its title, body, branch, and the
# rest), the head branch, and the whole context, which holds the event. It is matched
# in an expression with its spaces removed, so `format('{0}', github.event.x)` is read
# whole; `github.event_name` is not the event. The runner reads a context's name and
# its properties in any case (actions/runner, ExpressionParser.cs), so this does too.
UNTRUSTED: Final = re.compile(r"github(?:\.event(?:[.\[),]|$)|\.head_ref|\[|\)|,|$)", re.IGNORECASE)
# The event fields a step's `with:` may take, lowercase: a commit, and a release's tag,
# which only a writer creates and checkout reads as a ref.
TRUSTED_WITH: Final = frozenset(
    {"github.event.pull_request.head.sha", "github.event.release.tag_name"}
)
# The env context, in any case, as a context and not a property: `env.NAME`,
# `env['NAME']`, `toJSON(env)`. A `run:` line reads a variable as "$NAME" instead.
ENVIRONMENT: Final = re.compile(r"(?<![\w.])env(?:[.\[),]|$)", re.IGNORECASE)
# A shell operator, substitution, or second line around a make step's command.
SHELL: Final = re.compile(r"[;&|<>`$()\n]")
# A word that runs make, wherever it is in a step's command.
MAKE_WORD: Final = re.compile(r"\bmake\b")
# The step every setup-uv step follows, with setup-uv's own version and checksum: it puts
# that uv in the tool cache, because setup-uv otherwise fetches a manifest once with a
# fixed 5 s limit, and one slow answer failed a job (devtools/install_uv.sh).
SETUP_UV: Final = "astral-sh/setup-uv@"
INSTALL_UV: Final = "bash devtools/install_uv.sh {version} {checksum}"
# The step every setup-node step follows, with setup-node's own version: it unpacks that
# Node into the tool cache, because setup-node otherwise downloads it with no limit on a
# slow transfer and copies it in file by file, and each has stalled for over a minute
# (devtools/install_node.sh).
SETUP_NODE: Final = "actions/setup-node@"
INSTALL_NODE: Final = "bash devtools/install_node.sh {version}"

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


def _expression_spans(text: str) -> Iterator[tuple[int, int, str]]:
    """Each ``${{ … }}`` in *text*: its start, its end, and its body.

    It ends as the runner ends one (actions/runner, ``TemplateReader.cs``): at the first
    ``}}`` outside a single-quoted string, so ``format('{{}} {0}', x)`` and
    ``'}}' && x`` are read whole. One with no end runs to the end of *text*.
    """

    start = text.find(OPEN_EXPRESSION)
    while start != -1:
        body_start = start + len(OPEN_EXPRESSION)
        end, body_end = len(text), len(text)
        in_string = False
        for index in range(body_start, len(text)):
            if text[index] == "'":
                in_string = not in_string  # a quote written '' toggles twice
            elif not in_string and text[index] == "}" and text[index - 1] == "}":
                end, body_end = index + 1, index - 1
                break
        yield start, end, text[body_start:body_end]
        start = text.find(OPEN_EXPRESSION, end)


def expressions(text: str) -> list[str]:
    """The body of each expression in *text*, ended as the runner ends it."""

    return [body for _, _, body in _expression_spans(text)]


def _blanked(text: str, placeholder: str) -> str:
    """*text* with each expression replaced by *placeholder*."""

    kept: list[str] = []
    position = 0
    for start, end, _ in _expression_spans(text):
        kept += [text[position:start], placeholder]
        position = end
    return "".join([*kept, text[position:]])


def make_targets(command: str) -> set[str]:
    """The targets each ``make`` line of a ``run:`` names; an expression names none."""

    found: set[str] = set()
    for line in command.splitlines():
        words = _blanked(line, "$").split()
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

    for body in expressions(text):
        squeezed = re.sub(r"\s+", "", body)
        if squeezed.lower() not in trusted and UNTRUSTED.search(squeezed):
            return True
    return False


def reads_environment(text: str) -> bool:
    """Whether an expression in *text* reads the ``env`` context."""

    return any(ENVIRONMENT.search(re.sub(r"\s+", "", body)) for body in expressions(text))


def pr_chrome_python(ci: Json) -> object:
    """The ``plan`` job's ``PR_CHROME_PYTHON`` in ``ci.yml``, or ``None``."""

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


def _may_carry(job_name: str, condition: str, command: str) -> bool:
    """Whether a ci.yml step of *job_name* that runs *command* may run under *condition*."""

    if condition == SERIAL_IF:
        return make_targets(command) == {SERIAL_TARGET}
    if condition == CACHE_MISS_IF:
        return job_name == CACHE_JOB and not MAKE_WORD.search(command)
    return False


def _plain_make(command: str) -> bool:
    """Whether *command* is ``make``, target names, and ``SHARD=${{ matrix.shard }}``."""

    shard = "\0"
    words = PLAN_SHARD.sub(shard, command).split()
    return words[:1] == ["make"] and all(
        word == shard or TARGET.fullmatch(word) for word in words[1:]
    )


def _plain_part(part: str) -> bool:
    """Whether a stack-integration *part* is ``-k``, target names, and ``SHARD=I/N``."""

    words = part.split()
    return any(TARGET.fullmatch(word) for word in words) and all(
        word == KEEP_GOING or TARGET.fullmatch(word) or DEALT_SHARD.fullmatch(word)
        for word in words
    )


def _check_steps(found: dict[str, Json]) -> list[str]:
    """Each make step is that one plain command, and each condition is one this allows."""

    errors: list[str] = []
    for name, job in sorted(found.items()):
        condition = job.get("if")
        if condition is not None and str(condition) not in JOB_IFS.get(name, frozenset()):
            errors.append(f"ci.yml job {name} must not run under if: {condition}")
        for step in steps(job):
            run = step.get("run")
            command = run if isinstance(run, str) else ""
            condition = step.get("if")
            if condition is not None and not _may_carry(name, str(condition), command):
                errors.append(f"ci.yml job {name} has a step under if: {condition}")
            if not make_targets(command):
                # A make whose target is an expression names none: only this one may.
                if MAKE_WORD.search(command) and (name, command.strip()) != (STACK_JOB, STACK_RUN):
                    errors.append(
                        f"ci.yml job {name} runs `{command.strip()}`, a make with no target named"
                    )
                continue
            plain = _blanked(command.strip(), "EXPR")
            if not plain.startswith("make ") or SHELL.search(plain):
                errors.append(f"ci.yml job {name} must run `{command.strip()}` alone")
            elif not _plain_make(command):
                errors.append(
                    f"ci.yml job {name} runs `{command.strip()}`; a make step's words are "
                    "make, targets, and SHARD=${{ matrix.shard }}"
                )
            sharded = bool(make_targets(command) & SHARDED_TARGETS)
            if sharded and name in SHARD_OUTPUTS and not PLAN_SHARD.search(command):
                errors.append(
                    f"ci.yml job {name} runs `{command.strip()}` without its part; it takes "
                    "SHARD=${{ matrix.shard }}"
                )
    return errors


def _check_stack(stack: Json) -> list[str]:
    errors: list[str] = []
    parts = [str(part) for part in _list(matrix(stack).get("part"))]
    if missing := sorted(set(STACK_TARGETS) - _targets_of(f"make {part}" for part in parts)):
        errors.append(f"ci.yml {STACK_JOB} parts run no {', '.join(missing)}")
    errors += [
        f"ci.yml {STACK_JOB} part `{part}`: a part's words are -k, targets, and SHARD=I/N"
        for part in parts
        if not _plain_part(part)
    ]
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
    outputs = _mapping(plan.get("outputs"))
    for output in PLAN_OUTPUTS:
        if outputs.get(output) != STEP_OUTPUT.format(output=output):
            errors.append(
                f"ci.yml {PLAN_JOB} job's output {output} must be "
                f"{STEP_OUTPUT.format(output=output)}"
            )
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
    if CHROME_JOB in tiered:
        # Its target is the plan job's, which make_targets cannot read.
        tiered[CHROME_JOB] |= {CHROME_TARGET}
    for target in TIER_TARGETS:
        if not any(target in targets for targets in tiered.values()):
            errors.append(f"ci.yml runs no `make {target}`")
    for name, targets in sorted(tiered.items()):
        job = found[name]
        for target in sorted(targets & set(TIER_TARGETS)):
            pythons = matrix(job).get("python-version")
            if pythons != PLAN_PYTHONS:
                errors.append(
                    f"ci.yml job {name} runs {target} on {pythons}, not on the plan job's "
                    f"interpreters {PLAN_PYTHONS}"
                )
            elif PLAN_JOB not in _needs(job) or _uv_python(job) != MATRIX_PYTHON:
                errors.append(
                    f"ci.yml job {name} must need {PLAN_JOB} and install {MATRIX_PYTHON} "
                    f"for {target}"
                )
    for name, output in sorted(SHARD_OUTPUTS.items()):
        job = found.get(name, {})
        wanted = PLAN_LIST.format(output=output)
        if matrix(job).get("shard") != wanted or PLAN_JOB not in _needs(job):
            errors.append(
                f"ci.yml job {name}'s shard matrix must be {wanted}, and it needs {PLAN_JOB}"
            )
    chrome = found.get(CHROME_JOB, {})
    if [command.strip() for command in runs(chrome) if MAKE_WORD.search(command)] != [CHROME_RUN]:
        errors.append(f"ci.yml job {CHROME_JOB} must run `{CHROME_RUN}` and no other make")
    if matrix(found.get(CACHE_JOB, {})).get("git") != PLAN_GITS:
        errors.append(f"ci.yml job {CACHE_JOB}'s git matrix must be {PLAN_GITS}")

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
        commands = [
            (str(step["run"]).strip(), _mapping(step.get("env")).get("RESULTS"))
            for step in steps(verdict)
            if "run" in step
        ]
        if commands != [(VERDICT_RUN, VERDICT_RESULTS)]:
            errors.append(
                f"ci.yml {VERDICT_JOB} must run `{VERDICT_RUN}` and no other command, with "
                f"RESULTS: {VERDICT_RESULTS}"
            )
    if _mapping(workflow.get("concurrency")).get("cancel-in-progress") != CANCEL_IN_PROGRESS:
        errors.append(f"ci.yml concurrency must cancel in progress only {CANCEL_IN_PROGRESS}")
    return errors


def check_nightly(nightly: Json, ci: Json) -> list[str]:
    """What ``nightly.yml`` gets wrong: its rules, and the values it shares with ``ci.yml``."""

    errors = _check_owned("nightly.yml", nightly)
    chrome_python = pr_chrome_python(ci)
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
            if reads_environment(command):
                errors.append(f'{where} interpolates env into a run: line; read it as "$NAME"')
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
        job_steps = steps(job)
        for index, step in enumerate(job_steps):
            inputs = step.get("with")
            given = _mapping(inputs)
            before = job_steps[index - 1].get("run") if index else None
            ran = before.strip() if isinstance(before, str) else None
            # GitHub finds an action's owner and repository whatever their case.
            uses = str(step.get("uses", "")).lower()
            if uses.startswith(SETUP_UV):
                wanted = INSTALL_UV.format(
                    version=given.get("version"), checksum=given.get("checksum")
                )
                if ran != wanted:
                    errors.append(f"{where} must run `{wanted}` just before setup-uv")
            if uses.startswith(SETUP_NODE):
                wanted = INSTALL_NODE.format(version=given.get("node-version"))
                if ran != wanted:
                    errors.append(f"{where} must run `{wanted}` just before setup-node")
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
