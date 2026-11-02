"""Patch-file source: git-shaped input in, valid File Diff Format out."""

from __future__ import annotations

import textwrap

from metabrowser.diff.adapters import patch_file
from metabrowser.diff.adapters.patch_file import parse_unified_patch
from metabrowser.diff.apply import TreeSnapshot, apply_change_set
from metabrowser.diff.format import Availability, ChangeKind, dump_document, validate_document


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
    # Binary changes contribute no lines; line totals stay exact.
    assert document.manifest.totals.exact


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


# ── Hostile-input totality (probes from the format research) ───────


def test_context_format_input_is_a_warning_not_a_crash() -> None:
    """diff -c output must come back as a value; it once escaped as a
    ValidationError because the ``---`` header line opened a section."""
    document = parse_unified_patch(
        b"*** a/x.txt\t2026-01-01\n"
        b"--- b/x.txt\t2026-01-02\n"
        b"***************\n"
        b"*** 1,2 ****\n"
        b"! old\n"
        b"  keep\n"
        b"--- 1,2 ----\n"
        b"! new\n"
        b"  keep\n"
    )
    assert document.manifest.totals.files == 0
    assert any("context-format" in warning for warning in document.resolved.warnings)


def test_posix_tab_timestamp_headers_keep_the_path() -> None:
    """GNU/POSIX ``--- path<TAB>timestamp`` headers; git C-quotes any
    tab inside a real name, so a raw tab is always the separator."""
    document = parse_unified_patch(
        b"--- a/src/app.py\t2026-01-01 10:00:00.000000000 +0000\n"
        b"+++ b/src/app.py\t2026-01-02 10:00:00.000000000 +0000\n"
        b"@@ -1,1 +1,1 @@\n"
        b"-old\n"
        b"+new\n"
    )
    change = document.manifest.files[0]
    assert change.new is not None and change.new.path == "src/app.py"
    assert change.availability.value == "ready"


def test_combined_merge_diff_is_unsupported_not_silently_empty() -> None:
    """A --cc section once parsed as a clean modified file with zero
    hunks; it must surface as unsupported instead."""
    document = parse_unified_patch(
        b"diff --cc merged.py\n"
        b"index 1111111,2222222..3333333\n"
        b"--- a/merged.py\n"
        b"+++ b/merged.py\n"
        b"@@@ -1,2 -1,2 +1,3 @@@\n"
        b"  keep\n"
        b"- one\n"
        b" -two\n"
        b"++three\n"
    )
    change = document.manifest.files[0]
    assert change.availability.value == "unsupported"
    assert change.new is not None and change.new.path == "merged.py"
    assert document.patches == {}


def test_section_with_no_usable_path_is_dropped_with_a_warning() -> None:
    document = parse_unified_patch(b"diff --git irrecoverable\n")
    assert document.manifest.totals.files == 0
    assert any("skipped" in warning for warning in document.resolved.warnings)


def test_reviewed_crash_probes_all_return_values() -> None:
    """Review finding R1: six probes that once escaped as exceptions.

    Totality is structural now — the final-validation net degrades any
    unmodelable input to a warning-bearing empty document — but five of
    the six degrade at section level, keeping their neighbors.
    """
    probes = {
        "junk-similarity": b"diff --git a/x b/x\nsimilarity index junk%\nrename from x\nrename to y\n",
        "similarity-150": b"diff --git a/x b/x\nsimilarity index 150%\nrename from x\nrename to y\n",
        "similarity-huge": (
            b"diff --git a/x b/x\nsimilarity index "
            + b"9" * 5000
            + b"%\nrename from x\nrename to y\n"
        ),
        "rename-no-similarity": b"diff --git a/x b/y\nrename from x\nrename to y\n",
        "negative-span": b"--- a/x\n+++ b/x\n@@ --1,0 +0,0 @@\n",
        "bad-octal-quote": (
            b'diff --git "a\\9zz" "b\\9zz"\n--- "a\\9zz"\n+++ "b\\9zz"\n@@ -1,1 +1,1 @@\n-a\n+b\n'
        ),
    }
    for name, data in probes.items():
        document = parse_unified_patch(data)  # must not raise
        for change in document.manifest.files:
            assert change.availability.value in ("unsupported", "ready"), name


