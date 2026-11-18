"""Measure the cost shape behind the front-matter bounds in ``frontmatter_yaml``.

An exploration tool, not a release gate: it prints machine-dependent timings beside
the structural facts that set ``FRONTMATTER_MAX_EXPANDED_SIZE``. Three questions:

1. How big alias-free front matter gets once written out, against its bytes, for the
   shapes whose JSON text outgrows their YAML, at ``FRONTMATTER_MAX_BYTES``.
2. What the copy, the JSON encoding, and KPress's render cost per character of
   written-out front matter, at sizes in 2x steps up to past the bound.
3. That an alias bomb at any depth is refused after bounded work.

Run with ``uv --config-file uv.toml run --frozen python -m devtools.frontmatter_bound_benchmark``.
"""

from __future__ import annotations

import argparse
import json
import string
import time
from collections.abc import Callable
from typing import Any, cast

from frontmatter_format import from_yaml_string

from metabrowser import kpress_adapter
from metabrowser.frontmatter_yaml import (
    FRONTMATTER_MAX_BYTES,
    FRONTMATTER_MAX_EXPANDED_SIZE,
    FrontmatterError,
    _Walk,  # pyright: ignore[reportPrivateUsage]
    load_frontmatter_yaml,
)


def _best_ms(run: Callable[[], object], repeat: int) -> float:
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        run()
        best = min(best, time.perf_counter() - start)
    return best * 1e3


def _expanded_size(value: object) -> int:
    walk = _Walk(1 << 62)
    walk.value(value)
    return (1 << 62) - walk._remaining  # pyright: ignore[reportPrivateUsage]


def _flow(item: str, size: int) -> str:
    count = (size - 8) // (len(item) + 1)
    return "x: [" + ",".join([item] * count) + "]\n"


def alias_free_ratios() -> None:
    shapes = {
        "short strings": _flow("a", FRONTMATTER_MAX_BYTES),
        "empty strings": _flow('""', FRONTMATTER_MAX_BYTES),
        "short floats": _flow(".1", FRONTMATTER_MAX_BYTES),
        # 1e15 is the float whose JSON text most outgrows its YAML: 1000000000000000.0.
        "exponent floats": _flow("1e15", FRONTMATTER_MAX_BYTES),
        "dates": _flow("2001-12-14", FRONTMATTER_MAX_BYTES),
        "timestamps": _flow("2001-12-14t21:59:43.10-05:00", FRONTMATTER_MAX_BYTES),
        "keys": "".join(f"k{i}: {i}\n" for i in range(FRONTMATTER_MAX_BYTES // 16)),
    }
    print("alias-free front matter near FRONTMATTER_MAX_BYTES")
    for name, text in shapes.items():
        size = _expanded_size(from_yaml_string(text))
        print(f"  {name:<17} bytes={len(text):>7} expanded={size:>7} ratio={size / len(text):.2f}")


def _shared_string_bomb(expanded: int) -> str:
    # One 1,000-character anchor written out `count` times: the expanded size grows
    # with `count` while the parse stays a few kilobytes. The cheap shape: few nodes.
    count = max(1, expanded // 1_002)
    return f"a: &a {'y' * 1_000}\nb: [{', '.join(['*a'] * count)}]\n"


def _small_node_bomb(expanded: int) -> str:
    # An anchor of 100 three-letter strings written out `count` times. The dear shape:
    # every character of it is in a node of four.
    count = max(1, expanded // 401)
    return f"a: &a [{', '.join(['lol'] * 100)}]\nb: [{', '.join(['*a'] * count)}]\n"


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


def cost_per_character(repeat: int) -> None:
    print("copy, JSON encoding, and KPress render per written-out character")
    sizes = [FRONTMATTER_MAX_EXPANDED_SIZE // 8 * 2**step for step in range(5)]
    shapes = {"long strings": _shared_string_bomb, "small nodes": _small_node_bomb}
    for (shape, build), expanded in ((item, size) for item in shapes.items() for size in sizes):
        parsed = from_yaml_string(build(expanded))
        size = _expanded_size(parsed)
        copy = _Walk(1 << 62).value(parsed)
        copy_ms = _best_ms(lambda parsed=parsed: _Walk(1 << 62).value(parsed), repeat)
        encode_ms = _best_ms(lambda copy=copy: json.dumps(copy, ensure_ascii=False), repeat)
        json_bytes = len(json.dumps(copy, ensure_ascii=False).encode())
        frontmatter = cast("dict[str, Any]", copy)
        render_ms = _best_ms(lambda frontmatter=frontmatter: _render(frontmatter), repeat)
        within = "within" if size <= FRONTMATTER_MAX_EXPANDED_SIZE else "past"
        print(
            f"  {shape:<12} expanded={size:>8} ({within} bound) copy_ms={copy_ms:6.1f} "
            f"encode_ms={encode_ms:6.1f} kpress_ms={render_ms:6.1f} json_bytes={json_bytes:>9} "
            f"ns_per_char={(copy_ms + encode_ms) * 1e6 / size:5.1f}"
        )


def _nested_bomb(levels: int, width: int = 9) -> str:
    names = string.ascii_lowercase
    lines = [f"{names[0]}: &{names[0]} [{', '.join(['lol'] * width)}]"]
    for level in range(1, levels):
        refs = ", ".join([f"*{names[level - 1]}"] * width)
        lines.append(f"{names[level]}: &{names[level]} [{refs}]")
    return "\n".join(lines) + "\n"


def bombs(repeat: int) -> None:
    print("nested alias bombs through load_frontmatter_yaml")
    for levels in range(3, 13):
        text = _nested_bomb(levels)

        def load(text: str = text) -> str:
            try:
                load_frontmatter_yaml(text)
            except FrontmatterError:
                return "refused"
            return "accepted"

        outcome = load()
        load_ms = _best_ms(load, repeat)
        print(f"  levels={levels:>2} yaml_bytes={len(text):>4} {outcome:<8} load_ms={load_ms:6.1f}")
    # Each level is nine times the last; the largest accepted shows where the bound sits.
    print(f"  (five levels write out to {_expanded_size(from_yaml_string(_nested_bomb(5)))})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure the cost shape behind the front-matter bounds."
    )
    parser.add_argument("--repeat", type=int, default=3, help="runs per timing; best is kept")
    args = parser.parse_args()
    alias_free_ratios()
    cost_per_character(args.repeat)
    bombs(args.repeat)


if __name__ == "__main__":
    main()
