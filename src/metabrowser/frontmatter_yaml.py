"""Bounded YAML front matter: the one loader every front-matter path parses through.

A Markdown file's front matter is untrusted on a served GitHub mirror and in a folder
served with ``--untrusted``, and little better in a downloaded repository served as a
trusted folder. YAML aliases make it a compression format: seven anchors, each a list
of nine aliases to the one before, are 310 bytes of YAML and 9**7 values written out.
The safe loader keeps an alias as a second reference to one Python object, so parsing
stays linear in the text; the cost arrives when anything walks the value as a tree --
the JSON copy ``/api/file`` sends, the response encoder, KPress's Frontmatter
disclosure (``str()`` of each value), a cache key.

So the bound is on the tree a walk sees, and :func:`load_frontmatter_yaml` enforces it
while making the one copy every consumer reads: a plain, JSON-safe tree of ``dict``,
``list``, ``str``, ``int``, finite ``float``, ``bool``, and ``None``, with ``str`` keys
and no shared or cyclic references. Front matter past a bound raises
:class:`FrontmatterError`, whose text is the reason a caller shows in place of the
metadata; the file itself still reads as text.
"""

from __future__ import annotations

import base64
import datetime as _dt
import json
import math
import sys
from collections.abc import Mapping
from typing import Any, Final

from frontmatter_format import from_yaml_string
from ruamel.yaml.error import YAMLError

# The most front-matter text any path reads: a plain file's prefix, a compressed
# Markdown file's decoded prefix, and a Git blob's prefix all stop here, so an opening
# fence that is never closed costs one bounded read. It predates the expansion bound
# below and has no measurement of its own. Parsing is linear in it: ruamel takes about
# 0.9 s for a 256 KiB flow list of short strings and 0.55 s for 256 KiB of `key: value`
# lines (`devtools/frontmatter_bound_benchmark.py`, machine as below), which is why
# every caller parses off the event loop. The largest front matter among the 173
# Markdown files in this repository that have one is 10,138 bytes.
FRONTMATTER_MAX_BYTES: Final = 256 * 1024

# The most front matter a walk may see once every YAML alias is written out, in
# characters: each mapping, sequence, key, and scalar counts one, and each string, key,
# number, date, and binary value adds the length of its JSON text.
#
# Measured 2026-11-17 on an Apple M1 Pro, macOS 26.5.2, CPython 3.14, with
# `devtools/frontmatter_bound_benchmark.py`:
# - Alias-free front matter at FRONTMATTER_MAX_BYTES writes out to at most 3.8 times
#   its bytes (a flow list of `1e15`, whose JSON text is `1000000000000000.0`) and
#   otherwise to at most 1.33 times (`.1`), so four times the byte bound refuses no
#   front matter that has no aliases.
# - The copy is linear in the written-out size: about 65 ns a character when every
#   node is a short string, 3 ns when the strings are long. At this bound the dear
#   shape copies in about 63 ms, encodes in 10 ms to 1.8 MB of JSON, and renders in
#   KPress in 31 ms, all below the 0.9 s parse the byte bound already admits. An alias
#   block of any depth is refused after about 110 ms.
# - Without this bound, seven levels of nine aliases copied in 1.06 s and encoded in
#   0.25 s to 39 MB of JSON, and each further level multiplied both by nine.
FRONTMATTER_MAX_EXPANDED_SIZE: Final = 4 * FRONTMATTER_MAX_BYTES


class FrontmatterError(ValueError):
    """Front matter that is present but not shown as metadata; its text is the reason."""


class _ExpansionBudgetError(Exception):
    """The walk passed FRONTMATTER_MAX_EXPANDED_SIZE."""


class _CycleError(Exception):
    """An alias names a mapping or sequence that contains it."""


def load_frontmatter_yaml(text: str) -> object:
    """Parse front-matter YAML into its bounded, JSON-safe value.

    Returns ``None`` for YAML that holds no value (empty, or only comments), and the
    converted value otherwise -- a caller decides whether a non-mapping is an error.
    Raises :class:`FrontmatterError` for text longer than :data:`FRONTMATTER_MAX_BYTES`,
    YAML that does not parse, nesting too deep for the parser, an alias that contains
    itself, and a value larger than :data:`FRONTMATTER_MAX_EXPANDED_SIZE` written out.
    """

    if len(text) > FRONTMATTER_MAX_BYTES:
        raise FrontmatterError(
            f"Front matter not parsed: it is longer than {FRONTMATTER_MAX_BYTES // 1024} KiB"
        )
    try:
        parsed: object = from_yaml_string(text)
    except RecursionError as exc:
        raise FrontmatterError("Front matter not parsed: it nests too deeply") from exc
    # ValueError and TypeError are what ruamel's constructors raise for a scalar Python
    # refuses, such as an integer past the digit limit or an impossible date.
    except (YAMLError, ValueError, TypeError) as exc:
        raise FrontmatterError(f"Error parsing YAML metadata: {exc}") from exc
    return json_safe_frontmatter(parsed)


