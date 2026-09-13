"""Canonical browser-route validation.

The route names the address space; the path after it is written in that
space's own terms (see the Browser URL Grammar in docs/architecture.md).
"""

from __future__ import annotations

from pathlib import Path

from metabrowser.server import _set_root_dir
from metabrowser.view_routes import decode_safe_commit_route, format_commit_href

# ── The comparison address space (Browser URL Grammar) ─────────────


def test_commit_route_decodes_revision_and_inner_path() -> None:
    assert decode_safe_commit_route(b"/commit/abc123") == ("abc123", "")
    assert decode_safe_commit_route(b"/commit/abc123/") == ("abc123", "")
    assert decode_safe_commit_route(b"/commit/abc123/src/app.py") == ("abc123", "src/app.py")
    # Ref names git accepts, percent-encoded segments, and spaces.
    assert decode_safe_commit_route(b"/commit/HEAD~2/a%20b/c.md") == ("HEAD~2", "a b/c.md")
    assert decode_safe_commit_route(b"/commit/refs%2Fheads%2Fmain") == (
        "refs/heads/main",
        "",
    )


def test_commit_route_formats_a_slash_bearing_ref_as_one_segment() -> None:
    assert format_commit_href("refs/heads/main") == "/commit/refs%2Fheads%2Fmain"
    assert (
        format_commit_href("refs/heads/feature", "src/a b.py")
        == "/commit/refs%2Fheads%2Ffeature/src/a%20b.py"
    )
    assert decode_safe_commit_route(b"/commit/refs%2Fheads%2Ffeature/src/app.py") == (
        "refs/heads/feature",
        "src/app.py",
    )


def test_commit_route_refuses_malformed_and_traversing_routes() -> None:
    for probe in (
        b"/commit/",
        b"/commit//x",
        b"/commit/../etc/passwd",
        b"/commit/abc/./x",
        b"/commit/abc/../../x",
        b"/commit/%zz",
        b"/commit/refs%5Cheads%5Cmain",
        b"/commit/refs%00heads%00main",
        b"/commit/%2Frefs%2Fheads%2Fmain",
        b"/commit/main/src%2Fapp.py",
        b"/commit/main/src%5Capp.py",
        b"/commit/main/src%00app.py",
        b"/view/abc",
    ):
        assert decode_safe_commit_route(probe) is None, probe


def test_commit_inner_paths_need_not_exist_in_the_served_tree(tmp_path: Path) -> None:
    """A commit's files are addressed within the comparison, not the
    working tree: a deleted file still has a diff to show."""
    _set_root_dir(tmp_path)
    assert decode_safe_commit_route(b"/commit/abc123/deleted/long/ago.txt") == (
        "abc123",
        "deleted/long/ago.txt",
    )
