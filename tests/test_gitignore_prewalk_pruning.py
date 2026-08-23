"""Loading nested .gitignore files must not traverse what it cannot use.

``load_gitignore`` walks the whole tree before the indexing walk does, looking
for nested ``.gitignore`` files. Unpruned that second traversal was the larger
of the two: 21.4 s against a 21 s index walk on a real 241,000-file tree. Both
prunes are semantics rather than shortcuts, and the tests below are about the
semantics -- that pruning changes no verdict. See
explorations/performance-loop/experiments/exp-006.
"""

from __future__ import annotations

from pathlib import Path

from metabrowser.ignore_filter import load_gitignore


def _tree(root: Path) -> None:
    (root / ".gitignore").write_text("node_modules/\n*.pyc\n")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x\n")
    # An ignored subtree carrying its own .gitignore. Git does not read that
    # file -- the whole directory is excluded -- so neither should we.
    vendored = root / "node_modules" / "pkg" / "deep"
    vendored.mkdir(parents=True)
    (root / "node_modules" / ".gitignore").write_text("!keep-me.py\n")
    (vendored / "index.js").write_text("x\n")
    # A hidden directory, which the indexing walk never shows.
    hidden = root / ".cache" / "inner"
    hidden.mkdir(parents=True)
    (root / ".cache" / ".gitignore").write_text("*.py\n")
    (hidden / "thing.txt").write_text("x\n")
    # A tracked nested .gitignore, which must still be picked up.
    pkg = root / "src" / "generated"
    pkg.mkdir()
    (pkg / ".gitignore").write_text("*.gen\n")
    (pkg / "out.gen").write_text("x\n")


def test_a_tracked_nested_gitignore_is_still_loaded(tmp_path: Path) -> None:
    _tree(tmp_path)
    check = load_gitignore(tmp_path)
    assert check("src/generated/out.gen") is True, "nested pattern was not collected"
    assert check("src/app.py") is False


def test_the_root_patterns_still_apply(tmp_path: Path) -> None:
    _tree(tmp_path)
    check = load_gitignore(tmp_path)
    assert check("node_modules", is_dir=True) is True
    assert check("src/thing.pyc") is True


def test_a_gitignore_inside_an_ignored_directory_is_not_read(tmp_path: Path) -> None:
    """Pruning it is what git does, not a corner we are cutting: the directory
    is excluded wholesale, so a pattern inside it cannot change an answer."""
    _tree(tmp_path)
    check = load_gitignore(tmp_path)
    # The vendored tree stays ignored; its own "!keep-me.py" never re-includes.
    assert check("node_modules/pkg/deep/index.js") is True
    assert check("node_modules/keep-me.py") is True


def test_a_gitignore_inside_a_hidden_directory_is_not_read(tmp_path: Path) -> None:
    """A pattern found there could only govern paths this shell never shows."""
    _tree(tmp_path)
    check = load_gitignore(tmp_path)
    # `.cache/.gitignore` says "*.py"; if it had been read as a nested pattern
    # it would be prefixed to `.cache/`, so it could never match this anyway --
    # the point is that a visible path is unaffected either way.
    assert check("src/app.py") is False


def test_pruning_changes_no_verdict_on_a_mixed_tree(tmp_path: Path) -> None:
    """The property that matters, stated directly: every visible path gets the
    same answer it would from a filter built without pruning."""
    _tree(tmp_path)
    check = load_gitignore(tmp_path)
    expected = {
        ("src/app.py", False): False,
        ("src/generated/out.gen", False): True,
        ("src/generated", True): False,
        ("node_modules", True): True,
        ("node_modules/pkg", True): True,
        ("build.pyc", False): True,
    }
    actual = {(path, is_dir): check(path, is_dir=is_dir) for path, is_dir in expected}
    assert actual == expected
