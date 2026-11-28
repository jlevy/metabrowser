"""Bounded YAML for front matter, classification and native structured values.

A Markdown file's front matter is untrusted on a served GitHub mirror and in a folder
served with ``--untrusted``, and little better in a downloaded repository served as a
trusted folder. YAML aliases make it a compression format: seven anchors, each a list
of nine aliases to the one before, are 310 bytes of YAML and 9**7 values written out.
Anything that builds or walks the value as a tree pays for that: a YAML constructor (a
``<<`` merge key copies every entry it names into the mapping that holds it, nesting
multiplies the copies, and ruamel writes composed nodes into some error messages), the
JSON copy ``/api/file`` sends, the response encoder, KPress's Frontmatter disclosure,
and a cache key.

So ruamel only reads the text. :func:`load_bounded_yaml` composes the document, which
is linear in its text and refused past :data:`YAML_MAX_DEPTH` levels of nesting, and
measures the composed node graph: the size of the value written out without its
aliases, counted once per node and multiplied by the uses of a shared node, never
expanded. Past the budget, or for a node that contains itself, it refuses. Then the
loader builds the value from the node graph itself, spending the same budget on every
node, key, and merged entry it writes out: ruamel's constructor builds nothing but a
scalar, so no merge, sequence key, or message of its constructor is ever trusted with
a bound. The value is a plain, JSON-safe tree of ``dict``, ``list``, ``str``, ``int``,
finite ``float``, ``bool``, and ``None``, with ``str`` keys and no shared or cyclic
references.

Every failure, of the bound or of the parse, raises :class:`BoundedYamlError`
(:class:`FrontmatterError` for front matter), whose text is a reason of at most
:data:`YAML_ERROR_MAX_CHARS` characters, and whose ``over_budget`` says a budget refused
the document rather than its syntax. A refusal while building names a line and the
kind of node, never a scalar's text or a tag; a syntax error is ruamel's own message,
whose quotes of the document are a line each.

The loader owns its YAML instance: ruamel's pure-Python safe loader, so nothing another
package registers on ``frontmatter_format``'s shared instances changes what it reads,
and the C parser, whose nesting and cost were never measured here, is never used. It
reads YAML 1.2 only, and never writes a warning: ruamel warns on every reused anchor
name, with the author's text in each message, and Python keeps every distinct message
for the life of the process.

:func:`load_bounded_native_yaml_documents` shares the composer and graph measurement
with the JSON-safe loader. It then uses ruamel's safe constructor to preserve native
values, including those in streams with YAML version directives.
"""

from __future__ import annotations

import base64
import datetime as _dt
import json
import math
import sys
from typing import Any, ClassVar, Final

from ruamel.yaml import YAML
from ruamel.yaml.composer import Composer, MaxDepthExceededError
from ruamel.yaml.constructor import SafeConstructor
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

# The most front-matter text any path reads: a plain file's prefix, a compressed
# Markdown file's decoded prefix, and a Git blob's prefix all stop here, so an opening
# fence that is never closed costs one bounded read. It predates the expansion bound
# below; its cost is the parse, which runs on a worker thread.
#
# Measured 2026-11-18 on an Apple M1 Pro, macOS 26.5.2, CPython 3.14.7 with the GIL, at a
# load average near 10, with `devtools/frontmatter_bound_benchmark.py` (CPU time):
# - Alias-free front matter at this bound loads in 0.07 s to 5.5 s, depending on its
#   shape. The dearest is a flow list that rises to YAML_MAX_DEPTH, holds 440 items
#   there, and falls, repeated on one line (5.5 s, 21 us a byte); then flow sequences
#   that rise and fall to that depth (4.0 s), and flat flow lists of one-digit integers
#   and of one-character strings (2.9 and 2.3 s). The load is linear in the text: 0.55,
#   1.15, and 2.33 s at a quarter, a half, and all of the bound for the strings.
# - ruamel's scanner walks one pending simple key for each open flow level on every
#   token, so nesting costs a factor of its depth: 400 levels took 16 s (review C on
#   #542). YAML_MAX_DEPTH stops that at 1.9 times the flat integers' cost; 16 levels cost
#   what the flat lists do.
# - Integer keys chosen to share one hash load as fast as distinct ones (0.42 s each),
#   because keys are compared by their text, whose hash is seeded.
# - Off the event loop is not off the GIL: while one 2.3 s load ran on a worker thread,
#   a plain `/api/file` that answers in 0.7 ms alone answered in 217 ms (median of 12).
#   The bound is kept, not lowered, because it sets what front matter a file may have;
#   the largest front matter among the 185 tracked Markdown files of this repository
#   that have one is 10,138 bytes. Parsing untrusted front matter in a child process
#   under a deadline (bead mb-2y6a) is the follow-up that removes this cost.
FRONTMATTER_MAX_BYTES: Final = 256 * 1024

