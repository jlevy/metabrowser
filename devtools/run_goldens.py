"""Run the tryscript goldens several files at a time.

Each tryscript command starts ``metab`` or Node in a process of its own, and tryscript
0.3.1 runs its files one after another with no option to run them side by side, so the
goldens kept one of a CI runner's four processors busy for 3.3 to 4.3 minutes
(``docs/project/research/research-2026-11-16-ci-speed.md``). This runs one
``tryscript run <file>`` for each file the patterns match, from a queue of ``--jobs``
workers:

    python -m devtools.run_goldens --jobs 4 'tests/golden/*.tryscript.md' -- <tryscript> run

``--shard I/N`` runs the Ith of N disjoint parts of the matched files, so CI can split the
goldens across runners as it does the pytest tiers (``make test-goldens SHARD=1/2``).
``devtools/shard_weights.py`` deals them by the seconds CI measured for each file:
heaviest first, each to the part with the least so far. The same files always make the
same parts, and every file is in exactly one. Until run 45062416967 a file's size stood
in for its time, which had tracked it over the 119 files of run 44788663205 and no longer
did: one part of two held 568 s of the 844 s of golden time.

Everything after ``--`` is the command, and each file's path is added to its end: the
``Makefile``'s ``TRYSCRIPT``, ``devtools/tryscript.sh``, which holds the goldens'
environment, then ``run`` to check them or ``run --update`` to rewrite them, as
``make golden-update`` does. A file tryscript rewrote reports ``FAIL``, as tryscript
itself does.
Every pattern must match a file before sharding. ``--check-patterns PATTERN...`` applies
the same check before ``golden-update`` runs a recorder or rewrites a transcript.

Each file's output is printed whole when the file finishes, then one line that
``devtools/suite_report.py`` reads:

    golden: PASS 10.2 s tests/golden/cli-api-cache.tryscript.md

A file passes only when tryscript exited 0 and printed that file's ``PASS`` verdict. One
that printed no verdict, as when tryscript stopped before it ran a block, fails the run,
and so does a set of patterns that matches no file: no golden can be silently absent.
"""

from __future__ import annotations

import argparse
import glob
import re
import subprocess
import sys
import time
from collections.abc import Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devtools import shard_weights

# The start of the line printed for each file, and of the summary lines.
PREFIX: Final = "golden:"
PASS: Final = "PASS"
FAIL: Final = "FAIL"
# What a file that printed neither verdict is reported as.
NO_VERDICT: Final = "NO-VERDICT"

_ANSI: Final = re.compile(r"\x1b\[[0-9;]*m")
_VERDICT: Final = re.compile(rf"^(?P<verdict>{PASS}|{FAIL}) (?P<path>.+)$")
# tryscript's last line for a file: "3 passed (1.2s)" or "2 passed, 1 failed (58ms)".
_COUNTS: Final = re.compile(r"^(?:(?P<passed>\d+) passed)?(?:, )?(?:(?P<failed>\d+) failed)?\b")


@dataclass(frozen=True, slots=True)
class Result:
    """What one file's ``tryscript run`` printed, how it exited, and how long it took."""

    path: str
    verdict: str
    returncode: int
    seconds: float
    output: str
    commands: int

    @property
    def passed(self) -> bool:
        return self.verdict == PASS and self.returncode == 0

    def line(self) -> str:
        shown = self.verdict if self.passed or self.verdict != PASS else FAIL
        return f"{PREFIX} {shown} {self.seconds:.1f} s {self.path}"


def matched(patterns: Sequence[str], *, require_each: bool = False) -> list[str]:
    """The files the patterns match, each once. With *require_each*, reject unmatched patterns."""

    found: set[str] = set()
    unmatched: list[str] = []
    for pattern in patterns:
        files = {name for name in glob.glob(pattern) if name in found or Path(name).is_file()}
        found.update(files)
        if not files:
            unmatched.append(pattern)
    if require_each and unmatched:
        raise ValueError(f"no file matches {' '.join(unmatched)}")
    return sorted(found)


def _checked_paths(patterns: Sequence[str]) -> list[str] | None:
    try:
        return matched(patterns, require_each=True)
    except ValueError as exc:
        print(f"{PREFIX} {exc}", file=sys.stderr)
        return None


