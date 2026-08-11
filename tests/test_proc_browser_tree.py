"""Tests for the directory-tree builder in proc_browser.

Covers the gitignore integration, empty-directory flagging, and the lazy-load
sentinel path. Uses ``tmp_path`` with real ``.gitignore`` files rather than
mocks so pathspec behavior is exercised end-to-end.
"""

from __future__ import annotations

import inspect
import os
import subprocess
from pathlib import Path

from metabrowser import server as proc_browser
from metabrowser.server import (
    DEFAULT_TREE_DEPTH,
    MAX_TREE_DEPTH,
    _collect_trackable_files,
    _dir_tree,
    _find_git_root,
    _set_root_dir,
    _subtree_is_empty,
    _tree_depth_from_query,
    build_gitignore_check,
)


def _init_git(root: Path, *, gitignore: str = "") -> None:
    """Make *root* look like a git repo with an optional root ``.gitignore``."""
    (root / ".git").mkdir()
    if gitignore:
        (root / ".gitignore").write_text(gitignore)


def _touch(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _isolated_git_env() -> dict[str, str]:
    """Return an environment that does not target the caller's repository."""
    env = os.environ.copy()
    local_names = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.splitlines()
    for name in local_names:
        env.pop(name, None)
    return env


def test_subtree_is_empty_with_no_children() -> None:
    assert _subtree_is_empty([]) is True


def test_subtree_is_empty_with_a_file() -> None:
    assert _subtree_is_empty([{"type": "file", "name": "a"}]) is False


def test_subtree_is_not_empty_with_a_symlink() -> None:
    assert _subtree_is_empty([{"type": "symlink", "name": "linked"}]) is False


def test_subtree_is_empty_with_only_empty_dirs() -> None:
    children = [{"type": "dir", "name": "a", "empty": True}]
    assert _subtree_is_empty(children) is True


def test_subtree_is_empty_sees_through_lazy_sentinel() -> None:
    # Sentinel children carry total_files=0 as a placeholder; the empty flag
    # is what actually tells us whether the deferred subtree has content.
    sentinel_with_content = [{"type": "dir", "name": "a", "total_files": 0}]
    assert _subtree_is_empty(sentinel_with_content) is False
    sentinel_truly_empty = [{"type": "dir", "name": "a", "total_files": 0, "empty": True}]
    assert _subtree_is_empty(sentinel_truly_empty) is True


def test_find_git_root_walks_upward(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "deep" / "nested").mkdir(parents=True)
    _init_git(repo)
    assert _find_git_root(repo / "deep" / "nested") == repo.resolve()


def test_find_git_root_returns_none_outside_repo(tmp_path: Path) -> None:
    # tmp_path is typically under /private/var or /tmp, not inside a git repo.
    sub = tmp_path / "nogit"
    sub.mkdir()
    assert _find_git_root(sub) is None


def test_tree_depth_query_is_always_bounded() -> None:
    assert _tree_depth_from_query("") == DEFAULT_TREE_DEPTH
    assert _tree_depth_from_query("not-a-number") == DEFAULT_TREE_DEPTH
    assert _tree_depth_from_query("-1") == 0
    assert _tree_depth_from_query(str(MAX_TREE_DEPTH + 100)) == MAX_TREE_DEPTH


def test_tree_cold_start_uses_constant_time_child_lookup() -> None:
    source = inspect.getsource(proc_browser.api_tree)
    assert "inventory.has_direct_child(subpath)" in source
    assert 'inventory.entries(scope="all-known")' not in source


def test_build_gitignore_check_no_repo_returns_noop(tmp_path: Path) -> None:
    served = tmp_path / "plain"
    served.mkdir()
    check, git_root = build_gitignore_check(served)
    assert git_root is None
    assert check(served / "anything.txt") is False


def test_build_gitignore_check_matches_root_pattern(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo, gitignore="build/\n*.log\n")
    _touch(repo / "build" / "out.bin")
    _touch(repo / "app.log")
    _touch(repo / "app.py")

    check, git_root = build_gitignore_check(repo)
    assert git_root == repo.resolve()
    assert check(repo / "build", is_dir=True) is True
    assert check(repo / "app.log") is True
    assert check(repo / "app.py") is False


def test_build_gitignore_check_honors_nested_gitignore(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    (repo / "data").mkdir()
    (repo / "data" / ".gitignore").write_text("secret/\n")
    _touch(repo / "data" / "secret" / "oops.txt")
    _touch(repo / "data" / "public.txt")

    check, _ = build_gitignore_check(repo)
    assert check(repo / "data" / "secret", is_dir=True) is True
    assert check(repo / "data" / "public.txt") is False


def test_dir_tree_sets_gitignored_and_inherits_down(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo, gitignore="ignored/\n")
    _touch(repo / "ignored" / "child.txt")
    _touch(repo / "kept" / "file.txt")
    _set_root_dir(repo)

    try:
        check, _ = build_gitignore_check(repo)
        tree = _dir_tree(repo, ignore_check=check)
    finally:
        _set_root_dir(Path())

    by_name = {e["name"]: e for e in tree}
    assert by_name["ignored"].get("gitignored") is True
    # Children of the ignored dir inherit the flag even though file-level
    # pattern checks are skipped for perf.
    ignored_child = by_name["ignored"]["children"][0]
    assert ignored_child.get("gitignored") is True
    assert "gitignored" not in by_name["kept"]


def test_dir_tree_flags_empty_and_non_empty_dirs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    (repo / "empty").mkdir()
    (repo / "nested_empty" / "deeper").mkdir(parents=True)
    _touch(repo / "populated" / "a.txt")
    _set_root_dir(repo)

    try:
        check, _ = build_gitignore_check(repo)
        tree = _dir_tree(repo, ignore_check=check)
    finally:
        _set_root_dir(Path())

    by_name = {e["name"]: e for e in tree}
    assert by_name["empty"].get("empty") is True
    # A dir whose only descendants are more empty dirs is still empty.
    assert by_name["nested_empty"].get("empty") is True
    assert "empty" not in by_name["populated"]


def test_dir_tree_lazy_sentinel_is_not_wrongly_empty(tmp_path: Path) -> None:
    # With remaining_depth=1, children of first-level dirs become lazy
    # sentinels (total_files=0 placeholder). The parent dir's ``empty`` flag
    # must come from the sentinel's real subtree-walk, not the placeholder.
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    _touch(repo / "has_content" / "sub" / "deep.txt")
    _set_root_dir(repo)

    try:
        check, _ = build_gitignore_check(repo)
        tree = _dir_tree(repo, remaining_depth=1, ignore_check=check)
    finally:
        _set_root_dir(Path())

    top = next(e for e in tree if e["name"] == "has_content")
    assert "empty" not in top
    sentinel = top["children"][0]
    assert sentinel["children"] is None  # lazy-load marker
    assert "empty" not in sentinel  # real content down there


def test_dir_tree_propagates_gitignored_up_when_all_children_match(tmp_path: Path) -> None:
    # A dir whose only descendant is a gitignored subtree should itself
    # read as gitignored, so the UI dims the parent alongside the content.
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo, gitignore="__pycache__/\n")
    _touch(repo / "pkg" / "__pycache__" / "m.pyc")
    _touch(repo / "mixed" / "__pycache__" / "x.pyc")
    _touch(repo / "mixed" / "real.py")
    _set_root_dir(repo)

    try:
        check, _ = build_gitignore_check(repo)
        tree = _dir_tree(repo, ignore_check=check)
    finally:
        _set_root_dir(Path())

    by_name = {e["name"]: e for e in tree}
    # Only gitignored content → propagate up.
    assert by_name["pkg"].get("gitignored") is True
    # Mix of gitignored + real → don't propagate.
    assert "gitignored" not in by_name["mixed"]


def test_dir_tree_propagates_gitignored_up_recursively(tmp_path: Path) -> None:
    # Propagation reaches through intermediate non-matching dirs, so a
    # grandparent whose only leaf content is gitignored gets flagged too.
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo, gitignore="__pycache__/\n")
    _touch(repo / "wrap" / "inner" / "__pycache__" / "y.pyc")
    _set_root_dir(repo)

    try:
        check, _ = build_gitignore_check(repo)
        tree = _dir_tree(repo, ignore_check=check)
    finally:
        _set_root_dir(Path())

    wrap = next(e for e in tree if e["name"] == "wrap")
    inner = wrap["children"][0]
    assert inner.get("gitignored") is True
    assert wrap.get("gitignored") is True


