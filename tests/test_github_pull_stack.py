"""A stack's comparison: its identity, which files it keeps, and which layers change each.

The routes are ``tests/test_cli_github_stack_golden.py``'s, on the GitHub stand-in. These
are the rules on manifests of their own: a file two layers change, a file one layer renames
and another changes, and a key that moves with every member's pins and with the list.
"""

from __future__ import annotations

from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_stack
from metabrowser.builtin_plugins.github.pull_stack import StackPair, stack_digest, stack_scope
from metabrowser.diff.format import ChangeSetManifest, EntrySide, FileChange, Totals
from metabrowser.view_routes import decode_safe_stack_route, format_stack_href

A, B, C, D = ("a" * 40, "b" * 40, "c" * 40, "d" * 40)


def _change(file_id: str, old: str | None, new: str | None, added: int = 1) -> FileChange:
    kind = "added" if old is None else "deleted" if new is None else "modified"
    if old is not None and new is not None and old != new:
        kind = "renamed"
    return FileChange.model_construct(
        id=file_id,
        kind=kind,
        old=None if old is None else EntrySide.model_construct(path=old),
        new=None if new is None else EntrySide.model_construct(path=new),
        binary=False,
        additions=added,
        deletions=0,
    )


def _manifest(*changes: FileChange) -> ChangeSetManifest:
    return ChangeSetManifest.model_construct(
        files=changes,
        totals=Totals.model_construct(
            files=len(changes), additions=None, deletions=None, exact=False
        ),
        truncated=False,
    )


def test_the_key_moves_with_any_member_and_with_the_list() -> None:
    members = ((1, A, B), (2, B, C))
    digest = stack_digest(members)
    moved = {
        "a member's head": ((1, A, D), (2, B, C)),
        "a member's base": ((1, D, B), (2, B, C)),
        "the top's head": ((1, A, B), (2, B, D)),
        "a member added": ((1, A, B), (2, B, C), (3, C, D)),
        "a member gone": ((2, B, C),),
        "the order": ((2, B, C), (1, A, B)),
        "a renumbered member": ((1, A, B), (5, B, C)),
    }
    for why, other in moved.items():
        assert stack_digest(other) != digest, why
    assert stack_digest(((1, A, B), (2, B, C))) == digest
    pair = StackPair(7, A, C, digest, members, (True, True))
    # The restricted listing names itself apart from the two commits' own comparison.
    assert stack_scope(pair) == (f"stack-files-v1:{digest}",)


def test_only_the_layers_files_are_kept_and_each_names_its_layers() -> None:
    # Base to top: a file no layer changes (the base branch moved it, merged into a layer),
    # one two layers change, and one the bottom renames that the top then changes.
    combined = _manifest(
        _change("f1", "README.md", "README.md"),
        _change("f2", "src/app.py", "src/app.py", 3),
        _change("f3", "docs/old.md", "docs/new.md", 2),
    )
    members = (
        (
            10,
            1,
            {
                "src/app.py": "src/app.py",
                "docs/old.md": "docs/new.md",
                "docs/new.md": "docs/new.md",
            },
        ),
        (11, 2, {"src/app.py": "src/app.py", "docs/new.md": "docs/new.md"}),
    )
    kept = pull_stack._restricted(combined, members)
    assert [change.id for change in kept.files] == ["f2", "f3"]
    assert (kept.totals.files, kept.totals.additions, kept.totals.exact) == (2, 5, True)
    layers = pull_stack._layers(kept, members)
    assert [
        (
            entry["path"],
            [(layer["number"], layer["place"], layer["path"]) for layer in entry["layers"]],
        )
        for entry in layers
    ] == [
        ("src/app.py", [(10, 1, "src/app.py"), (11, 2, "src/app.py")]),
        ("docs/new.md", [(10, 1, "docs/new.md"), (11, 2, "docs/new.md")]),
    ]


def test_a_layer_names_a_file_by_its_own_path() -> None:
    # The bottom changes `lib.py` and the top renames it: the bottom's chip opens the path
    # its own Changes has, the old one.
    combined = _manifest(_change("f1", "lib.py", "core.py"))
    members = (
        (20, 1, {"lib.py": "lib.py"}),
        (21, 2, {"lib.py": "core.py", "core.py": "core.py"}),
    )
    [entry] = pull_stack._layers(pull_stack._restricted(combined, members), members)
    assert [(layer["number"], layer["path"]) for layer in entry["layers"]] == [
        (20, "lib.py"),
        (21, "core.py"),
    ]


def test_a_member_the_top_lacks_adds_no_file() -> None:
    combined = _manifest(_change("f1", "a.txt", "a.txt"), _change("f2", "b.txt", "b.txt"))
    # Only the members the top contains are read (`_member_paths`); a lacking one's own
    # file is in no member's paths here, so the comparison leaves it out.
    members = ((30, 1, {"a.txt": "a.txt"}),)
    kept = pull_stack._restricted(combined, members)
    assert [change.id for change in kept.files] == ["f1"]


@pytest.mark.parametrize(
    ("raw", "route"),
    [
        (b"/stack/7", (7, "", "")),
        (b"/stack/7/", (7, "", "")),
        (b"/stack/7/files", (7, "files", "")),
        (b"/stack/7/docs", (7, "docs", "")),
        (b"/stack/7/changes", (7, "changes", "")),
        (b"/stack/7/changes/docs/a%20b.md", (7, "changes", "docs/a b.md")),
        (b"/stack/7/files/docs/a.md", None),
        (b"/stack/7/docs/a.md", None),
        (b"/stack/7/guided", None),
        (b"/stack/7/conversation", None),
        (b"/stack/07", None),
        (b"/stack/7/changes/../x", None),
        (b"/stack/7/changes/a/", None),
        (b"/pull/7", None),
    ],
)
def test_the_stack_route_grammar(raw: bytes, route: Any) -> None:
    decoded = decode_safe_stack_route(raw)
    assert decoded == (None if route is None else tuple(route))
    if decoded is not None and (decoded.tab, decoded.file) != ("", "") and not raw.endswith(b"/"):
        assert format_stack_href(*decoded).encode() == raw


def test_format_stack_href_refuses_what_the_route_does_not_parse() -> None:
    for number, tab, file in (
        (0, "", ""),
        (7, "guided", ""),
        (7, "files", "a.md"),
        (7, "changes", "../a"),
    ):
        with pytest.raises(ValueError):
            format_stack_href(number, tab, file)
