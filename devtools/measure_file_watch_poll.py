"""Measure what one file-watch poll costs, for ``FILE_WATCH_MAX_PATHS``.

A poll (``metabrowser.file_watches.FileWatches.poll``) asks every watched path's
generation once. This times that for a page at the bound: ``--paths`` delimited files,
each classified and its table source's generation asked, and as many plain text files,
each statted, in a folder served as ``metab`` serves one. It reports the poll's wall time
and the event loop's CPU time per path, the median of ``--repeats`` polls.

    uv run python devtools/measure_file_watch_poll.py --paths 32
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import tempfile
import time
from pathlib import Path


async def _poll(paths: list[str]) -> tuple[float, float]:
    from metabrowser.file_watches import watch_generation

    wall = time.perf_counter()
    cpu = time.thread_time()
    for path in paths:
        await watch_generation(path)
    return time.perf_counter() - wall, time.thread_time() - cpu


def _measure(paths: list[str], repeats: int) -> tuple[float, float]:
    walls: list[float] = []
    cpus: list[float] = []

    async def run() -> None:
        for _ in range(repeats):
            wall, cpu = await _poll(paths)
            walls.append(wall)
            cpus.append(cpu)

    asyncio.run(run())
    return statistics.median(walls), statistics.median(cpus)


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--paths", type=int, default=32)
    parser.add_argument("--repeats", type=int, default=50)
    args = parser.parse_args()

    from metabrowser import server

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rows = "".join(f"{n},name {n},{n * 1.5}\n" for n in range(1000))
        for n in range(args.paths):
            (root / f"t{n}.csv").write_text("n,name,score\n" + rows, encoding="utf-8")
            (root / f"t{n}.txt").write_text("plain text\n" * 100, encoding="utf-8")
        server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
        for suffix in ("csv", "txt"):
            paths = [f"t{n}.{suffix}" for n in range(args.paths)]
            wall, cpu = _measure(paths, args.repeats)
            print(
                f"{args.paths} .{suffix} paths: poll {wall * 1000:.2f} ms wall, "
                f"{cpu * 1000:.2f} ms event-loop CPU, {wall * 1000 / args.paths:.3f} ms a path"
            )


if __name__ == "__main__":
    main()