def test_dir_tree_lazy_sentinel_flags_gitignored_subtree(tmp_path: Path) -> None:
    # Sentinel counterpart: when the lazy boundary hides the subtree, the
    # effective-gitignored decision has to come from a walk rather than
    # the child-flag propagation the recursive path uses.
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo, gitignore="__pycache__/\n")
    _touch(repo / "wrap" / "a" / "b" / "__pycache__" / "z.pyc")
    _touch(repo / "real" / "a" / "b" / "kept.py")
    _set_root_dir(repo)

    try:
        check, _ = build_gitignore_check(repo)
        tree = _dir_tree(repo, remaining_depth=2, ignore_check=check)
    finally:
        _set_root_dir(Path())

    wrap = next(e for e in tree if e["name"] == "wrap")
    wrap_a = wrap["children"][0]
    wrap_b = wrap_a["children"][0]  # sentinel (remaining_depth=2 exhausts here)
    assert wrap_b["children"] is None
    assert wrap_b.get("gitignored") is True
    assert wrap_a.get("gitignored") is True
    assert wrap.get("gitignored") is True

    real = next(e for e in tree if e["name"] == "real")
    real_b = real["children"][0]["children"][0]
    assert real_b["children"] is None
    assert "gitignored" not in real_b
    assert "gitignored" not in real


