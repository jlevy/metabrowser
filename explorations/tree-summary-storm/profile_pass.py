"""Time one root-summary tally pass over a synthetic index, and optionally profile it.

    uv --config-file uv.toml run --frozen python \
        explorations/tree-summary-storm/profile_pass.py [ENTRIES] [--profile]

The pass is ``_compute_navigation_tallies``, the work behind every root
``/api/tree?depth=0`` whose memo a write has superseded. Entries are files across ten
extensions, nine in ten gitignored, as a tree under a large ``node_modules`` is.
"""

from __future__ import annotations

import cProfile
import pstats
import sys
import time

from metabrowser.events import FsEntry
from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from metabrowser.inventory_engine.providers.python_inventory import (
    _PythonInventoryStore as PythonInventoryStore,  # pyright: ignore[reportPrivateUsage]
)

EXTENSIONS = ("js", "py", "md", "json", "ts", "txt", "png", "css", "map", "d.ts")


def main(argv: list[str]) -> None:
    count = int(argv[0]) if argv and argv[0].isdigit() else 300_000
    store = PythonInventoryStore()
    entries = [
        FsEntry.for_observed_file(
            path=f"d{index // 100}/f{index}.{EXTENSIONS[index % len(EXTENSIONS)]}",
            parent=f"d{index // 100}",
            name=f"f{index}.{EXTENSIONS[index % len(EXTENSIONS)]}",
            size=index % 1000,
            mtime_ns=1_700_000_000_000_000_000 + index,
            gitignored=index % 10 != 0,
        )
        for index in range(count)
    ]
    presets = [
        (str(preset["id"]), tuple(str(value) for value in preset["values"]))
        for preset in FILTER_TYPE_PRESETS
    ]

    def one_pass() -> None:
        store._compute_navigation_tallies(presets, 200, entries)  # pyright: ignore[reportPrivateUsage]

    for _ in range(3):
        started = time.perf_counter()
        one_pass()
        print(f"pass over {count:,} entries: {(time.perf_counter() - started) * 1000:.0f} ms")
    if "--profile" in argv:
        profiler = cProfile.Profile()
        profiler.runcall(one_pass)
        pstats.Stats(profiler).sort_stats("tottime").print_stats(10)


if __name__ == "__main__":
    main(sys.argv[1:])