# The most front matter a load may build once every YAML alias is written out. It is
# spent in two places, in the same unit, so either bounds its own work:
# - On the composed node graph, before anything is built: each node counts one, and
#   each scalar adds the length of its text in the document, after escapes. A merge
#   key's mappings count into each mapping that merges them, and a node used twice
#   counts twice.
# - While building: each value and key written out counts one, each string and string
#   key adds its length in characters, and each number, date, and binary value adds the
#   length of its JSON text; resolving a merge key costs one more for each mapping it
#   names and each entry it visits, twice (once for which value wins, once for the
#   order of the keys). The encoded response can be larger than the count: JSON escapes
#   a control character in six bytes, and UTF-8 takes up to four a character.
#
# Measured 2026-11-18 (machine as above) with `devtools/frontmatter_bound_benchmark.py`:
# - Alias-free front matter at FRONTMATTER_MAX_BYTES writes out to at most 1.17 times
#   its bytes on the node graph, and once built to at most 3.99995 times: one key that
#   is a flow list of `1e15`, five bytes of YAML an item and twenty characters of the
#   key's JSON text, builds to 1,048,563, 13 units inside this budget (review D on #542).
#   Flow mappings of the keys `1e15` to `9e15` build to 3.85 times, and a flow list of
#   `1e15` to 3.80. So four times the byte bound refuses no front matter that has no
#   aliases, with almost no margin; a change to what a key's text or a node costs has to
#   rerun this.
# - Refusal on the node graph takes 1 to 2 ms in all, at any depth of aliases, merge
#   keys, or aliases under a duplicated key (7 to 12 levels of nine), and costs 2 to 6%
#   more than the compose for the shapes quadratic in their text (one mapping merged
#   into many, a list used as the key of many mappings).
# - Accepted front matter near this budget loads in at most 0.91 s (a mapping that merges
#   one empty mapping, aliased: 3.7 KB) and holds at most 85.5 MiB while it does (lists
#   of one-key mappings of an empty mapping, aliased: 4.1 KB), because the budget counts
#   one for an empty mapping or list, which costs Python about 60 bytes and a
#   microsecond to build; review D on #542 found these shapes. Empty mappings aliased
#   take 0.84 s and 72.8 MiB, and one mapping of 200 keys merged into many 0.17 s and
#   4.9 MiB; 60 levels of inline merges around 330,000 merged entries load in 39 ms and
#   0.3 MiB. A value encodes in at most 46 ms to at most 6.3 MB of JSON (a string of NUL
#   escapes), and renders in KPress in at most 96 ms. All of it is linear in the budget,
#   and below the load of the text FRONTMATTER_MAX_BYTES already admits.
# - Without the loader's own build, seven levels of nine aliases copied in 1.06 s to
#   39 MB of JSON, eight levels of nine merges took 5.3 s in ruamel's constructor, 480
#   levels of inline merges held 2.5 GB, and `!!timestamp` over one long-tagged alias
#   built a 2.6 GB message from 120 KB (reviews A and C on #542, same machine); here
#   the last is refused in 0.31 s with 2.6 MiB at 120 KB, and 0.65 s with 5.7 MiB at
#   the byte bound.
FRONTMATTER_MAX_EXPANDED_SIZE: Final = 4 * FRONTMATTER_MAX_BYTES

# The deepest nesting a document and its value may have: the top-level node is one, and
# each node inside a collection is one more, a scalar included. ruamel's composer checks
# it on the text, where an alias is a leaf, and the builder on the value, through every
# alias, so a chain of aliases cannot nest the value deeper than the text may be.
#
# Measured 2026-11-18 with `devtools/frontmatter_bound_benchmark.py` (machine as above):
# the deepest of the 185 tracked Markdown files' front matter here nests 6 levels, and
# the deepest of the 17 tracked YAML files 9, so 64 refuses no real document found. At
# this bound flow lists on one line cost up to 1.9 times a flat list
# (FRONTMATTER_MAX_BYTES records the times), and 400 levels are refused in 34 ms at the
# byte bound. Because the builder checks it too, an alias chain that nests the value one
# level past it is refused, its recursion stays within a few hundred frames, and a nesting
# refusal no longer depends on how deep the caller's stack already is: before, a chain
# of 300 aliases was accepted from a shallow stack and refused 420 frames deeper, and a
# chain to Python's recursion limit called a valid scalar invalid (review D on #542).
YAML_MAX_DEPTH: Final = 64

