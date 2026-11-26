"""Rewrite the shard weights from what CI measured (``make shard-weights``).

``devtools/shard_weights.py`` deals each tier's parts by the seconds in its ``WEIGHTS``
file. This rewrites that file from the newest successful ``CI`` run on ``main``, or from
the runs ``--run`` names, as ``gh`` reads their job logs:

    python -m devtools.refresh_shard_weights
    python -m devtools.refresh_shard_weights --run 45062416967 --run 45023473576

It reads what each tier already prints (the ``Makefile``'s ``PYTEST`` and
``devtools/run_goldens.py``): pytest's ``--durations`` lines in the ``chrome`` and
``goldens and serial`` jobs, a test's setup, call, and teardown summed;
``--file-durations`` (``tests/suite_timing.py``) in the ``unit`` jobs; and the
``golden: PASS 7.7 s <file>`` lines. A unit ran once on each interpreter of a run, and
its weight is the median of those times, over every run read: the dealers need what a
unit costs against the others, which one slow runner should not move, as it would the
maximum or the mean. The file is written sorted, a unit to a line, so a refresh reads as a
diff of the units whose time changed.

Refresh when ``make ci-report --check`` says a sharded job is near its limit, and after a
change that moves a tier's time between units, such as a new slow test or a split file.
Nothing needs it sooner: a stale weight makes the parts less even, never wrong.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

from devtools import suite_report
from devtools.shard_weights import FILES, GOLDENS, ROOT, SOURCE, TABLES, TESTS, WEIGHTS, Json

# The start of the name of each ci.yml job a table is read from; tests/test_shard_weights.py
# holds them to the workflow's job names. A test's seconds come from the two tiers dealt
# by test, a file's from the parallel tier alone: a file of the Chrome tier that also
# holds a parallel test is dealt by its parallel tests' time.
CHROME_JOB: Final = "chrome ("
SERIAL_JOB: Final = "goldens and serial ("
UNIT_JOB: Final = "unit ("
JOBS: Final = (CHROME_JOB, SERIAL_JOB, UNIT_JOB)

WORKFLOW: Final = "ci.yml"
BRANCH: Final = "main"
# One gh answer, a job's log included, has this long, as devtools/ci_report.py's has.
GH_TIMEOUT_S: Final = 60
# Job logs read at a time: a run has some forty jobs, and gh answers each in a second or two.
FETCH_WORKERS: Final = 8
JOBS_PER_PAGE: Final = 100

type Tables = dict[str, dict[str, float]]


class RefreshError(Exception):
    """The weights cannot be refreshed; the message says why."""


# ── Reading a run's logs ───────────────────────────────────────────────────────

# pytest's --durations section, and each of its lines: a phase of a test.
_DURATIONS: Final = re.compile(r"^=+ slowest (?:\d+ )?durations =+$")
_DURATION: Final = re.compile(
    r"^(?P<seconds>\d+(?:\.\d+)?)s (?:setup|call|teardown)\s+(?P<nodeid>\S.*)$"
)


def durations_of(text: str) -> dict[str, float]:
    """Seconds per test in a job log's ``--durations`` sections, its phases summed."""

    seconds: defaultdict[str, float] = defaultdict(float)
    listing = False
    for line in suite_report.log_lines(text):
        if _DURATIONS.match(line):
            listing = True
        elif listing and (phase := _DURATION.match(line)):
            seconds[phase["nodeid"]] += float(phase["seconds"])
        elif line.startswith("="):
            listing = False
    return dict(seconds)


@dataclass(slots=True)
class Samples:
    """Every time read for each unit of each table, one for each job that ran it."""

    seconds: dict[str, defaultdict[str, list[float]]] = field(
        default_factory=lambda: {table: defaultdict(list) for table in TABLES}
    )

    def add(self, job: str, log: str) -> None:
        """Read one job's log into the tables its kind of job measures."""

        read: dict[str, dict[str, float]] = {}
        if job.startswith((CHROME_JOB, SERIAL_JOB)):
            read[TESTS] = durations_of(log)
        if job.startswith((SERIAL_JOB, UNIT_JOB)):
            run = suite_report.parse_log(log)
            if job.startswith(SERIAL_JOB):
                read[GOLDENS] = run.goldens
            elif run.listed:
                # Without a --file-durations section the times are gaps between
                # progress lines, which under xdist name no file: not a measurement.
                read[FILES] = run.files
        for table, found in read.items():
            for name, seconds in found.items():
                self.seconds[table][name].append(seconds)

    def combined(self) -> Tables:
        """The median of each unit's times, to pytest's hundredth of a second."""

        return {
            table: {
                name: round(statistics.median(times), 2)
                for name, times in sorted(self.seconds[table].items())
            }
            for table in TABLES
        }


