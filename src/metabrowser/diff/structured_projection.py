"""The rendered view of a changed YAML or JSON file: one merged tree of both sides.

The file browser shows a YAML or JSON file as the structured plugin's tree
(``builtin_plugins/structured``). A changed file's Rendered view is that same tree with
each entry marked: ``context`` where both sides hold the same value, ``modified`` on a
mapping or list whose entries differ, and ``removed`` and ``added`` for what only one
side holds. A scalar that changed is its old entry removed and its new one added, as a
changed Markdown block is. The page draws the tree with the change gutter Markdown blocks
use, and folds what did not change.

Each side is read as the file view reads it (:mod:`metabrowser.structured_text`), through
bounded parsers: strict JSON, then JSONC through ``json5``, and YAML through the bounded
loader (:mod:`metabrowser.frontmatter_yaml`), whose documents collapse as the tree view
collapses a stream. That loader admits aliases and merge keys within a budget on the
value written out, and refuses what the tree view's own loader expands without one
(mb-7th1). A JSON object that holds a key twice reads as the tree view reads it, the last
value at the key's first place, and so does a mapping two of whose keys are one text once
made JSON-safe, such as two strings whose unpaired surrogates were replaced; the values
they hide are compared, and a change to one is a change Source shows. YAML's loader
refuses a key twice in one mapping, as the tree view's own loader does, which then shows
its parse error. It also refuses two keys of one text and different types, such as ``1``
and ``"1"``, which the tree view reads as two keys and draws as the last, since the
structured route's answer then holds that key twice. Values are made JSON-safe as the loader
makes them (:func:`~metabrowser.frontmatter_yaml.json_safe_scalar`): keys are strings, a
date or time ISO-8601, binary base64, a set a sorted list, and a number JSON cannot hold
its text. The structured route sends what its parser built and fails on a date, binary,
or a value that is not finite (bead mb-hs06); the diff coerces what that route cannot
send. Values are compared before that coercion (:class:`~metabrowser.frontmatter_yaml.TypedText`
keeps the type), so the key ``1`` and the key ``"1"``, a date and the string that spells
it, a set and a list, and a stream of documents and a list of them differ.

Mappings align by key: a key both sides hold is drawn once, at its new place, and a key
only the old side holds is drawn after the key it followed there, wherever that key is
now, or first when it followed none that stayed. Lists align by value: after the common
prefix and suffix, the middle is aligned by Myers' shortest edit script over each item's
identity (equal values of equal types share one), within a work budget, and past the
budget the middle is one replaced run. In a replaced run, a removed and an added mapping
or list that share entries are paired first, choosing the pairing in order that shares
the most (within its own budget), and the items between paired ones are paired in order;
a pair of mappings or lists is compared entry by entry.

``source_only`` says Source shows a change the tree does not draw: the bytes differ and
the tree shows no change, as when only a comment, a quote style or the order of a
mapping's keys changed; or, beside changes it draws, two values differ only in what the
tree does not show, such as a key's type, and are drawn unchanged, or the values a key
written twice hides differ.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Final, Literal, NotRequired, TypedDict, cast

from metabrowser.frontmatter_yaml import (
    BoundedYamlError,
    TypedText,
    json_safe_scalar,
    load_bounded_yaml_documents,
)
from metabrowser.structured_text import collapse_yaml_documents, decode_text

STRUCTURED_DIFF_VERSION: Final = "structured-diff-v1"

# Both sides' bytes together, for a pair that strict JSON parses. Measured with
# `explorations/structured-diff/measure.py` (Python 3.13, Linux container, 2026-11-18;
# ranges over four runs, recorded in its README) over this repository's 624 distinct
# real pairs: the 456 JSON pairs are p50 15 KiB, p90 156 KiB, and 60 are past this bound
# (lock files and recorded fixtures). The slowest real pair inside it took 7-8 ms, and a
# synthetic 127 KiB pair of nested mappings 4 ms. The slowest shape found is one key
# written again and again, each value it hides written as JSON with its object's path
# (_last_wins, _placed): 10,912 times a side (130,952 bytes) took 98-229 ms at best and
# 283-498 ms at the median of 15, against 7 ms and 131 ms for a real 61 KB file, one
# digit changed, in the same process (Apple M1 Pro, Python 3.14.7, load average 387-412,
# 2026-11-23; review A8 of #766 measured 95 and 217 ms at a load of 150 to 270).
STRUCTURED_DIFF_MAX_BYTES: Final = 128 * 1024
# Both sides' bytes together, for a YAML pair. ruamel's loader is pure Python, and its
# cost follows the nodes the text composes to, which _MAX_YAML_NODES bounds; this bounds
# the scan of text that composes to few nodes (long strings, comments). Every one of the
# 168 real YAML pairs fits (p50 5 KiB, p90 18 KiB, largest 38 KiB).
SLOW_PARSE_MAX_BYTES: Final = 48 * 1024
# Both sides' bytes together, for a JSON pair strict JSON refuses, which json5 reads as
# JSONC (comments, trailing commas). json5 is pure Python, the slowest reader here, and
# its cost follows the items: a side of 4,096 one-digit items (8 KiB) read in 257-272 ms,
# and 2,048 (4 KiB) in 120-149 ms, at a load average of 33-41 (Apple M1 Pro, Python
# 3.14, 2026-11-18; `explorations/structured-diff/measure.py`), so this bound's densest
# pair costs about what the slowest Markdown projection does. One of this repository's
# 456 real JSON pairs is not strict JSON, a 120-byte fixture.
JSONC_MAX_BYTES: Final = 8 * 1024
# The nodes one YAML side may compose to, aliases counting one each. Composing costs
# about 21-30 us a node whatever the text spells (flow or block lists of one-digit
# integers, nested mappings): 6,000 nodes took 153-244 ms and 4,000 took 111-198 ms at a
# load average of 33-41, so a pair at this bound costs about the slowest Markdown
# projection. The largest real YAML file, `.github/workflows/ci.yml`, is 681 nodes in
# 20 KiB.
_MAX_YAML_NODES: Final = 5_000
# Values in both sides' trees together, counted as they are converted, so a pair of
# short scalars cannot outgrow the byte bounds' measurements: 128 KiB of strict JSON
# holds up to about 65,000 one-digit list items. Two equal lists of 19,999 (40,000
# values) projected in 14-55 ms, and with one item changed were refused in 18-28 ms.
_MAX_NODES: Final = 40_000
# Entries an answer draws: every entry of a modified mapping or list, which the page
# draws as rows. The real pairs draw p50 17, p90 110, p99 627 and at most 1,250 (a
# recorded fixture), and answer at most 120 KiB. One changed item in a list of 10,000
# drew 10,002 entries in 341 KiB, more than a reader reviews as a tree.
_MAX_ENTRIES: Final = 2_000
# Steps of list alignment one projection may take, across all its lists: a step is one
# diagonal Myers' algorithm extends or one item it slides along a diagonal. Past it, the
# middle of each later list is one replaced run. Review A1's shapes, two lists of 1,000
# to 2,000 items drawn from ten values, answer in 90-99 ms at a load average of 33-41,
# where difflib took 1.1 s and more (the 2,000 draw more than _MAX_ENTRIES and answer
# too_large); two lists of 1,000 random bits with the first and last flipped take 3 ms.
_MAX_ALIGNMENT_STEPS: Final = 400_000
# Shared entries one projection may compare while it pairs the mappings and lists of
# replaced runs, across all its runs; a run whose removed and added items make more pairs
# than _MAX_PAIRING_CELLS is paired in order. A run of 100 removed and 100 added mappings
# of 40 keys spends it and answers, too_large by its entries, in 27 ms at a load average
# of 33-41. A step is one entry of the smaller side `_shared` walks: one removed list of
# 15,000 against 8,000 added lists of one took 9.7 s when the intersection walked the
# removed list for each pair, and takes 137-140 ms (review E1, load average 37-40).
_MAX_PAIRING_STEPS: Final = 200_000
_MAX_PAIRING_CELLS: Final = 10_000
# Nesting deeper than this is refused: the merge recurses once per level. YAML's loader
# refuses past its own YAML_MAX_DEPTH, the same 64, as it composes.
_MAX_DEPTH: Final = 64
# The largest integer a JavaScript number holds exactly.
_SAFE_INTEGER: Final = 2**53
# Below this a JavaScript number writes an integral float without an exponent or ".0".
_JS_EXPONENT: Final = 1e21

type Change = Literal["context", "modified", "added", "removed"]
type Status = Literal["ready", "unsupported", "too_large"]
type Format = Literal["yaml", "json"]

_FORMATS: Final[dict[str, Format]] = {".json": "json", ".yaml": "yaml", ".yml": "yaml"}


class StructuredDiffEntry(TypedDict):
    """One mapping key or list item and how its value changed.

    ``key`` is the mapping key; a list item and the document itself have none. A
    ``modified`` entry is a mapping or list (``type``) whose ``entries`` differ; every
    other entry carries its whole ``value`` as JSON, unchanged, added or removed. ``text``
    is a number's JSON text, sent for a number value a JavaScript number does not keep:
    an integer past 2**53, or a float whose value is integral (``1.0``).
    """

    key: NotRequired[str]
    change: Change
    value: NotRequired[Any]
    text: NotRequired[str]
    type: NotRequired[Literal["map", "list"]]
    entries: NotRequired[list[StructuredDiffEntry]]


# Why a projection refuses, where that says more than its status, as a Markdown
# projection's ``reason`` does: both sides hold the same bytes, or the worker stopped it.
type StructuredRefusal = Literal["no_changes", "deadline", "memory"]


class StructuredDiffProjection(TypedDict):
    version: str
    status: Status
    # Present on a refusal whose cause the page can name.
    reason: NotRequired[StructuredRefusal]
    format: NotRequired[Format]
    root: list[StructuredDiffEntry]
    source_only: bool


class _Unsupported(Exception):
    """A side the tree view would not draw: malformed, or YAML with a key twice in one
    mapping, which the tree view's loader refuses too."""


