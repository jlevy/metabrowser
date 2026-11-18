"""Bounded YAML: the one loader front matter, and the classifier's YAML prefix, parse through.

A Markdown file's front matter is untrusted on a served GitHub mirror and in a folder
served with ``--untrusted``, and little better in a downloaded repository served as a
trusted folder. YAML aliases make it a compression format: seven anchors, each a list
of nine aliases to the one before, are 310 bytes of YAML and 9**7 values written out.
Two parts of a YAML load can expand them. The constructor does, while building the
value: a ``<<`` merge key copies every entry of the mappings it names into the mapping
that holds it, a sequence used as a key is copied at each use, and a duplicated key
writes the values on both sides of it into the error message. And so does anything that
walks the built value as a tree: the JSON copy ``/api/file`` sends, the response
encoder, KPress's Frontmatter disclosure (``str()`` of each value), a cache key.

So :func:`load_bounded_yaml` composes the document first, which is linear in its text,
and measures the composed node graph before anything is constructed: the size of the
value written out without its aliases, counted once per node and multiplied by the
uses of a shared node, never expanded. Past the budget, or for a node that contains
itself, it refuses, and the constructor never runs. Then it constructs, and makes the
one copy every consumer reads: a plain, JSON-safe tree of ``dict``, ``list``, ``str``,
``int``, finite ``float``, ``bool``, and ``None``, with ``str`` keys and no shared or
cyclic references. Every failure, of the bound or of the parse, raises
:class:`BoundedYamlError` (:class:`FrontmatterError` for front matter), whose text is a
reason of at most :data:`YAML_ERROR_MAX_CHARS` characters that never carries expanded
content.

The loader owns its YAML instance: ruamel's pure-Python safe loader, so nothing another
package registers on ``frontmatter_format``'s shared instances changes what it builds,
and the C parser, whose nesting and cost were never measured here, is never used. It
also never writes a warning: ruamel warns on every reused anchor name and on some YAML
1.1 floats, with the author's text in each message, and Python keeps every distinct
message for the life of the process.
"""

from __future__ import annotations

import base64
import datetime as _dt
import json
import math
import sys
from collections.abc import Mapping
from typing import Any, ClassVar, Final

from ruamel.yaml import YAML
from ruamel.yaml.composer import Composer
from ruamel.yaml.constructor import DuplicateKeyError, SafeConstructor
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

# The most front-matter text any path reads: a plain file's prefix, a compressed
# Markdown file's decoded prefix, and a Git blob's prefix all stop here, so an opening
# fence that is never closed costs one bounded read. It predates the expansion bound
# below; its cost is the parse, which is linear in the text and runs on a worker thread.
#
# Measured 2026-11-17 on an Apple M1 Pro, macOS 26.5.2, CPython 3.14.7 with the GIL, at a
# load average of 16 to 22, with `devtools/frontmatter_bound_benchmark.py`:
# - Alias-free front matter at this bound loads in 0.07 s to 2.9 s, depending on its
#   shape; the dearest found are flow lists of one-digit integers and of one-character
#   strings (11 and 9 us a byte). The load is linear in the text: 0.55, 1.13, and 2.29 s
#   at a quarter, a half, and all of the bound.
# - Off the event loop is not off the GIL: while one such load ran on a worker thread
#   for 2.3 s, a plain `/api/file` that answers in 0.7 ms alone answered in 206 ms
#   (median of 12). The bound is kept, not lowered, because it sets what front matter a
#   file may have; the largest front matter among the 178 tracked Markdown files of this
#   repository that have one is 10,138 bytes. Parsing untrusted front matter in a child
#   process under a deadline is the follow-up that removes this cost.
FRONTMATTER_MAX_BYTES: Final = 256 * 1024

