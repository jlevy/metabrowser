"""The rendered view of a changed YAML or JSON file: one merged tree of both sides.

The file browser shows a YAML or JSON file as the structured plugin's tree
(``builtin_plugins/structured``). A changed file's Rendered view is that same tree with
each entry marked: ``context`` where both sides hold the same value, ``modified`` on a
mapping or list whose entries differ, and ``removed`` and ``added`` for what only one
side holds. A scalar that changed is its old entry removed and its new one added, as a
changed Markdown block is. The page draws the tree with the change gutter Markdown blocks
use, and folds what did not change.

Both sides parse as the structured plugin parses them (``parser.parse_structured_text``): JSON,
then JSONC through ``json5``; a YAML stream collapses as the tree view collapses it. A
YAML side with an alias is refused before it is loaded, since loading expands every
alias and a few hundred bytes can expand to gigabytes (mb-7th1). Values are made JSON's,
as the structured route's answer makes them: keys become strings and dates ISO-8601.

Mappings align by key: a key both sides hold stays at its new position, and one only the
old side holds stays after the key it followed there. Lists align by value with
``difflib``; a replaced run pairs its items in order, and a pair of mappings or lists is
compared entry by entry. ``source_only`` says the bytes differ and the tree shows no
change, as when only a comment, a quote style or the order of a mapping's keys changed.
"""

from __future__ import annotations

import base64
import datetime as dt
import difflib
import json
import math
from collections.abc import Callable, Iterator, Sequence
from contextvars import ContextVar
from typing import Any, Literal, NotRequired, TypedDict

STRUCTURED_DIFF_VERSION = "structured-diff-v1"

# Both sides' bytes together, for a pair that strict JSON parses. Measured with
# `explorations/structured-diff/measure.py` (Python 3.13, Linux container, 2026-11-18;
# ranges over four runs, recorded in its README) over this repository's 624 distinct
# real pairs: the 456 JSON pairs are p50 15 KiB, p90 156 KiB, and 60 are past this bound
# (lock files and recorded fixtures). The slowest real pair inside it took 7-8 ms, and a
# synthetic 127 KiB pair of nested mappings 4 ms.
STRUCTURED_DIFF_MAX_BYTES = 128 * 1024
# Both sides' bytes together, for a pair ruamel.yaml or json5 parses: both are pure
# Python, about 5 ms per KiB of dense synthetic YAML and 6 of JSONC, against 0.03 for
# strict JSON. Every one of the 168 real YAML pairs fits (p50 5 KiB, p90 18 KiB, largest
# 38 KiB; 13-15 ms p50, 40-42 ms p90, 62-76 ms at most). A synthetic 48 KiB pair took
# 208-244 ms as YAML and 271-300 ms as JSONC, beside the 222-268 ms of the slowest
# Markdown projection inside its own budgets.
SLOW_PARSE_MAX_BYTES = 48 * 1024
# Values in both sides' trees together, counted as they are composed or converted, so
# a pair of short scalars cannot outgrow the byte bounds' measurements: 128 KiB of strict
# JSON holds up to about 65,000 one-digit list items. Two equal lists of 19,999 (40,000
# values) projected in 14-55 ms, and with one item changed were refused in 18-28 ms.
_MAX_NODES = 40_000
# Entries an answer draws: every entry of a modified mapping or list, which the page
# draws as rows. The real pairs draw p50 17, p90 110, p99 627 and at most 1,250 (a
# recorded fixture), and answer at most 120 KiB. One changed item in a list of 10,000
# drew 10,002 entries in 341 KiB, more than a reader reviews as a tree.
_MAX_ENTRIES = 2_000
# Alignment work: the product of the two runs `SequenceMatcher` aligns once a common
# prefix and suffix are set aside. It is quadratic when values repeat: two runs of 1,000
# items drawn from 10 values took 19 ms, 2,000 took 83 ms and 4,000 took 477 ms, against
# 5 ms for 4,000 distinct values. A larger run pairs its items in order.
_MAX_ALIGNMENT_WORK = 1_000_000
# Nesting deeper than this is refused: the merge recurses once per level.
_MAX_DEPTH = 64

type Change = Literal["context", "modified", "added", "removed"]
type Status = Literal["ready", "unsupported", "too_large"]
type Format = Literal["yaml", "json"]
type Scalar = str | int | float | bool | None

