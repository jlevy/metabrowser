"""Measure the structured diff projection over a repository's real YAML and JSON pairs.

Run from the repository root:

    uv --config-file uv.toml run --frozen python explorations/structured-diff/measure.py [REPO]

Every commit's changed `.yaml`, `.yml` and `.json` files, as (parent blob, commit blob)
pairs, deduplicated by blob pair. Prints the pair size distribution and the projection's
time, entries and answer size for the pairs inside `STRUCTURED_DIFF_MAX_BYTES`, then the
synthetic shapes each budget is measured on: the densest text at each parser's bound,
lists of repeated values (review A1), nesting (C3), and the node, entry, alignment and
pairing budgets. An answer counts as `ready` only when it encodes as the route's
`JSONResponse` encodes it; one that does not counts as `unsendable`.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from metabrowser.diff import structured_projection
from metabrowser.diff.structured_projection import (
    JSONC_MAX_BYTES,
    STRUCTURED_DIFF_MAX_BYTES,
    StructuredDiffEntry,
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


def _entries(entries: list[StructuredDiffEntry]) -> int:
    return sum(1 + _entries(entry.get("entries", [])) for entry in entries)


def _time(old: bytes | None, new: bytes | None, fmt: str) -> tuple[float, str, int, int]:
    """Milliseconds, status, encoded bytes and entries of one projection."""

    start = time.perf_counter()
    answer = project_structured_diff(old=old, new=new, fmt=fmt)  # type: ignore[arg-type]
    elapsed = (time.perf_counter() - start) * 1000
    try:
        # As the route's JSONResponse renders an answer.
        size = len(
            json.dumps(
                answer, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")
            ).encode("utf-8")
        )
    except (ValueError, UnicodeError):
        return elapsed, "unsendable", 0, 0
    return elapsed, answer["status"], size, _entries(answer["root"])


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
        entries: list[int] = []
        statuses: dict[str, int] = {}
        worst = (0.0, "", 0)
        for path, old, new in pairs:
            if structured_format(Path(path).suffix) != fmt:
                continue
            ms, status, size, drawn = _time(old, new, fmt)
            statuses[status] = statuses.get(status, 0) + 1
            if status == "ready":
                times.append(ms)
                answers.append(size)
                entries.append(drawn)
                pair = len(old or b"") + len(new or b"")
                if ms > worst[0]:
                    worst = (ms, path, pair)
        if times:
            print(
                f"{fmt}: {statuses}; ms p50 {statistics.median(times):.2f} p90 {_pct(times, 0.9):.2f} "
                f"max {max(times):.2f} ({worst[1]}, {worst[2] / 1024:.1f} KiB pair); "
                f"answer KiB p90 {_pct(answers, 0.9) / 1024:.1f} max {max(answers) / 1024:.1f}; "
                f"entries p50 {_pct(entries, 0.5)} p90 {_pct(entries, 0.9)} "
                f"p99 {_pct(entries, 0.99)} max {max(entries)}"
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
        ("JSONC", "json", jsonc_text, (4, 8)),
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
    _budgets()


def _report(label: str, old: bytes, new: bytes, fmt: str, runs: int = 3) -> None:
    timed = [_time(old, new, fmt) for _ in range(runs)]
    ms = sorted(each[0] for each in timed)
    print(
        f"{label}: {(len(old) + len(new)) / 1024:.0f} KiB pair, {ms[0]:.0f}-{ms[-1]:.0f} ms, "
        f"{timed[0][1]}, {timed[0][3]} entries"
    )


def _json_pair(old: object, new: object) -> tuple[bytes, bytes]:
    return json.dumps(old).encode(), json.dumps(new).encode()


def _budgets() -> None:
    """The shapes each budget is measured on, worst first."""

    # The densest text each slow parser reads at its bound: a list of one-digit integers
    # beside a changed scalar, so the answer is small and the parse is the cost.
    nodes = structured_projection._MAX_YAML_NODES  # pyright: ignore[reportPrivateUsage]
    for count in (nodes - 4, 4_000):
        flow = "a: [" + ", ".join("1" for _ in range(count)) + "]\nb: "
        block = "a:\n" + "".join("- 1\n" for _ in range(count)) + "b: "
        _report(
            f"YAML flow list of {count:,}", f"{flow}1\n".encode(), f"{flow}2\n".encode(), "yaml"
        )
        _report(
            f"YAML block list of {count:,}", f"{block}1\n".encode(), f"{block}2\n".encode(), "yaml"
        )
    items = JSONC_MAX_BYTES // 4 - 16
    jsonc = '{"a": [' + ",".join("1" for _ in range(items)) + '], "b": '
    _report(
        f"JSONC list of {items:,} a side", f"{jsonc}1,}}".encode(), f"{jsonc}2,}}".encode(), "json"
    )
    for size in (1_000, 2_000):
        _report(
            f"lists of {size:,} drawn from ten values (A1)",
            *_json_pair([i % 10 for i in range(size)], [(i * 7) % 10 for i in range(size)]),
            "json",
        )
    bits = [(i * 7919) % 2 for i in range(1_000)]
    flipped = [1 - bits[0], *bits[1:-1], 1 - bits[-1]]
    _report("1,000 bits, the first and last flipped", *_json_pair(bits, flipped), "json")
    inner = [i % 10 for i in range(19_900)]
    for depth in (15, 60):
        old: object = [inner, 1]
        new: object = [inner, 2]
        for _ in range(depth):
            old, new = [old, 0], [new, 0]
        _report(f"a list of 19,900 nested {depth} deep (C3)", *_json_pair(old, new), "json")
    _report(
        "two lists of 19,999, one item changed",
        *_json_pair([1] * 19_999, [1] * 19_998 + [2]),
        "json",
    )
    ten = list(range(10_000))
    _report(
        "a list of 10,000, one item changed", *_json_pair(ten, [*ten[:10], -1, *ten[11:]]), "json"
    )
    _report(
        "4,000 items, nothing shared",
        *_json_pair(list(range(4_000)), [-i - 1 for i in range(4_000)]),
        "json",
    )
    maps = [{f"k{j}": i * 1_000 + j for j in range(40)} for i in range(100)]
    halves = [{f"k{j}": (i * 1_000 + j if j % 2 else -1) for j in range(40)} for i in range(100)]
    _report("100 mappings of 40 keys, each half changed", *_json_pair(maps, halves), "json")


if __name__ == "__main__":
    main()
