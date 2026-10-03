"""Fail the build when a golden can pass while wrong, go stale, or outgrow review.

A golden is only evidence while three things hold, and none of them is visible in a
green test run:

- **It is regenerated with everything it is built from.** A browserless session
  replays a recorded response fixture, and its transcript pins what the session printed.
  If ``make golden-update`` skips the recorder, or runs it after tryscript, the
  transcript is rewritten from a stale recording and both still pass. So every module
  that calls ``tests/golden_harness.py`` must be in the Makefile list ``golden-update``
  runs, the recipe must run recorders, then tryscript and its fixup, then drivers, the
  ``GOLDEN_UPDATE`` switch is read in the harness and nowhere else, and every committed
  in-process transcript is named by a driver that writes it.
- **It records what the command did.** A block has one exit status, the last command's,
  so ``metab … | grep …`` records ``grep``'s and a command documented to exit 1 reads
  ``? 0`` (``devtools/shell_status.py``). A fence tryscript does not open, a test
  annotated ``skip`` or ``only``, and a transcript with no block at all, are the same
  failure: text that looks like evidence and is never executed
  (``devtools/tryscript_blocks.py``).
- **It is small enough to read.** ``make golden-update`` rewrites whole files, and a
  diff nobody can review turns a regression into a committed expectation.

    python -m devtools.check_goldens            # check, as `make lint-check` does
    python -m devtools.check_goldens --report   # the current size distribution
"""

from __future__ import annotations

import argparse
import ast
import re
import statistics
import sys
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Final

from devtools import shell_status, tryscript_blocks

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

# The review budget for one golden or recorded fixture, in lines.
#
# `tbd guidelines golden-testing-guidelines` gives the figure: a session small enough to
# review in a pull request and commit is under 2,000 lines. Measured on 2026-09-30 with
# `python -m devtools.check_goldens --report`, over the 57 goldens and 7 recorded
# fixtures then in the tree (25,851 lines): the median file was 226 lines and the 90th
# percentile 976. Two files were over 2,000, at 2,434 and 2,203, and both are inside the
# budget now: the first, a transcript, has been split by scenario, and the second, a
# recording that repeated pull-request records, holds each distinct record once. The
# largest inside it were a recording of 1,895 lines and a transcript of 1,217. So the
# guideline's figure fails only what is already too long to read in one sitting, and
# leaves the largest transcript room to grow by more than half before it must be split.
# A lower limit would be a number this tree did not ask for. Run the report again
# before changing it.
#
# One file has little room: `tests/fixtures/inert-html-kpress-tree.json` was 1,895
# lines, 105 under the limit, and its size is KPress's render of the hostile README,
# which this repository does not write. A KPress upgrade that adds markup can take it
# over. That is the check working, not a reason to raise the limit or to give
# recordings a looser one, which no measurement supports: shorten the fixture README or
# record a narrower projection of the tree.
MAX_GOLDEN_LINES: Final = 2000


@dataclass(frozen=True, slots=True)
class Excepted:
    """A file over the budget: the most lines it may have, and the bead that shrinks it."""

    ceiling: int
    reason: str


# Files over the budget when the check was added. Each has a ceiling, its line count
# when it was listed, so an excepted file can shrink and cannot grow. An entry is
# removed by the change that brings its file under the budget: the check fails on an
# entry whose file fits again, so the list cannot outlive its reasons.
OVER_BUDGET: Final[dict[str, Excepted]] = {}

HARNESS: Final = "tests/golden_harness.py"
UPDATE_ENV: Final = "GOLDEN_UPDATE"
# The harness function a module calls decides which Makefile list must name it.
_LIST_FOR: Final = {"check_recording": "GOLDEN_RECORDERS", "check_golden": "GOLDEN_DRIVERS"}
# The harness's own switch. A module that asks it rewrites something by itself, which
# no list can order and no check can see.
_UPDATING: Final = "updating"
# What `golden-update` must run, in this order: a session's transcript is rewritten from
# its recording, and the fixup restores what `--update` wrote literally. The lists run
# through `devtools.golden_update`, which fails on a skipped test.
_RECIPE_ORDER: Final = (
    (
        "devtools.golden_update $(GOLDEN_RECORDERS)",
        "the recorders through `devtools.golden_update`",
    ),
    ("run --update", "`tryscript run --update`"),
    ("devtools.golden_fixup", "`devtools.golden_fixup`"),
    ("devtools.golden_update $(GOLDEN_DRIVERS)", "the drivers through `devtools.golden_update`"),
)
_DOLLAR_LINE: Final = re.compile(r"^\s*\$ (.*)$")


def makefile_list(makefile: str, name: str) -> list[str]:
    """The words of the Makefile variable *name*, written with line continuations."""

    match = re.search(rf"^{re.escape(name)} :=((?:.*\\\n)*.*)$", makefile, re.MULTILINE)
    if match is None:
        return []
    return match.group(1).replace("\\\n", " ").split()


