"""Untimed probe: bytes and gzip level-6 time for the assets a cold Markdown landing fetches.

Reads files only, from a checkout given as the first argument. The asset lists are the
shell's startup scripts and the `shell-tools`, `view-composition` and `sdk-views` bundles as
`src/metabrowser/server.py` named them at `4fe109b9`; a later checkout may name others. The
Markdown plugin and KPress lists are every `.js` and `.css` they ship, an upper bound for
KPress.

    python gzip_probe.py CHECKOUT

The architecture review of 2026-11-14 ran it once on a loaded host; its readings are orders
of magnitude, not results.
"""

from __future__ import annotations

import gzip
import importlib
import statistics
import sys
import time
from pathlib import Path

EAGER = [
    "asset-loader",
    "theme-state",
    "request-error",
    "formatters",
    "inventory-scope",
    "directory-totals-store",
    "contribution-registry",
    "resource-context",
    "view-state",
    "navigation",
    "file-type-taxonomy",
    "plugin-sdk",
    "perf",
    "filter-state",
    "filter-controls",
    "icons",
    "tree-expansion",
    "tree-filter-model",
    "pending-tally-diagnostics",
    "app",
]
SHELL_TOOLS = [
    "main-tabs",
    "known-file-catalog",
    "catalog-feed",
    "file-fuzzy-match",
    "search-controller",
    "keyboard-shortcuts",
    "overlay-layer",
    "keyboard-help",
    "key-reveal",
    "shell-keymap",
    "plugin-shortcuts",
    "tree-keyboard-navigation",
    "search-palette",
    "git-graph",
    "git-history-window",
    "git-panel",
    "pulls-nav",
]
VIEW = ["view-composition", "plugin-sdk-views"]


def asset_groups(root: Path) -> dict[str, list[Path]]:
    static = root / "src/metabrowser/static"
    markdown = root / "src/metabrowser/builtin_plugins/markdown"
    groups = {
        "eager scripts": [static / f"{name}.js" for name in EAGER],
        "styles.css": [static / "styles.css"],
        "shell-tools bundle": [static / f"{name}.js" for name in SHELL_TOOLS],
        "view bundles": [static / f"{name}.js" for name in VIEW],
        "markdown plugin": sorted(markdown.glob("*.js")) + sorted(markdown.glob("*.css")),
    }
    try:
        kpress = importlib.import_module("kpress")
    except ImportError as exc:
        print("kpress not importable:", exc)
        return groups
    kpress_file = getattr(kpress, "__file__", None)
    if isinstance(kpress_file, str):
        kroot = Path(kpress_file).parent
        groups["kpress js+css (all shipped, upper bound)"] = [
            path
            for path in sorted(kroot.rglob("*"))
            if path.suffix in (".js", ".css") and path.is_file()
        ]
    return groups


def measure(paths: list[Path]) -> tuple[int, int, int, float, float, float]:
    blobs = [path.read_bytes() for path in paths if path.exists()]
    raw = sum(len(blob) for blob in blobs)
    times: list[float] = []
    compressed = 0
    for _ in range(7):
        start = time.perf_counter()
        compressed = sum(len(gzip.compress(blob, compresslevel=6)) for blob in blobs)
        times.append((time.perf_counter() - start) * 1000)
    return len(blobs), raw, compressed, statistics.median(times), min(times), max(times)


def main() -> None:
    files_total, raw_total, gz_total, ms_total = 0, 0, 0, 0.0
    for name, paths in asset_groups(Path(sys.argv[1])).items():
        n, raw, compressed, median, low, high = measure(paths)
        print(
            f"{name:45s} files={n:3d} raw={raw / 1024:8.1f} KB gz={compressed / 1024:7.1f} KB"
            f" gzip6={median:6.1f} ms ({low:.1f}-{high:.1f})"
        )
        if "kpress" not in name:
            files_total += n
            raw_total += raw
            gz_total += compressed
            ms_total += median
    print(
        f"{'TOTAL without kpress':45s} files={files_total:3d} raw={raw_total / 1024:8.1f} KB"
        f" gz={gz_total / 1024:7.1f} KB gzip6={ms_total:6.1f} ms"
    )


if __name__ == "__main__":
    main()