class _Unchanged(_Unsupported):
    """Both sides are the same bytes."""


class _OverBudget(Exception):
    """A pair past one of the projection's budgets."""


_MISSING: Final = object()


class _Stream(list[object]):
    """A YAML stream of more than one document, as the tree view collapses it to a list."""

    origin: str = "stream"


type _Hiding = tuple[dict[str, Any], str]


def _last_wins(hidden: list[_Hiding]) -> Callable[[Iterable[tuple[str, Any]]], dict[str, Any]]:
    """An ``object_pairs_hook`` that builds a JSON object as ``json.loads`` does, the last
    value at the key's first place, and appends each value a later one hides to *hidden*,
    written as JSON with the object that hid it, in the order the parser closes the
    objects. The object is kept, so that its identity names it until :func:`_placed`
    reads where it is."""

    def build(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
        built: dict[str, Any] = {}
        for key, value in pairs:
            if key in built:
                hidden.append((built, json.dumps([key, built[key]])))
            built[key] = value
        return built

    return build


def _placed(value: object, hidden: list[_Hiding]) -> list[str]:
    """Each hidden value with the path of the object that hid it in *value*, so a value
    hidden in another object is another entry; ``null`` for an object inside a value a
    later one hid, which the tree holds nowhere."""

    if not hidden:
        return []
    paths: dict[int, list[str | int]] = {}
    pending: list[tuple[object, list[str | int]]] = [(value, [])]
    while pending:
        node, path = pending.pop()
        if isinstance(node, dict):
            paths[id(node)] = path
            pending.extend((item, [*path, key]) for key, item in node.items())  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        elif isinstance(node, list):
            pending.extend((item, [*path, index]) for index, item in enumerate(node))  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return [f"[{json.dumps(paths.get(id(owner)))},{entry[1:]}" for owner, entry in hidden]


class _Budget:
    """What one projection may still spend; each spend past its limit is `_OverBudget`."""

    __slots__ = ("alignment", "entries", "nodes", "pairing")

    def __init__(self) -> None:
        self.nodes = _MAX_NODES
        self.entries = _MAX_ENTRIES
        self.alignment = _MAX_ALIGNMENT_STEPS
        self.pairing = _MAX_PAIRING_STEPS

    def node(self) -> None:
        self.nodes -= 1
        if self.nodes < 0:
            raise _OverBudget("structured nodes")

    def entry(self) -> None:
        self.entries -= 1
        if self.entries < 0:
            raise _OverBudget("structured entries")


class _Values:
    """Each value's identity: equal values of equal types share one integer.

    ``1``, ``1.0`` and ``true`` differ, as they read; ``0.0`` and ``-0.0`` are one value,
    as ``==`` has them. A value written as text keeps the type it had (``origin``), and a
    mapping's keys theirs, so a date and the string that spells it differ. A mapping's
    identity ignores the order of its keys. Containers
    are the projection's own fresh objects, kept alive for its length, so their ``id`` is
    theirs; each is given its identity once, as it is built, so comparing two values and
    aligning a list never walk a value twice.
    """

    __slots__ = ("_containers", "_table")

    def __init__(self) -> None:
        self._table: dict[object, int] = {}
        self._containers: dict[int, int] = {}

    def _intern(self, key: object) -> int:
        return self._table.setdefault(key, len(self._table))

    def of(self, value: object) -> int:
        if isinstance(value, dict | list):
            return self._containers[id(value)]
        return self._intern((type(value), _origin(value), value))

    def mapping(self, value: dict[str, Any]) -> None:
        members = sorted((key, _origin(key), self.of(item)) for key, item in value.items())
        self._containers[id(value)] = self._intern(("map", tuple(members)))

    def sequence(self, value: list[Any], origin: str) -> None:
        members = tuple(self.of(item) for item in value)
        self._containers[id(value)] = self._intern(("list", origin, members))

    def same(self, old: object, new: object) -> bool:
        return self.of(old) == self.of(new)


class _Projection:
    """One pair's merge: its budget and its values' identities."""

    __slots__ = ("budget", "hidden", "values")

    def __init__(self) -> None:
        self.budget = _Budget()
        self.values = _Values()
        # Whether two values differ only in what the tree does not draw.
        self.hidden = False

    def side(self, data: bytes, fmt: Format, pair_bytes: int) -> tuple[Any, list[object]]:
        """One side's tree, and the values in it that a key written again hides."""

        written: list[_Hiding] = []
        value = _parse(data, fmt, pair_bytes, written)
        alike: list[object] = []
        plain = self.plain(value, alike)
        return plain, [*_placed(value, written), *alike]

    def plain(self, value: object, alike: list[object], depth: int = 0) -> Any:
        """*value* as JSON-safe values, counted against the node budget and given identities.

        A mapping two of whose keys are one text keeps the last value at the first key's
        place, as the tree view's JSON does; each value it hides is appended to *alike*.
        """

        if depth > _MAX_DEPTH:
            raise _OverBudget("structured nesting")
        self.budget.node()
        if isinstance(value, dict):
            mapping: dict[str, Any] = {}
            for key, item in value.items():  # pyright: ignore[reportUnknownVariableType]
                text = _key(key)
                converted = self.plain(item, alike, depth + 1)
                if text in mapping:
                    # Two keys that are one text once made JSON-safe, such as two strings
                    # whose unpaired surrogates were replaced: an answer holds one key.
                    alike.append((str(text), self.values.of(mapping[text])))
                mapping[text] = converted
            self.values.mapping(mapping)
            return mapping
        if isinstance(value, list):
            sequence = [self.plain(item, alike, depth + 1) for item in value]  # pyright: ignore[reportUnknownVariableType]
            self.values.sequence(sequence, _origin(value) or "list")
            return sequence
        safe = json_safe_scalar(value)
        if safe is not value and isinstance(safe, str):
            # JSON's own scalars written as text: a number JSON cannot hold, or a string
            # whose unpaired surrogates were replaced. The loader types YAML's.
            return TypedText(safe, type(value).__name__)
        return safe

    def whole(self, key: str | None, value: object, change: Change) -> StructuredDiffEntry:
        """*value* as one side holds it, whole."""

        self.budget.entry()
        entry: StructuredDiffEntry = {"change": change, "value": value}
        if key is not None:
            entry["key"] = key
        text = _number_text(value)
        if text is not None:
            entry["text"] = text
        return entry

    def merge(
        self, entries: list[StructuredDiffEntry], key: str | None, old: object, new: object
    ) -> None:
        """Append how *old* became *new* under *key*: one entry, or a removed and an added."""

        if old is _MISSING:
            entries.append(self.whole(key, new, "added"))
            return
        if new is _MISSING:
            entries.append(self.whole(key, old, "removed"))
            return
        if self.values.same(old, new):
            entries.append(self.whole(key, new, "context"))
            return
        kind: Literal["map", "list"]
        if isinstance(old, dict) and isinstance(new, dict):
            kind, children = "map", self._merge_map(old, new)  # pyright: ignore[reportUnknownArgumentType]
        elif isinstance(old, list) and isinstance(new, list):
            kind, children = "list", self._merge_list(old, new)  # pyright: ignore[reportUnknownArgumentType]
        elif _drawn_alike(old, new):
            # A date and the string that spells it: the rows would read the same.
            self.hidden = True
            entries.append(self.whole(key, new, "context"))
            return
        else:
            entries.append(self.whole(key, old, "removed"))
            entries.append(self.whole(key, new, "added"))
            return
        if not _visible(children):
            # Only a key's or a set's type differs, or a stream became a list: nothing in
            # the merged rows would show it.
            self.hidden = True
            entries.append(self.whole(key, new, "context"))
            return
        self.budget.entry()
        modified: StructuredDiffEntry = {"change": "modified", "type": kind, "entries": children}
        if key is not None:
            modified["key"] = key
        entries.append(modified)

    def _merge_map(
        self, old: dict[str, object], new: dict[str, object]
    ) -> list[StructuredDiffEntry]:
        # Each key only the old side holds, under the last key before it there that the
        # new side holds too (None: no such key, so it comes first).
        gone: dict[str | None, list[str]] = {}
        anchor: str | None = None
        for key in old:
            if key in new:
                anchor = key
            else:
                gone.setdefault(anchor, []).append(key)
        entries: list[StructuredDiffEntry] = []
        for key in gone.get(None, ()):
            self.merge(entries, key, old[key], _MISSING)
        for key, value in new.items():
            self.merge(entries, key, old.get(key, _MISSING), value)
            for removed in gone.get(key, ()):
                self.merge(entries, removed, old[removed], _MISSING)
        return entries

    def _merge_list(self, old: list[object], new: list[object]) -> list[StructuredDiffEntry]:
        before = [self.values.of(item) for item in old]
        after = [self.values.of(item) for item in new]
        entries: list[StructuredDiffEntry] = []
        for tag, old_start, old_stop, new_start, new_stop in self._align(before, after):
            if tag == "equal":
                entries.extend(
                    self.whole(None, item, "context") for item in new[new_start:new_stop]
                )
            else:
                entries.extend(self._replaced(old[old_start:old_stop], new[new_start:new_stop]))
        return entries

    def _align(self, old: list[int], new: list[int]) -> list[tuple[str, int, int, int, int]]:
        """Equal and replaced runs of two lists of identities, which together cover both."""

        head = 0
        while head < min(len(old), len(new)) and old[head] == new[head]:
            head += 1
        tail = 0
        while tail < min(len(old), len(new)) - head and old[-1 - tail] == new[-1 - tail]:
            tail += 1
        old_stop, new_stop = len(old) - tail, len(new) - tail
        runs: list[tuple[int, int, int]] = [(0, 0, head)] if head else []
        if old_stop > head and new_stop > head:
            matched = _myers(old[head:old_stop], new[head:new_stop], self.budget)
            runs += [(head + x, head + y, length) for x, y, length in matched or ()]
        if tail:
            runs.append((old_stop, new_stop, tail))
        opcodes: list[tuple[str, int, int, int, int]] = []
        x = y = 0
        for start_x, start_y, length in [*runs, (len(old), len(new), 0)]:
            if start_x > x or start_y > y:
                opcodes.append(("replace", x, start_x, y, start_y))
            if length:
                opcodes.append(("equal", start_x, start_x + length, start_y, start_y + length))
            x, y = start_x + length, start_y + length
        return opcodes

    def _replaced(
        self, removed: Sequence[object], added: Sequence[object]
    ) -> list[StructuredDiffEntry]:
        """A replaced run: alike mappings and lists paired, and the rest in order."""

        entries: list[StructuredDiffEntry] = []
        at_removed = at_added = 0
        for paired_removed, paired_added in [*self._likeness(removed, added), (None, None)]:
            stop_removed = len(removed) if paired_removed is None else paired_removed
            stop_added = len(added) if paired_added is None else paired_added
            entries += self._in_order(removed[at_removed:stop_removed], added[at_added:stop_added])
            if paired_removed is not None and paired_added is not None:
                self.merge(entries, None, removed[paired_removed], added[paired_added])
            at_removed, at_added = stop_removed + 1, stop_added + 1
        return entries

    def _in_order(
        self, removed: Sequence[object], added: Sequence[object]
    ) -> list[StructuredDiffEntry]:
        """Items paired in order. A pair of mappings or of lists is compared entry by entry,
        a pair of equal values is unchanged (past the alignment budget, where equal items
        were not aligned), and scalars that changed read as one removed run and one added
        run, as changed lines do."""

        entries: list[StructuredDiffEntry] = []
        pending_removed: list[StructuredDiffEntry] = []
        pending_added: list[StructuredDiffEntry] = []
        for index in range(max(len(removed), len(added))):
            before = removed[index] if index < len(removed) else _MISSING
            after = added[index] if index < len(added) else _MISSING
            kind = _container(before)
            if (
                before is not _MISSING
                and after is not _MISSING
                and (
                    self.values.same(before, after)
                    or (kind is not None and kind == _container(after))
                    or _drawn_alike(before, after)
                )
            ):
                entries += pending_removed + pending_added
                pending_removed, pending_added = [], []
                self.merge(entries, None, before, after)
                continue
            if before is not _MISSING:
                pending_removed.append(self.whole(None, before, "removed"))
            if after is not _MISSING:
                pending_added.append(self.whole(None, after, "added"))
        return entries + pending_removed + pending_added

    def _likeness(
        self, removed: Sequence[object], added: Sequence[object]
    ) -> list[tuple[int, int]]:
        """The removed and added mappings and lists to pair, in order: of the pairings that
        keep both sides' order, the one whose pairs share the most entries. Empty when the
        run makes more pairs than _MAX_PAIRING_CELLS or the comparisons run past the
        projection's pairing budget, so the run is paired in order."""

        cells = len(removed) * len(added)
        if cells == 0 or cells > _MAX_PAIRING_CELLS or cells > self.budget.pairing:
            return []
        self.budget.pairing -= cells
        old = [self._members(item) for item in removed]
        new = [self._members(item) for item in added]
        if not any(old) or not any(new):
            return []
        # best[i][j]: the most shared entries pairing removed[:i] with added[:j].
        best = [[0] * (len(added) + 1) for _ in range(len(removed) + 1)]
        shared = [[0] * len(added) for _ in range(len(removed))]
        for i, members in enumerate(old):
            for j, others in enumerate(new):
                if members is not None and others is not None and type(members) is type(others):
                    # What _shared walks: the smaller side's distinct entries.
                    self.budget.pairing -= min(len(members), len(others))
                    if self.budget.pairing < 0:
                        return []
                    shared[i][j] = _shared(members, others)
                best[i + 1][j + 1] = max(
                    best[i][j + 1], best[i + 1][j], best[i][j] + shared[i][j] if shared[i][j] else 0
                )
        pairs: list[tuple[int, int]] = []
        i, j = len(removed), len(added)
        while i and j:
            if shared[i - 1][j - 1] and best[i][j] == best[i - 1][j - 1] + shared[i - 1][j - 1]:
                pairs.append((i - 1, j - 1))
                i, j = i - 1, j - 1
            elif best[i][j] == best[i - 1][j]:
                i -= 1
            else:
                j -= 1
        pairs.reverse()
        return pairs

    def _members(self, value: object) -> frozenset[tuple[str, int]] | Counter[int] | None:
        """What a mapping or list holds, as its entries' identities, to count shared ones."""

        if isinstance(value, dict):
            return frozenset((key, self.values.of(item)) for key, item in value.items())  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        if isinstance(value, list):
            return Counter(self.values.of(item) for item in value)  # pyright: ignore[reportUnknownVariableType]
        return None


def _shared(
    members: frozenset[tuple[str, int]] | Counter[int],
    others: frozenset[tuple[str, int]] | Counter[int],
) -> int:
    """The entries two mappings or two lists share, walking only the smaller of the two:
    the work `_likeness` charges for. A set intersection walks the smaller in C, but
    ``Counter.__and__`` walks its left operand in Python, so one long removed list
    against many short added ones cost the long list's length for every pair while
    being charged one (mb-8274 review E1: a 111 KB pair took 10-11 s)."""

    if isinstance(members, Counter) and isinstance(others, Counter):
        small, large = (members, others) if len(members) <= len(others) else (others, members)
        return sum(min(count, large.get(item, 0)) for item, count in small.items())
    if isinstance(members, frozenset) and isinstance(others, frozenset):
        return len(members & others)
    return 0


def _myers(
    old: Sequence[int], new: Sequence[int], budget: _Budget
) -> list[tuple[int, int, int]] | None:
    """The equal runs of a shortest edit script turning *old* into *new*, as
    ``(old_start, new_start, length)``, or ``None`` once the work passes the budget.

    Myers' greedy algorithm (1986): round *d* extends each diagonal *k* reachable with *d*
    edits by one edit, then slides along equal items. Each diagonal and each item slid is
    one step, so a pair of lists of any values costs at most what the budget allows;
    ``difflib.SequenceMatcher`` is cubic for repeated values (mb-8274 review A1). The
    rounds' frontiers are kept to walk the script back, which is quadratic in the edits
    and so bounded by the steps too.
    """

    n, m = len(old), len(new)
    frontier: dict[int, int] = {1: 0}
    trace: list[list[int]] = []
    steps = 0
    for d in range(n + m + 1):
        row: list[int] = []
        for k in range(-d, d + 1, 2):
            if k == -d or (k != d and frontier[k - 1] < frontier[k + 1]):
                x = frontier[k + 1]
            else:
                x = frontier[k - 1] + 1
            y = x - k
            start = x
            while x < n and y < m and old[x] == new[y]:
                x += 1
                y += 1
            steps += 1 + x - start
            frontier[k] = x
            row.append(x)
            if x >= n and y >= m:
                trace.append(row)
                budget.alignment -= steps
                return _walk_back(trace, n, m)
        trace.append(row)
        if steps > budget.alignment:
            budget.alignment = 0
            return None
    budget.alignment -= steps
    return _walk_back(trace, n, m)


def _walk_back(trace: list[list[int]], n: int, m: int) -> list[tuple[int, int, int]]:
    """The equal runs of the script whose rounds' frontiers *trace* holds, in order."""

    runs: list[tuple[int, int, int]] = []
    x, y = n, m
    for d in range(len(trace) - 1, 0, -1):
        previous = trace[d - 1]

        def at(k: int, previous: list[int] = previous, d: int = d) -> int:
            return previous[(k + d - 1) // 2]

        k = x - y
        down = k == -d or (k != d and at(k - 1) < at(k + 1))
        prior_k = k + 1 if down else k - 1
        prior_x = at(prior_k)
        edited_x = prior_x if down else prior_x + 1
        if x > edited_x:
            runs.append((edited_x, edited_x - k, x - edited_x))
        x, y = prior_x, prior_x - prior_k
    if x > 0:
        runs.append((0, 0, x))
    runs.reverse()
    return runs


def _origin(value: object) -> str:
    """The type a value written as text had, or a list's kind; empty for every other."""

    origin = getattr(value, "origin", "")
    return origin if isinstance(origin, str) else ""


def _drawn_alike(old: object, new: object) -> bool:
    """Whether two scalars draw as the same row: their JSON text is the same."""

    if _container(old) is not None or _container(new) is not None:
        return False
    return json.dumps(old) == json.dumps(new)


def _container(value: object) -> Literal["map", "list"] | None:
    if isinstance(value, dict):
        return "map"
    if isinstance(value, list):
        return "list"
    return None


def _key(key: object) -> str:
    """A mapping key as text, keeping its type: JSON's keys are strings, and the typed
    loader writes YAML's others as :class:`TypedText`."""

    if isinstance(key, str):
        safe = json_safe_scalar(key)
        return key if safe is key else TypedText(str(safe), "str")
    return TypedText(json.dumps(key), type(key).__name__)


def _number_text(value: object) -> str | None:
    """A number's JSON text when a JavaScript number would draw it otherwise, else None."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if abs(value) > _SAFE_INTEGER else None
    if isinstance(value, float) and value.is_integer() and abs(value) < _JS_EXPONENT:
        return json.dumps(value)
    return None


def _parse(data: bytes, fmt: Format, pair_bytes: int, hidden: list[_Hiding]) -> object:
    """One side as the tree view reads it; each JSON value a key written again hides is
    appended to *hidden*."""

    text = decode_text(data)
    try:
        if fmt == "json":
            try:
                return json.loads(text, object_pairs_hook=_last_wins(hidden))
            except json.JSONDecodeError:
                hidden.clear()
            if pair_bytes > JSONC_MAX_BYTES:
                raise _OverBudget("JSONC input bytes")
            import json5

            # JSONC, as the tree view reads it.
            return json5.loads(text, object_pairs_hook=_last_wins(hidden))
        if pair_bytes > SLOW_PARSE_MAX_BYTES:
            raise _OverBudget("YAML input bytes")
        documents = load_bounded_yaml_documents(
            text,
            max_expanded_size=4 * SLOW_PARSE_MAX_BYTES,
            max_nodes=_MAX_YAML_NODES,
            typed=True,
        )
        value = collapse_yaml_documents(documents)
        if sum(document is not None for document in documents) > 1:
            # The tree view draws the documents as a list, which a list is not.
            value = _Stream(cast("list[object]", value))
        return value
    except (_OverBudget, _Unsupported):
        raise
    except BoundedYamlError as exc:
        if exc.over_budget:
            raise _OverBudget(str(exc)) from exc
        raise _Unsupported(str(exc)) from exc
    except Exception as exc:
        # Whatever the parsers raise on malformed input: the tree view shows Source then.
        raise _Unsupported(type(exc).__name__) from exc


def _visible(entries: Sequence[StructuredDiffEntry]) -> bool:
    return any(entry["change"] != "context" for entry in entries)


def unavailable_structured_diff(
    status: Literal["unsupported", "too_large"], reason: StructuredRefusal | None = None
) -> StructuredDiffProjection:
    """A projection that refuses, with no partial tree, and *reason* where one is known."""

    refusal: StructuredDiffProjection = {
        "version": STRUCTURED_DIFF_VERSION,
        "status": status,
        "root": [],
        "source_only": False,
    }
    if reason is not None:
        refusal["reason"] = reason
    return refusal


def structured_format(ext: str) -> Format | None:
    """The format a logical extension names, as the structured plugin claims it, or ``None``."""

    return _FORMATS.get(ext.lower())


def structured_byte_budget(fmt: Format) -> int:
    """Both sides' bytes a pair of *fmt* may hold, which the route reads at most."""

    return STRUCTURED_DIFF_MAX_BYTES if fmt == "json" else SLOW_PARSE_MAX_BYTES


def _project(old: bytes | None, new: bytes | None, fmt: Format) -> StructuredDiffProjection:
    pair_bytes = len(old or b"") + len(new or b"")
    if pair_bytes > structured_byte_budget(fmt):
        raise _OverBudget("structured input bytes")
    if old is not None and new is not None and old == new:
        # A rename or a mode change: nothing to draw, as Markdown refuses a patch with no
        # hunks, and the page says that the content did not change.
        raise _Unchanged("both sides are the same bytes")
    projection = _Projection()
    before, old_hidden = (_MISSING, []) if old is None else projection.side(old, fmt, pair_bytes)
    after, new_hidden = (_MISSING, []) if new is None else projection.side(new, fmt, pair_bytes)
    if old_hidden != new_hidden:
        # A value the tree does not draw, under a key written twice, changed.
        projection.hidden = True
    root: list[StructuredDiffEntry] = []
    projection.merge(root, None, before, after)
    return {
        "version": STRUCTURED_DIFF_VERSION,
        "status": "ready",
        "format": fmt,
        "root": root,
        "source_only": (
            (projection.hidden or not _visible(root))
            if old is not None and new is not None
            # An added or a deleted file: the one side's tree draws no value a key written
            # again hides.
            else bool(old_hidden or new_hidden)
        ),
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
    except _Unchanged:
        return unavailable_structured_diff("unsupported", "no_changes")
    except _Unsupported:
        return unavailable_structured_diff("unsupported")


def warm_structured_projection() -> None:
    """Import and run every reader once, so a child's first YAML or JSON file does not."""

    project_structured_diff(old=b"a: [1]\n", new=b"a: [1, 2]\n", fmt="yaml")
    project_structured_diff(old=b'{"a": 1}', new=b"{a: 2, // c\n}", fmt="json")