def test_unmodelable_input_degrades_with_a_warning() -> None:
    """The structural net: junk that slips past section rules becomes an
    empty, valid document stating why — never an exception."""
    # A malformed section beside a good one: the good file survives.
    document = parse_unified_patch(
        b"diff --git a/ok.txt b/ok.txt\n--- a/ok.txt\n+++ b/ok.txt\n"
        b"@@ -1,1 +1,1 @@\n-a\n+b\n"
        b"diff --git a/x b/y\nrename from x\nrename to y\n"
    )
    kinds = {c.availability.value for c in document.manifest.files}
    assert document.manifest.totals.files == 2
    assert kinds == {"ready", "unsupported"}


def test_plain_multifile_unified_diff_splits_per_file() -> None:
    """Review finding R5: diff -ru output has no diff --git separators;
    the next file's headers must open a new section, not be eaten as
    deletion lines of the previous hunk."""
    document = parse_unified_patch(
        b"--- a/one.txt\t2026-01-01\n"
        b"+++ b/one.txt\t2026-01-02\n"
        b"@@ -1,2 +1,2 @@\n"
        b" keep\n"
        b"-old one\n"
        b"+new one\n"
        b"--- a/two.txt\t2026-01-01\n"
        b"+++ b/two.txt\t2026-01-02\n"
        b"@@ -1,1 +1,1 @@\n"
        b"-old two\n"
        b"+new two\n"
    )
    files = document.manifest.files
    assert [c.new.path for c in files if c.new] == ["one.txt", "two.txt"]
    assert all(c.availability.value == "ready" for c in files)
    assert document.manifest.totals.additions == 2


