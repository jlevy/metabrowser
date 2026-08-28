"""The session schema for golden transcripts: what is normalized, what is kept.

`tbd guidelines golden-testing-guidelines` asks for one stated list of stable
and unstable fields rather than a `touch -t` in one fixture and a regex in
another. This module is that list.

The bias is deliberate: normalize only what a fixture cannot pin. Hiding a
value the fixture controls removes the coverage the golden existed to provide,
so revisions and mtimes stay real by default and only sandbox-dependent paths
are rewritten unconditionally.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_PLACEHOLDER = "[ROOT]"
HOME_PLACEHOLDER = "[HOME]"
MTIME_PLACEHOLDER = "[MTIME]"

# Filesystem timestamps, which a fixture normally pins with `touch -t`. A clone
# into the cache cannot pin them, which is the case `normalize_mtimes` serves.
MTIME_FIELDS: tuple[str, ...] = ("mtime", "mtime_hash")


@dataclass(frozen=True, slots=True)
class NormalizeContext:
    """Which sandbox paths to rewrite, and whether mtimes can be pinned."""

    root: Path | None = None
    home: Path | None = None
    normalize_mtimes: bool = False

    def prefixes(self) -> tuple[tuple[str, str], ...]:
        """Path prefixes to rewrite, longest first so the most specific wins."""

        pairs: list[tuple[str, str]] = []
        if self.root is not None:
            pairs.append((str(self.root), ROOT_PLACEHOLDER))
        if self.home is not None:
            pairs.append((str(self.home), HOME_PLACEHOLDER))
        return tuple(sorted(pairs, key=lambda pair: len(pair[0]), reverse=True))


def normalize_text(text: str, ctx: NormalizeContext) -> str:
    """Rewrite sandbox-dependent paths in free text such as console output."""

    for prefix, placeholder in ctx.prefixes():
        text = text.replace(prefix, placeholder)
    return text


def normalize_payload(value: Any, ctx: NormalizeContext) -> Any:
    """Rewrite unstable values throughout a decoded JSON payload."""

    return _normalize(value, ctx, key=None)


def _normalize(value: Any, ctx: NormalizeContext, *, key: str | None) -> Any:
    if ctx.normalize_mtimes and key in MTIME_FIELDS:
        return MTIME_PLACEHOLDER
    if isinstance(value, str):
        return normalize_text(value, ctx)
    if isinstance(value, Mapping):
        return {item_key: _normalize(item, ctx, key=item_key) for item_key, item in value.items()}
    # str is a Sequence, so it is handled above; bytes carry no sandbox paths.
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_normalize(item, ctx, key=key) for item in value]
    return value


def describe_schema() -> str:
    """Render the schema as a table, so the rules are readable beside the goldens."""

    lines = [
        "| Value | Becomes | Why |",
        "| --- | --- | --- |",
        f"| Absolute path under the served root | `{ROOT_PLACEHOLDER}` | the sandbox path varies |",
        f"| Absolute path under the application home | `{HOME_PLACEHOLDER}` | the cache home varies |",
        f"| `{'`, `'.join(MTIME_FIELDS)}` | `{MTIME_PLACEHOLDER}` |"
        " only when the fixture cannot pin them |",
        "| Git revisions | kept | fixture repositories build deterministically |",
    ]
    return "\n".join(lines)