_FORMATS: dict[str, Format] = {".json": "json", ".yaml": "yaml", ".yml": "yaml"}


class StructuredDiffEntry(TypedDict):
    """One mapping key or list item and how its value changed.

    ``key`` is the mapping key; a list item and the document itself have none. A
    ``modified`` entry is a mapping or list (``type``) whose ``entries`` differ; every
    other entry carries its whole ``value`` as JSON, unchanged, added or removed.
    """

    key: NotRequired[str]
    change: Change
    value: NotRequired[Any]
    type: NotRequired[Literal["map", "list"]]
    entries: NotRequired[list[StructuredDiffEntry]]


class StructuredDiffProjection(TypedDict):
    version: str
    status: Status
    format: NotRequired[Format]
    root: list[StructuredDiffEntry]
    source_only: bool


class _Unsupported(Exception):
    """A side the tree view would not draw: malformed, or YAML with an alias."""


class _OverBudget(Exception):
    """A pair past one of the projection's budgets."""


class UnboundedYamlError(ValueError):
    """YAML whose load would not be bounded by its text: an alias, or too many nodes."""


_MISSING = object()


def _scalar(value: object) -> Scalar:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        # JSON has no NaN or infinity; the tree shows what the YAML says.
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode()
    return str(value)


def _key(value: object) -> str:
    """A mapping key as JSON spells it, which is how the tree view receives it."""

    if isinstance(value, str):
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return json.dumps(value)
    return str(_scalar(value))


class _Counter:
    def __init__(self) -> None:
        self.nodes = 0

    def spend(self) -> None:
        self.nodes += 1
        if self.nodes > _MAX_NODES:
            raise _OverBudget("structured nodes")


