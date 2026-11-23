"""Whether a file is of the types a File type filter selected.

One rule for every surface that narrows by type: the Files tree on a Git revision
(``git/content_routes.py``) and a diff narrowed to the changed files of some types. The
browser's own filter (``static/filter-state.js``, ``rowMatches``) states the same rule
for rows it already holds.

The tokens are ``tree_filter.parse_types``'s vocabulary, lowercased and deduplicated.
A dotted token is a logical extension, matched against the file's compound tail
(``fs_paths.derive_ext``): ``.md`` keeps ``notes.md``. A token that names a registry
family also keeps every tail ending in it, so ``.ts`` keeps ``types.d.ts``. A token with
no dot is a whole filename, such as ``makefile``. Matching folds ASCII case only
(``ascii_casefold``).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import TypedDict

from metabrowser.diff.format import FileChange
from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.fs_paths import derive_ext
from metabrowser.inventory_engine.contract import ascii_casefold

TYPE_TALLY_LIMIT = 200
"""Rows a ranked tally keeps: the same cap as ``PythonInventoryStore.navigation_tallies``,
so a revision's menu and a folder's list the same number of extensions."""


class TypeTallyRows(TypedDict):
    """A File type menu's counts, in the rows ``/api/rollup`` and ``/api/tree`` send.

    Each row is ``[key, tracked, ignored]``. Neither a Git revision nor a comparison has
    gitignored files, so the ignored column is 0 here.
    """

    extensions: list[list[object]]
    canonical_extensions: list[list[object]]
    type_families: list[list[object]]
    type_presets: list[list[object]]


def semantic_extension_tokens(types: Iterable[str]) -> frozenset[str]:
    """The dotted tokens that name a registry family, which also match as suffixes.

    Worked out once per request and handed to each match, because classifying a token
    reads the registry.
    """

    registry = load_file_type_registry()
    return frozenset(
        token
        for token in types
        if token.startswith(".") and registry.classify("", token).family_id is not None
    )


def basename_of(path: str) -> str:
    """The last component of a ``/``-separated display path."""

    return path.rsplit("/", 1)[-1]


def name_matches_types(
    name: str,
    types: tuple[str, ...],
    *,
    semantic: frozenset[str] | None = None,
) -> bool:
    """Whether the file named *name* (a basename) is of one of *types*.

    *semantic* is ``semantic_extension_tokens(types)``, passed by a caller matching
    many files; it is worked out here when omitted.
    """

    folded_name = ascii_casefold(name)
    ext = derive_ext(name)
    semantic_tokens = semantic if semantic is not None else semantic_extension_tokens(types)
    for token in types:
        folded = ascii_casefold(token)
        if folded.startswith("."):
            if ext and (ext == folded or (folded in semantic_tokens and ext.endswith(folded))):
                return True
        elif folded_name == folded:
            return True
    return False


def change_matches_types(
    change: FileChange,
    types: tuple[str, ...],
    *,
    semantic: frozenset[str] | None = None,
) -> bool:
    """Whether a changed file is of one of *types* on either side.

    A rename from ``notes.txt`` to ``notes.md`` is of both types: a reader narrowing to
    either asked about files of that type, and this change is one on one side of it.
    """

    semantic_tokens = semantic if semantic is not None else semantic_extension_tokens(types)
    return any(
        side is not None
        and name_matches_types(basename_of(side.path), types, semantic=semantic_tokens)
        for side in (change.new, change.old)
    )


def change_sides(change: FileChange) -> tuple[tuple[str, str], ...]:
    """A changed file's distinct ``(basename, extension)`` sides, for ``type_tally``."""

    named: dict[tuple[str, str], None] = {}
    for side in (change.new, change.old):
        if side is not None:
            name = basename_of(side.path)
            named[(name, derive_ext(name))] = None
    return tuple(named)


def _ranked_rows(counts: Mapping[str, int], limit: int) -> list[list[object]]:
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [[key, count, 0] for key, count in ranked[:limit]]


def type_tally(
    files: Iterable[Sequence[tuple[str, str]]], *, limit: int = TYPE_TALLY_LIMIT
) -> TypeTallyRows:
    """Count *files* by extension, canonical extension, family, and preset.

    Each file is its ``(basename, extension)`` pairs: one for a file in a tree, and for
    a changed file the distinct names of its two sides (``change_sides``). A file counts
    once under each key any of its sides has, so a rename from ``.txt`` to ``.md``
    counts under both, as ``change_matches_types`` keeps it under both. A preset counts a
    file whose group is the preset's, or whose extension or whole name the preset lists.
    """

    registry = load_file_type_registry()
    normalized_presets: list[tuple[str, frozenset[str], frozenset[str]]] = []
    for preset in FILTER_TYPE_PRESETS:
        extensions: set[str] = set()
        names: set[str] = set()
        for value in preset["values"]:
            normalized = ascii_casefold(value)
            (extensions if normalized.startswith(".") else names).add(normalized)
        normalized_presets.append((preset["id"], frozenset(extensions), frozenset(names)))
    counters: tuple[Counter[str], Counter[str], Counter[str], Counter[str]] = (
        Counter(),
        Counter(),
        Counter(),
        Counter({preset["id"]: 0 for preset in FILTER_TYPE_PRESETS}),
    )
    extension_counts, canonical_counts, family_counts, preset_counts = counters
    for sides in files:
        if len(sides) == 1:
            # A file in a tree, or a change whose sides share a name: counted directly, as a
            # revision's every blob is, with no sets to deduplicate.
            display_name, ext = sides[0]
            name = ascii_casefold(display_name)
            classification = registry.classify(name, ext)
            if ext:
                extension_counts[ext] += 1
                canonical_counts[classification.canonical_extension or ext] += 1
                if classification.family_id is not None:
                    family_counts[classification.family_id] += 1
            for preset_id, preset_extensions, preset_names in normalized_presets:
                if (
                    preset_id == classification.group_id
                    or ext in preset_extensions
                    or name in preset_names
                ):
                    preset_counts[preset_id] += 1
            continue
        keys: tuple[set[str], set[str], set[str], set[str]] = (set(), set(), set(), set())
        for display_name, ext in sides:
            name = ascii_casefold(display_name)
            classification = registry.classify(name, ext)
            if ext:
                keys[0].add(ext)
                keys[1].add(classification.canonical_extension or ext)
                if classification.family_id is not None:
                    keys[2].add(classification.family_id)
            for preset_id, preset_extensions, preset_names in normalized_presets:
                if (
                    preset_id == classification.group_id
                    or ext in preset_extensions
                    or name in preset_names
                ):
                    keys[3].add(preset_id)
        for counter, found in zip(counters, keys, strict=True):
            counter.update(found)
    return {
        "extensions": _ranked_rows(extension_counts, limit),
        "canonical_extensions": _ranked_rows(canonical_counts, limit),
        # Every family is listed, as the inventory's tally lists them.
        "type_families": _ranked_rows(family_counts, len(family_counts)),
        "type_presets": [
            [preset["id"], preset_counts[preset["id"]], 0] for preset in FILTER_TYPE_PRESETS
        ],
    }
