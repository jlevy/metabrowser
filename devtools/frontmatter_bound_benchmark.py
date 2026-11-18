"""Measure the cost shape behind the front-matter bounds in ``frontmatter_yaml``.

An exploration tool, not a release gate: it prints machine-dependent timings beside
the structural facts that set ``FRONTMATTER_MAX_BYTES``, ``FRONTMATTER_MAX_EXPANDED_SIZE``,
``YAML_MAX_DEPTH``, and ``YAML_ERROR_MAX_CHARS``. Load times are CPU time, the best of
``--repeat`` runs, so a loaded machine changes them less than it changes wall time.
Five questions:

1. How long alias-free front matter takes to load at ``FRONTMATTER_MAX_BYTES``, whether
   that is linear in its bytes, and how big it gets once written out, on the composed
   node graph and once built, for the shapes whose JSON text outgrows their YAML and
   the shapes that cost the parser most (deep flow nesting, colliding integer keys).
2. That front matter past the expansion budget or the depth bound is refused before it
   is built, after bounded work, for aliases, merge keys, nested inline merges,
   sequence keys, duplicated keys, and deep flow nesting.
3. What accepted front matter near the budget costs to build, encode, and render, and
   what it holds in memory.
4. What a load at the byte bound on a worker thread costs a plain request beside it.
5. How long the reasons for malformed front matter are, against ``YAML_ERROR_MAX_CHARS``,
   and how large and how deep the front matter and YAML in this repository are.

Run with ``uv --config-file uv.toml run --frozen python -m devtools.frontmatter_bound_benchmark``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import string
import subprocess
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

from ruamel.yaml.nodes import Node

from metabrowser import kpress_adapter, server
from metabrowser.frontmatter_yaml import (
    FRONTMATTER_MAX_BYTES,
    YAML_MAX_DEPTH,
    FrontmatterError,
    _Builder,  # pyright: ignore[reportPrivateUsage]
    _children,  # pyright: ignore[reportPrivateUsage]
    _new_yaml,  # pyright: ignore[reportPrivateUsage]
    _written_out_size,  # pyright: ignore[reportPrivateUsage]
    load_frontmatter_yaml,
)

_UNBOUNDED = 1 << 62


def _best_ms(run: Callable[[], object], repeat: int) -> float:
    """The least CPU time of *repeat* runs, in milliseconds."""

    best = float("inf")
    for _ in range(repeat):
        start = time.process_time()
        run()
        best = min(best, time.process_time() - start)
    return best * 1e3


def _peak_mib(run: Callable[[], object]) -> float:
    """The most memory Python allocated during one run, in MiB."""

    tracemalloc.start()
    try:
        run()
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak / (1 << 20)


def _compose(text: str) -> Node:
    yaml = _new_yaml(_UNBOUNDED, keep_last=False)
    node: Node = yaml.compose(text)  # pyright: ignore[reportUnknownMemberType]
    return node


def _copy_size(text: str) -> int:
    """What building *text* spends of an unbounded budget."""

    yaml = _new_yaml(_UNBOUNDED, keep_last=False)
    node: Node = yaml.compose(text)  # pyright: ignore[reportUnknownMemberType]
    builder = _Builder(yaml.constructor, _UNBOUNDED, keep_last=False)
    builder.value(node)
    return _UNBOUNDED - builder.remaining


def _graph_size(text: str) -> int:
    return _written_out_size(_compose(text), _UNBOUNDED)


def _flow(item: str, size: int) -> str:
    count = (size - 8) // (len(item) + 1)
    return "x: [" + ",".join([item] * count) + "]\n"


def _lines(line: Callable[[int], str], size: int) -> str:
    parts: list[str] = []
    total = 0
    index = 0
    while total + len(line(index)) <= size:
        parts.append(line(index))
        total += len(parts[-1])
        index += 1
    return "".join(parts)


# A flow mapping of the keys 1e15 to 9e15 and no values.
_NINE_FLOAT_KEYS = "{" + ",".join(f"{digit}e15" for digit in range(1, 10)) + "}"

# CPython hashes an integer modulo this prime, unseeded, so its multiples share a hash.
_HASH_MODULUS = (1 << 61) - 1


def _flow_sawtooth(depth: int, size: int) -> str:
    """Flow sequences *depth* deep, rising and falling on one line (review C, C3)."""

    unit = "[" * depth + "]" * depth + ","
    return "x: [" + unit * ((size - 6) // len(unit)) + "]\n"


def _integer_keys(size: int, step: int) -> str:
    keys: list[str] = []
    total = 3
    index = 1
    while total + len(f"{index * step},") <= size:
        keys.append(f"{index * step}")
        total += len(keys[-1]) + 1
        index += 1
    return "{" + ",".join(keys) + "}\n"


# The deepest a flow sequence under `x:` may nest: the mapping, the outer list, and the
# innermost scalar are three of YAML_MAX_DEPTH's levels.
_DEEPEST_FLOW = YAML_MAX_DEPTH - 3

ALIAS_FREE_SHAPES: dict[str, Callable[[int], str]] = {
    "one-character strings": lambda size: _flow("a", size),
    "three-letter strings": lambda size: _flow("lol", size),
    "empty strings": lambda size: _flow('""', size),
    "integers": lambda size: _flow("7", size),
    "short floats": lambda size: _flow(".1", size),
    # `1e15` is five bytes of YAML and `1000000000000000.0` once built: the densest
    # alias-free shape found.
    "exponent floats": lambda size: _flow("1e15", size),
    "nine float keys": lambda size: _flow(_NINE_FLOAT_KEYS, size),
    "dates": lambda size: _flow("2001-12-14", size),
    "timestamps": lambda size: _flow("2001-12-14t21:59:43.10-05:00", size),
    "NUL escapes": lambda size: 'x: "' + "\\0" * ((size - 7) // 2) + '"\n',
    "key-value lines": lambda size: _lines(lambda i: f"k{i}: {i}\n", size),
    "block one-key mappings": lambda size: "x:\n" + _lines(lambda i: f"- k{i}: v\n", size - 3),
    f"flow sequences {_DEEPEST_FLOW} deep": lambda size: _flow_sawtooth(_DEEPEST_FLOW, size),
    "flow sequences 16 deep": lambda size: _flow_sawtooth(16, size),
    # Review C, C4: integer keys that share one hash, and a control of distinct hashes.
    "colliding integer keys": lambda size: _integer_keys(size, _HASH_MODULUS),
    "distinct integer keys": lambda size: _integer_keys(size, _HASH_MODULUS + 2),
}


def alias_free(repeat: int) -> None:
    print("alias-free front matter at FRONTMATTER_MAX_BYTES")
    for name, build in ALIAS_FREE_SHAPES.items():
        text = build(FRONTMATTER_MAX_BYTES)
        load_frontmatter_yaml(text)
        copy = _copy_size(text)
        graph = _graph_size(text)
        load_ms = _best_ms(lambda text=text: load_frontmatter_yaml(text), repeat)
        print(
            f"  {name:<24} bytes={len(text):>7} cpu_ms={load_ms:7.1f} "
            f"us_per_byte={load_ms * 1e3 / len(text):5.2f} graph_ratio={graph / len(text):.2f} "
            f"copy_ratio={copy / len(text):.3f}"
        )
    dearest = "one-character strings"
    print(f"  linearity of the load ({dearest})")
    for fraction in (4, 2, 1):
        text = ALIAS_FREE_SHAPES[dearest](FRONTMATTER_MAX_BYTES // fraction)
        load_ms = _best_ms(lambda text=text: load_frontmatter_yaml(text), repeat)
        print(f"    bytes={len(text):>7} cpu_ms={load_ms:7.1f}")


def alias_bomb(levels: int, width: int = 9) -> str:
    names = string.ascii_lowercase
    lines = [f"{names[0]}: &{names[0]} [{', '.join(['lol'] * width)}]"]
    for level in range(1, levels):
        refs = ", ".join([f"*{names[level - 1]}"] * width)
        lines.append(f"{names[level]}: &{names[level]} [{refs}]")
    return "\n".join(lines) + "\n"


def merge_bomb(levels: int, width: int = 9) -> str:
    names = string.ascii_lowercase
    lines = [f"{names[0]}: &{names[0]} {{k: v}}"]
    for level in range(1, levels):
        refs = ", ".join([f"*{names[level - 1]}"] * width)
        lines.append(f"{names[level]}: &{names[level]} {{<<: [{refs}]}}")
    return "\n".join(lines) + "\n"


def duplicate_key_bomb(levels: int) -> str:
    top = string.ascii_lowercase[levels - 1]
    return alias_bomb(levels) + f"z:\n  d: *{top}\n  d: *{top}\n"


def merged_into_many(keys: int, mappings: int) -> str:
    lines = ["b: &b"] + [f"  k{i}: v" for i in range(keys)] + ["items:"]
    return "\n".join(lines + ["- <<: *b"] * mappings) + "\n"


def sequence_key_bomb(items: int, uses: int) -> str:
    head = f"k: &k [{', '.join(['x'] * items)}]\n"
    return head + "".join(f"m{i}: {{? *k : v}}\n" for i in range(uses))


def nested_inline_merges(depth: int, fan1: int = 100, fan2: int = 3_300) -> str:
    """One mapping near the budget wrapped in *depth* anchored inline merges (C2)."""

    head = "c: &c {'': ''}\n"
    head += "d: &d {<<: [" + ",".join(["*c"] * fan1) + "]}\n"
    inner = "{<<: [" + ",".join(["*d"] * fan2) + "]}"
    opens = "".join(f"{{<<: &n{index} " for index in range(depth))
    return head + "x: " + opens + inner + "}" * depth + "\n"


def long_tag_timestamp(tag_length: int, uses: int) -> str:
    """`!!timestamp` over one long-tagged scalar aliased many times (review C, C1)."""

    return f"z: !!timestamp [&a !<{'t' * tag_length}> v, {','.join(['*a'] * uses)}]\n"


def _outcome(text: str) -> str:
    try:
        load_frontmatter_yaml(text)
    except FrontmatterError as exc:
        return f"refused ({len(str(exc))} characters)"
    return "accepted"


def over_budget(repeat: int) -> None:
    print("front matter past the budget through load_frontmatter_yaml")
    shapes: dict[str, Callable[[int], str]] = {
        "aliases": alias_bomb,
        "merge keys": merge_bomb,
        "duplicate key": duplicate_key_bomb,
    }
    for name, build in shapes.items():
        for levels in (3, 5, 7, 9, 12):
            text = build(levels)
            load_ms = _best_ms(lambda text=text: _outcome(text), repeat)
            print(
                f"  {name:<14} levels={levels:>2} bytes={len(text):>5} {_outcome(text):<26} "
                f"cpu_ms={load_ms:6.1f}"
            )
    quadratic = {
        "merged into many 1000x1000": merged_into_many(1_000, 1_000),
        "merged into many 2000x2000": merged_into_many(2_000, 2_000),
        "sequence key 20000x4000": sequence_key_bomb(20_000, 4_000),
    }
    for name, text in quadratic.items():
        load_ms = _best_ms(lambda text=text: _outcome(text), repeat)
        compose_ms = _best_ms(lambda text=text: _compose(text), repeat)
        print(
            f"  {name:<27} bytes={len(text):>6} {_outcome(text):<26} cpu_ms={load_ms:6.1f} "
            f"compose_cpu_ms={compose_ms:6.1f}"
        )
    deep = {
        "nested inline merges 400 deep": nested_inline_merges(400),
        "flow sequences 400 deep": _flow_sawtooth(400, FRONTMATTER_MAX_BYTES),
        "timestamp over a long tag 64000x64000": long_tag_timestamp(64_000, 64_000),
    }
    for name, text in deep.items():
        load_ms = _best_ms(lambda text=text: _outcome(text), repeat)
        peak = _peak_mib(lambda text=text: _outcome(text))
        print(
            f"  {name:<37} bytes={len(text):>6} {_outcome(text):<26} cpu_ms={load_ms:6.1f} "
            f"peak_mib={peak:6.1f}"
        )


def _render(frontmatter: dict[str, Any]) -> object:
    return kpress_adapter.render_kpress_view(
        source_text="body\n",
        source_path="bench.md",
        kind="markdown",
        view="document",
        ext=".md",
        # KPress keeps renders by this; a new one each time measures a render.
        mtime_hash=str(time.perf_counter_ns()),
        size=5,
        frontmatter=frontmatter,
    )


def _largest_accepted(build: Callable[[int], str]) -> str:
    """The largest *build(n)* the loader accepts, by bisection on n."""

    low, high = 1, 1
    while _outcome(build(high)) == "accepted":
        low, high = high, high * 2
    while high - low > 1:
        middle = (low + high) // 2
        low, high = (middle, high) if _outcome(build(middle)) == "accepted" else (low, middle)
    return build(low)


# A thousand NUL escapes: two bytes of YAML each, and six of JSON (`\u0000`).
_ESCAPES = "\\0" * 1_000


def near_budget(repeat: int) -> None:
    print("accepted front matter near FRONTMATTER_MAX_EXPANDED_SIZE")
    shapes: dict[str, Callable[[int], str]] = {
        "one mapping merged into many": lambda n: merged_into_many(200, n),
        "small nodes aliased": lambda n: (
            f"a: &a [{', '.join(['lol'] * 100)}]\nb: [{', '.join(['*a'] * n)}]\n"
        ),
        "long string aliased": lambda n: f"a: &a {'y' * 1_000}\nb: [{', '.join(['*a'] * n)}]\n",
        "escapes aliased": lambda n: f'a: &a "{_ESCAPES}"\nb: [{", ".join(["*a"] * n)}]\n',
        f"inline merges {_DEEPEST_FLOW - 1} deep": lambda n: nested_inline_merges(
            _DEEPEST_FLOW - 1, fan2=n
        ),
    }
    for name, build in shapes.items():
        text = _largest_accepted(build)
        parsed = load_frontmatter_yaml(text)
        load_ms = _best_ms(lambda text=text: load_frontmatter_yaml(text), repeat)
        peak = _peak_mib(lambda text=text: load_frontmatter_yaml(text))
        encode_ms = _best_ms(lambda parsed=parsed: json.dumps(parsed, ensure_ascii=False), repeat)
        json_bytes = len(json.dumps(parsed, ensure_ascii=False).encode())
        frontmatter = cast("dict[str, Any]", parsed)
        render_ms = _best_ms(lambda frontmatter=frontmatter: _render(frontmatter), repeat)
        print(
            f"  {name:<29} bytes={len(text):>6} graph={_graph_size(text):>8} "
            f"built={_copy_size(text):>8} cpu_ms={load_ms:6.1f} peak_mib={peak:5.1f} "
            f"encode_ms={encode_ms:5.1f} json_bytes={json_bytes:>8} kpress_ms={render_ms:5.1f}"
        )


def _request(path: str) -> Any:
    request = Mock(spec=["query_params", "headers", "method", "path_params"])
    request.query_params = {"path": path}
    request.headers = {}
    request.method = "GET"
    request.path_params = {}
    return request


async def _contention(samples: int) -> tuple[list[float], list[float], float]:
    root = Path(tempfile.mkdtemp(prefix="frontmatter-bench-"))
    (root / "plain.md").write_text("---\ntitle: Plain\n---\nbody\n", encoding="utf-8")
    server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]

    async def plain_ms() -> float:
        start = time.perf_counter()
        await server.api_file(_request("plain.md"))
        return (time.perf_counter() - start) * 1e3

    alone = [await plain_ms() for _ in range(samples)]
    text = ALIAS_FREE_SHAPES["one-character strings"](FRONTMATTER_MAX_BYTES)
    start = time.perf_counter()
    load = asyncio.create_task(asyncio.to_thread(load_frontmatter_yaml, text))
    beside: list[float] = []
    while not load.done():
        beside.append(await plain_ms())
    await load
    return alone, beside, (time.perf_counter() - start) * 1e3


def contention(samples: int) -> None:
    print("a plain /api/file while a worker thread loads front matter at the byte bound")
    alone, beside, load_ms = asyncio.run(_contention(samples))
    print(
        f"  alone: median_ms={statistics.median(alone):6.1f} max_ms={max(alone):6.1f}\n"
        f"  beside a {load_ms:.0f} ms load: requests={len(beside)} "
        f"median_ms={statistics.median(beside):6.1f} max_ms={max(beside):6.1f}"
    )


MALFORMED = {
    "unclosed flow": "a: [1, 2\nb: 3\n",
    "bad indent": "a:\n  b: 1\n c: 2\n",
    "tab": "a:\n\tb: 1\n",
    "colon in a plain scalar": "a: b: c\n",
    "duplicate key": "title: one\ntitle: two\n",
    "unknown tag": "a: !foo 1\n",
    "undefined alias": "a: *nope\n",
    "bad escape": 'a: "\\q"\n',
    "unclosed quote": 'a: "abc\nb: 1\n',
    "long line": "a: " + "x" * 500 + ": y\n",
    "block in a flow": "a: {b: c\n  d: e\n",
    "two documents": "a: 1\n---\nb: 2\n",
    "duplicate merge key": "a: &a {x: 1}\nb: {<<: *a, <<: *a}\n",
    "merge of a scalar": "a: {<<: 1}\n",
    "unknown boolean": "a: !!bool maybe\n",
    "timestamp on a list": long_tag_timestamp(30_000, 30_000),
}


def reasons() -> None:
    print("reasons for malformed front matter, against YAML_ERROR_MAX_CHARS")
    for name, text in MALFORMED.items():
        peak = _peak_mib(lambda text=text: _outcome(text))
        print(f"  {name:<24} {_outcome(text):<26} peak_mib={peak:6.1f}")


def _depth(node: Node, level: int, seen: set[int]) -> int:
    """How deep *node* nests, as the composer counts it: an alias is a leaf where used."""

    if id(node) in seen:
        return level
    seen.add(id(node))
    return max([level, *(_depth(child, level + 1, seen) for child in _children(node))])


def _nesting(text: str) -> int | None:
    try:
        return _depth(_compose(text), 1, set())
    # A file that does not parse, or nests past YAML_MAX_DEPTH, has no depth to report.
    except Exception:
        return None


def survey() -> None:
    print("front matter in this repository's tracked Markdown files")
    root = Path(__file__).resolve().parent.parent
    listed = subprocess.run(
        ["git", "ls-files", "-z", "*.md"], cwd=root, capture_output=True, check=True
    ).stdout
    sizes: list[int] = []
    depths: list[int] = []
    for name in filter(None, listed.decode().split("\0")):
        head = (root / name).read_bytes()[: FRONTMATTER_MAX_BYTES + 1]
        if not head.startswith(b"---\n"):
            continue
        end = head.find(b"\n---\n", 3)
        if end != -1:
            sizes.append(end - 3)
            found = _nesting(head[4 : end + 1].decode("utf-8", "replace"))
            if found is not None:
                depths.append(found)
    print(
        f"  files={len(sizes)} largest_bytes={max(sizes, default=0)} "
        f"deepest={max(depths, default=0)}"
    )
    print("the first 16 KiB of this repository's tracked YAML files")
    listed = subprocess.run(
        ["git", "ls-files", "-z", "*.yaml", "*.yml"], cwd=root, capture_output=True, check=True
    ).stdout
    depths = []
    for name in filter(None, listed.decode().split("\0")):
        found = _nesting((root / name).read_bytes()[: 16 * 1024].decode("utf-8", "replace"))
        if found is not None:
            depths.append(found)
    print(f"  files={len(depths)} deepest={max(depths, default=0)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure the cost shape behind the front-matter bounds."
    )
    parser.add_argument("--repeat", type=int, default=3, help="runs per timing; best is kept")
    parser.add_argument(
        "--samples", type=int, default=20, help="plain requests timed alone, for contention"
    )
    args = parser.parse_args()
    alias_free(args.repeat)
    over_budget(args.repeat)
    near_budget(args.repeat)
    contention(args.samples)
    reasons()
    survey()


if __name__ == "__main__":
    main()
