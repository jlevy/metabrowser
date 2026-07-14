"""The dot-dir visibility filter has exactly one source.

Regression guard for the divergence vector where `fs_paths` (walker +
watcher) and `tree` (tree builder) each carried their own copy of the
`.logs`/`.state` allowlist: adding a visible-hidden dir to one source
would silently disagree with the other.
"""

from __future__ import annotations

from metabrowser import constants, fs_paths, tree


def test_tree_delegates_to_canonical_visibility_filter() -> None:
    # tree's _is_visible is the same callable the walker/watcher use.
    assert vars(tree)["_is_visible"] is fs_paths.is_visible


def test_visible_hidden_allowlist_comes_from_constants() -> None:
    assert frozenset({constants.LOGS_DIR, constants.STATE_DIR}) == fs_paths._VISIBLE_HIDDEN


def test_visibility_behavior_for_known_names() -> None:
    for visible in (constants.LOGS_DIR, constants.STATE_DIR, "src", "README.md", "data"):
        assert fs_paths.is_visible(visible), visible
    for hidden in (".git", ".hidden", ".env", ".venv"):
        assert not fs_paths.is_visible(hidden), hidden