# The most front matter a load may build and copy once every YAML alias is written out.
# It is spent in two places, in the same unit, so either bounds its own work:
# - On the composed node graph, before construction: each node counts one, and each
#   scalar adds the length of its text in the document, after escapes. A merge key's
#   mappings count into each mapping that merges them, and a node used twice counts
#   twice.
# - In the copy, after construction: each value and key counts one, each string and
#   string key adds its length in characters, and each number, date, and binary value
#   adds the length of its JSON text. The encoded response can be larger than the count:
#   JSON escapes a control character in six bytes, and UTF-8 takes up to four a
#   character.
#
# Measured 2026-11-17 (machine as above) with `devtools/frontmatter_bound_benchmark.py`:
# - Alias-free front matter at FRONTMATTER_MAX_BYTES writes out to at most 1.17 times
#   its bytes on the node graph, and in the copy to at most 3.85 times (a flow list of
#   mappings of the keys `1e15` to `9e15`, each `1000000000000000.0` in JSON; the limit
#   of that family is 4.0, and distinct keys run out before it). So four times the byte
#   bound refuses no front matter that has no aliases.
# - Refusal on the node graph takes 1 to 2 ms in all, at any depth of aliases, merge
#   keys, or aliases under a duplicated key (3 to 12 levels of nine), and costs 3% more
#   than the compose for the shapes quadratic in their text (one mapping merged into
#   many, a list used as the key of many mappings).
# - Accepted front matter near this bound loads in at most 0.27 s (the dearest shape
#   found merges one mapping of 200 keys into many), encodes in at most 12 ms to at
#   most 6.3 MB of JSON (a string of NUL escapes), and renders in KPress in at most
#   38 ms; all below the load of the text FRONTMATTER_MAX_BYTES already admits.
# - Without this bound, seven levels of nine aliases copied in 1.06 s and encoded in
#   0.25 s to 39 MB of JSON, and eight levels of nine merges took 5.3 s in the
#   constructor (review A on #542, same machine); each further level multiplies all
#   three by nine.
FRONTMATTER_MAX_EXPANDED_SIZE: Final = 4 * FRONTMATTER_MAX_BYTES

# The longest reason a refusal carries, in characters. ruamel's messages quote the
# document (an unknown tag of any length, a key), and a reason is shown in a header
# badge and in KPress's diagnostics. Measured 2026-11-17 with
# `devtools/frontmatter_bound_benchmark.py` over fifteen kinds of malformed front
# matter (unclosed flows and quotes, bad indents, tabs, escapes, unknown tags, undefined
# aliases, duplicate keys, two documents, bad merges): the reasons run from 46 to 364
# characters, so none of them is cut.
YAML_ERROR_MAX_CHARS: Final = 500


class BoundedYamlError(ValueError):
    """YAML that :func:`load_bounded_yaml` does not answer as a value; its text is why."""

    subject: ClassVar[str] = "YAML"
    parse_failure: ClassVar[str] = "Error parsing YAML"


class FrontmatterError(BoundedYamlError):
    """Front matter that is present but not shown as metadata; its text is the reason."""

    subject: ClassVar[str] = "Front matter"
    parse_failure: ClassVar[str] = "Error parsing YAML metadata"


class _ExpansionBudgetError(Exception):
    """The document passed its budget, written out without its aliases."""


class _CycleError(Exception):
    """An alias names a mapping or sequence that contains it."""


def load_frontmatter_yaml(text: str) -> object:
    """Parse front-matter YAML into its bounded, JSON-safe value.

    Returns ``None`` for YAML that holds no value (empty, or only comments), and the
    converted value otherwise -- a caller decides whether a non-mapping is an error.
    Raises :class:`FrontmatterError` for text longer than :data:`FRONTMATTER_MAX_BYTES`,
    and for everything :func:`load_bounded_yaml` refuses.
    """

    if len(text) > FRONTMATTER_MAX_BYTES:
        raise FrontmatterError(
            f"Front matter not parsed: it is longer than {FRONTMATTER_MAX_BYTES // 1024} KiB"
        )
    return _load(text, FRONTMATTER_MAX_EXPANDED_SIZE, FrontmatterError)


def load_bounded_yaml(text: str, *, max_expanded_size: int) -> object:
    """Parse one YAML document into its bounded, JSON-safe value.

    *max_expanded_size* bounds the document written out without its aliases, in the
    unit :data:`FRONTMATTER_MAX_EXPANDED_SIZE` describes; four times the caller's byte
    bound on *text* refuses nothing that has no aliases. Raises
    :class:`BoundedYamlError` for YAML that does not parse, nesting too deep for the
    parser, an alias that contains itself, a duplicated key, and a document past
    *max_expanded_size*.
    """

    return _load(text, max_expanded_size, BoundedYamlError)


def unclosed_frontmatter_error(limit: int = FRONTMATTER_MAX_BYTES) -> FrontmatterError:
    """The reason for an opening fence whose closing one is not within *limit* bytes."""

    return FrontmatterError(
        f"Front matter not parsed: its closing delimiter is not within the first "
        f"{limit // 1024} KiB"
    )