def _plain(value: object, counter: _Counter, depth: int = 0) -> Any:
    """*value* as JSON values, counted against the node budget."""

    if depth > _MAX_DEPTH:
        raise _OverBudget("structured nesting")
    counter.spend()
    if isinstance(value, dict):
        return {_key(key): _plain(item, counter, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=repr) if isinstance(value, (set, frozenset)) else value
        return [_plain(item, counter, depth + 1) for item in items]
    return _scalar(value)


def load_guarded_yaml(text: str, *, stream: bool = True) -> object:
    """Load YAML with ruamel's safe loader, as the tree view and front matter do.

    An alias is refused as it is composed, before anything expands, and so is a document
    past `_MAX_NODES`. *stream* loads every document and collapses them as the tree view
    does; otherwise the text is one document, as front matter is.
    """

    from ruamel.yaml import YAML
    from ruamel.yaml.composer import Composer
    from ruamel.yaml.events import AliasEvent

    from metabrowser.builtin_plugins.structured.parser import collapse_yaml_documents

    composed = 0

    class _Guarded(Composer):
        def compose_node(self, parent: Any, index: Any) -> Any:
            nonlocal composed
            if self.parser.check_event(AliasEvent):
                raise UnboundedYamlError("YAML aliases expand without a bound")
            composed += 1
            if composed > _MAX_NODES:
                raise UnboundedYamlError("YAML nodes")
            return super().compose_node(parent, index)

    yaml = YAML(typ="safe")
    yaml.Composer = _Guarded
    if not stream:
        return yaml.load(text)
    return collapse_yaml_documents(list(yaml.load_all(text)))


def _parse(data: bytes, fmt: Format, pair_bytes: int) -> object:
    from metabrowser.builtin_plugins.structured.parser import (
        decode_text,
        parse_structured_text,
    )

    text = decode_text(data)
    try:
        if fmt == "json":
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        if pair_bytes > SLOW_PARSE_MAX_BYTES:
            raise _OverBudget("YAML or JSONC input bytes")
        if fmt == "yaml":
            return load_guarded_yaml(text)
        # JSONC, as the tree view reads it.
        return parse_structured_text(text, ".json")
    except (_OverBudget, _Unsupported):
        raise
    except UnboundedYamlError as exc:
        raise _Unsupported(str(exc)) from exc
    except Exception as exc:
        # Whatever the parsers raise on malformed input: the tree view shows Source then.
        raise _Unsupported(type(exc).__name__) from exc


def _container(value: object) -> Literal["map", "list"] | None:
    if isinstance(value, dict):
        return "map"
    if isinstance(value, list):
        return "list"
    return None


def _same(old: object, new: object) -> bool:
    """Equal values of equal types, so ``1``, ``1.0`` and ``true`` differ, as they read."""

    if type(old) is not type(new):
        return False
    if isinstance(old, dict):
        assert isinstance(new, dict)
        return old.keys() == new.keys() and all(_same(old[key], new[key]) for key in old)
    if isinstance(old, list):
        assert isinstance(new, list)
        return len(old) == len(new) and all(_same(a, b) for a, b in zip(old, new, strict=True))
    return old == new


def _fingerprint(value: object) -> str:
    """A key that equal values share and `_same` distinguishes, for list alignment."""

    def tagged(item: object) -> object:
        if isinstance(item, dict):
            return {"m": sorted((key, tagged(each)) for key, each in item.items())}
        if isinstance(item, list):
            return {"l": [tagged(each) for each in item]}
        return [type(item).__name__, item]

    return json.dumps(tagged(value), separators=(",", ":"))


# The entries the projection in progress has drawn, so a merge stops at the budget rather
# than after building every entry past it.
_DRAWN: ContextVar[list[int]] = ContextVar("structured_diff_drawn")


def _draw() -> None:
    drawn = _DRAWN.get()
    drawn[0] += 1
    if drawn[0] > _MAX_ENTRIES:
        raise _OverBudget("structured entries")


def _whole(key: str | None, value: object, change: Change) -> StructuredDiffEntry:
    """*value* as one side holds it, whole."""

    _draw()
    entry: StructuredDiffEntry = {"change": change, "value": value}
    if key is not None:
        entry["key"] = key
    return entry


def _merge(key: str | None, old: object, new: object) -> Iterator[StructuredDiffEntry]:
    if old is _MISSING:
        yield _whole(key, new, "added")
    elif new is _MISSING:
        yield _whole(key, old, "removed")
    elif _same(old, new):
        yield _whole(key, new, "context")
    elif (kind := _container(old)) is not None and kind == _container(new):
        entries = (
            _merge_map(old, new)  # pyright: ignore[reportArgumentType]
            if kind == "map"
            else _merge_list(old, new)  # pyright: ignore[reportArgumentType]
        )
        _draw()
        modified: StructuredDiffEntry = {"change": "modified", "type": kind, "entries": entries}
        if key is not None:
            modified["key"] = key
        yield modified
    else:
        yield _whole(key, old, "removed")
        yield _whole(key, new, "added")


def _merge_map(old: dict[str, object], new: dict[str, object]) -> list[StructuredDiffEntry]:
    old_keys, new_keys = list(old), list(new)
    entries: list[StructuredDiffEntry] = []
    for _, old_start, old_stop, new_start, new_stop in _opcodes(old_keys, new_keys):
        # A key both sides hold is drawn once, where the new side has it.
        for key in old_keys[old_start:old_stop]:
            if key not in new:
                entries.extend(_merge(key, old[key], _MISSING))
        for key in new_keys[new_start:new_stop]:
            entries.extend(_merge(key, old.get(key, _MISSING), new[key]))
    return entries


def _opcodes[T](
    old: Sequence[T], new: Sequence[T], key: Callable[[T], object] | None = None
) -> list[tuple[str, int, int, int, int]]:
    """`SequenceMatcher`'s opcodes for *old* and *new*, within the alignment budget.

    The common prefix and suffix (`_same` items) are equal runs, so only the middle is
    aligned, by *key* when one is given, and a middle past `_MAX_ALIGNMENT_WORK` is one
    replaced run.
    """

    head = 0
    while head < min(len(old), len(new)) and _same(old[head], new[head]):
        head += 1
    tail = 0
    while tail < min(len(old), len(new)) - head and _same(
        old[len(old) - 1 - tail], new[len(new) - 1 - tail]
    ):
        tail += 1
    old_stop, new_stop = len(old) - tail, len(new) - tail
    middle: list[tuple[str, int, int, int, int]] = []
    if (old_stop - head) * (new_stop - head) > _MAX_ALIGNMENT_WORK:
        middle.append(("replace", head, old_stop, head, new_stop))
    elif old_stop > head or new_stop > head:
        before: Sequence[object] = old[head:old_stop]
        after: Sequence[object] = new[head:new_stop]
        if key is not None:
            before = [key(item) for item in old[head:old_stop]]
            after = [key(item) for item in new[head:new_stop]]
        matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
        middle.extend(
            (tag, i1 + head, i2 + head, j1 + head, j2 + head)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        )
    return [
        *([("equal", 0, head, 0, head)] if head else []),
        *middle,
        *([("equal", old_stop, len(old), new_stop, len(new))] if tail else []),
    ]


def _replaced(removed: Sequence[object], added: Sequence[object]) -> list[StructuredDiffEntry]:
    """A replaced run, its items paired in order.

    A pair of mappings or of lists is compared entry by entry; scalars that changed read
    as one removed run and one added run, as changed lines do.
    """

    entries: list[StructuredDiffEntry] = []
    pending_removed: list[StructuredDiffEntry] = []
    pending_added: list[StructuredDiffEntry] = []
    for index in range(max(len(removed), len(added))):
        before = removed[index] if index < len(removed) else _MISSING
        after = added[index] if index < len(added) else _MISSING
        kind = _container(before)
        if kind is not None and kind == _container(after):
            entries += pending_removed + pending_added
            pending_removed, pending_added = [], []
            entries.extend(_merge(None, before, after))
            continue
        if before is not _MISSING:
            pending_removed.append(_whole(None, before, "removed"))
        if after is not _MISSING:
            pending_added.append(_whole(None, after, "added"))
    return entries + pending_removed + pending_added


def _merge_list(old: list[object], new: list[object]) -> list[StructuredDiffEntry]:
    opcodes = _opcodes(old, new, _fingerprint)
    entries: list[StructuredDiffEntry] = []
    for tag, old_start, old_stop, new_start, new_stop in opcodes:
        if tag == "equal":
            entries.extend(_whole(None, item, "context") for item in new[new_start:new_stop])
        else:
            entries.extend(_replaced(old[old_start:old_stop], new[new_start:new_stop]))
    return entries


def _visible(entries: Sequence[StructuredDiffEntry]) -> bool:
    return any(entry["change"] != "context" for entry in entries)


def unavailable_structured_diff(
    status: Literal["unsupported", "too_large"],
) -> StructuredDiffProjection:
    """A projection that refuses, with no partial tree."""

    return {"version": STRUCTURED_DIFF_VERSION, "status": status, "root": [], "source_only": False}


def structured_format(ext: str) -> Format | None:
    """The format a logical extension names, as the structured plugin claims it, or ``None``."""

    return _FORMATS.get(ext.lower())


def _project(old: bytes | None, new: bytes | None, fmt: Format) -> StructuredDiffProjection:
    pair_bytes = len(old or b"") + len(new or b"")
    if pair_bytes > STRUCTURED_DIFF_MAX_BYTES:
        raise _OverBudget("structured input bytes")
    counter = _Counter()
    before = _MISSING if old is None else _plain(_parse(old, fmt, pair_bytes), counter)
    after = _MISSING if new is None else _plain(_parse(new, fmt, pair_bytes), counter)
    token = _DRAWN.set([0])
    try:
        root = list(_merge(None, before, after))
    finally:
        _DRAWN.reset(token)
    return {
        "version": STRUCTURED_DIFF_VERSION,
        "status": "ready",
        "format": fmt,
        "root": root,
        "source_only": old is not None and new is not None and old != new and not _visible(root),
    }


def project_structured_diff(
    *, old: bytes | None, new: bytes | None, fmt: Format
) -> StructuredDiffProjection:
    """The merged tree of a changed YAML or JSON file, or a refusal with no partial tree.

    ``None`` is a side the comparison does not hold, as for an added or deleted file.
    """

    try:
        return _project(old, new, fmt)
    except _OverBudget:
        return unavailable_structured_diff("too_large")
    except _Unsupported:
        return unavailable_structured_diff("unsupported")


def walk_entries(
    entries: Sequence[StructuredDiffEntry],
    visit: Callable[[StructuredDiffEntry, int], None],
    depth: int = 0,
) -> None:
    """Call *visit* on every entry, parents first, with its depth."""

    for entry in entries:
        visit(entry, depth)
        walk_entries(entry.get("entries", ()), visit, depth + 1)