# The longest reason a refusal carries, in characters. ruamel's syntax messages quote
# the document a line at a time, and a reason is shown in a header badge and in KPress's
# diagnostics. Measured 2026-11-17 with `devtools/frontmatter_bound_benchmark.py` over
# sixteen kinds of malformed front matter (unclosed flows and quotes, bad indents, tabs,
# escapes, unknown tags, undefined aliases, duplicate keys, two documents, bad merges, a
# timestamp tag on a list): the reasons run from 55 to 251 characters, so none of them
# is cut.
YAML_ERROR_MAX_CHARS: Final = 500


class BoundedYamlError(ValueError):
    """YAML that :func:`load_bounded_yaml` does not answer as a value; its text is why.

    *over_budget* is true when a budget refused it (its expansion, its nesting, or the
    nodes a caller allowed), and false when it does not parse or holds what the loader
    does not read.
    """

    subject: ClassVar[str] = "YAML"
    parse_failure: ClassVar[str] = "Error parsing YAML"

    def __init__(self, reason: str, *, over_budget: bool = False) -> None:
        super().__init__(reason)
        self.over_budget = over_budget


class TypedText(str):
    """A key or scalar a typed load wrote as text, and the type it had in the YAML.

    ``origin`` names that type (``int``, ``date``, ``bytes``, ``float`` and so on), which
    tells the key ``1`` from the key ``"1"`` and a date from the string that spells it,
    where the plain value cannot. Everywhere else it is the ``str`` it holds, and it
    encodes as one.
    """

    origin: str

    def __new__(cls, text: str, origin: str) -> TypedText:
        made = super().__new__(cls, text)
        made.origin = origin
        return made


class TypedList(list[object]):
    """A ``!!set`` a typed load wrote as its sorted members; its ``origin`` is ``set``."""

    origin: str = "set"


class FrontmatterError(BoundedYamlError):
    """Front matter that is present but not shown as metadata; its text is the reason."""

    subject: ClassVar[str] = "Front matter"
    parse_failure: ClassVar[str] = "Error parsing YAML metadata"


# What a page says of front matter that is present and not shown: the tooltip of the
# file header's "Frontmatter error" badge and the notice KPress draws above the document.
# The reason, a FrontmatterError's text, is the answer's `frontmatter_error_detail`
# (docs/design-system-messages.md).
FRONTMATTER_ERROR_MESSAGE: Final = "The frontmatter could not be read."


def shown_frontmatter_error(reason: str | None) -> str | None:
    """The reader's sentence for front matter refused for *reason*, or None for none."""
    return None if reason is None else FRONTMATTER_ERROR_MESSAGE


def frontmatter_error_fields(reason: str | None) -> dict[str, str]:
    """An answer's fields for front matter refused for *reason*: the reader's sentence as
    ``frontmatter_error`` and the reason as ``frontmatter_error_detail``, or none."""
    if reason is None:
        return {}
    return {"frontmatter_error": FRONTMATTER_ERROR_MESSAGE, "frontmatter_error_detail": reason}


class _ExpansionBudgetError(Exception):
    """The document passed its budget, written out without its aliases."""


class _NodeBudgetError(Exception):
    """The text composed to more nodes than the caller allowed."""


class _CycleError(Exception):
    """An alias names a mapping or sequence that contains it."""


class _DepthError(Exception):
    """The value, built through its aliases, nests past YAML_MAX_DEPTH."""


class _VersionError(Exception):
    """The document declares a YAML version other than 1.2; its text is the version."""


class _NodeError(Exception):
    """A node the loader does not build; its text names the line and the kind of node."""

    def __init__(self, node: Node, problem: str) -> None:
        super().__init__(f"line {node.start_mark.line + 1}: {problem}")


