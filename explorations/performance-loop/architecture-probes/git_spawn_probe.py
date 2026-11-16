"""Untimed probe: wall time of the Git commands one commit comparison runs, each as its own
process, against one process that emits the listing and the patch together. Read-only.

    python git_spawn_probe.py REPOSITORY SHA [SHA ...]

The four commands mirror `GitDiffSource`'s `resolve`, `manifest` and patch reads in
`src/metabrowser/diff/adapters/git.py`. The architecture review of 2026-11-14 ran it once on
a loaded host; its readings are orders of magnitude, not results.
"""

from __future__ import annotations

import statistics
import subprocess
import sys
import time


def timed(args: list[str], n: int = 9) -> tuple[float, float]:
    """Median and minimum wall time, in milliseconds, of *n* runs of one command."""

    out: list[float] = []
    for _ in range(n):
        start = time.perf_counter()
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        out.append((time.perf_counter() - start) * 1000)
    return statistics.median(out), min(out)


def main() -> None:
    repo, shas = sys.argv[1], sys.argv[2:]
    git = ["git", "--no-optional-locks", "-C", repo]
    print(
        "git --version (spawn floor): median {:.1f} ms, min {:.1f}".format(
            *timed(["git", "--version"])
        )
    )
    for sha in shas:
        full = subprocess.run(
            [*git, "rev-parse", sha], capture_output=True, text=True, check=False
        ).stdout.strip()
        parent = subprocess.run(
            [*git, "rev-parse", sha + "~1"], capture_output=True, text=True, check=False
        ).stdout.strip()
        common = ["-M50", "-C", "--diff-merges=first-parent", parent, full]
        steps = {
            "rev-parse left": [
                *git,
                "rev-parse",
                "--verify",
                "--end-of-options",
                parent + "^{commit}",
            ],
            "rev-parse right": [
                *git,
                "rev-parse",
                "--verify",
                "--end-of-options",
                full + "^{commit}",
            ],
            "diff --raw --numstat": [
                *git,
                "diff",
                "--raw",
                "--numstat",
                "-z",
                "--no-abbrev",
                *common,
            ],
            "diff (patch)": [
                *git,
                "--literal-pathspecs",
                "diff",
                "--src-prefix=a/",
                "--dst-prefix=b/",
                "--no-ext-diff",
                *common,
            ],
        }
        one = [
            *git,
            "--literal-pathspecs",
            "diff",
            "--patch-with-raw",
            "--numstat",
            "-z",
            "--no-abbrev",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            "--no-ext-diff",
            *common,
        ]
        results = {name: timed(args) for name, args in steps.items()}
        single = timed(one)
        total = sum(median for median, _ in results.values())
        print(
            f"{sha[:8]}: "
            + ", ".join(f"{name} {median:.1f}" for name, (median, _) in results.items())
        )
        print(
            f"          four processes, medians summed {total:.1f} ms;"
            f" one process {single[0]:.1f} ms (min {single[1]:.1f}); saved {total - single[0]:.1f} ms"
        )


if __name__ == "__main__":
    main()