def json_safe_frontmatter(value: object) -> object:
    """Copy a parsed front-matter value as a bounded, JSON-safe tree.

    The work is bounded by :data:`FRONTMATTER_MAX_EXPANDED_SIZE` whatever *value*
    shares: every step of the walk spends budget, so it stops there. Raises
    :class:`FrontmatterError` past that, or for a value that contains itself.
    """

    walk = _Walk(FRONTMATTER_MAX_EXPANDED_SIZE)
    try:
        return walk.value(value)
    except _ExpansionBudgetError as exc:
        raise FrontmatterError(
            "Front matter not parsed: written out without its YAML aliases it is larger "
            f"than {FRONTMATTER_MAX_EXPANDED_SIZE:,} characters"
        ) from exc
    except _CycleError as exc:
        raise FrontmatterError(
            "Front matter not parsed: a YAML alias refers to a value that contains it"
        ) from exc
    except RecursionError as exc:
        raise FrontmatterError("Front matter not parsed: it nests too deeply") from exc


class _Walk:
    __slots__ = ("_active", "_remaining")

    def __init__(self, budget: int) -> None:
        self._remaining = budget
        # Containers on the path from the root to the node being copied: meeting one
        # again is a cycle, which would otherwise spend the budget one level at a time.
        self._active: set[int] = set()

    def _spend(self, size: int) -> None:
        self._remaining -= size
        if self._remaining < 0:
            raise _ExpansionBudgetError

    def value(self, value: object) -> object:
        self._spend(1)
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, str):
            self._spend(len(value))
            return value
        if isinstance(value, int):
            return self._int(value)
        if isinstance(value, float):
            text = _float_text(value)
            self._spend(len(text))
            return value if math.isfinite(value) else text
        if isinstance(value, Mapping | list | tuple | set | frozenset):
            return self._container(value)
        text = _scalar_text(value)
        self._spend(len(text))
        return text

    def _int(self, value: int) -> int | str:
        # A decimal digit holds about 3.3 bits, so this never under-counts the digits and
        # over-counts them by about a tenth.
        digits = value.bit_length() // 3 + 1
        self._spend(digits)
        limit = sys.get_int_max_str_digits()
        if limit and digits > limit:
            # A hexadecimal literal can build an integer past the decimal digit limit,
            # which the JSON encoder would refuse; its hexadecimal text has no limit.
            return hex(value)
        return value

    def _container(
        self,
        value: Mapping[Any, Any] | list[Any] | tuple[Any, ...] | set[Any] | frozenset[Any],
    ) -> object:
        marker = id(value)
        if marker in self._active:
            raise _CycleError
        self._active.add(marker)
        try:
            if isinstance(value, Mapping):
                # Keys that coincide once written as text keep the last value, as a JSON
                # parser does with a repeated key.
                return {self._key(key): self.value(item) for key, item in value.items()}
            items = [self.value(item) for item in value]
            if isinstance(value, set | frozenset):
                # A YAML !!set is unordered; sorting its text makes the copy the same
                # on every load.
                items.sort(key=lambda item: json.dumps(item, sort_keys=True))
            return items
        finally:
            self._active.discard(marker)

    def _key(self, key: object) -> str:
        if isinstance(key, str):
            self._spend(1 + len(key))
            return key
        converted = self.value(key)
        if isinstance(converted, str):
            return converted
        # JSON's own spelling of a scalar key (``true``, ``null``, ``2``), and a
        # sequence key (YAML ``? [a, b]``) as its JSON text; both were spent above.
        return json.dumps(converted, ensure_ascii=False)


def _float_text(value: float) -> str:
    if math.isnan(value):
        return ".nan"
    if math.isinf(value):
        return ".inf" if value > 0 else "-.inf"
    return repr(value)


def _scalar_text(value: object) -> str:
    """Text for a scalar JSON has no type for: ISO 8601 for a date, base64 for binary."""

    if isinstance(value, _dt.date | _dt.time):
        return value.isoformat()
    if isinstance(value, bytes | bytearray):
        return base64.b64encode(value).decode("ascii")
    # The safe loader builds nothing else; name the type rather than call its str(),
    # whose cost nothing here bounds.
    return f"<{type(value).__name__}>"