def test_dir_tree_lazy_sentinel_flags_dir_of_only_empty_dirs(tmp_path: Path) -> None:
    # A sentinel whose subtree contains only empty subdirs must still
    # be flagged empty — deciding from `has_visible_children` alone would
    # miss this because the empty subdir is itself a "visible child".
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    (repo / "outer" / "mid" / "inner" / "deep").mkdir(parents=True)
    _set_root_dir(repo)

    try:
        check, _ = build_gitignore_check(repo)
        tree = _dir_tree(repo, remaining_depth=2, ignore_check=check)
    finally:
        _set_root_dir(Path())

    outer = next(e for e in tree if e["name"] == "outer")
    mid = outer["children"][0]
    inner = mid["children"][0]
    assert inner["children"] is None  # sentinel
    assert inner.get("empty") is True
    assert mid.get("empty") is True
    assert outer.get("empty") is True


def test_matches_git_check_ignore_behavior(tmp_path: Path) -> None:
    # Cross-validate that our checker agrees with ``git check-ignore`` itself
    # on a concrete case. Skip gracefully if git isn't available.
    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        return
    git_env = _isolated_git_env()
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=git_env)
    (repo / ".gitignore").write_text("*.log\ncache/\n")
    _touch(repo / "cache" / "a.bin")
    _touch(repo / "app.log")
    _touch(repo / "app.py")

    check, _ = build_gitignore_check(repo)

    def git_ignored(rel: str) -> bool:
        r = subprocess.run(["git", "check-ignore", "--quiet", rel], cwd=repo, env=git_env)
        return r.returncode == 0

    assert check(repo / "cache", is_dir=True) == git_ignored("cache")
    assert check(repo / "app.log") == git_ignored("app.log")
    assert check(repo / "app.py") == git_ignored("app.py")


def test_collect_trackable_files_uses_short_lived_cache(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    logs = repo / ".logs"
    logs.mkdir(parents=True)
    _touch(logs / "first.jsonl")
    _set_root_dir(repo)

    try:
        first = {p.name for p in _collect_trackable_files(repo)}
        _touch(logs / "second.jsonl")
        cached = {p.name for p in _collect_trackable_files(repo)}
        _set_root_dir(repo)
        refreshed = {p.name for p in _collect_trackable_files(repo)}
    finally:
        _set_root_dir(Path())

    assert first == {"first.jsonl"}
    assert cached == {"first.jsonl"}
    assert refreshed == {"first.jsonl", "second.jsonl"}
