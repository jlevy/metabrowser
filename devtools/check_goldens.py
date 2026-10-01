"""Fail the build when a golden can pass while wrong, go stale, or outgrow review.

A golden is only evidence while three things hold, and none of them is visible in a
green test run:

- **It is regenerated with everything it is built from.** A browserless session
  replays a recorded response fixture, and its transcript pins what the session printed.
  If ``make golden-update`` skips the recorder, the transcript is rewritten from a stale
  recording and both still pass. So every module that calls
  ``tests/golden_harness.py`` must be in the Makefile list ``golden-update`` runs, the
  ``GOLDEN_UPDATE`` switch is read in the harness and nowhere else, and every committed
  in-process transcript is named by a driver that writes it.
- **It records what the command did.** A pipeline's exit status is its last stage's, so
  ``metab … | grep …`` records ``grep``'s status and a command documented to exit 1
  reads ``? 0``. A fenced block tryscript does not run, a test annotated ``skip`` or
  ``only``, and a transcript with no block at all, are the same failure: text that
  looks like evidence and is never executed.
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
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

# The review budget for one golden or recorded fixture, in lines.
#
# `tbd guidelines golden-testing-guidelines` gives the figure: a session small enough to
# review in a pull request and commit is under 2,000 lines. Measured on 2026-09-30 with
# `python -m devtools.check_goldens --report`, over the 57 goldens and 7 recorded
# fixtures then in the tree (25,851 lines): the median file was 226 lines and the 90th
# percentile 976. Two files were over 2,000, at 2,434 and 2,203, and are listed below.
# The largest inside it were a recording of 1,895 lines and a transcript of 1,217. So
# the guideline's figure fails only what is already too long to read in one sitting, and
# leaves the largest transcript room to grow by more than half before it must be split.
# A lower limit would be a number this tree did not ask for. Run the report again
# before changing it.
MAX_GOLDEN_LINES: Final = 2000

# Files over the budget when the check was added, each with the bead that brings it
# under. An entry is removed by the change that shrinks its file: the check fails on an
# entry whose file is back inside the budget, so the list cannot outlive its reasons.
OVER_BUDGET: Final[dict[str, str]] = {
    "tests/golden/cli-git-pin.txt": "mb-79t3 shards the pin transcript by scenario",
    "tests/fixtures/github-pull-page-responses.json": (
        "mb-738k stores each distinct pull-request record once"
    ),
}

HARNESS: Final = "tests/golden_harness.py"
UPDATE_ENV: Final = "GOLDEN_UPDATE"
# The harness function a module calls decides which Makefile list must name it.
_LIST_FOR: Final = {"check_recording": "GOLDEN_RECORDERS", "check_golden": "GOLDEN_DRIVERS"}

_FENCE: Final = re.compile(r"^(`{3,})(.*)$")
# The program under test followed by a pipe in the same command. Filters over a saved
# file (`grep … out.txt | sort`) are not matched: only their input's producer matters.
# tryscript reports a `skip` test as passed, and `only` skips every other test in its file.
_ANNOTATION: Final = re.compile(r"<!--\s*(skip|only)\s*-->")
_PIPED_COMMAND: Final = re.compile(r"(?:^|[\s;&(])(metab|node)\s(?:(?!;|&&|\|\|)[^|])*\|(?!\|)")


@dataclass(frozen=True, slots=True)
class Tryscript:
    """The executable part of one tryscript file."""

    path: str
    commands: tuple[tuple[int, str], ...]
    unrun: tuple[int, ...]


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
    return HarnessUse(frozenset(functions), frozenset(recordings), frozenset(literals))


def registration_findings(root: Path) -> list[str]:
    """Every caller of the harness is in the list `make golden-update` runs."""

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    listed = {name: makefile_list(makefile, name) for name in _LIST_FOR.values()}
    findings: list[str] = []
    for name, modules in listed.items():
        if not modules:
            findings.append(f"Makefile: {name} is missing or empty")
        if f"$({name})" not in makefile.split("golden-update:", 1)[-1]:
            findings.append(f"Makefile: golden-update does not run $({name})")
        for module in modules:
            if not (root / module).is_file():
                findings.append(f"Makefile: {name} names {module}, which does not exist")

    uses: dict[str, HarnessUse] = {}
    for path in sorted((root / "tests").rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if relative == HARNESS:
            continue
        use = harness_use(path.read_text(encoding="utf-8"))
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
    for path in (root / "tests").rglob("*.py"):
        names |= harness_use(path.read_text(encoding="utf-8")).recordings
    return sorted(root / "tests" / "fixtures" / name for name in names)


def sized_files(root: Path) -> list[Path]:
    """Everything `make golden-update` rewrites: the goldens and the recorded fixtures."""

    goldens = sorted(path for path in (root / "tests" / "golden").iterdir() if path.is_file())
    return goldens + [path for path in recorded_fixtures(root) if path.is_file()]


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def size_findings(
    root: Path, *, limit: int = MAX_GOLDEN_LINES, over_budget: dict[str, str] | None = None
) -> list[str]:
    allowed = OVER_BUDGET if over_budget is None else over_budget
    findings: list[str] = []
    seen: set[str] = set()
    for path in sized_files(root):
        relative = path.relative_to(root).as_posix()
        seen.add(relative)
        lines = line_count(path)
        if lines > limit and relative not in allowed:
            findings.append(
                f"{relative}: {lines} lines is over the {limit}-line review budget; split it "
                "by scenario, or show a repeated payload once"
            )
        if lines <= limit and relative in allowed:
            findings.append(
                f"{relative}: {lines} lines is inside the budget now; remove it from OVER_BUDGET"
            )
    for relative in sorted(set(allowed) - seen):
        findings.append(f"{relative}: listed in OVER_BUDGET but is not a golden or a recording")
    return findings


def parse_tryscript(path: str, text: str) -> Tryscript:
    """The commands tryscript runs in *text*, and the fenced commands it does not."""

    commands: list[tuple[int, str]] = []
    unrun: list[int] = []
    fence: str | None = None
    console = False
    first_line = False
    for number, line in enumerate(text.splitlines(), start=1):
        opened = _FENCE.match(line)
        if fence is None:
            if opened is not None:
                fence, console, first_line = opened.group(1), opened.group(2) == "console", True
            continue
        if line.startswith(fence) and line.strip() == fence:
            fence = None
            continue
        if console and line.startswith("$ "):
            commands.append((number, line[2:]))
        elif console and line.startswith("> ") and commands:
            previous_number, previous = commands[-1]
            commands[-1] = (previous_number, f"{previous}\n{line[2:]}")
        elif not console and first_line and line.startswith("$ "):
            unrun.append(number)
        first_line = False
    return Tryscript(path, tuple(commands), tuple(unrun))


def _body(text: str) -> tuple[str, int]:
    """A transcript without its frontmatter, and how many lines the frontmatter took.

    The frontmatter is configuration; its `before` command is setup, not a block.
    """

    if not text.startswith("---\n"):
        return text, 0
    frontmatter, _separator, body = text.partition("\n---\n")
    return body, frontmatter.count("\n") + 2


def tryscript_findings(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted((root / "tests" / "golden").glob("*.tryscript.md")):
        relative = path.relative_to(root).as_posix()
        body, offset = _body(path.read_text(encoding="utf-8"))
        parsed = parse_tryscript(relative, body)
        if not parsed.commands:
            findings.append(
                f"{relative}: no console block with a command, so tryscript runs nothing in it"
            )
        for number, line in enumerate(body.splitlines(), start=1):
            annotation = _ANNOTATION.search(line)
            if annotation is not None:
                findings.append(
                    f"{relative}:{number + offset}: a `{annotation.group(1)}` annotation, which "
                    "makes tryscript report tests it did not run as passed"
                )
        for number in parsed.unrun:
            findings.append(
                f"{relative}:{number + offset}: a command in a block that is not ```console, "
                "which tryscript does not run"
            )
        for number, command in parsed.commands:
            if _PIPED_COMMAND.search(command) is not None:
                findings.append(
                    f"{relative}:{number + offset}: the command under test is piped, so the "
                    "block records the last stage's exit status; redirect it to a file, "
                    "record its own `? N`, and filter the file in a second command"
                )
    return findings


def find_findings(
    root: Path = REPO_ROOT, *, over_budget: dict[str, str] | None = None
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
        len(parse_tryscript(path.name, _body(path.read_text(encoding="utf-8"))[0]).commands)
        for path in tryscripts
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