def parse_shard(value: str) -> tuple[int, int]:
    """The ``(index, count)`` of ``I/N``, such as ``2/3``, with ``1 <= I <= N``."""

    match = re.fullmatch(r"(\d+)/(\d+)", value)
    if match is None or not 1 <= int(match[1]) <= int(match[2]):
        raise argparse.ArgumentTypeError(
            f"--shard takes I/N with 1 <= I <= N, such as 2/3, not {value!r}"
        )
    return int(match[1]), int(match[2])


def _measured_name(path: str) -> str:
    """*path* as the weights name it: from the repository's root, if it is under it."""

    try:
        return Path(path).resolve().relative_to(shard_weights.ROOT).as_posix()
    except ValueError:
        return path


def dealt(
    paths: Sequence[str], index: int, count: int, seconds: Mapping[str, float] | None = None
) -> list[str]:
    """The files of part *index* of *count*, weighed by *seconds* or else as measured."""

    measured = shard_weights.load(shard_weights.GOLDENS) if seconds is None else seconds
    names = {path: _measured_name(path) for path in paths}
    part_of = shard_weights.parts(names.values(), count, measured)
    return [path for path in paths if part_of[names[path]] == index - 1]


def read_output(path: str, output: str) -> tuple[str, int]:
    """The verdict tryscript printed for *path*, and how many commands it counted."""

    verdict = NO_VERDICT
    commands = 0
    wanted = Path(path).resolve()
    for line in _ANSI.sub("", output).splitlines():
        if (found := _VERDICT.match(line.strip())) and Path(found["path"]).resolve() == wanted:
            verdict = found["verdict"]
        elif (counts := _COUNTS.match(line.strip())) and (counts["passed"] or counts["failed"]):
            commands = int(counts["passed"] or 0) + int(counts["failed"] or 0)
    return verdict, commands


def run_one(command: Sequence[str], path: str) -> Result:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [*command, path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    except OSError as error:
        # The command could not start: the file is reported, with the reason, as one that
        # gave no verdict, and the others still run.
        return Result(path, NO_VERDICT, 127, time.monotonic() - started, f"{error}\n", 0)
    seconds = time.monotonic() - started
    verdict, commands = read_output(path, completed.stdout)
    return Result(path, verdict, completed.returncode, seconds, completed.stdout, commands)


def run_all(command: Sequence[str], paths: Sequence[str], jobs: int) -> Iterator[Result]:
    """Each file's result as it finishes, with at most *jobs* running at once."""

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(run_one, command, path) for path in paths]
        for future in as_completed(futures):
            yield future.result()


def _jobs(value: str) -> int:
    count = int(value)
    if count < 1:
        raise argparse.ArgumentTypeError(f"--jobs takes 1 or more, not {value}")
    return count


def main(arguments: Sequence[str] | None = None) -> int:
    given = list(sys.argv[1:] if arguments is None else arguments)
    if given[:1] == ["--check-patterns"]:
        return 1 if _checked_paths(given[1:]) is None else 0
    if "--" not in given or given.index("--") == len(given) - 1:
        print(
            "usage: python -m devtools.run_goldens [--jobs N] PATTERN... -- COMMAND...",
            file=sys.stderr,
        )
        return 2
    split = given.index("--")
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    parser.add_argument("--jobs", type=_jobs, default=1, help="files to run at a time")
    parser.add_argument(
        "--shard", type=parse_shard, default=None, help="run part I of N, as 1/2, of the files"
    )
    parser.add_argument("patterns", nargs="+", help="golden files or glob patterns")
    args = parser.parse_args(given[:split])
    command = given[split + 1 :]
    paths = _checked_paths(args.patterns)
    if paths is None:
        return 1
    if args.shard is not None:
        paths = dealt(paths, *args.shard)
    started = time.monotonic()
    results: list[Result] = []
    for result in run_all(command, paths, args.jobs):
        results.append(result)
        print(result.output, end="" if result.output.endswith("\n") else "\n")
        print(result.line(), flush=True)
    elapsed = time.monotonic() - started
    failed = sorted(result.path for result in results if not result.passed)
    commands = sum(result.commands for result in results)
    files_s = sum(result.seconds for result in results)
    print(
        f"{PREFIX} {len(results)} files and {commands} commands in {elapsed:.1f} s, "
        f"{args.jobs} at a time ({files_s:.1f} s of files): "
        f"{len(results) - len(failed)} passed, {len(failed)} failed"
    )
    for path in failed:
        print(f"{PREFIX} failed: {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
