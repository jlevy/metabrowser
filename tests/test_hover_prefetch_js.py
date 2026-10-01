"""Which tree rows a hover prefetches, on a served folder and on a pinned revision.

Hovering a file row fetches its ``/api/file`` envelope ahead of the click. Two kinds
of row are left out. A JSONL file: ``/api/file`` answers one with every line parsed
into events and not with a bounded text window, so the request costs a whole-file
parse and a payload of the whole file for a row the pointer only crossed. And a file
over the prefetch size cap.

Every layer here is the production one. The rows' data comes from the production
``/api/tree``, event stream and container hook for real files; the rows are drawn by
the production renderers, and the decision is the production ``shouldPrefetchFile``
reading what they wrote (``tests/dom/hover-prefetch-behavior.js``); and it is checked
against the production ``/api/file``: a file the server parses as JSONL is not
prefetched. The rule went wrong once through a renderer: a row gained ``data-ext``,
the rule read it, and a compound name got through.
"""

from __future__ import annotations

import asyncio
import gzip
import json
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import server as proc_browser
from metabrowser.events import _event_to_dict
from metabrowser.git.tree_source import GitPath
from metabrowser.plugin_loader.discovery import _try_load_plugin
from metabrowser.plugin_loader.static_assets import build_plugin_routes
from tests.git_pin_harness import fast_import_store, pinned_client
from tests.golden_harness import run_session
from tests.inventory_harness import inventory_harness
from tests.test_api_logical_fields import _call_file, _call_tree

EVENT = b'{"type":"assistant","message":{"role":"assistant","content":[]}}\n'

# Names ending ``.jsonl``, with and without more before the suffix. v0.11.0 skipped
# every one of them on a served folder.
JSONL_NAMES = (
    "plain.jsonl",
    "run.codex.jsonl",
    "events.2026-01-01.jsonl",
    "UPPER.JSONL",
    "a.b.c.jsonl",
)
# The same content behind a compression suffix: the inner name decides.
COMPRESSED_JSONL_NAMES = ("events.jsonl.gz", "run.codex.jsonl.gz")
OTHER_NAMES = ("README.md", "data.json", "bundle.min.js", "notes.jsonl.txt", "jsonl")

# app.js's FILE_PREFETCH_MAX_BYTES; the session reports the one it lifted.
PREFETCH_CAP = 512 * 1024
AT_CAP, OVER_CAP = "at-cap.md", "over-cap.md"

# A patch file is a container: its changed files are child rows under it, and a child
# row carries its path and nothing else.
PATCH = (
    b"diff --git a/logs/Run.JSONL b/logs/Run.JSONL\n"
    b"--- a/logs/Run.JSONL\n"
    b"+++ b/logs/Run.JSONL\n"
    b"@@ -1,1 +1,1 @@\n"
    b"-{}\n"
    b"+[]\n"
    b"diff --git a/src/app.py b/src/app.py\n"
    b"--- a/src/app.py\n"
    b"+++ b/src/app.py\n"
    b"@@ -1,1 +1,1 @@\n"
    b"-old\n"
    b"+new\n"
)

_DIFF_DIR = Path(proc_browser.__file__).resolve().parent / "builtin_plugins" / "diff"


def _file_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for node in nodes:
        if node["type"] == "file":
            found.append(node)
        found.extend(_file_nodes(node.get("children") or []))
    return found


def _not_prefetched(rows: list[dict[str, Any]]) -> set[str]:
    return {row["path"] for row in rows if not row["prefetch"]}


def _live_entries(root: Path) -> list[dict[str, Any]]:
    """Every file as the event stream sends it, which is what a live-inserted row is drawn from."""

    async def read() -> list[dict[str, Any]]:
        async with inventory_harness(root) as harness:
            snapshot = await harness.bus.snapshot("all-known")
            return _event_to_dict(snapshot)["entries"]

    return [entry for entry in asyncio.run(read()) if entry["type"] == "file"]


def _container_children(path: str) -> list[dict[str, Any]]:
    plugin = _try_load_plugin(_DIFF_DIR, source="builtin:test")
    assert plugin is not None and not isinstance(plugin, str), plugin
    client = TestClient(Starlette(routes=build_plugin_routes([plugin])))
    response = client.get("/api/plugin/diff/children", params={"path": path})
    assert response.status_code == 200, response.text
    return response.json()["children"]


