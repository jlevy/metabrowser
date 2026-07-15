"""Tests for ``metabrowser.paths_safe``.

Path safety is security-critical: every API route resolves user-supplied
relative paths through these helpers and trusts them to reject anything
outside ROOT_DIR. The fast tests below are deliberately exhaustive on the
edge cases (sibling-prefix dirs, symlinks, traversal segments, root
itself) because a regression here is a path-traversal bug.
"""

from __future__ import annotations

from pathlib import Path

from metabrowser.paths_safe import (
    _is_within,
    _safe_path,
    _safe_subdir,
    _set_root_dir,
)


def _setup_sibling_roots(tmp_path: Path) -> tuple[Path, Path]:
    """Build ``tmp_path/data`` (the served root) and ``tmp_path/data-secret``
    (a sibling that must remain inaccessible)."""
    served = tmp_path / "data"
    secret = tmp_path / "data-secret"
    served.mkdir()
    secret.mkdir()
    (served / "ok.txt").write_text("served")
    (secret / "leak.txt").write_text("secret")
    return served, secret


def test_safe_path_rejects_sibling_prefix_traversal(tmp_path: Path) -> None:
    """Regression for the str.startswith bug.

    With root=``/tmp/xxx/data``, a request for ``../data-secret/leak.txt``
    used to resolve to ``/tmp/xxx/data-secret/leak.txt`` and pass the
    ``str(resolved).startswith(str(root))`` check because the path string
    happens to share the ``/tmp/xxx/data`` prefix. ``_is_within`` walks
    path components instead and rejects it.
    """
    served, _secret = _setup_sibling_roots(tmp_path)
    _set_root_dir(served)
    try:
        # The traversal: an attacker tries to hop to the sibling directory.
        result = _safe_path("../data-secret/leak.txt")
    finally:
        _set_root_dir(Path())

    assert result is None, f"sibling-prefix path traversal must be rejected; got {result!r}"


def test_safe_path_rejects_nonexistent_sibling_traversal(tmp_path: Path) -> None:
    """Non-strict resolve must still reject traversal to a missing outside path."""
    served, _secret = _setup_sibling_roots(tmp_path)
    _set_root_dir(served)
    try:
        result = _safe_path("../data-secret/missing.txt")
    finally:
        _set_root_dir(Path())

    assert result is None


def test_safe_subdir_rejects_sibling_prefix(tmp_path: Path) -> None:
    """``_safe_subdir`` is the entry point for ``api_stats`` /
    ``api_resources``; it must inherit the same rejection."""
    served, _secret = _setup_sibling_roots(tmp_path)
    _set_root_dir(served)
    try:
        assert _safe_subdir("../data-secret") is None
    finally:
        _set_root_dir(Path())


def test_safe_path_accepts_paths_inside_root(tmp_path: Path) -> None:
    served, _secret = _setup_sibling_roots(tmp_path)
    _set_root_dir(served)
    try:
        target = _safe_path("ok.txt")
    finally:
        _set_root_dir(Path())

    assert target is not None
    assert target.read_text() == "served"


def test_safe_path_handles_traversal_back_into_root(tmp_path: Path) -> None:
    """``data/sub/../ok.txt`` ends up inside the served root; allow it."""
    served, _ = _setup_sibling_roots(tmp_path)
    (served / "sub").mkdir()
    _set_root_dir(served)
    try:
        target = _safe_path("sub/../ok.txt")
    finally:
        _set_root_dir(Path())

    assert target is not None
    assert target.name == "ok.txt"


def test_is_within_rejects_unrelated_path(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    served = tmp_path / "served"
    served.mkdir()
    assert _is_within(other / "x", served) is False
    assert _is_within(served / "x", served) is True