def load_frontmatter_yaml(
    text: str, *, max_nodes: int | None = None, typed: bool = False
) -> object:
    """Parse front-matter YAML into its bounded, JSON-safe value.

    Returns ``None`` for YAML that holds no value (empty, or only comments), and the
    converted value otherwise -- a caller decides whether a non-mapping is an error.
    Raises :class:`FrontmatterError` for text longer than :data:`FRONTMATTER_MAX_BYTES`,
    and for everything :func:`load_bounded_yaml` refuses. *max_nodes* and *typed* are
    as :func:`load_bounded_yaml_documents` takes them.
    """

    if len(text) > FRONTMATTER_MAX_BYTES:
        raise FrontmatterError(
            f"Front matter not parsed: it is longer than {FRONTMATTER_MAX_BYTES // 1024} KiB"
        )
    return _load(
        text,
        FRONTMATTER_MAX_EXPANDED_SIZE,
        FrontmatterError,
        keep_last=False,
        max_nodes=max_nodes,
        typed=typed,
    )


def load_bounded_yaml(
    text: str, *, max_expanded_size: int, keep_last_duplicate: bool = False
) -> object:
    """Parse one YAML 1.2 document into its bounded, JSON-safe value.

    *max_expanded_size* bounds the document written out without its aliases, in the
    unit :data:`FRONTMATTER_MAX_EXPANDED_SIZE` describes; four times the caller's byte
    bound on *text* refuses nothing that has no aliases. A key that appears twice in
    one mapping is refused, or, with *keep_last_duplicate*, keeps its last value. Keys
    are compared by their JSON text, so ``1`` and ``"1"`` are the same key. Raises
    :class:`BoundedYamlError` for YAML that does not parse, declares another version,
    nests past :data:`YAML_MAX_DEPTH`, has an alias that contains itself, a tag or a
    scalar the loader does not read, or is larger than *max_expanded_size*.
    """

    return _load(text, max_expanded_size, BoundedYamlError, keep_last=keep_last_duplicate)


def load_bounded_yaml_documents(
    text: str, *, max_expanded_size: int, max_nodes: int | None = None, typed: bool = False
) -> list[object]:
    """Parse a YAML 1.2 stream into the bounded, JSON-safe value of each document.

    As :func:`load_bounded_yaml`, with the documents sharing *max_expanded_size*, an empty
    document read as ``None``, and a repeated key refused. *max_nodes*, when given, bounds
    the nodes composed from the text, aliases counting one each, so a caller can bound the
    parse itself: its cost follows the nodes, not the bytes (a flow list of one-digit
    integers composes a node every three bytes). Past it, the load stops where it is and
    raises :class:`BoundedYamlError` with ``over_budget``. *typed* writes each key and
    scalar that is not already a string as :class:`TypedText`, and a set as
    :class:`TypedList`, so a caller comparing two documents can tell what the plain value
    writes alike.
    """

    return _load(
        text,
        max_expanded_size,
        BoundedYamlError,
        keep_last=False,
        stream=True,
        max_nodes=max_nodes,
        typed=typed,
    )


def load_bounded_native_yaml_documents(
    text: str, *, max_expanded_size: int, max_nodes: int
) -> list[object]:
    """Read native safe-loader values for the record grid, sizing each graph first."""
    yaml = YAML(typ="safe", pure=True)
    yaml.Composer = _Composer
    yaml.max_depth = YAML_MAX_DEPTH
    yaml.composer.nodes_left = max_nodes
    remaining = max_expanded_size
    documents: list[object] = []
    try:
        for node in yaml.compose_all(text):
            remaining -= _written_out_size(node, remaining, native_value=True)
            documents.append(yaml.constructor.construct_document(node))
    except _ExpansionBudgetError as exc:
        raise BoundedYamlError(
            f"YAML written out without its aliases is larger than {max_expanded_size:,} characters",
            over_budget=True,
        ) from exc
    except _NodeBudgetError as exc:
        raise BoundedYamlError(
            f"YAML holds more than {max_nodes:,} values", over_budget=True
        ) from exc
    except _CycleError as exc:
        raise BoundedYamlError("A YAML alias refers to a value that contains it") from exc
    except (_DepthError, MaxDepthExceededError) as exc:
        raise BoundedYamlError(
            f"YAML nests past {YAML_MAX_DEPTH} levels", over_budget=True
        ) from exc
    except BoundedYamlError:
        raise
    except Exception as exc:
        raise BoundedYamlError(_parse_reason(BoundedYamlError, exc)) from exc
    return documents


def json_safe_scalar(value: object) -> object:
    """*value*, a scalar a YAML or JSON parser built, as the loader writes one into its value.

    A string with an unpaired surrogate has U+FFFD in its place, an integer past the
    decimal digit limit is its hexadecimal text, a float that is not finite is YAML's
    text for it, a date or time is ISO-8601, and binary is base64; ``None``, a boolean,
    and every other string and number are themselves.
    """

    return _json_scalar(value)[0]


