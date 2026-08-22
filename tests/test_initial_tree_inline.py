"""The shell carries the tree's first rows, so the reader does not wait for a fetch.

Time to first row was DOMContentLoaded plus the whole ``/api/tree`` request, and
during a walk that request is the slow one. Measured on a 300,000-file tree,
median of three cold loads: 1,604 ms to 242 ms. See
explorations/performance-loop/experiments/exp-004.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from unittest.mock import Mock

from metabrowser import server
from metabrowser.walker import FsEntry

STATIC_ROOT = Path(server.__file__).resolve().parent / "static"


def _index_html() -> str:
    return bytes(asyncio.run(server.index(Mock())).body).decode("utf-8")


def _inline_payload(html: str) -> dict[str, object] | None:
    match = re.search(r"window\.METABROWSER_INITIAL_TREE=(\{.*?\});</script>", html)
    if match is None:
        return None
    parsed: dict[str, object] = json.loads(match.group(1))
    return parsed


def test_the_shell_carries_the_roots_first_rows(tmp_path: Path) -> None:
    previous_root = server._resolved_root_dir()
    inventory = server.get_inventory()
    try:
        (tmp_path / "alpha").mkdir()
        (tmp_path / "beta.md").write_text("# beta\n")
        server._set_root_dir(tmp_path)
        # Populated directly rather than by running the walker: the walker owns
        # an event loop, and what this test is about is the shell reading a
        # warm index, not how the index got warm.
        inventory.clear()
        inventory.apply_walker_entries(
            [
                FsEntry.for_observed_dir(path="alpha", parent="", name="alpha"),
                FsEntry.for_observed_file(
                    path="beta.md", parent="", name="beta.md", size=7, mtime_ns=1
                ),
            ]
        )
        payload = _inline_payload(_index_html())
    finally:
        inventory.clear()
        server._set_root_dir(previous_root)

    assert payload is not None, "the shell no longer inlines the first rows"
    tree = payload["tree"]
    assert isinstance(tree, list) and tree, "inlined an empty tree"
    names = {str(node.get("name")) for node in tree if isinstance(node, dict)}
    assert {"alpha", "beta.md"} <= names


def test_the_inline_is_bounded_rather_than_the_whole_level() -> None:
    """It rides in the HTML, so every byte is on the critical path for every
    reader — including one whose root holds ten thousand entries."""
    assert server._INLINE_INITIAL_TREE_ROWS > 0
    assert server._INLINE_INITIAL_TREE_ROWS <= 500


def test_the_inline_rows_are_painted_once_and_only_unfiltered() -> None:
    """A filter is client state the server did not have when it rendered the
    page, so these rows do not describe it; and the fetch that follows is
    authoritative, so painting from the snapshot twice would be a regression
    rather than a shortcut."""
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    block = app[app.index("function renderInitialTreeRows()") :]
    block = block[: block.index("async function loadTree()")]

    assert "_inlineTreeRows = null;" in block, "the inline rows must be consumed once"
    assert "treeFilterKey()" in block, "a filtered view must not paint server-rendered rows"
    assert "filesPanelUsesRecentSource()" in block
    assert "if (!Array.isArray(rows) || rows.length === 0 || _lastTreeRender)" in block

    # And loadTree still owns the authoritative render that follows.
    load_tree = app[app.index("async function loadTree()") :][:2000]
    assert "renderInitialTreeRows()" in load_tree
    assert "await fetch(treeUrl(" in load_tree
