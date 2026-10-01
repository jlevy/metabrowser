"""Measure the test suite: its size by area, and what a recorded run of it cost.

A change to the tests is judged on numbers taken the same way before and after it: the
lines of Python tests, of browser-contract JavaScript, of goldens and of fixtures, the
tests each outer tier holds, and where a run spent its time. Counted by hand, those
numbers cannot be reproduced by the next person, so this prints them from one command,
at the working tree or at any commit.

    python -m devtools.suite_report                         # the working tree, by area
    python -m devtools.suite_report origin/main HEAD .      # commits side by side; `.` is the tree
    python -m devtools.suite_report --log run.log           # and what that run cost

``--log`` takes the output of ``pytest -rs --durations=N``, or a CI log from
``gh run view <run> --job <job> --log``. From a CI log the time of each test file and
each tryscript golden is the gap between the timestamps of consecutive lines: pytest
ends a file's progress line when the next file starts, and tryscript prints a golden's
verdict when it finishes. From ``--durations`` it is the sum of the listed phases, which
covers only the tests pytest listed. A skip is given the tier of the test it is in.

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
from devtools.check_goldens import makefile_list

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
# The name that stands for the working tree where a commit is expected.
WORKING_TREE: Final = "."
# The tiers of docs/e2e-testing.md, as this report can tell them apart: a marker that
# ``tests/conftest.py`` registers, or the Makefile list the admitted-Git job runs.
ADMITTED_GIT: Final = "the admitted-Git tier"
NO_TIER: Final = "no tier"

_TEST_DEF: Final = re.compile(rb"^[ \t]*(?:async[ \t]+)?def test_", re.MULTILINE)
# ``tests/conftest.py`` registers one marker for each tier a marker selects.
_REGISTERED_MARKER: Final = re.compile(r'addinivalue_line\(\s*"markers",\s*"(\w+):')
_ADMITTED_GIT_REASON: Final = re.compile(r'^ADMITTED_GIT_SKIP = "(.+)"$', re.MULTILINE)


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
    # Test functions in each outer tier: by marker, and by the Makefile's admitted-Git list.
    tiers: dict[str, int] = field(default_factory=lambda: dict[str, int]())

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


def read_tree(ref: str, root: Path = REPO_ROOT) -> dict[str, bytes]:
    """``tests/`` and the ``Makefile``, from the working tree or from a commit."""

    wanted = ["tests", "Makefile"]
    if ref == WORKING_TREE:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *wanted],
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
        ["git", "archive", "--format=tar", ref, "--", *wanted],
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


def tier_name(marker: str) -> str:
    return marker if marker in (ADMITTED_GIT, NO_TIER) else f"the `{marker}` tier"


def tier_markers(files: Mapping[str, bytes]) -> list[str]:
    conftest = files.get("tests/conftest.py", b"").decode("utf-8", "replace")
    return sorted(set(_REGISTERED_MARKER.findall(conftest)))


@dataclass(frozen=True, slots=True)
class MarkedTest:
    """A test function and the tier markers it carries, by the lines it spans."""

    first_line: int
    last_line: int
    markers: frozenset[str]


def marked_tests(source: str, markers: Sequence[str]) -> list[MarkedTest]:
    """Each ``test_`` function with the markers on it, on its module, or in a decorator it names.

    A marker reaches a test three ways here: written on it, through the module's
    ``pytestmark``, or through a decorator defined in the module that applies it.
    """

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    named: dict[str, str] = {}
    for node in tree.body:
        text = ast.get_source_segment(source, node) or ""
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            named[node.name] = text
        elif isinstance(node, ast.Assign):
            named.update({t.id: text for t in node.targets if isinstance(t, ast.Name)})
    found: list[MarkedTest] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.name.startswith("test_"):
            continue
        texts = [named.get("pytestmark", "")]
        for decorator in node.decorator_list:
            texts.append(ast.get_source_segment(source, decorator) or "")
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(target, ast.Name):
                texts.append(named.get(target.id, ""))
        carried = "\n".join(texts)
        first = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
        found.append(
            MarkedTest(
                first,
                node.end_lineno or node.lineno,
                frozenset(m for m in markers if re.search(rf"\bmark\.{m}\b", carried)),
            )
        )
    return found


def measure(files: Mapping[str, bytes]) -> Suite:
    suite = Suite()
    markers = tier_markers(files)
    makefile = files.get("Makefile", b"").decode("utf-8", "replace")
    admitted = set(makefile_list(makefile, "ADMITTED_GIT_TESTS"))
    tiers: Counter[str] = Counter()
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
            tests = len(_TEST_DEF.findall(data))
            suite.areas.setdefault(area_of(parts[1]), Size()).add(data, tests=tests)
            if path in admitted:
                tiers[ADMITTED_GIT] += tests
            for test in marked_tests(data.decode("utf-8", "replace"), markers):
                tiers.update(test.markers)
    suite.tiers = {tier_name(name): tiers[name] for name in [*markers, ADMITTED_GIT] if tiers[name]}
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
    rows = [
        ("`tests/test_*.py` files", python.files),
        ("`tests/test_*.py` lines", python.lines),
        ("`def test_` functions", python.tests),
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
    return rows + [(f"tests in {name}", count) for name, count in suite.tiers.items()]


def _largest_areas(suite: Suite, limit: int) -> list[str]:
    ranked = sorted(suite.areas, key=lambda name: (-suite.areas[name].lines, name))
    return ranked if limit <= 0 else ranked[:limit]


def render(labels: Sequence[str], suites: Sequence[Suite], *, areas: int) -> str:
    """One tree in full, or several side by side with the change from first to last."""

    last = suites[-1]
    if len(suites) == 1:
        shown = _largest_areas(last, areas)
        rows: list[Sequence[object]] = [
            (name, last.areas[name].files, last.areas[name].lines, last.areas[name].tests)
            for name in shown
        ]
        rest = [last.areas[name] for name in last.areas if name not in shown]
        if rest:
            rows.append(
                (
                    f"{len(rest)} smaller areas",
                    sum(size.files for size in rest),
                    sum(size.lines for size in rest),
                    sum(size.tests for size in rest),
                )
            )
        python = last.python
        rows.append(("all Python tests", python.files, python.lines, python.tests))
        lines = table(("Area", "Files", "Lines", "`def test_`"), rows)
        lines += ["", *table(("Measure", labels[0]), _measures(last))]
        return "\n".join(lines)

    def signed(change: int) -> str:
        return f"{change:+,}" if change else "0"

    names = list(dict.fromkeys(name for suite in suites for name, _value in _measures(suite)))
    values = [dict(_measures(suite)) for suite in suites]
    rows = [
        (
            name,
            *(v.get(name, 0) for v in values),
            signed(values[-1].get(name, 0) - values[0].get(name, 0)),
        )
        for name in names
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
        (name, *by_area[name], signed(by_area[name][-1] - by_area[name][0]))
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
_DURATION: Final = re.compile(
    r"^(?P<seconds>\d+\.\d+)s (?:call|setup|teardown)\s+(?P<file>\S+?\.py)::"
)
_SKIPPED: Final = re.compile(
    r"^SKIPPED \[(?P<count>\d+)\] (?P<file>[^:]+):(?P<line>\d+): (?P<reason>.*)$"
)
_TRYSCRIPT_START: Final = re.compile(r"\btryscript run\b")
_TRYSCRIPT_FILE: Final = re.compile(
    r"^(?:PASS|FAIL) \S*?(?P<file>tests/golden/\S+\.tryscript\.md)$"
)


@dataclass(frozen=True, slots=True)
class Skip:
    count: int
    file: str
    line: int
    reason: str


@dataclass(slots=True)
class Run:
    """What one pytest and tryscript run recorded."""

    job: str = ""
    other_jobs: list[str] = field(default_factory=lambda: list[str]())
    summary: str = ""
    # Seconds per test file, from timestamps; empty for a log that has none.
    files: dict[str, float] = field(default_factory=lambda: dict[str, float]())
    # Seconds per test file, summed over the phases ``--durations`` listed.
    listed: dict[str, float] = field(default_factory=lambda: dict[str, float]())
    goldens: dict[str, float] = field(default_factory=lambda: dict[str, float]())
    skips: list[Skip] = field(default_factory=lambda: list[Skip]())


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
        elif duration := _DURATION.match(line):
            listed = run.listed.get(duration["file"], 0.0)
            run.listed[duration["file"]] = listed + float(duration["seconds"])
        elif skipped := _SKIPPED.match(line):
            run.skips.append(
                Skip(
                    int(skipped["count"]), skipped["file"], int(skipped["line"]), skipped["reason"]
                )
            )
        elif _TRYSCRIPT_START.search(line):
            previous, in_tryscript = stamp, True
        elif in_tryscript and (golden := _TRYSCRIPT_FILE.match(line)):
            if stamp is not None and previous is not None:
                run.goldens[golden["file"]] = stamp - previous
            previous = stamp
    return run


def skip_tiers(skips: Sequence[Skip], files: Mapping[str, bytes]) -> dict[str, int]:
    """The skips of a run by tier: the marker on the test, or the admitted-Git reason."""

    markers = tier_markers(files)
    gates = files.get("tests/suite_gates.py", b"").decode("utf-8", "replace")
    reason = _ADMITTED_GIT_REASON.search(gates)
    tiers: Counter[str] = Counter()
    for skip in skips:
        source = files.get(skip.file, b"").decode("utf-8", "replace")
        carried = [
            marker
            for test in marked_tests(source, markers)
            if test.first_line <= skip.line <= test.last_line
            for marker in sorted(test.markers)
        ]
        if carried:
            tiers[carried[0]] += skip.count
        elif reason is not None and reason[1] in skip.reason:
            tiers[ADMITTED_GIT] += skip.count
        else:
            tiers[NO_TIER] += skip.count
    return {tier_name(name): count for name, count in sorted(tiers.items())}


def render_run(run: Run, files: Mapping[str, bytes], *, top: int) -> str:
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
    elif run.listed:
        lines += [
            "",
            "No timestamps in this log. Seconds below are sums over the tests --durations listed.",
            *table(("Test file", "Seconds listed"), slowest(run.listed)),
        ]
    if run.goldens:
        total = sum(run.goldens.values())
        lines += [
            "",
            f"{len(run.goldens)} tryscript goldens, {total:.1f} s",
            *table(("Golden", "Seconds"), slowest(run.goldens)),
        ]
    if run.skips:
        skipped = sum(skip.count for skip in run.skips)
        lines += ["", f"{skipped} skips listed by -rs"]
        lines += table(("Tier", "Skips"), list(skip_tiers(run.skips, files).items()))
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
    parser.add_argument("--log", type=Path, help="a pytest output or a CI job log to time")
    parser.add_argument("--job", default="", help="the job to read from a log that holds several")
    parser.add_argument(
        "--top", type=int, default=15, help="slowest files to list; 0 lists every one"
    )
    args = parser.parse_args(arguments)
    trees = [read_tree(ref) for ref in args.refs]
    labels = [describe(ref) for ref in args.refs]
    print(render(labels, [measure(tree) for tree in trees], areas=args.areas))
    if args.log is not None:
        run = parse_log(args.log.read_text(encoding="utf-8", errors="replace"), job=args.job)
        print()
        print(render_run(run, trees[-1], top=args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