def test_authoritative_headers_beat_the_diff_git_guess() -> None:
    """Review finding R12: a filename containing " b/" defeats the
    diff --git split; the ---/+++ lines are authoritative."""
    document = parse_unified_patch(
        b"diff --git a/x b/y b/x b/y\n--- a/x b/y\n+++ b/x b/y\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    )
    change = document.manifest.files[0]
    assert change.old is not None and change.old.path == "x b/y"
    assert change.new is not None and change.new.path == "x b/y"
    assert change.availability.value == "ready"


# ── Sections with no hunks ─────────────────────────────────────────
#
# Git writes no ``---``, ``+++`` or ``@@`` for a change with no lines to show, so the
# ``diff --git`` line and the extended headers are all the section says.

_MODIFIED = (
    b"diff --git a/kept.txt b/kept.txt\n"
    b"index 1111111..2222222 100644\n"
    b"--- a/kept.txt\n+++ b/kept.txt\n"
    b"@@ -1,1 +1,1 @@\n-old\n+new\n"
)


def test_a_deleted_empty_file_keeps_the_sections_beside_it() -> None:
    """Any pull request deleting an empty ``__init__.py`` once had no Files changed."""
    document = parse_unified_patch(
        _MODIFIED
        + b"diff --git a/pkg/__init__.py b/pkg/__init__.py\n"
        + b"deleted file mode 100644\n"
        + b"index e69de29..0000000\n"
    )
    kept, gone = document.manifest.files
    assert kept.availability is Availability.ready
    assert gone.kind is ChangeKind.deleted
    assert gone.new is None
    assert gone.old is not None and gone.old.path == "pkg/__init__.py"
    assert gone.availability is Availability.ready
    assert (gone.additions, gone.deletions) == (0, 0)
    assert document.patches[gone.id].hunks == ()
    assert document.resolved.warnings == ()
    assert document.manifest.totals.exact


def test_a_deleted_binary_file_is_the_same_section_shape() -> None:
    """The second way to reach it: Git writes ``Binary files``, and no ``+++ /dev/null``."""
    document = parse_unified_patch(
        _MODIFIED
        + b"diff --git a/logo.bin b/logo.bin\n"
        + b"deleted file mode 100644\n"
        + b"index 1234567..0000000\n"
        + b"Binary files a/logo.bin and /dev/null differ\n"
    )
    assert document.manifest.totals.files == 2
    gone = document.manifest.files[1]
    assert gone.kind is ChangeKind.deleted and gone.new is None
    assert gone.binary and gone.availability is Availability.binary


def test_the_other_sections_with_no_hunks() -> None:
    document = parse_unified_patch(
        b"diff --git a/new.txt b/new.txt\n"
        b"new file mode 100644\n"
        b"index 0000000..e69de29\n"
        b"diff --git a/run.sh b/run.sh\n"
        b"old mode 100644\n"
        b"new mode 100755\n"
        b"diff --git a/was.txt b/now.txt\n"
        b"similarity index 100%\n"
        b"rename from was.txt\n"
        b"rename to now.txt\n"
        b"diff --git a/from.txt b/to.txt\n"
        b"similarity index 100%\n"
        b"copy from from.txt\n"
        b"copy to to.txt\n"
    )
    added, chmod, renamed, copied = document.manifest.files
    assert added.kind is ChangeKind.added and added.old is None
    assert chmod.kind is ChangeKind.modified
    assert chmod.old is not None and chmod.old.mode.value == "100644"
    assert chmod.new is not None and chmod.new.mode.value == "100755"
    assert renamed.kind is ChangeKind.renamed
    assert renamed.old is not None and renamed.old.path == "was.txt"
    assert renamed.new is not None and renamed.new.path == "now.txt"
    assert copied.kind is ChangeKind.copied
    assert all(change.availability is Availability.ready for change in document.manifest.files)
    assert all(patch.hunks == () for patch in document.patches.values())
    assert document.resolved.warnings == ()


def test_a_path_holding_the_prefix_needs_only_the_header() -> None:
    """The middle of ``a/P b/P`` is the separator, wherever `` b/`` also appears in P."""
    document = parse_unified_patch(
        b"diff --git a/spaced b/x.txt b/spaced b/x.txt\n"
        b"deleted file mode 100644\n"
        b"index e69de29..0000000\n"
    )
    only = document.manifest.files[0]
    assert only.old is not None and only.old.path == "spaced b/x.txt"


def test_quoted_paths_with_no_hunks_are_kept() -> None:
    """A patch written by a stock Git quotes a name that is not ASCII, each side on its own."""
    document = parse_unified_patch(
        b'diff --git "a/na\\303\\257ve.sh" "b/na\\303\\257ve.sh"\n'
        b"old mode 100644\n"
        b"new mode 100755\n"
        b'diff --git "a/say \\"hi\\".txt" "b/say \\"hi\\".txt"\n'
        b"deleted file mode 100644\n"
        b"index e69de29..0000000\n"
        b'diff --git a/plain.txt "b/na\\303\\257ve.txt"\n'
        b"similarity index 100%\n"
        b"rename from plain.txt\n"
        b'rename to "na\\303\\257ve.txt"\n'
    )
    chmod, deleted, renamed = document.manifest.files
    assert chmod.new is not None and chmod.new.path == "naïve.sh"
    assert deleted.old is not None and deleted.old.path == 'say "hi".txt'
    assert renamed.new is not None and renamed.new.path == "naïve.txt"
    assert document.resolved.warnings == ()


def test_a_section_that_fails_validation_is_named_and_the_rest_are_kept() -> None:
    """The structural net, reached directly: nothing a probe has found still reaches it."""
    good = parse_unified_patch(_MODIFIED)
    change = good.manifest.files[0]
    # A deleted change with a new side is what validation refuses.
    bad = change.model_copy(update={"id": "f2", "kind": ChangeKind.deleted})
    mixed = good.model_copy(
        update={"manifest": good.manifest.model_copy(update={"files": (change, bad)})}
    )

    kept = patch_file._without_unmodeled_sections(mixed)

    first, second = kept.manifest.files
    assert first.availability is Availability.ready and "f1" in kept.patches
    assert second.availability is Availability.unsupported and "f2" not in kept.patches
    assert kept.manifest.totals.files == 2 and not kept.manifest.totals.exact
    assert kept.resolved.warnings == (
        "1 section(s) could not be modeled and are left out: kept.txt",
    )
    # What came back is what a document has to be.
    assert validate_document(dump_document(kept)).manifest.totals.files == 2