def _load(text: str, budget: int, error: type[BoundedYamlError]) -> object:
    try:
        parsed: object = _new_yaml(budget).load(text)
    except _ExpansionBudgetError as exc:
        raise error(_expansion_reason(error, budget)) from exc
    except _CycleError as exc:
        raise error(_cycle_reason(error)) from exc
    except RecursionError as exc:
        raise error(f"{error.subject} not parsed: it nests too deeply") from exc
    # Any other failure of the parser means the text is not parsed. ruamel's
    # constructors raise more than YAMLError for scalars Python refuses: ValueError and
    # TypeError, KeyError (`!!bool maybe`), IndexError (`!!int ''`), OverflowError (a
    # timestamp past year 9999), and AssertionError (a repeated `!!omap` key, a
    # `%YAML 1.31` directive).
    except Exception as exc:
        raise error(_parse_reason(error, exc)) from exc
    return _json_safe(parsed, budget, error)


def json_safe_frontmatter(value: object) -> object:
    """Copy a parsed front-matter value as a bounded, JSON-safe tree.

    The work is bounded by :data:`FRONTMATTER_MAX_EXPANDED_SIZE` whatever *value*
    shares: every step of the walk spends budget, so it stops there. Raises
    :class:`FrontmatterError` past that, or for a value that contains itself.
    """

    return _json_safe(value, FRONTMATTER_MAX_EXPANDED_SIZE, FrontmatterError)


def _json_safe(value: object, budget: int, error: type[BoundedYamlError]) -> object:
    walk = _Walk(budget)
    try:
        return walk.value(value)
    except _ExpansionBudgetError as exc:
        raise error(_expansion_reason(error, budget)) from exc
    except _CycleError as exc:
        raise error(_cycle_reason(error)) from exc
    except RecursionError as exc:
        raise error(f"{error.subject} not parsed: it nests too deeply") from exc


def _expansion_reason(error: type[BoundedYamlError], budget: int) -> str:
    return (
        f"{error.subject} not parsed: written out without its YAML aliases it is larger "
        f"than {budget:,} characters"
    )


def _cycle_reason(error: type[BoundedYamlError]) -> str:
    return f"{error.subject} not parsed: a YAML alias refers to a value that contains it"


def _parse_reason(error: type[BoundedYamlError], exc: Exception) -> str:
    detail = str(exc)
    if not isinstance(exc, YAMLError):
        detail = f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__
    reason = f"{error.parse_failure}: {detail}"
    if len(reason) > YAML_ERROR_MAX_CHARS:
        reason = reason[: YAML_ERROR_MAX_CHARS - 1] + "…"
    # A message can quote a value an escape built, lone surrogates included.
    return _encodable(reason)


def _new_yaml(budget: int) -> YAML:
    # A YAML instance holds the state of one parse, and loads run on worker threads,
    # so each load gets its own; building one takes about 50 us.
    yaml = YAML(typ="safe", pure=True)
    yaml.Composer = _Composer
    yaml.Constructor = _BoundedConstructor
    constructor: _BoundedConstructor = yaml.constructor
    constructor.max_expanded_size = budget
    return yaml


class _Composer(Composer):
    """ruamel's composer, without the warning it writes for each reused anchor name."""

    def __init__(self, loader: Any = None) -> None:
        super().__init__(loader)
        self.warn_double_anchors = False


class _BoundedConstructor(SafeConstructor):
    """ruamel's safe constructor, run only on a composed document within its budget."""

    max_expanded_size: int = FRONTMATTER_MAX_EXPANDED_SIZE

    def get_single_data(self) -> Any:
        node = self.composer.get_single_node()
        if node is None:
            return None
        _written_out_size(node, self.max_expanded_size)
        return self.construct_document(node)

    def check_mapping_key(
        self, node: Any, key_node: Any, mapping: Any, key: Any, value: Any
    ) -> bool:
        # ruamel's own message writes out the value on both sides of the duplicate.
        if key not in mapping:
            return True
        raise DuplicateKeyError(
            "while constructing a mapping",
            node.start_mark,
            f"found duplicate key {_key_preview(key)}",
            key_node.start_mark,
        )

    def check_set_key(self, node: Any, key_node: Any, setting: Any, key: Any) -> None:
        if key in setting:
            raise DuplicateKeyError(
                "while constructing a set",
                node.start_mark,
                f"found duplicate key {_key_preview(key)}",
                key_node.start_mark,
            )

    def construct_yaml_float(self, node: Any) -> float:
        # Under `%YAML 1.1` ruamel warns for an exponent without a dot in the mantissa
        # (`1e3`) and then reads it as Python does; read it here without the warning.
        if self.resolver.processing_version != (1, 2):
            text = self.construct_scalar(node).replace("_", "").lower()
            if "e" in text and ":" not in text:
                sign = -1 if text[:1] == "-" else 1
                return sign * float(text[1:] if text[:1] in {"-", "+"} else text)
        result: float = super().construct_yaml_float(node)
        return result