def unclosed_frontmatter_error(limit: int = FRONTMATTER_MAX_BYTES) -> FrontmatterError:
    """The reason for an opening fence whose closing one is not within *limit* bytes."""

    return FrontmatterError(
        f"Front matter not parsed: its closing delimiter is not within the first "
        f"{limit // 1024} KiB"
    )


def _load(
    text: str,
    budget: int,
    error: type[BoundedYamlError],
    *,
    keep_last: bool,
    stream: bool = False,
    max_nodes: int | None = None,
    typed: bool = False,
) -> Any:
    try:
        yaml = _new_yaml(budget, keep_last=keep_last, max_nodes=max_nodes, typed=typed)
        parsed: object = list(yaml.load_all(text)) if stream else yaml.load(text)
    except _ExpansionBudgetError as exc:
        raise error(
            f"{error.subject} not parsed: written out without its YAML aliases it is larger "
            f"than {budget:,} characters",
            over_budget=True,
        ) from exc
    except _NodeBudgetError as exc:
        raise error(
            f"{error.subject} not parsed: it holds more than {max_nodes:,} values",
            over_budget=True,
        ) from exc
    except _CycleError as exc:
        raise error(
            f"{error.subject} not parsed: a YAML alias refers to a value that contains it"
        ) from exc
    except (MaxDepthExceededError, _DepthError, RecursionError) as exc:
        raise error(
            f"{error.subject} not parsed: it nests too deeply (more than {YAML_MAX_DEPTH} levels)",
            over_budget=True,
        ) from exc
    except _VersionError as exc:
        raise error(
            f"{error.subject} not parsed: it declares YAML {exc}, and only YAML 1.2 is read"
        ) from exc
    except _NodeError as exc:
        raise error(f"{error.parse_failure}: {exc}") from exc
    # Any other failure of the parser means the text is not parsed: a syntax error, an
    # undefined alias, two documents, or an exception ruamel's parser raises that is not
    # a YAMLError (an AssertionError for a `%YAML 1.31` directive).
    except Exception as exc:
        raise error(_parse_reason(error, exc)) from exc
    return parsed


def _parse_reason(error: type[BoundedYamlError], exc: Exception) -> str:
    detail = str(exc)
    if not isinstance(exc, YAMLError):
        detail = f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__
    reason = f"{error.parse_failure}: {detail}"
    if len(reason) > YAML_ERROR_MAX_CHARS:
        reason = reason[: YAML_ERROR_MAX_CHARS - 1] + "…"
    # A message can quote the document, lone surrogates included.
    return _encodable(reason)


def _new_yaml(
    budget: int, *, keep_last: bool, max_nodes: int | None = None, typed: bool = False
) -> YAML:
    # A YAML instance holds the state of one parse, and loads run on worker threads,
    # so each load gets its own; building one takes about 50 us.
    yaml = YAML(typ="safe", pure=True)
    yaml.Composer = _Composer
    yaml.Constructor = _BoundedConstructor
    yaml.max_depth = YAML_MAX_DEPTH
    constructor: _BoundedConstructor = yaml.constructor
    constructor.max_expanded_size = budget
    constructor.keep_last_duplicate = keep_last
    constructor.typed = typed
    composer: _Composer = yaml.composer
    composer.nodes_left = max_nodes
    return yaml


class _Composer(Composer):
    """ruamel's composer, without the warning it writes for each reused anchor name, and
    with the nodes it may compose, when a caller bounds them."""

    def __init__(self, loader: Any = None) -> None:
        super().__init__(loader)
        self.warn_double_anchors = False
        self.nodes_left: int | None = None

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.nodes_left is not None:
            self.nodes_left -= 1
            if self.nodes_left < 0:
                raise _NodeBudgetError
        return super().compose_node(parent, index)


class _BoundedConstructor(SafeConstructor):
    """ruamel's safe constructor, used for scalars only, after the document is measured."""

    max_expanded_size: int = FRONTMATTER_MAX_EXPANDED_SIZE
    keep_last_duplicate: bool = False
    typed: bool = False

    def get_single_data(self) -> Any:
        node = self.composer.get_single_node()
        if node is None:
            return None
        return self._bounded(node)

    def get_data(self) -> Any:
        # One document of a stream (``load_all``); the documents share the budget.
        return self._bounded(self.composer.get_node())

    def _bounded(self, node: Node | None) -> object:
        if node is None:
            return None
        version = self.resolver.processing_version
        if version != (1, 2):
            raise _VersionError(".".join(str(part) for part in version))
        _written_out_size(node, self.max_expanded_size)
        builder = _Builder(
            self, self.max_expanded_size, keep_last=self.keep_last_duplicate, typed=self.typed
        )
        value = builder.value(node)
        self.max_expanded_size = builder.remaining
        return value


