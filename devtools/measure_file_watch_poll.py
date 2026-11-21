"""Measure what one file-watch poll costs, for ``FILE_WATCH_MAX_PATHS``.

A poll (``metabrowser.file_watches.FileWatches.poll``) asks every watched path's
generation once. This times that for a page at the bound: ``--paths`` delimited files,
each classified and its table source's generation asked, and as many plain text files,
each statted, in a folder served as ``metab`` serves one. It reports the poll's wall time
and the event loop's CPU time per path, the median of ``--repeats`` polls.

It then times ``FileWatches.nudge``, which runs on the event loop for every inventory
change, for a change of ``MAX_CHANGE_PATHS`` paths none of which is watched, the most a
change carries and the case that asks the most, against 1, 6, and 20 pages each at
``FILE_WATCH_MAX_PATHS``.

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


def _measure_nudge(pages: int, repeats: int) -> float:
    """The median time of one nudge for a change no watch reaches, *pages* pages full."""

    from metabrowser.file_watches import FILE_WATCH_MAX_PATHS, FileWatches
    from metabrowser.inventory_engine.contract import MAX_CHANGE_PATHS

    async def run() -> float:
        watches = FileWatches(send=lambda _connection, _event: None, generation_of=_none)
        for page in range(pages):
            watches.open(f"c{page}")
            for n in range(FILE_WATCH_MAX_PATHS):
                await watches.register(f"c{page}", f"page{page}/data/t{n}.csv")
        dirty = [f"other/deep/folder/f{n}.txt" for n in range(MAX_CHANGE_PATHS)]
        times: list[float] = []
        for _ in range(repeats):
            start = time.perf_counter()
            watches.nudge(dirty)
            times.append(time.perf_counter() - start)
        return statistics.median(times)

    return asyncio.run(run())


async def _none(_path: str) -> str | None:
    return None


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
    for pages in (1, 6, 20):
        nudge = _measure_nudge(pages, args.repeats)
        print(f"nudge of a full change, {pages} full pages: {nudge * 1000:.3f} ms")


if __name__ == "__main__":
    main()
