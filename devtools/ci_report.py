"""Each CI job's median and 90th percentile, and each run's push to green, from run data.

The tables of ``docs/project/research/research-2026-11-16-ci-speed.md`` were taken by
hand. This takes them again from the same data with one command, so each step of the
fast CI plan is verified the same way, and no baseline has to be kept in prose:

    python -m devtools.ci_report                         # the newest runs of ci.yml
    python -m devtools.ci_report --runs 300 --branch main
    python -m devtools.ci_report --save attic/ci-runs    # and keep the data it read
    python -m devtools.ci_report --from attic/ci-runs    # read kept data, not the network
    python -m devtools.ci_report --check                 # fail on a job near its limit

The data is ``gh api``'s: the workflow's runs, newest first, and the jobs of every
attempt of each. What it reports:

- **Push to green**, for first attempts: from the run's creation, which the push caused,
  to the end of its last job, by the kind of run and its outcome. An attempt is green
  when every job succeeded or was skipped, cancelled when one was cancelled and none
  failed, and red otherwise; a run still going is left out.
- **Runner minutes**: the sum of a first attempt's job times.
- **Jobs**: each job's time, from its start to its end, over the jobs that succeeded in
  any attempt, each execution once. Percentiles interpolate linearly between ranks.
- **Reruns**: the runs with more than one attempt, and the push to green of those whose
  newest attempt is green.
- With ``--check``, a failure when a job's 90th percentile passes ``CHECK_FRACTION`` of the
  ``timeout-minutes`` the workflow gives it, or of GitHub's default where it gives none.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, cast
from urllib.parse import quote, urlencode

import yaml

from devtools.suite_report import REPO_ROOT, table

WORKFLOW: Final = REPO_ROOT / ".github" / "workflows" / "ci.yml"
# A day of runs at the rate of 2026-11-16, when the repository ran 142 CI runs.
DEFAULT_RUNS: Final = 100
# The early warning the fast CI plan's Time Limits section asks for: a job is reported
# when its 90th percentile passes this share of its limit, before the limit trips.
CHECK_FRACTION: Final = 0.8
# What GitHub gives a job that sets no timeout-minutes.
GITHUB_DEFAULT_TIMEOUT_MINUTES: Final = 360
# One `gh api` call answers in about a second; a call past this has stalled.
GH_TIMEOUT_S: Final = 60
# Calls in flight at once: one per attempt, and a few hundred attempts in a report.
FETCH_WORKERS: Final = 8
# The most jobs one listing returns; more than this in one attempt is refused.
JOBS_PER_PAGE: Final = 100
# The runs file and the folder of jobs files that --save writes and --from reads.
RUNS_FILE: Final = "runs.json"
JOBS_DIR: Final = "jobs"

GREEN: Final = "green"
RED: Final = "red"
CANCELLED: Final = "cancelled"
_PASSING: Final = frozenset({"success", "skipped", "neutral"})

Json = dict[str, object]


class ReportError(Exception):
    """The run data could not be read."""


@dataclass(frozen=True, slots=True)
class Step:
    name: str
    conclusion: str
    minutes: float


@dataclass(frozen=True, slots=True)
class Job:
    id: int
    name: str
    status: str
    conclusion: str
    started: datetime | None
    completed: datetime | None
    steps: tuple[Step, ...]

    @property
    def minutes(self) -> float:
        if self.started is None or self.completed is None:
            return 0.0
        return (self.completed - self.started).total_seconds() / 60


@dataclass(frozen=True, slots=True)
class Attempt:
    number: int
    jobs: tuple[Job, ...]

    @property
    def outcome(self) -> str | None:
        """Green, red, or cancelled; ``None`` while a job has not completed."""

        if not self.jobs or any(job.status != "completed" for job in self.jobs):
            return None
        conclusions = {job.conclusion for job in self.jobs}
        if conclusions <= _PASSING:
            return GREEN
        if CANCELLED in conclusions and not conclusions & {"failure", "timed_out"}:
            return CANCELLED
        return RED

    @property
    def end(self) -> datetime | None:
        ends = [job.completed for job in self.jobs if job.completed is not None]
        return max(ends) if ends else None


@dataclass(frozen=True, slots=True)
class Run:
    id: int
    event: str
    branch: str
    base: str | None
    created: datetime
    attempts: tuple[Attempt, ...]

    @property
    def kind(self) -> str:
        if self.event == "push":
            return f"push to {self.branch}"
        if self.event == "pull_request":
            if self.base is None:
                return "pull request"
            return "pull request to main" if self.base == "main" else "stacked pull request"
        return self.event

    def minutes_to(self, attempt: Attempt) -> float | None:
        end = attempt.end
        return None if end is None else (end - self.created).total_seconds() / 60


def _time(value: object) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else None


def _minutes(started: object, completed: object) -> float:
    start, end = _time(started), _time(completed)
    return 0.0 if start is None or end is None else (end - start).total_seconds() / 60


def parse_job(raw: Json) -> Job:
    steps = cast("list[Json]", raw.get("steps") or [])
    return Job(
        id=int(cast("int", raw["id"])),
        name=str(raw["name"]),
        status=str(raw.get("status") or ""),
        conclusion=str(raw.get("conclusion") or ""),
        started=_time(raw.get("started_at")),
        completed=_time(raw.get("completed_at")),
        steps=tuple(
            Step(
                str(step["name"]),
                str(step.get("conclusion") or ""),
                _minutes(step.get("started_at"), step.get("completed_at")),
            )
            for step in steps
        ),
    )


def parse_run(raw: Json, attempts: Mapping[int, Sequence[Json]]) -> Run:
    pulls = cast("list[Json]", raw.get("pull_requests") or [])
    base = cast("Json", pulls[0].get("base") or {}).get("ref") if pulls else None
    created = _time(raw["created_at"])
    if created is None:
        raise ReportError(f"run {raw.get('id')} has no creation time")
    return Run(
        id=int(cast("int", raw["id"])),
        event=str(raw.get("event") or ""),
        branch=str(raw.get("head_branch") or ""),
        base=str(base) if base is not None else None,
        created=created,
        attempts=tuple(
            Attempt(number, tuple(parse_job(job) for job in attempts[number]))
            for number in sorted(attempts)
        ),
    )


# ── Reading the data ───────────────────────────────────────────────────────────


def gh_api(path: str) -> Json:
    """One ``gh api`` answer; ``{owner}`` and ``{repo}`` are the checkout's own."""

    try:
        completed = subprocess.run(
            ["gh", "api", path],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ReportError(f"gh api {path} did not answer: {error}") from error
    if completed.returncode != 0:
        raise ReportError(f"gh api {path} failed: {completed.stderr.strip()}")
    try:
        return cast("Json", json.loads(completed.stdout))
    except json.JSONDecodeError as error:
        raise ReportError(f"gh api {path} answered with no JSON: {error}") from error


def fetch(
    count: int, *, workflow: str, branch: str | None, event: str | None
) -> tuple[list[Json], dict[tuple[int, int], list[Json]]]:
    """The newest *count* runs, and the jobs of each of their attempts."""

    runs: list[Json] = []
    page = 1
    while len(runs) < count:
        # A branch may hold `&`, `#`, or `/`, so each value is encoded into the query.
        query = urlencode(
            {"per_page": 100, "page": page}
            | ({"branch": branch} if branch else {})
            | ({"event": event} if event else {})
        )
        runs_path = f"repos/{{owner}}/{{repo}}/actions/workflows/{quote(workflow)}/runs"
        answer = gh_api(f"{runs_path}?{query}")
        listed = cast("list[Json]", answer.get("workflow_runs") or [])
        runs += listed
        if len(listed) < 100:
            break
        page += 1
    runs = runs[:count]
    wanted = [
        (int(cast("int", run["id"])), number)
        for run in runs
        for number in range(1, int(cast("int", run.get("run_attempt") or 1)) + 1)
    ]

    def jobs_of(key: tuple[int, int]) -> list[Json]:
        run, number = key
        path = f"repos/{{owner}}/{{repo}}/actions/runs/{run}/attempts/{number}/jobs"
        answer = gh_api(f"{path}?per_page={JOBS_PER_PAGE}")
        jobs = cast("list[Json]", answer.get("jobs") or [])
        if int(cast("int", answer.get("total_count") or 0)) > len(jobs):
            raise ReportError(f"run {run} attempt {number} has more than {JOBS_PER_PAGE} jobs")
        return jobs

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        return runs, dict(zip(wanted, pool.map(jobs_of, wanted), strict=True))


def save(
    directory: Path, runs: Sequence[Json], jobs: Mapping[tuple[int, int], Sequence[Json]]
) -> None:
    (directory / JOBS_DIR).mkdir(parents=True, exist_ok=True)
    (directory / RUNS_FILE).write_text(json.dumps(list(runs), indent=1), encoding="utf-8")
    for (run, number), listed in jobs.items():
        path = directory / JOBS_DIR / f"{run}-{number}.json"
        path.write_text(json.dumps(list(listed), indent=1), encoding="utf-8")


def load(directory: Path) -> tuple[list[Json], dict[tuple[int, int], list[Json]]]:
    try:
        runs = cast("list[Json]", json.loads((directory / RUNS_FILE).read_text(encoding="utf-8")))
        jobs: dict[tuple[int, int], list[Json]] = {}
        for path in sorted((directory / JOBS_DIR).glob("*-*.json")):
            run, number = path.stem.rsplit("-", 1)
            jobs[int(run), int(number)] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ReportError(f"{directory} holds no report data: {error}") from error
    return runs, jobs


def assemble(runs: Iterable[Json], jobs: Mapping[tuple[int, int], Sequence[Json]]) -> list[Run]:
    assembled: list[Run] = []
    for raw in runs:
        run = int(cast("int", raw["id"]))
        attempts = {number: listed for (owner, number), listed in jobs.items() if owner == run}
        assembled.append(parse_run(raw, attempts))
    return assembled


# ── The measures ───────────────────────────────────────────────────────────────


def percentile(values: Sequence[float], fraction: float) -> float:
    """Linear interpolation between the closest ranks, as the research brief computed."""

    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = math.floor(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def limits(workflow: Path) -> list[tuple[re.Pattern[str], int | None]]:
    """Each job's display name, as a pattern, and its ``timeout-minutes``.

    A name with an expression in it matches any value there, and a matrix job with no
    name is shown as its key and its matrix values. ``None`` is a limit given by an
    expression, which this cannot read.
    """

    try:
        document = cast("Json", yaml.safe_load(workflow.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError) as error:
        raise ReportError(f"cannot read {workflow}: {error}") from error
    found: list[tuple[re.Pattern[str], int | None]] = []
    for key, raw in cast("Json", document.get("jobs") or {}).items():
        job = cast("Json", raw)
        name = job.get("name")
        if isinstance(name, str):
            parts = re.split(r"\$\{\{.*?\}\}", name)
            pattern = ".+?".join(re.escape(part) for part in parts)
        elif "matrix" in cast("Json", job.get("strategy") or {}):
            pattern = re.escape(key) + r" \(.+\)"
        else:
            pattern = re.escape(key)
        limit = job.get("timeout-minutes", GITHUB_DEFAULT_TIMEOUT_MINUTES)
        found.append((re.compile(pattern), limit if isinstance(limit, int) else None))
    return found


def limit_of(name: str, known: Sequence[tuple[re.Pattern[str], int | None]]) -> int | None:
    for pattern, limit in known:
        if pattern.fullmatch(name):
            return limit
    return None


@dataclass(frozen=True, slots=True)
class JobRow:
    name: str
    count: int
    median: float
    p90: float
    longest: float
    limit: int | None

    @property
    def near_limit(self) -> bool:
        return self.limit is not None and self.p90 > CHECK_FRACTION * self.limit


def job_rows(
    runs: Sequence[Run], known: Sequence[tuple[re.Pattern[str], int | None]]
) -> list[JobRow]:
    """One row per job name, over the successful executions, each counted once."""

    seen: set[int] = set()
    times: defaultdict[str, list[float]] = defaultdict(list)
    for run in runs:
        for attempt in run.attempts:
            for job in attempt.jobs:
                if job.conclusion == "success" and job.id not in seen:
                    seen.add(job.id)
                    times[job.name].append(job.minutes)
    return [
        JobRow(
            name,
            len(values),
            percentile(values, 0.5),
            percentile(values, 0.9),
            max(values),
            limit_of(name, known),
        )
        for name, values in sorted(times.items())
    ]


def _fmt(minutes: float) -> str:
    return f"{minutes:.1f}"


def render(
    runs: Sequence[Run],
    known: Sequence[tuple[re.Pattern[str], int | None]],
    *,
    steps: bool,
) -> tuple[str, list[JobRow]]:
    """The report, and its job rows for ``--check``."""

    attempts = sum(len(run.attempts) for run in runs)
    executions = len({job.id for run in runs for attempt in run.attempts for job in attempt.jobs})
    created = sorted(run.created for run in runs)
    lines = [
        f"{len(runs)} runs, {attempts} attempts, {executions} job executions"
        + (
            f", created {created[0]:%Y-%m-%d %H:%M} to {created[-1]:%Y-%m-%d %H:%M} UTC"
            if created
            else ""
        ),
        "",
    ]

    groups: defaultdict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    unfinished = 0
    for run in runs:
        first = run.attempts[0] if run.attempts else None
        outcome = first.outcome if first is not None else None
        wall = run.minutes_to(first) if first is not None else None
        if first is None or outcome is None or wall is None:
            unfinished += 1
            continue
        groups[run.kind, outcome].append((wall, sum(job.minutes for job in first.jobs)))
    rows = [
        (
            kind,
            outcome,
            len(values),
            _fmt(percentile([wall for wall, _ in values], 0.5)),
            _fmt(percentile([wall for wall, _ in values], 0.9)),
            _fmt(percentile([minutes for _, minutes in values], 0.5)),
        )
        for (kind, outcome), values in sorted(groups.items())
    ]
    lines += ["Push to the end of the first attempt:", ""]
    header = (
        "Run",
        "Outcome",
        "Runs",
        "Median (min)",
        "90th percentile (min)",
        "Median runner minutes",
    )
    lines += table(header, rows)
    if unfinished:
        lines += ["", f"{unfinished} run(s) still going or without jobs are left out."]

    reruns = [run for run in runs if len(run.attempts) > 1]
    green = [
        wall
        for run in reruns
        if run.attempts[-1].outcome == GREEN and (wall := run.minutes_to(run.attempts[-1]))
    ]
    lines += ["", f"{len(reruns)} of {len(runs)} runs had more than one attempt"]
    if green:
        lines[-1] += (
            f"; push to green for the {len(green)} that ended green: median "
            f"{_fmt(percentile(green, 0.5))} min, 90th percentile {_fmt(percentile(green, 0.9))}"
        )

    job_table = job_rows(runs, known)
    lines += ["", "Successful jobs:", ""]
    lines += table(
        ("Job", "Jobs", "Median (min)", "90th percentile (min)", "Longest (min)", "Limit (min)"),
        [
            (
                row.name,
                row.count,
                _fmt(row.median),
                _fmt(row.p90),
                _fmt(row.longest),
                "unknown" if row.limit is None else row.limit,
            )
            for row in job_table
        ],
    )

    if steps:
        step_times: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
        seen: set[int] = set()
        for run in runs:
            for attempt in run.attempts:
                for job in attempt.jobs:
                    if job.conclusion == "success" and job.id not in seen:
                        seen.add(job.id)
                        for step in job.steps:
                            if step.conclusion == "success":
                                step_times[job.name, step.name].append(step.minutes)
        lines += ["", "Steps of successful jobs:", ""]
        lines += table(
            ("Job", "Step", "Median (min)", "90th percentile (min)"),
            [
                (job, step, f"{percentile(values, 0.5):.2f}", f"{percentile(values, 0.9):.2f}")
                for (job, step), values in sorted(step_times.items())
            ],
        )
    return "\n".join(lines), job_table


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="newest runs to read")
    parser.add_argument("--branch", help="only runs of this head branch")
    parser.add_argument("--event", help="only runs of this event, such as push")
    parser.add_argument("--workflow", type=Path, default=WORKFLOW, help="the workflow file")
    parser.add_argument("--save", type=Path, help="write the data read to this folder")
    parser.add_argument("--from", dest="source", type=Path, help="read saved data, not gh")
    parser.add_argument("--steps", action="store_true", help="also list each job's steps")
    parser.add_argument(
        "--check",
        action="store_true",
        # argparse formats help with %, so the percent sign is doubled.
        help=f"fail when a job's 90th percentile passes {CHECK_FRACTION:.0%}% of its limit",
    )
    args = parser.parse_args(arguments)
    try:
        if args.source is not None:
            raw_runs, raw_jobs = load(args.source)
        else:
            raw_runs, raw_jobs = fetch(
                args.runs, workflow=args.workflow.name, branch=args.branch, event=args.event
            )
        if args.save is not None:
            save(args.save, raw_runs, raw_jobs)
        known = limits(args.workflow)
    except ReportError as error:
        print(f"ci-report: {error}", file=sys.stderr)
        return 1
    report, rows = render(assemble(raw_runs, raw_jobs), known, steps=args.steps)
    print(report)
    if not args.check:
        return 0
    near = [row for row in rows if row.near_limit]
    for row in near:
        print(
            f"ci-report: {row.name}'s 90th percentile, {_fmt(row.p90)} min, passes "
            f"{CHECK_FRACTION:.0%} of its {row.limit}-minute limit: add a shard, or make its "
            "slowest tests cheaper",
            file=sys.stderr,
        )
    return 1 if near else 0


if __name__ == "__main__":
    sys.exit(main())