def _written_out_size(root: Node, budget: int, *, native_value: bool = False) -> int:
    """The size of *root* written out without its aliases, never past *budget*.

    Each node is visited once and its size remembered, so a node that many aliases
    share costs its children once and its size once per use. Raises
    :class:`_ExpansionBudgetError` as soon as one node's size passes *budget* (the root's
    is at least as large), and :class:`_CycleError` for a node that contains itself.
    The walk keeps its own stack, so its depth is not Python's.
    """

    sizes: dict[int, int] = {}
    heights: dict[int, int] = {}
    # Nodes whose children are being sized: the path from the root to the current node.
    active: set[int] = set()
    stack: list[tuple[Node, bool]] = [(root, False)]
    while stack:
        node, children_sized = stack.pop()
        marker = id(node)
        if children_sized:
            active.discard(marker)
            children = _children(node)
            size = 1 + sum(sizes[id(child)] for child in children)
            if native_value:
                heights[marker] = 1 + max(
                    (heights.get(id(child), 1) for child in children), default=0
                )
                if heights[marker] > YAML_MAX_DEPTH:
                    raise _DepthError
        elif marker in sizes:
            continue
        elif isinstance(node, ScalarNode):
            if native_value and node.tag not in _SCALAR_TAGS and node.tag not in _TEXT_TAGS:
                raise BoundedYamlError("YAML scalar has an unsupported tag")
            # YAML 1.1 base-60 integer construction repeatedly multiplies a growing
            # Python integer. Apply Python's decimal conversion ceiling to its input.
            if (
                native_value
                and node.tag == _TAG + "int"
                and ":" in node.value
                and len(node.value) > sys.int_info.default_max_str_digits
            ):
                raise BoundedYamlError("YAML base-60 integer is too long", over_budget=True)
            size = 1 + len(node.value)
        else:
            if native_value:
                tags = (_SEQ, _OMAP, _PAIRS) if isinstance(node, SequenceNode) else (_MAP, _SET)
                if node.tag not in tags:
                    raise BoundedYamlError("YAML collection has an unsupported tag")
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


_TAG: Final = "tag:yaml.org,2002:"
_MAP: Final = _TAG + "map"
_SEQ: Final = _TAG + "seq"
_SET: Final = _TAG + "set"
_OMAP: Final = _TAG + "omap"
_PAIRS: Final = _TAG + "pairs"
_MERGE: Final = _TAG + "merge"
# The scalar tags of YAML 1.2's core schema and the safe loader's extras, the only tags
# a scalar may carry; ruamel's constructor builds each.
_SCALAR_TAGS: Final = frozenset(
    _TAG + name for name in ("null", "bool", "int", "float", "str", "binary", "timestamp")
)
# The tags ruamel's resolver gives a plain `=` and `<<`, which the loader reads as text
# wherever `<<` is not a merge key.
_TEXT_TAGS: Final = frozenset((_TAG + "value", _MERGE))

_Pair = tuple[Node, Node]