def render(tables: Tables, runs: Sequence[Mapping[str, object]]) -> str:
    """WEIGHTS's text: the source, then each table, sorted, a unit to a line."""

    document = {SOURCE: {"workflow": WORKFLOW, "runs": list(runs)}} | {
        table: dict(sorted(tables[table].items())) for table in TABLES
    }
    return json.dumps(document, indent=1, ensure_ascii=False) + "\n"


# ── Asking gh ──────────────────────────────────────────────────────────────────


def gh(*arguments: str) -> str:
    """What one ``gh`` command printed."""

    try:
        completed = subprocess.run(
            ["gh", *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GH_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RefreshError(f"gh {' '.join(arguments)} did not answer: {error}") from error
    if completed.returncode != 0:
        raise RefreshError(f"gh {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout


def _json(text: str, asked: str) -> Json:
    try:
        return cast("Json", json.loads(text))
    except json.JSONDecodeError as error:
        raise RefreshError(f"gh api {asked} answered with no JSON: {error}") from error


def newest_green_run(ask: Callable[..., str] = gh) -> int:
    """The newest successful run of ``WORKFLOW`` for a push to ``BRANCH``."""

    path = (
        f"repos/{{owner}}/{{repo}}/actions/workflows/{WORKFLOW}/runs"
        f"?branch={BRANCH}&event=push&status=success&per_page=1"
    )
    runs = cast("list[Json]", _json(ask("api", path), path).get("workflow_runs") or [])
    if not runs:
        raise RefreshError(f"no successful {WORKFLOW} run for a push to {BRANCH}")
    return int(cast("int", runs[0]["id"]))


def read_run(run: int, samples: Samples, ask: Callable[..., str] = gh) -> Json:
    """Add the times of *run*'s sharded jobs to *samples*; what ``source`` says of the run.

    The run has to be of a push, which runs every tier whole on every interpreter, and
    every sharded job of it has to have succeeded: one that failed or was cancelled
    ran only some of its units, and the rest would silently weigh the fallback.
    """

    path = f"repos/{{owner}}/{{repo}}/actions/runs/{run}"
    head = _json(ask("api", path), path)
    if head.get("event") != "push":
        raise RefreshError(
            f"run {run} is of a {head.get('event')}, not a push: a pull request's run may "
            "leave out the slow Chrome tests and all but one interpreter (devtools/ci_plan.sh)"
        )
    jobs_path = f"{path}/jobs?per_page={JOBS_PER_PAGE}"
    answer = _json(ask("api", jobs_path), jobs_path)
    jobs = cast("list[Json]", answer.get("jobs") or [])
    if int(cast("int", answer.get("total_count") or 0)) > len(jobs):
        raise RefreshError(f"run {run} has more than {JOBS_PER_PAGE} jobs")
    sharded = [job for job in jobs if str(job.get("name") or "").startswith(JOBS)]
    unfinished = sorted(str(job["name"]) for job in sharded if job.get("conclusion") != "success")
    if unfinished:
        raise RefreshError(f"run {run} has jobs that did not succeed: {', '.join(unfinished)}")
    missing = [
        kind for kind in JOBS if not any(str(job["name"]).startswith(kind) for job in sharded)
    ]
    if missing:
        raise RefreshError(f"run {run} has no job named {' or '.join(missing)}…")

    def log_of(job: Json) -> str:
        # Not `gh api …/jobs/<id>/logs`, which refuses to print a log's colour sequences.
        return ask("run", "view", "--job", str(job["id"]), "--log")

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        for job, log in zip(sharded, pool.map(log_of, sharded), strict=True):
            samples.add(str(job["name"]), log)
    return {"id": run, "commit": str(head.get("head_sha") or "")}


def refresh(runs: Sequence[int], ask: Callable[..., str] = gh) -> str:
    """WEIGHTS's text as *runs*, or else the newest green run on main, measured it."""

    samples = Samples()
    sources = [read_run(run, samples, ask) for run in sorted(set(runs)) or [newest_green_run(ask)]]
    tables = samples.combined()
    empty = [table for table in TABLES if not tables[table]]
    if empty:
        raise RefreshError(f"the logs read list no time for: {', '.join(empty)}")
    return render(tables, sources)


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    parser.add_argument(
        "--run",
        dest="runs",
        type=int,
        action="append",
        default=[],
        help=f"a CI run to read, and again for each more; the newest green one on {BRANCH} if none",
    )
    parser.add_argument("--output", type=Path, default=WEIGHTS, help="the file to write")
    args = parser.parse_args(arguments)
    try:
        text = refresh(args.runs, gh)
    except RefreshError as error:
        print(f"shard-weights: {error}", file=sys.stderr)
        return 1
    args.output.write_text(text, encoding="utf-8")
    written = cast("Json", json.loads(text))
    counts = ", ".join(f"{len(cast('Json', written[table]))} {table}" for table in TABLES)
    print(f"shard-weights: wrote {args.output} ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
