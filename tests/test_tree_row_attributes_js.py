"""The attributes on a tree row, as the HTML parser reads the markup app.js writes.

A row is written as a string. A helper that returns a whole attribute, quotes included,
followed by a template that closes a quote of its own, writes ``…"">``. The parser reads
that as one more attribute, named ``"``: every folder row in the page was
``<div "="" …>``, and ``element.getAttributeNames()`` said so, while a search of the
markup for ``name="value"`` pairs found nothing wrong.

Every layer here is the production one. The rows' data comes from the production
``/api/tree``, event stream and container hook for real files, on a served folder and
on a pinned revision; the rows are drawn by the production renderers; and each start tag
is tokenized by the HTML standard's rules (``tests/dom/tree-row-attributes-behavior.js``).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import server as proc_browser
from metabrowser.events import _event_to_dict
from metabrowser.plugin_loader.discovery import _try_load_plugin
from metabrowser.plugin_loader.static_assets import build_plugin_routes
from tests.git_pin_harness import fast_import_store, pinned_client
from tests.golden_harness import run_session
from tests.inventory_harness import inventory_harness
from tests.test_api_logical_fields import _call_tree

PATCH = b"diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1,1 +1,1 @@\n-old\n+new\n"

_DIFF_DIR = Path(proc_browser.__file__).resolve().parent / "builtin_plugins" / "diff"

# What every row carries: its place in the tree, for the keyboard and for a screen reader.
TREE_ITEM = [
    "class",
    "role",
    "tabindex",
    "data-tree-kind",
    "data-tree-id",
    "data-tree-level",
    "data-tree-position",
    "data-tree-set-size",
    "aria-level",
    "aria-posinset",
    "aria-setsize",
    "aria-labelledby",
]
FOLDER = [*TREE_ITEM, "aria-expanded", "aria-owns", "data-action", "data-path"]
FOLDER_TIP = ["data-tip-type", "data-tip-name"]
FOLDER_TALLIES = ["data-tip-files", "data-tip-size", "data-tip-mtime"]


def _rows(elements: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [element for element in elements if kind in element["classes"]]


def _live_entries(root: Path) -> list[dict[str, Any]]:
    """Every entry as the event stream sends it, which is what a live row is drawn from.

    The served root is an entry too, and it is the one the page draws no row for.
    """

    async def read() -> list[dict[str, Any]]:
        async with inventory_harness(root) as harness:
            snapshot = await harness.bus.snapshot("all-known")
            return _event_to_dict(snapshot)["entries"]

    return [entry for entry in asyncio.run(read()) if entry["path"]]


def _container_children(path: str) -> list[dict[str, Any]]:
    plugin = _try_load_plugin(_DIFF_DIR, source="builtin:test")
    assert plugin is not None and not isinstance(plugin, str), plugin
    client = TestClient(Starlette(routes=build_plugin_routes([plugin])))
    response = client.get("/api/plugin/diff/children", params={"path": path})
    assert response.status_code == 200, response.text
    return response.json()["children"]


def test_a_served_folders_rows_carry_only_the_attributes_their_templates_name(
    tmp_path: Path,
) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_bytes(b"# a\n")
    (tmp_path / "docs" / "deep").mkdir()
    (tmp_path / "docs" / "deep" / "b.md").write_bytes(b"# b\n")
    (tmp_path / "hollow").mkdir()
    (tmp_path / "notes.txt").write_bytes(b"notes\n")
    (tmp_path / "change.patch").write_bytes(PATCH)
    (tmp_path / "link").symlink_to("notes.txt")
    proc_browser._set_root_dir(tmp_path)

    tree = _call_tree()["tree"]
    live = _live_entries(tmp_path)
    children = _container_children("change.patch")
    assert {node["type"] for node in tree} == {"dir", "file", "symlink"}
    assert {entry["type"] for entry in live} == {"dir", "file", "symlink"}

    session = run_session(
        "tree-row-attributes-behavior.js",
        json.dumps(
            {
                "tree": tree,
                "live": live,
                "children": children,
                "containers": proc_browser._container_exts(),
            }
        ),
    )

    # No element any renderer wrote has a name that is not a name, or a name twice.
    assert session["malformed"] == []

    # A folder row, drawn from `/api/tree` and drawn live: exactly these, in this order.
    folders = _rows(session["tree"], "tree-folder")
    assert len(folders) == 3
    with_children = [row["names"] for row in folders if "aria-expanded" in row["names"]]
    assert with_children == [[*FOLDER, *FOLDER_TIP, *FOLDER_TALLIES]] * 2
    # A folder with nothing in it has no group to own or to expand.
    (hollow,) = (row["names"] for row in folders if "aria-expanded" not in row["names"])
    assert hollow == [
        *TREE_ITEM,
        "data-action",
        "data-path",
        *FOLDER_TIP,
        *FOLDER_TALLIES,
    ]
    live_folders = _rows(session["live"], "tree-folder")
    assert len(live_folders) == 3
    assert all(row["names"][-5:] == [*FOLDER_TIP, *FOLDER_TALLIES] for row in live_folders)

    # Every kind of row was drawn, so every template was read.
    for group, kinds in (
        ("tree", ("tree-file", "tree-symlink", "tree-container", "tree-children")),
        ("live", ("tree-file", "tree-symlink", "tree-children")),
        ("children", ("tree-container-child",)),
    ):
        for kind in kinds:
            assert _rows(session[group], kind), (group, kind)


def test_a_pinned_revisions_folder_row_ends_at_its_last_tally(tmp_path: Path) -> None:
    """A pin's tree has no modification times, so its folder row has one attribute fewer.

    The helper that writes a tally returns nothing for a number the subject does not
    have, and the row then ends one attribute sooner, at the same closing bracket.
    """

    store, commit = fast_import_store(
        tmp_path, {b"docs/a.md": b"# a\n", b"docs/deep/b.md": b"# b\n", b"README.md": b"# r\n"}
    )

    async def read() -> list[dict[str, Any]]:
        async with pinned_client(store, commit) as (client, _subject):
            return (await client.get("/api/tree")).json()["tree"]

    tree = asyncio.run(read())
    (docs,) = (node for node in tree if node["type"] == "dir")
    assert "mtime" not in docs and {"total_files", "total_size"} <= set(docs)

    session = run_session("tree-row-attributes-behavior.js", json.dumps({"tree": tree}))

    assert session["malformed"] == []
    folders = _rows(session["tree"], "tree-folder")
    assert len(folders) == 2
    assert all(row["names"] == [*FOLDER, *FOLDER_TIP, *FOLDER_TALLIES[:2]] for row in folders)