class _Builder:
    """Builds the JSON-safe value of a measured node graph, spending a budget on each step.

    Collections and merge keys are the builder's own; only a scalar goes to ruamel's
    constructor, once per node. A mapping or sequence is written out afresh at each use,
    so the value shares nothing.
    """

    __slots__ = (
        "_active",
        "_constructor",
        "_keep_last",
        "_keys",
        "_remaining",
        "_scalars",
        "_typed",
    )

    def __init__(
        self, constructor: SafeConstructor, budget: int, *, keep_last: bool, typed: bool = False
    ) -> None:
        self._constructor = constructor
        self._remaining = budget
        self._keep_last = keep_last
        self._typed = typed
        self._scalars: dict[int, tuple[object, int]] = {}
        self._keys: dict[int, str] = {}
        # Collections on the path from the root to the node being built.
        self._active: set[int] = set()

    @property
    def remaining(self) -> int:
        """What is left of the budget; the benchmark reads it to size a document."""

        return self._remaining

    def _spend(self, size: int) -> None:
        self._remaining -= size
        if self._remaining < 0:
            raise _ExpansionBudgetError

    def value(self, node: Node) -> object:
        # The composer counts the nesting of the text, where an alias is a leaf; this
        # counts the value's, through every alias, in the same unit: a node inside n
        # collections is level n + 1.
        if len(self._active) >= YAML_MAX_DEPTH:
            raise _DepthError
        self._spend(1)
        if isinstance(node, ScalarNode):
            converted, size = self._scalar(node)
            self._spend(size)
            return converted
        marker = id(node)
        if marker in self._active:
            raise _CycleError
        self._active.add(marker)
        try:
            if isinstance(node, SequenceNode):
                return self._sequence(node)
            if isinstance(node, MappingNode):
                return self._mapping(node)
            raise _NodeError(node, "a node the loader does not read")
        finally:
            self._active.discard(marker)

    def _sequence(self, node: SequenceNode) -> object:
        tag = node.tag
        if tag == _SEQ:
            return [self.value(child) for child in node.value]
        if tag == _OMAP:
            ordered: dict[str, object] = {}
            for key_node, value_node in self._single_pairs(node):
                key = self._key(key_node)
                if key in ordered:
                    raise _NodeError(key_node, "a key appears twice in an ordered map")
                self._spend(1 + len(key))
                ordered[key] = self.value(value_node)
            return ordered
        if tag == _PAIRS:
            return [
                [self.value(key_node), self.value(value_node)]
                for key_node, value_node in self._single_pairs(node)
            ]
        raise _NodeError(node, "a sequence has a tag the loader does not read")

    def _single_pairs(self, node: SequenceNode) -> list[_Pair]:
        pairs: list[_Pair] = []
        for item in node.value:
            if not isinstance(item, MappingNode) or item.tag != _MAP or len(item.value) != 1:
                raise _NodeError(item, "an ordered map or pairs item is not a one-key mapping")
            pairs.append(item.value[0])
        return pairs

    def _mapping(self, node: MappingNode) -> object:
        tag = node.tag
        if tag == _MAP:
            built: dict[str, object] = {}
            for key, (_key_node, value_node) in self._entries(node).items():
                self._spend(1 + len(key))
                built[key] = self.value(value_node)
            return built
        if tag == _SET:
            members = [self.value(key_node) for key_node, _value in self._entries(node).values()]
            # A YAML !!set is unordered; sorting its text makes the value the same on
            # every load.
            members.sort(key=lambda member: json.dumps(member, sort_keys=True))
            return TypedList(members) if self._typed else members
        raise _NodeError(node, "a mapping has a tag the loader does not read")

    def _entries(self, node: MappingNode) -> dict[str, _Pair]:
        """The entries of *node* by key, with its merge keys applied, in ruamel's order.

        A key of the mapping itself wins over a merged one; among the mappings a merge
        key names, an earlier one wins, and a mapping's own keys win over those it
        merges. The order is ruamel's: the merged keys first, from the last mapping
        named to the first, then the mapping's own. A mapping reached twice through
        merges adds nothing the second time, so nesting multiplies nothing.
        """

        own, sources = _split(node)
        chosen = self._own_entries(own)
        if not sources:
            return chosen
        # Which value wins: the mapping's own entries, then each merged mapping, depth
        # first, in the order the merge key names them.
        seen = {id(node)}
        pending = list(reversed(sources))
        while pending:
            source = pending.pop()
            self._spend(1)
            if id(source) in seen:
                continue
            seen.add(id(source))
            source_own, source_sources = _split(source)
            self._spend(len(source_own))
            for key, pair in self._own_entries(source_own).items():
                chosen.setdefault(key, pair)
            pending.extend(reversed(source_sources))
        # The order of the keys: where each first appears in ruamel's flattened list,
        # which puts a mapping's merged entries, last named first, before its own.
        order: dict[str, None] = {}
        visited: set[int] = set()
        walk: list[tuple[MappingNode, bool]] = [(node, False)]
        while walk:
            current, sources_done = walk.pop()
            if sources_done:
                for pair in _split(current)[0]:
                    self._spend(1)
                    order.setdefault(self._key(pair[0]))
                continue
            self._spend(1)
            if id(current) in visited:
                continue
            visited.add(id(current))
            walk.append((current, True))
            walk.extend((source, False) for source in _split(current)[1])
        return {key: chosen[key] for key in order}

    def _own_entries(self, pairs: list[_Pair]) -> dict[str, _Pair]:
        """One mapping's own entries by key: a repeated key is refused, or keeps its last
        value where the caller asked for that, whether or not the mapping is merged."""

        entries: dict[str, _Pair] = {}
        for pair in pairs:
            key = self._key(pair[0])
            if key in entries and not self._keep_last:
                raise _NodeError(pair[0], "a key appears twice in one mapping")
            entries[key] = pair
        return entries

    def _key(self, node: Node) -> str:
        """A key's text: a string as it is, any other scalar or a sequence as JSON."""

        known = self._keys.get(id(node))
        if known is not None:
            return known
        if isinstance(node, ScalarNode):
            converted = self._scalar(node)[0]
            text = converted if isinstance(converted, str) else json.dumps(converted)
            if self._typed and not isinstance(converted, str):
                text = TypedText(text, type(converted).__name__)
        elif (
            isinstance(node, SequenceNode)
            and node.tag == _SEQ
            and all(isinstance(item, ScalarNode) for item in node.value)
        ):
            text = json.dumps([self._scalar(item)[0] for item in node.value], ensure_ascii=False)
            if self._typed:
                text = TypedText(text, "list")
        else:
            raise _NodeError(node, "a key is a mapping, or a sequence that holds a collection")
        self._keys[id(node)] = text
        return text

    def _scalar(self, node: ScalarNode) -> tuple[object, int]:
        """A scalar's JSON-safe value and its size, built by ruamel once per node."""

        known = self._scalars.get(id(node))
        if known is not None:
            return known
        tag = node.tag
        if tag in _TEXT_TAGS:
            # A plain `=` or `<<` that is not a merge key reads as its text, as YAML 1.2's
            # core schema reads it; ruamel's resolver tags them for YAML 1.1's types.
            built: object = node.value
        elif tag not in _SCALAR_TAGS:
            raise _NodeError(node, "a scalar has a tag the loader does not read")
        else:
            try:
                built = self._constructor.construct_object(node)
            except RecursionError:
                raise
            except Exception as exc:
                # ruamel's messages quote the scalar; this names only its tag.
                raise _NodeError(node, f"not a valid !!{tag.removeprefix(_TAG)}") from exc
        result = _json_scalar(built)
        if self._typed and result[0] is not built and isinstance(result[0], str):
            # Written as text it was not: a date, binary, a number JSON cannot hold, or a
            # string whose unpaired surrogates were replaced.
            result = (TypedText(result[0], type(built).__name__), result[1])
        self._scalars[id(node)] = result
        return result