_BoundedConstructor.add_constructor(
    "tag:yaml.org,2002:float", _BoundedConstructor.construct_yaml_float
)

# Longest key text a duplicate-key reason quotes, before it is cut.
_KEY_PREVIEW_CHARS: Final = 80


def _key_preview(key: object) -> str:
    if isinstance(key, str):
        text = key if len(key) <= _KEY_PREVIEW_CHARS else key[:_KEY_PREVIEW_CHARS] + "…"
        return json.dumps(text, ensure_ascii=False)
    if (
        key is None
        or isinstance(key, bool | float)
        or (isinstance(key, int) and key.bit_length() < 64)
    ):
        return repr(key)
    return f"of type {type(key).__name__}"


def _written_out_size(root: Node, budget: int) -> int:
    """The size of *root* written out without its aliases, never past *budget*.

    Each node is visited once and its size remembered, so a node that many aliases
    share costs its children once and its size once per use. Raises
    :class:`_ExpansionBudgetError` as soon as one node's size passes *budget* (the root's
    is at least as large), and :class:`_CycleError` for a node that contains itself.
    The walk keeps its own stack, so its depth is not Python's.
    """

    sizes: dict[int, int] = {}
    # Nodes whose children are being sized: the path from the root to the current node.
    active: set[int] = set()
    stack: list[tuple[Node, bool]] = [(root, False)]
    while stack:
        node, children_sized = stack.pop()
        marker = id(node)
        if children_sized:
            active.discard(marker)
            size = 1 + sum(sizes[id(child)] for child in _children(node))
        elif marker in sizes:
            continue
        elif isinstance(node, ScalarNode):
            size = 1 + len(node.value)
        else:
            if marker in active:
                raise _CycleError
            active.add(marker)
            stack.append((node, True))
            for child in _children(node):
                child_marker = id(child)
                if child_marker in active:
                    raise _CycleError
                if child_marker not in sizes:
                    stack.append((child, False))
            continue
        if size > budget:
            raise _ExpansionBudgetError
        sizes[marker] = size
    return sizes[id(root)]


def _children(node: Node) -> list[Node]:
    if isinstance(node, MappingNode):
        # A merge key's value is an entry like any other: the mappings it names are
        # written out into this one.
        return [part for pair in node.value for part in pair]
    if isinstance(node, SequenceNode):
        return list(node.value)
    return []


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
            return _encodable(value)
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
        # over-counts them by about a tenth: right for the budget, not for the limit.
        digits = value.bit_length() // 3 + 1
        self._spend(digits)
        limit = sys.get_int_max_str_digits()
        if limit and digits > limit:
            try:
                # Refuses past the limit before it converts, so this costs little.
                str(value)
            except ValueError:
                # A hexadecimal literal can build an integer past the decimal digit
                # limit, which the JSON encoder would refuse; its hexadecimal text has
                # no limit.
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
            return _encodable(key)
        converted = self.value(key)
        if isinstance(converted, str):
            return converted
        # JSON's own spelling of a scalar key (``true``, ``null``, ``2``), and a
        # sequence key (YAML ``? [a, b]``) as its JSON text; both were spent above.
        return json.dumps(converted, ensure_ascii=False)


def _encodable(text: str) -> str:
    """*text* with each unpaired surrogate replaced by U+FFFD, so it encodes as UTF-8.

    A YAML escape (``"\\ud800"``) builds a lone surrogate, which the response encoder
    refuses. Two escapes that make a surrogate pair become the character they name.
    """

    if text.isascii():
        return text
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    return text


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
