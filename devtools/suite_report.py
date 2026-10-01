"""Measure the test suite: its size by area, and what a recorded run of it cost.

A change to the tests is judged on numbers taken the same way before and after it: the
lines of Python tests, of browser-contract JavaScript, of goldens and of fixtures, and
where a run spent its time. Counted by hand, those numbers cannot be reproduced by the
next person, so this prints them from one command, at the working tree or at any commit.

    python -m devtools.suite_report                         # the working tree, by area
    python -m devtools.suite_report origin/main HEAD .      # commits side by side; `.` is the tree
    python -m devtools.suite_report --log run.log           # and what that run cost

``--log`` takes a CI job log from ``gh run view <run> --job <job> --log``. The time of
each test file and each tryscript golden is the gap between the timestamps of consecutive
lines: pytest ends a file's progress line when the next file starts, and tryscript prints
a golden's verdict when it finishes. A pytest output with no timestamps gives the summary
line and the skips ``-rs`` listed, and no times.

Sizes come from the files alone, so they are the same on every machine. Run times are
one run's: quote the run they came from.

``python -m devtools.check_goldens --report`` gives the size distribution of the goldens
and recordings against their review budget; this does not repeat it.
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import re
import subprocess
import sys
import tarfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final

from devtools import tryscript_blocks

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
# The name that stands for the working tree where a commit is expected.
WORKING_TREE: Final = "."


@dataclass(slots=True)
class Size:
    """Files, their lines, and the test functions in them."""

    files: int = 0
    lines: int = 0
    tests: int = 0

    def add(self, data: bytes, *, tests: int = 0) -> None:
        self.files += 1
        self.lines += line_count(data)
        self.tests += tests


@dataclass(slots=True)
class Suite:
    """What one tree holds under ``tests``."""

    areas: dict[str, Size] = field(default_factory=lambda: dict[str, Size]())
    helpers: Size = field(default_factory=Size)
    dom: Size = field(default_factory=Size)
    goldens: Size = field(default_factory=Size)
    fixtures: Size = field(default_factory=Size)
    other: Size = field(default_factory=Size)
    tryscript_commands: int = 0

    @property
    def python(self) -> Size:
        total = Size()
        for size in self.areas.values():
            total.files += size.files
            total.lines += size.lines
            total.tests += size.tests
        return total


def line_count(data: bytes) -> int:
    """Newlines, plus a last line that has none; a binary file has no lines."""

    if b"\0" in data[:8000]:
        return 0
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def count_tests(source: bytes, path: str) -> int:
    """The test functions pytest collects: at module level, and in a ``Test`` class.

    Read from the syntax tree, so a ``def test_`` at the start of a line inside a string
    is not counted.
    """

    def is_test(node: ast.stmt) -> bool:
        named = isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        return named and node.name.startswith("test_")

    count = 0
    for node in ast.parse(source, filename=path).body:
        if is_test(node):
            count += 1
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            count += sum(is_test(member) for member in node.body)
    return count


def read_tree(ref: str, root: Path = REPO_ROOT) -> dict[str, bytes]:
    """Every file under ``tests``, from the working tree or from a commit."""

    if ref == WORKING_TREE:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "tests"],
            cwd=root,
            capture_output=True,
            check=True,
        ).stdout
        paths = sorted({os.fsdecode(name) for name in listed.split(b"\0") if name})
        # A file deleted and not yet staged is listed and is not there.
        return {
            path: (root / path).read_bytes()
            for path in paths
            if (root / path).is_file() and not (root / path).is_symlink()
        }
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref, "--", "tests"],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            extracted = tar.extractfile(member) if member.isfile() else None
            if extracted is not None:
                files[member.name] = extracted.read()
    return files


def area_of(name: str) -> str:
    """``test_cache_update.py`` is in ``cache``: the first word says what a module tests."""

    return name.removeprefix("test_").removesuffix(".py").split("_", 1)[0]


def measure(files: Mapping[str, bytes]) -> Suite:
    suite = Suite()
    for path, data in sorted(files.items()):
        parts = path.split("/")
        if parts[0] != "tests":
            continue
        if len(parts) > 2:
            folder = {"dom": suite.dom, "golden": suite.goldens, "fixtures": suite.fixtures}
            folder.get(parts[1], suite.other).add(data)
            if parts[1] == "golden" and path.endswith(".tryscript.md"):
                suite.tryscript_commands += len(tryscript_blocks.blocks(data.decode("utf-8")))
        elif not path.endswith(".py"):
            suite.other.add(data)
        elif not parts[1].startswith("test_"):
            suite.helpers.add(data)
        else:
            area = suite.areas.setdefault(area_of(parts[1]), Size())
            area.add(data, tests=count_tests(data, path))
    return suite


# ── Rendering ──────────────────────────────────────────────────────────────────


def table(header: Sequence[str], rows: Iterable[Sequence[object]]) -> list[str]:
    """A Markdown table: it reads in a terminal and pastes into a pull request."""

    def cell(value: object) -> str:
        return f"{value:,}" if isinstance(value, int) else str(value)

    lines = ["| " + " | ".join(header) + " |"]
    lines.append("| " + " | ".join(["---", *["---:"] * (len(header) - 1)]) + " |")
    lines += ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]
    return lines


def _measures(suite: Suite) -> list[tuple[str, int]]:
    python = suite.python
    return [
        ("`tests/test_*.py` files", python.files),
        ("`tests/test_*.py` lines", python.lines),
        ("test functions", python.tests),
        ("test helper modules", suite.helpers.files),
        ("test helper lines", suite.helpers.lines),
        ("`tests/dom` files", suite.dom.files),
        ("`tests/dom` lines", suite.dom.lines),
        ("`tests/golden` files", suite.goldens.files),
        ("`tests/golden` lines", suite.goldens.lines),
        ("tryscript commands", suite.tryscript_commands),
        ("`tests/fixtures` files", suite.fixtures.files),
        ("`tests/fixtures` lines", suite.fixtures.lines),
        ("other files under `tests`", suite.other.files),
        ("other lines under `tests`", suite.other.lines),
    ]


def _signed(change: int) -> str:
    return f"{change:+,}" if change else "0"


def render_tree(label: str, suite: Suite, *, areas: int) -> str:
    """One tree: its largest areas, the rest folded into one row, then the totals."""

    ranked = sorted(suite.areas, key=lambda name: (-suite.areas[name].lines, name))
    shown = ranked if areas <= 0 else ranked[:areas]
    rows: list[Sequence[object]] = [
        (name, suite.areas[name].files, suite.areas[name].lines, suite.areas[name].tests)
        for name in shown
    ]
    rest = [suite.areas[name] for name in ranked[len(shown) :]]
    if rest:
        folded = (sum(size.files for size in rest), sum(size.lines for size in rest))
        rows.append((f"{len(rest)} smaller areas", *folded, sum(size.tests for size in rest)))
    python = suite.python
    rows.append(("all Python tests", python.files, python.lines, python.tests))
    lines = table(("Area", "Files", "Lines", "Test functions"), rows)
    return "\n".join([*lines, "", *table(("Measure", label), _measures(suite))])


def render_trees(labels: Sequence[str], suites: Sequence[Suite], *, areas: int) -> str:
    """Several trees side by side, with the change from the first to the last."""

    values = [dict(_measures(suite)) for suite in suites]
    rows = [
        (name, *(value[name] for value in values), _signed(values[-1][name] - values[0][name]))
        for name in values[0]
    ]
    lines = table(("Measure", *labels, "Change"), rows)
    # Side by side, the areas worth reading are the ones that changed, largest change first.
    by_area = {
        name: [suite.areas.get(name, Size()).lines for suite in suites]
        for name in sorted({name for suite in suites for name in suite.areas})
    }
    changed = sorted(
        (name for name, counts in by_area.items() if counts[-1] != counts[0]),
        key=lambda name: (-abs(by_area[name][-1] - by_area[name][0]), name),
    )
    area_rows = [
        (name, *by_area[name], _signed(by_area[name][-1] - by_area[name][0]))
        for name in (changed if areas <= 0 else changed[:areas])
    ]
    if area_rows:
        heading = f"Lines of Python tests, {len(area_rows)} of {len(changed)} changed areas"
        lines += ["", *table((heading, *labels, "Change"), area_rows)]
    return "\n".join(lines)


# ── A recorded run ─────────────────────────────────────────────────────────────

# A CI log line is "<job>\t<step>\t<timestamp> <text>"; pytest's own output has no prefix.
_LOG_LINE: Final = re.compile(
    r"^(?:(?P<job>[^\t]*)\t[^\t]*\t)?\ufeff?"
    r"(?:(?P<stamp>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?)Z )?(?P<text>.*)$"
)
# A colour sequence, as the terminal got it or as `gh run view --log` spells the escape.
_ANSI: Final = re.compile(r"(?:\x1b|\^\[)\[[0-9;]*m")
_COLLECTED: Final = re.compile(r"^collected \d+ items?")
_PROGRESS: Final = re.compile(r"^(?:(?P<file>\S+\.py) )?[.sxXEF]+(?:\s+\[\s*\d+%\])?$")
_SUMMARY: Final = re.compile(r"^=+ (?P<summary>.*\bin [\d.]+s.*?) =+$")
_SKIPPED: Final = re.compile(r"^SKIPPED \[(?P<count>\d+)\] [^:]+:\d+: (?P<reason>.*)$")
_TRYSCRIPT_START: Final = re.compile(r"\btryscript run\b")
_TRYSCRIPT_FILE: Final = re.compile(
    r"^(?:PASS|FAIL) \S*?(?P<file>tests/golden/\S+\.tryscript\.md)$"
)


@dataclass(slots=True)
class Run:
    """What one pytest and tryscript run recorded."""

    job: str = ""
    other_jobs: list[str] = field(default_factory=lambda: list[str]())
    summary: str = ""
    # Seconds per test file and per golden, from timestamps; empty for a log that has none.
    files: dict[str, float] = field(default_factory=lambda: dict[str, float]())
    goldens: dict[str, float] = field(default_factory=lambda: dict[str, float]())
    # Skipped cases by the reason ``-rs`` printed.
    skips: Counter[str] = field(default_factory=lambda: Counter[str]())


def _seconds(stamp: str) -> float:
    whole, _, fraction = stamp.partition(".")
    return datetime.fromisoformat(whole + "+00:00").timestamp() + float(f"0.{fraction or 0}")


def parse_log(text: str, *, job: str = "") -> Run:
    """Read one job of a log: the one named, or the first that ran pytest."""

    parsed = [match for line in text.splitlines() if (match := _LOG_LINE.match(line))]
    jobs = list(dict.fromkeys(match["job"] for match in parsed if match["job"]))
    ran_pytest = [match["job"] for match in parsed if _COLLECTED.match(match["text"])]
    named = [name for name in jobs if job and job in name]
    run = Run(job=(named or ran_pytest or jobs or [""])[0] or "")
    run.other_jobs = [name for name in jobs if name != run.job]
    previous: float | None = None
    current = ""
    in_tryscript = False
    for match in parsed:
        if (match["job"] or "") != run.job:
            continue
        line = _ANSI.sub("", match["text"]).rstrip()
        stamp = _seconds(match["stamp"]) if match["stamp"] else None
        if _COLLECTED.match(line):
            previous, current, in_tryscript = stamp, "", False
        elif (progress := _PROGRESS.match(line)) and (progress["file"] or current):
            current = progress["file"] or current
            if stamp is not None and previous is not None:
                run.files[current] = run.files.get(current, 0.0) + stamp - previous
            previous = stamp
        elif line.startswith("="):
            # A section rule ends the progress lines; the last one carries the totals.
            current = ""
            if summary := _SUMMARY.match(line):
                run.summary = summary["summary"]
        elif skipped := _SKIPPED.match(line):
            run.skips[skipped["reason"]] += int(skipped["count"])
        elif _TRYSCRIPT_START.search(line):
            previous, in_tryscript = stamp, True
        elif in_tryscript and (golden := _TRYSCRIPT_FILE.match(line)):
            if stamp is not None and previous is not None:
                run.goldens[golden["file"]] = stamp - previous
            previous = stamp
    return run


def render_run(run: Run, *, top: int) -> str:
    def slowest(durations: Mapping[str, float]) -> list[Sequence[object]]:
        ranked = sorted(durations.items(), key=lambda item: (-item[1], item[0]))
        return [
            (name, f"{seconds:.1f}") for name, seconds in (ranked if top <= 0 else ranked[:top])
        ]

    lines = [f"job: {run.job}" if run.job else "job: (a pytest output, not a CI log)"]
    if run.other_jobs:
        lines.append("other jobs in this log, chosen with --job: " + ", ".join(run.other_jobs))
    lines.append(f"pytest: {run.summary or 'no summary line in this log'}")
    if run.files:
        total = sum(run.files.values())
        lines += [
            "",
            f"{len(run.files)} test files, {total:.1f} s between their progress lines",
            *table(("Test file", "Seconds"), slowest(run.files)),
        ]
    else:
        lines += ["", "No timestamps in this log, so no time per file; use a CI job log."]
    if run.goldens:
        total = sum(run.goldens.values())
        lines += [
            "",
            f"{len(run.goldens)} tryscript goldens, {total:.1f} s",
            *table(("Golden", "Seconds"), slowest(run.goldens)),
        ]
    if run.skips:
        lines += ["", f"{run.skips.total()} skips listed by -rs"]
        lines += table(("Reason", "Skips"), run.skips.most_common())
    else:
        lines += ["", "No skip is listed in this log: none happened, or pytest ran without -rs."]
    return "\n".join(lines)


def describe(ref: str, root: Path = REPO_ROOT) -> str:
    """The commit a column was measured at, so the numbers can be traced to it."""

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD" if ref == WORKING_TREE else ref],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if ref == WORKING_TREE:
        return f"working tree on {commit}"
    return commit if commit.startswith(ref) or ref.startswith(commit) else f"{ref} ({commit})"


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    parser.add_argument(
        "refs",
        nargs="*",
        default=[WORKING_TREE],
        help="commits to measure; `.` is the working tree",
    )
    parser.add_argument("--areas", type=int, default=15, help="areas to list; 0 lists every one")
    parser.add_argument("--log", type=Path, help="a CI job log, or a pytest output, to read")
    parser.add_argument("--job", default="", help="the job to read from a log that holds several")
    parser.add_argument(
        "--top", type=int, default=15, help="slowest files to list; 0 lists every one"
    )
    args = parser.parse_args(arguments)
    labels = [describe(ref) for ref in args.refs]
    suites = [measure(read_tree(ref)) for ref in args.refs]
    if len(suites) == 1:
        print(render_tree(labels[0], suites[0], areas=args.areas))
    else:
        print(render_trees(labels, suites, areas=args.areas))
    if args.log is not None:
        run = parse_log(args.log.read_text(encoding="utf-8", errors="replace"), job=args.job)
        print()
        print(render_run(run, top=args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
