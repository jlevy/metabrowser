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

from collections.abc import Iterable

from metabrowser.diff.format import FileChange
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.fs_paths import derive_ext
from metabrowser.inventory_engine.contract import ascii_casefold


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