def test_a_served_folder_prefetches_no_file_the_server_parses_as_jsonl(tmp_path: Path) -> None:
    for name in (*JSONL_NAMES, *OTHER_NAMES):
        (tmp_path / name).write_bytes(EVENT)
    for name in COMPRESSED_JSONL_NAMES:
        (tmp_path / name).write_bytes(gzip.compress(EVENT))
    # A directory named like a log does not make its files logs.
    (tmp_path / "logs.jsonl").mkdir()
    (tmp_path / "logs.jsonl" / "notes.md").write_bytes(b"# notes\n")
    (tmp_path / AT_CAP).write_bytes(b"x" * PREFETCH_CAP)
    (tmp_path / OVER_CAP).write_bytes(b"x" * (PREFETCH_CAP + 1))
    (tmp_path / "change.patch").write_bytes(PATCH)
    proc_browser._set_root_dir(tmp_path)
    every_file = {
        *JSONL_NAMES,
        *COMPRESSED_JSONL_NAMES,
        *OTHER_NAMES,
        "logs.jsonl/notes.md",
        AT_CAP,
        OVER_CAP,
        "change.patch",
    }

    nodes = _file_nodes(_call_tree()["tree"])
    live = _live_entries(tmp_path)
    children = _container_children("change.patch")
    assert {node["path"] for node in nodes} == {entry["path"] for entry in live} == every_file
    assert [child["path"] for child in children] == [
        "change.patch/logs/Run.JSONL",
        "change.patch/src/app.py",
    ]

    session = run_session(
        "hover-prefetch-behavior.js",
        json.dumps({"tree": nodes, "live": live, "children": children}),
    )
    assert session["cap"] == PREFETCH_CAP
    tree_rows = {row["path"]: row for row in session["tree"]}
    live_rows = {row["path"]: row for row in session["live"]}
    assert set(tree_rows) == set(live_rows) == every_file

    # The row of a compound name carries the compound tail, which is why a rule that
    # compares the whole of `data-ext` with `.jsonl` lets this one through; a compressed
    # one also carries the inner extension; and a live row has only the first.
    assert (
        tree_rows["run.codex.jsonl"]["ext"] == live_rows["run.codex.jsonl"]["ext"] == ".codex.jsonl"
    )
    assert (tree_rows["events.jsonl.gz"]["ext"], tree_rows["events.jsonl.gz"]["logicalExt"]) == (
        ".jsonl.gz",
        ".jsonl",
    )
    assert (live_rows["events.jsonl.gz"]["ext"], live_rows["events.jsonl.gz"]["logicalExt"]) == (
        ".jsonl.gz",
        None,
    )

    parsed_as_jsonl = {path for path in every_file if _call_file(path)["type"] == "jsonl"}
    assert parsed_as_jsonl == {*JSONL_NAMES, *COMPRESSED_JSONL_NAMES}
    # A rendered row: nothing the server parses as JSONL, and nothing over the cap. A
    # file of exactly the cap is prefetched.
    assert _not_prefetched(session["tree"]) == parsed_as_jsonl | {OVER_CAP}
    assert (tree_rows[AT_CAP]["tipSize"], tree_rows[OVER_CAP]["tipSize"]) == (
        str(PREFETCH_CAP),
        str(PREFETCH_CAP + 1),
    )
    # A row inserted while the page is open is decided the same way, but for a
    # compressed JSONL: the event carries no inner extension, so that row is
    # prefetched, as it was in v0.11.0.
    assert _not_prefetched(session["live"]) == {*JSONL_NAMES, OVER_CAP}
    # A container's child row has only its path, whose suffix is as the patch spells it.
    assert [
        (row["path"], row["ext"], row["tipSize"], row["prefetch"]) for row in session["children"]
    ] == [
        ("change.patch/logs/Run.JSONL", None, None, False),
        ("change.patch/src/app.py", None, None, True),
    ]


def test_a_pinned_revision_prefetches_no_blob_named_jsonl(tmp_path: Path) -> None:
    """A pin's row path is a GitPath wire with no suffix, so ``data-ext`` is the signal."""

    names = ("plain.jsonl", "run.codex.jsonl", "README.md", "data.json")
    store, commit = fast_import_store(tmp_path, {name.encode(): EVENT for name in names})

    async def read() -> tuple[list[dict[str, Any]], dict[str, str]]:
        async with pinned_client(store, commit) as (client, _subject):
            tree = (await client.get("/api/tree")).json()["tree"]
            types = {
                node["name"]: (await client.get("/api/file", params={"path": node["path"]})).json()[
                    "type"
                ]
                for node in tree
            }
            return tree, types

    tree, types = asyncio.run(read())
    nodes = _file_nodes(tree)
    wire = {name: GitPath.from_display(name).to_wire() for name in names}
    assert {node["path"] for node in nodes} == set(wire.values())
    assert not any("." in node["path"] for node in nodes)

    session = run_session("hover-prefetch-behavior.js", json.dumps({"tree": nodes}))
    decisions = {row["path"]: row["prefetch"] for row in session["tree"]}

    assert decisions == {
        wire["plain.jsonl"]: False,
        wire["run.codex.jsonl"]: False,
        wire["README.md"]: True,
        wire["data.json"]: True,
    }
    # Nothing the pin's `/api/file` parses as JSONL is prefetched. A pin reads a
    # compound name as text, so the rule skips one more row than that route requires.
    assert {wire[name] for name, kind in types.items() if kind == "jsonl"} <= _not_prefetched(
        session["tree"]
    )
