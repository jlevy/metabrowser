"""Shared Metabrowser test fixtures."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest

from metabrowser.git.process import _REPO_PINNING_GIT_VARS

# Test discovery imports the server from several module scopes. Never let an
# operator's shell or dotenv configuration alter collection or load external plugins.
os.environ["METABROWSER_PLUGINS_DIRS"] = ""

# The pre-push gate runs this suite inside a githook, and from a linked worktree git
# exports GIT_DIR there. It outranks the working directory and `git -C`, so a fixture
# that spawns git with the inherited environment acts on the developer's repository:
# its `git init` writes core.bare = true into the configuration every worktree
# shares. Scrub once, here, before any test module is imported, so a fixture that
# forgets to scrub its own calls cannot do that. A test that needs a poisoned GIT_DIR
# sets one itself. tests/test_git_hook_environment.py pins this.
for _name in _REPO_PINNING_GIT_VARS:
    os.environ.pop(_name, None)


@pytest.fixture(autouse=True)
def _reset_browser_response_caches() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Keep route response caches isolated between tests."""
    yield
    try:
        from metabrowser.server import reset_response_caches_for_tests

        reset_response_caches_for_tests()
    except Exception:
        # Defensive: never let cleanup failure mask a test failure.
        pass


class SyntheticIndexWriter:
    """Dict-like façade for building a Python provider handle in tests.

    Several rollup tests assemble an index in memory instead of on disk. The
    index keeps derived structures alongside ``_entries`` (the parent/child
    grouping and the subtree-aggregate memo), so assigning into ``_entries``
    directly would leave those out of sync and produce empty rollups. Writing
    through the real store path keeps a synthetic index behaving like a
    walked one.
    """

    __slots__ = ("_index",)

    def __init__(self, index: object) -> None:
        self._index = index

    def __setitem__(self, path: str, entry: object) -> None:
        assert getattr(entry, "path", None) == path, "entry.path must match its key"
        self._index._replace_index_entry(entry)  # type: ignore[attr-defined]
