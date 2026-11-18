"""Measure the structured diff projection over a repository's real YAML and JSON pairs.

Run from the repository root:

    uv run python explorations/structured-diff/measure.py [REPO]

Every commit's changed `.yaml`, `.yml` and `.json` files, as (parent blob, commit blob)
pairs, deduplicated by blob pair. Prints the pair size distribution and the projection's
time and answer size for the pairs inside `STRUCTURED_DIFF_MAX_BYTES`, then a synthetic
sweep of YAML and JSON pairs by size.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from metabrowser.diff.structured_projection import (
    STRUCTURED_DIFF_MAX_BYTES,
    project_structured_diff,
    structured_format,
)


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def _pairs(repo: Path) -> list[tuple[str, bytes | None, bytes | None]]:
    log = _git(
        repo,
        "log",
        "--no-merges",
        "--raw",
        "--no-abbrev",
        "--format=%H",
        "--",
        "*.json",
        "*.yaml",
        "*.yml",
    )
    seen: set[tuple[str, str]] = set()
    wanted: list[tuple[str, str, str]] = []
    for line in log.decode().splitlines():
        if not line.startswith(":"):
            continue
        meta, path = line.split("\t", 1)
        _, _, old, new, status = meta.split()
        if structured_format(Path(path).suffix) is None or status[0] not in "MAD":
            continue
        if (old, new) in seen:
            continue
        seen.add((old, new))
        wanted.append((path, old, new))
    zero = "0" * 40

    def read(oid: str) -> bytes | None:
        return None if oid == zero else _git(repo, "cat-file", "blob", oid)

    out: list[tuple[str, bytes | None, bytes | None]] = []
    for path, old, new in wanted:
        out.append((path, read(old), read(new)))
    return out


def _time(old: bytes | None, new: bytes | None, fmt: str) -> tuple[float, str, int]:
    start = time.perf_counter()
    answer = project_structured_diff(old=old, new=new, fmt=fmt)  # type: ignore[arg-type]
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed, answer["status"], len(json.dumps(answer))


def _pct(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    pairs = _pairs(repo)
    sizes = [len(o or b"") + len(n or b"") for _, o, n in pairs]
    print(f"pairs: {len(pairs)}")
    print(
        f"pair KiB p50 {_pct(sizes, 0.5) / 1024:.1f} p90 {_pct(sizes, 0.9) / 1024:.1f} p99 {_pct(sizes, 0.99) / 1024:.1f} max {max(sizes) / 1024:.1f}; past bound: {sum(size > STRUCTURED_DIFF_MAX_BYTES for size in sizes)}"
    )
    for fmt in ("yaml", "json"):
        times: list[float] = []
        answers: list[int] = []
        statuses: dict[str, int] = {}
        worst = (0.0, "", 0)
        for path, old, new in pairs:
            if structured_format(Path(path).suffix) != fmt:
                continue
            ms, status, size = _time(old, new, fmt)
            statuses[status] = statuses.get(status, 0) + 1
            if status == "ready":
                times.append(ms)
                answers.append(size)
                pair = len(old or b"") + len(new or b"")
                if ms > worst[0]:
                    worst = (ms, path, pair)
        if times:
            print(
                f"{fmt}: {statuses}; ms p50 {statistics.median(times):.2f} p90 {_pct(times, 0.9):.2f} "
                f"max {max(times):.2f} ({worst[1]}, {worst[2] / 1024:.1f} KiB pair); "
                f"answer KiB p90 {_pct(answers, 0.9) / 1024:.1f} max {max(answers) / 1024:.1f}"
            )

    def nested(count: int) -> dict[str, object]:
        return {f"key{i}": {"name": f"value number {i}", "n": i} for i in range(count)}

    def sized(encode: Callable[[object], bytes], pair_kib: int) -> bytes:
        """A side of nested mappings whose pair is just inside *pair_kib*."""

        per_entry = len(encode(nested(1000))) / 1000
        count = int(pair_kib * 1024 / 2 / per_entry)
        while len(encode(nested(count))) * 2 + 32 > pair_kib * 1024:
            count -= 10
        return encode(nested(count))

    def changed(data: bytes) -> bytes:
        return data.replace(b"value number 7", b"changed value 7", 1)

    import yaml

    def yaml_text(value: object) -> bytes:
        return yaml.safe_dump(value, sort_keys=False).encode()

    def jsonc_text(value: object) -> bytes:
        return b"// c\n" + json.dumps(value, indent=2).encode()

    def json_text(value: object) -> bytes:
        return json.dumps(value, indent=2).encode()

    cases: list[tuple[str, str, Callable[[object], bytes], tuple[int, int]]] = [
        ("YAML", "yaml", yaml_text, (16, 48)),
        ("JSONC", "json", jsonc_text, (16, 48)),
        ("JSON", "json", json_text, (48, 128)),
    ]
    for label, fmt, encode, sizes in cases:
        for kib in sizes:
            old = sized(encode, kib)
            new = changed(old)
            runs = [_time(old, new, fmt) for _ in range(5)]
            print(
                f"synthetic {label} {(len(old) + len(new)) / 1024:.0f} KiB pair: "
                f"{statistics.median(r[0] for r in runs):.1f} ms, {runs[0][1]}, "
                f"answer {runs[0][2] / 1024:.0f} KiB"
            )
    wide = list(range(4000))
    other = [-x - 1 for x in wide]
    runs = [_time(json.dumps(wide).encode(), json.dumps(other).encode(), "json") for _ in range(3)]
    print(
        f"4,000-item lists, nothing shared: {statistics.median(r[0] for r in runs):.0f} ms, {runs[0][1]}"
    )


if __name__ == "__main__":
    main()
