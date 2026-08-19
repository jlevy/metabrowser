"""Patch-file source: git-shaped input in, valid File Diff Format out."""

from __future__ import annotations

import textwrap

from metabrowser.diff.adapters.patch_file import parse_unified_patch
from metabrowser.diff.apply import TreeSnapshot, apply_change_set
from metabrowser.diff.format import Availability, ChangeKind


def _patch(text: str) -> bytes:
    return textwrap.dedent(text).lstrip("\n").encode()


def test_modify_with_context_and_counts() -> None:
    document = parse_unified_patch(
        _patch(
            """
            diff --git a/a.py b/a.py
            index 1111111..2222222 100644
            --- a/a.py
            +++ b/a.py
            @@ -1,2 +1,2 @@ def f():
             def f():
            -    return 1
            +    return 2
            """
        )
    )
    change = document.manifest.files[0]
    assert change.kind is ChangeKind.modified
    assert (change.additions, change.deletions) == (1, 1)
    hunk = document.patches["f1"].hunks[0]
    assert hunk.heading == "def f():"
    assert [line.op.value for line in hunk.lines] == ["context", "del", "add"]
    assert document.manifest.totals.exact


def test_added_and_deleted_files_via_dev_null() -> None:
    document = parse_unified_patch(
        _patch(
            """
            diff --git a/new.txt b/new.txt
            new file mode 100644
            --- /dev/null
            +++ b/new.txt
            @@ -0,0 +1,1 @@
            +hello
            diff --git a/gone.txt b/gone.txt
            deleted file mode 100644
            --- a/gone.txt
            +++ /dev/null
            @@ -1,1 +0,0 @@
            -bye
            """
        )
    )
    added, deleted = document.manifest.files
    assert added.kind is ChangeKind.added and added.old is None
    assert added.new is not None and added.new.path == "new.txt"
    assert deleted.kind is ChangeKind.deleted and deleted.new is None


def test_rename_with_mode_change_and_similarity() -> None:
    document = parse_unified_patch(
        _patch(
            """
            diff --git a/run b/tools/run
            old mode 100644
            new mode 100755
            similarity index 90%
            rename from run
            rename to tools/run
            --- a/run
            +++ b/tools/run
            @@ -1,1 +1,2 @@
             #!/bin/sh
            +set -e
            """
        )
    )
    change = document.manifest.files[0]
    assert change.kind is ChangeKind.renamed
    assert change.similarity == 90
    assert change.old is not None and change.old.mode.value == "100644"
    assert change.new is not None and change.new.mode.value == "100755"


def test_binary_files_are_elided_not_failed() -> None:
    document = parse_unified_patch(
        _patch(
            """
            diff --git a/logo.png b/logo.png
            new file mode 100644
            Binary files /dev/null and b/logo.png differ
            """
        )
    )
    change = document.manifest.files[0]
    assert change.binary and change.availability is Availability.binary
    assert "f1" not in document.patches
    assert not document.manifest.totals.exact


def test_no_newline_marker_attaches_to_previous_line() -> None:
    document = parse_unified_patch(
        _patch(
            """
            diff --git a/end.txt b/end.txt
            --- a/end.txt
            +++ b/end.txt
            @@ -1,1 +1,1 @@
            -old
            \\ No newline at end of file
            +new
            \\ No newline at end of file
            """
        )
    )
    lines = document.patches["f1"].hunks[0].lines
    assert [line.no_newline for line in lines] == [True, True]


def test_non_utf8_quoted_path_keeps_bytes() -> None:
    raw = (
        b'diff --git "a/calf\\351.txt" "b/calf\\351.txt"\n'
        b"new file mode 100644\n"
        b"--- /dev/null\n"
        b'+++ "b/calf\\351.txt"\n'
        b"@@ -0,0 +1,1 @@\n"
        b"+hi\n"
    )
    document = parse_unified_patch(raw)
    new = document.manifest.files[0].new
    assert new is not None
    assert new.path_b64 is not None
    import base64

    assert base64.b64decode(new.path_b64) == b"calf\xe9.txt"


def test_malformed_hunk_becomes_unsupported_not_an_exception() -> None:
    document = parse_unified_patch(
        _patch(
            """
            diff --git a/a.txt b/a.txt
            --- a/a.txt
            +++ b/a.txt
            @@ -1,5 +1,1 @@
            -only one line
            """
        )
    )
    change = document.manifest.files[0]
    assert change.availability is Availability.unsupported
    assert "f1" not in document.patches


def test_parsed_patch_survives_the_apply_oracle() -> None:
    document = parse_unified_patch(
        _patch(
            """
            diff --git a/x.txt b/x.txt
            --- a/x.txt
            +++ b/x.txt
            @@ -1,2 +1,2 @@
             keep
            -old
            +new
            """
        )
    )
    base = TreeSnapshot.from_corpus(
        {
            "entries": {
                "x.txt": {"entry_type": "file", "mode": "100644", "content_b64": "a2VlcApvbGQK"}
            }
        }
    )
    produced = apply_change_set(document, base)
    assert produced.entries["x.txt"].content == b"keep\nnew\n"