def _string_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "text"`` assignments, to resolve a name passed to the harness."""

    constants: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            constants[node.targets[0].id] = node.value.value
    return constants


@dataclass(frozen=True, slots=True)
class HarnessUse:
    """Which harness functions a test module calls, and the recordings it names."""

    functions: frozenset[str]
    recordings: frozenset[str]
    literals: frozenset[str]
    asks_updating: bool = False


def harness_use(source: str) -> HarnessUse:
    tree = ast.parse(source)
    constants = _string_constants(tree)
    functions: set[str] = set()
    recordings: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = node.func
        name = called.id if isinstance(called, ast.Name) else getattr(called, "attr", None)
        if name not in _LIST_FOR:
            continue
        functions.add(name)
        if name == "check_recording" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                recordings.add(first.value)
            elif isinstance(first, ast.Name) and first.id in constants:
                recordings.add(constants[first.id])
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    asks_updating = any(
        (isinstance(node, ast.Name) and node.id == _UPDATING)
        or (isinstance(node, ast.Attribute) and node.attr == _UPDATING)
        or (isinstance(node, ast.alias) and node.name == _UPDATING)
        for node in ast.walk(tree)
    )
    return HarnessUse(
        frozenset(functions), frozenset(recordings), frozenset(literals), asks_updating
    )


def test_modules(root: Path) -> list[Path]:
    """The test modules, which are the files directly in ``tests``.

    Not the tree below it: ``tests/fixtures`` and ``tests/manual-fixtures`` hold Python
    that is content to be served, which need not even parse.
    """

    return sorted((root / "tests").glob("*.py"))


def recipe(makefile: str, target: str) -> str:
    """The recipe lines of *target*."""

    lines = makefile.split(f"\n{target}:", 1)[-1].splitlines()[1:]
    body: list[str] = []
    for line in lines:
        if not line.startswith("\t"):
            break
        body.append(line)
    return "\n".join(body)


def registration_findings(root: Path) -> list[str]:
    """Every caller of the harness is in the list `make golden-update` runs."""

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    listed = {name: makefile_list(makefile, name) for name in _LIST_FOR.values()}
    findings: list[str] = []
    for name, modules in listed.items():
        if not modules:
            findings.append(f"Makefile: {name} is missing or empty")
        for module in modules:
            if not (root / module).is_file():
                findings.append(f"Makefile: {name} names {module}, which does not exist")
    steps = recipe(makefile, "golden-update")
    placed = [(steps.find(marker), what) for marker, what in _RECIPE_ORDER]
    findings += [f"Makefile: golden-update does not run {what}" for at, what in placed if at < 0]
    present = [step for step in placed if step[0] >= 0]
    for (earlier_at, earlier), (later_at, later) in pairwise(present):
        if later_at < earlier_at:
            findings.append(
                f"Makefile: golden-update runs {later} before {earlier}; it needs the "
                "recorders, then `tryscript run --update`, then the fixup, then the drivers"
            )
            break

    uses: dict[str, HarnessUse] = {}
    for path in test_modules(root):
        relative = path.relative_to(root).as_posix()
        if relative == HARNESS:
            continue
        use = harness_use(path.read_text(encoding="utf-8"))
        if use.asks_updating:
            findings.append(
                f"{relative}: asks the harness whether this run is updating; write through "
                "`check_golden` or `check_recording`, which `make golden-update` orders"
            )
        # The name as a whole string, which is how code asks the environment for it;
        # prose and probe sources that merely mention it are longer strings.
        if UPDATE_ENV in use.literals:
            findings.append(
                f"{relative}: reads {UPDATE_ENV} itself; compare through {HARNESS} so "
                "`make golden-update` is the one way to rewrite an expectation"
            )
        if use.functions:
            uses[relative] = use
        for function in sorted(use.functions):
            if relative not in listed[_LIST_FOR[function]]:
                findings.append(
                    f"{relative}: calls {function} but is not in {_LIST_FOR[function]}, so "
                    "`make golden-update` would leave what it writes stale"
                )
    for name, modules in listed.items():
        function = next(key for key, value in _LIST_FOR.items() if value == name)
        for module in modules:
            if (root / module).is_file() and function not in uses.get(module, _NO_USE).functions:
                findings.append(f"Makefile: {name} names {module}, which does not call {function}")

    named = {literal for module in listed["GOLDEN_DRIVERS"] for literal in _literals(uses, module)}
    for path in sorted((root / "tests" / "golden").glob("*.txt")):
        if path.name not in named:
            findings.append(
                f"{path.relative_to(root).as_posix()}: no module in GOLDEN_DRIVERS names it, "
                "so nothing compares or regenerates it"
            )
    for module, use in sorted(uses.items()):
        for recording in sorted(use.recordings):
            if not (root / "tests" / "fixtures" / recording).is_file():
                findings.append(f"{module}: records tests/fixtures/{recording}, which is missing")
    return findings


_NO_USE: Final = HarnessUse(frozenset(), frozenset(), frozenset())


def _literals(uses: dict[str, HarnessUse], module: str) -> frozenset[str]:
    return uses.get(module, _NO_USE).literals


def recorded_fixtures(root: Path) -> list[Path]:
    """The response fixtures the recorders write, read from their harness calls."""

    names: set[str] = set()
    for path in test_modules(root):
        names |= harness_use(path.read_text(encoding="utf-8")).recordings
    return sorted(root / "tests" / "fixtures" / name for name in names)


def sized_files(root: Path) -> list[Path]:
    """Everything `make golden-update` rewrites: the goldens and the recorded fixtures."""

    goldens = sorted(path for path in (root / "tests" / "golden").iterdir() if path.is_file())
    return goldens + [path for path in recorded_fixtures(root) if path.is_file()]


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def size_findings(
    root: Path, *, limit: int = MAX_GOLDEN_LINES, over_budget: dict[str, Excepted] | None = None
) -> list[str]:
    allowed = OVER_BUDGET if over_budget is None else over_budget
    findings: list[str] = []
    seen: set[str] = set()
    for path in sized_files(root):
        relative = path.relative_to(root).as_posix()
        seen.add(relative)
        lines = line_count(path)
        excepted = allowed.get(relative)
        if excepted is None:
            if lines > limit:
                findings.append(
                    f"{relative}: {lines} lines is over the {limit}-line review budget; split "
                    "it by scenario, or show a repeated payload once"
                )
        elif lines <= limit:
            findings.append(
                f"{relative}: {lines} lines is inside the budget now; remove it from OVER_BUDGET"
            )
        elif lines > excepted.ceiling:
            findings.append(
                f"{relative}: {lines} lines is over its ceiling of {excepted.ceiling}; a file "
                "excepted from the budget may shrink and may not grow"
            )
    for relative in sorted(set(allowed) - seen):
        findings.append(f"{relative}: listed in OVER_BUDGET but is not a golden or a recording")
    return findings


def transcript_findings(relative: str, text: str) -> list[str]:
    """What in one transcript reads as evidence and is not."""

    findings: list[str] = []
    blocks = tryscript_blocks.blocks(text)
    if not blocks:
        findings.append(f"{relative}: no block with a command, so tryscript runs nothing in it")
    for block in blocks:
        where = f"{relative}:{block.line}"
        if block.annotation is not None:
            findings.append(
                f"{where}: a `{block.annotation}` annotation, which makes tryscript report "
                "tests it did not run as passed"
            )
        if block.dollar_lines > 1:
            findings.append(
                f"{where}: {block.dollar_lines} `$` lines in one block, which tryscript joins "
                "into one command line; give each command its own block"
            )
        for reason in shell_status.hidden_statuses(block.command):
            findings.append(
                f"{where}: {reason}, so the block records another command's exit status; "
                "end the line with the command under test, redirected to a file if its "
                "output is long, and filter the file in the next block"
            )
    run = tryscript_blocks.run_lines(text)
    for number, line in enumerate(text.split("\n"), start=1):
        dollar = _DOLLAR_LINE.match(line)
        if number in run or dollar is None:
            continue
        if shell_status.runs_program_under_test(dollar.group(1)):
            findings.append(
                f"{relative}:{number}: a command outside the blocks tryscript runs; a block "
                "opens on an unindented line of backticks and `console` or `bash`"
            )
    return findings


def tryscript_findings(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted((root / "tests" / "golden").glob("*.tryscript.md")):
        findings += transcript_findings(
            path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")
        )
    return findings


def find_findings(
    root: Path = REPO_ROOT, *, over_budget: dict[str, Excepted] | None = None
) -> list[str]:
    return [
        *registration_findings(root),
        *size_findings(root, over_budget=over_budget),
        *tryscript_findings(root),
    ]


def report(root: Path = REPO_ROOT) -> str:
    """The size distribution the limit was chosen against, largest files first."""

    sizes = sorted(((line_count(path), path) for path in sized_files(root)), reverse=True)
    counts = [lines for lines, _path in sizes]
    deciles = statistics.quantiles(counts, n=10) if len(counts) > 1 else counts
    tryscripts = sorted((root / "tests" / "golden").glob("*.tryscript.md"))
    blocks = sum(
        len(tryscript_blocks.blocks(path.read_text(encoding="utf-8"))) for path in tryscripts
    )
    lines = [
        f"{len(counts)} files, {sum(counts)} lines; limit {MAX_GOLDEN_LINES}",
        f"median {statistics.median(counts):.0f}, 90th percentile {deciles[-1]:.0f}, "
        f"largest {counts[0]}",
        f"{len(tryscripts)} tryscript files with {blocks} commands",
        "",
    ]
    lines += [f"{count:6d}  {path.relative_to(root).as_posix()}" for count, path in sizes[:12]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    parser.add_argument("--report", action="store_true", help="print the size distribution")
    args = parser.parse_args()
    if args.report:
        print(report())
        return 0
    findings = find_findings()
    if findings:
        print("Golden checks failed:")
        print("\n".join(f"- {finding}" for finding in findings))
        return 1
    print("Golden checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
