"""Which tree rows a hover prefetches, on a served folder and on a pinned revision.

Hovering a file row fetches its ``/api/file`` envelope ahead of the click. A JSONL
file is left out: ``/api/file`` answers one with every line parsed into events and
not with a bounded text window, so the request costs a whole-file parse and a
payload of the whole file for a row the pointer only crossed.

The rows here are what the production ``/api/tree`` sends for real files, the
decision is the production ``shouldPrefetchFile``
(``tests/dom/hover-prefetch-behavior.js``), and what it is checked against is the
production ``/api/file``: a file the server parses as JSONL is not prefetched.
"""

from __future__ import annotations

import asyncio
import gzip
import json
from pathlib import Path
from typing import Any

from metabrowser import server as proc_browser
from metabrowser.git.tree_source import GitPath
from tests.git_pin_harness import fast_import_store, pinned_client
from tests.golden_harness import run_session
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


def _file_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for node in nodes:
        if node["type"] == "file":
            found.append(node)
        found.extend(_file_nodes(node.get("children") or []))
    return found


def _decisions(nodes: list[dict[str, Any]]) -> dict[str, bool]:
    rows = [
        {key: node[key] for key in ("path", "ext", "logical_ext", "size") if key in node}
        for node in nodes
    ]
    session = run_session("hover-prefetch-behavior.js", json.dumps(rows))
    # Every fixture is far under the size cap, so the cap decides nothing below.
    assert all(node["size"] < session["cap"] for node in nodes)
    return session["decisions"]


def test_a_served_folder_prefetches_no_file_the_server_parses_as_jsonl(tmp_path: Path) -> None:
    for name in (*JSONL_NAMES, *OTHER_NAMES):
        (tmp_path / name).write_bytes(EVENT)
    for name in COMPRESSED_JSONL_NAMES:
        (tmp_path / name).write_bytes(gzip.compress(EVENT))
    # A directory named like a log does not make its files logs.
    (tmp_path / "logs.jsonl").mkdir()
    (tmp_path / "logs.jsonl" / "notes.md").write_bytes(b"# notes\n")
    proc_browser._set_root_dir(tmp_path)

    nodes = _file_nodes(_call_tree()["tree"])
    by_path = {node["path"]: node for node in nodes}
    assert set(by_path) == {
        *JSONL_NAMES,
        *COMPRESSED_JSONL_NAMES,
        *OTHER_NAMES,
        "logs.jsonl/notes.md",
    }
    # The row of a compound name carries the compound tail, which is why a rule that
    # compares the whole of `data-ext` with `.jsonl` lets this one through.
    assert by_path["run.codex.jsonl"]["ext"] == ".codex.jsonl"

    decisions = _decisions(nodes)

    parsed_as_jsonl = {path for path in by_path if _call_file(path)["type"] == "jsonl"}
    assert parsed_as_jsonl == {*JSONL_NAMES, *COMPRESSED_JSONL_NAMES}
    assert {path for path, prefetch in decisions.items() if not prefetch} == parsed_as_jsonl
    assert all(decisions[path] for path in (*OTHER_NAMES, "logs.jsonl/notes.md"))


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

    decisions = _decisions(nodes)

    assert decisions == {
        wire["plain.jsonl"]: False,
        wire["run.codex.jsonl"]: False,
        wire["README.md"]: True,
        wire["data.json"]: True,
    }
    # Nothing the pin's `/api/file` parses as JSONL is prefetched. A pin reads a
    # compound name as text, so the rule skips one more row than that route requires.
    assert {wire[name] for name, kind in types.items() if kind == "jsonl"} <= {
        path for path, prefetch in decisions.items() if not prefetch
    }