def _split(node: MappingNode) -> tuple[list[_Pair], list[MappingNode]]:
    """A mapping's own entries, and the mappings its merge key names, in that order."""

    own: list[_Pair] = []
    merges: list[Node] = []
    for pair in node.value:
        if pair[0].tag == _MERGE:
            merges.append(pair[1])
        else:
            own.append(pair)
    if not merges:
        return own, []
    if len(merges) > 1:
        raise _NodeError(node, "a mapping has two merge keys")
    named = merges[0]
    candidates: list[Node] = list(named.value) if isinstance(named, SequenceNode) else [named]
    sources: list[MappingNode] = []
    for source in candidates:
        if not isinstance(source, MappingNode) or source.tag != _MAP:
            raise _NodeError(source, "a merge key names something other than a mapping")
        sources.append(source)
    return own, sources


def _json_scalar(value: object) -> tuple[object, int]:
    """A built scalar as JSON-safe value, with its size as the budget counts it."""

    if value is None or isinstance(value, bool):
        return value, 0
    if isinstance(value, str):
        return _encodable(value), len(value)
    if isinstance(value, int):
        return _json_int(value)
    if isinstance(value, float):
        text = _float_text(value)
        return (value if math.isfinite(value) else text), len(text)
    if isinstance(value, _dt.date | _dt.time):
        text = value.isoformat()
    elif isinstance(value, bytes | bytearray):
        text = base64.b64encode(value).decode("ascii")
    else:
        # The safe loader builds no other scalar; name the type rather than call its
        # str(), whose cost nothing here bounds.
        text = f"<{type(value).__name__}>"
    return text, len(text)


def _json_int(value: int) -> tuple[object, int]:
    # A decimal digit holds about 3.3 bits, so this never under-counts the digits and
    # over-counts them by about a tenth: right for the budget, not for the limit.
    digits = value.bit_length() // 3 + 1
    limit = sys.get_int_max_str_digits()
    if limit and digits > limit:
        try:
            # Refuses past the limit before it converts, so this costs little.
            str(value)
        except ValueError:
            # A hexadecimal literal can build an integer past the decimal digit limit,
            # which the JSON encoder would refuse; its hexadecimal text has no limit.
            return hex(value), digits
    return value, digits


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
