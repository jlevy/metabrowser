"""The File type filter's one matching rule (``metabrowser.file_type_match``)."""

from __future__ import annotations

import pytest

from metabrowser.diff.format import (
    Availability,
    ChangeKind,
    ContentRef,
    ContentRefKind,
    EntrySide,
    EntryType,
    FileChange,
    FileMode,
)
from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from metabrowser.file_type_match import (
    change_matches_types,
    change_sides,
    name_matches_types,
    semantic_extension_tokens,
    type_tally,
)
from metabrowser.fs_paths import derive_ext
from metabrowser.tree_filter import parse_types


@pytest.mark.parametrize(
    ("name", "raw", "expected"),
    [
        ("notes.md", ".md", True),
        ("notes.md", ".py", False),
        # ASCII case folds on both sides.
        ("PHOTO.JPG", ".jpg", True),
        ("photo.jpg", ".JPG", True),
        # A family's token keeps every compound tail ending in it.
        ("types.d.ts", ".ts", True),
        ("bundle.min.js", ".js", True),
        # A compound token matches its own tail exactly.
        ("bundle.min.js", ".min.js", True),
        ("app.js", ".min.js", False),
        # A token that names no family is not a suffix of a longer tail.
        ("archive.tar.zzq", ".zzq", False),
        ("thing.zzq", ".zzq", True),
        # A bare token is a whole filename, not a suffix.
        ("Makefile", "makefile", True),
        ("Makefile.am", "makefile", False),
        # A leading dot belongs to the basename: .gitignore has no extension.
        (".gitignore", ".gitignore", False),
        (".gitignore", "", False),
        # Any one of several tokens is enough.
        ("README.md", ".py,.md", True),
    ],
)
def test_name_matches_types(name: str, raw: str, expected: bool) -> None:
    types = parse_types([raw])
    assert name_matches_types(name, types) is expected
    assert name_matches_types(name, types, semantic=semantic_extension_tokens(types)) is expected


def test_no_types_match_nothing() -> None:
    """The caller decides that no selection is the whole set; the matcher keeps nothing."""

    assert name_matches_types("notes.md", ()) is False


def test_semantic_tokens_are_the_dotted_family_tokens() -> None:
    types = parse_types([".ts,.zzq,makefile"])
    assert semantic_extension_tokens(types) == frozenset({".ts"})


def _side(path: str) -> EntrySide:
    return EntrySide(
        path=path,
        entry_type=EntryType.file,
        mode=FileMode("100644"),
        content=ContentRef(kind=ContentRefKind.git_object, oid="0" * 40),
    )


def _change(kind: ChangeKind, *, old: str | None = None, new: str | None = None) -> FileChange:
    return FileChange(
        id=f"{old}->{new}",
        kind=kind,
        old=None if old is None else _side(old),
        new=None if new is None else _side(new),
        similarity=90 if kind in (ChangeKind.renamed, ChangeKind.copied) else None,
        binary=False,
        availability=Availability.ready,
    )


@pytest.mark.parametrize(
    ("change", "raw", "expected"),
    [
        (_change(ChangeKind.added, new="docs/guide.md"), ".md", True),
        (_change(ChangeKind.deleted, old="docs/guide.md"), ".md", True),
        (_change(ChangeKind.modified, old="src/app.py", new="src/app.py"), ".md", False),
        # A rename across types is of both.
        (_change(ChangeKind.renamed, old="notes.txt", new="notes.md"), ".md", True),
        (_change(ChangeKind.renamed, old="notes.txt", new="notes.md"), ".txt", True),
        (_change(ChangeKind.renamed, old="notes.txt", new="notes.md"), ".py", False),
        # The basename decides, not a folder that looks like an extension.
        (_change(ChangeKind.added, new="pkg.md/main.py"), ".md", False),
        (_change(ChangeKind.added, new="build/Makefile"), "makefile", True),
    ],
)
def test_change_matches_types(change: FileChange, raw: str, expected: bool) -> None:
    assert change_matches_types(change, parse_types([raw])) is expected


def _rows(rows: list[list[object]]) -> dict[object, object]:
    return {row[0]: row[1] for row in rows}


def test_type_tally_counts_a_file_once_under_each_type_either_side_has() -> None:
    changes = [
        _change(ChangeKind.modified, old="README.md", new="README.md"),
        _change(ChangeKind.renamed, old="notes.txt", new="notes.md"),
        _change(ChangeKind.added, new="src/app.py"),
        _change(ChangeKind.added, new="build/Makefile"),
    ]
    tally = type_tally(change_sides(change) for change in changes)
    # README.md once (its two sides are one name), and the rename under both types.
    assert _rows(tally["extensions"]) == {".md": 2, ".txt": 1, ".py": 1}
    assert all(row[2] == 0 for row in tally["extensions"])
    families = _rows(tally["type_families"])
    assert families["markdown"] == 2
    assert families["plain-text"] == 1
    presets = _rows(tally["type_presets"])
    # Every preset has a row, in the menu's order, counted or not.
    assert [row[0] for row in tally["type_presets"]] == [p["id"] for p in FILTER_TYPE_PRESETS]
    # The documentation group holds the Markdown, the rename, and nothing else.
    assert presets["docs"] == 2


def test_type_tally_ranks_by_count_then_key_and_honors_its_limit() -> None:
    names = ["a.py", "b.py", "c.md", "d.rs", "e.rs", "f.rs"]
    tally = type_tally(((name, derive_ext(name)),) for name in names)
    assert tally["extensions"] == [[".rs", 3, 0], [".py", 2, 0], [".md", 1, 0]]
    limited = type_tally((((name, derive_ext(name)),) for name in names), limit=1)
    assert limited["extensions"] == [[".rs", 3, 0]]


def test_type_tally_of_nothing_still_lists_every_preset() -> None:
    tally = type_tally([])
    assert tally["extensions"] == []
    assert tally["type_families"] == []
    assert len(tally["type_presets"]) == len(FILTER_TYPE_PRESETS)
