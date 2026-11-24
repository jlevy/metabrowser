"""The Treemap's compact rollup decoder against the route's two encodings.

The route answers one folder in the ordinary encoding and in ``encoding=compact``, with
and without gitignored nodes, at a budget that covers it and one that leaves folders
unexpanded and siblings in ``rest``, and ``tests/dom/treemap-rollup-decode-behavior.js`` holds,
with the production decoder, that each compact body decodes to the ordinary body asked
for with the same options.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

from metabrowser import server
from tests.inventory_harness import inventory_harness
from tests.required_tools import require_node
from tests.test_rollup_route import _body

REPO_ROOT = Path(__file__).resolve().parent.parent
BEHAVIOR_JS = Path(__file__).resolve().parent / "dom" / "treemap-rollup-decode-behavior.js"


def _fixture(root: Path) -> None:
    """Folders of several file types, nested, some gitignored, some without extensions."""
    (root / ".git").mkdir()
    (root / ".gitignore").write_text("build/\n*.log\n")
    for folder, files in {
        "src": {"a.py": 640, "b.py": 120, "c.ts": 300, "Makefile": 40},
        "src/deep/deeper": {"x.json": 80, "y.md": 9},
        "docs": {"guide.md": 2048, "notes.txt": 12, "run.log": 700},
        "build": {"out.bin": 5000, "out.map": 900},
        "": {"README.md": 400, "trace.log": 60},
    }.items():
        directory = root / folder
        directory.mkdir(parents=True, exist_ok=True)
        for name, size in files.items():
            (directory / name).write_text("x" * size)


def test_compact_rollups_decode_to_the_ordinary_rollup(tmp_path: Path) -> None:
    require_node()
    served = tmp_path / "served"
    served.mkdir()
    _fixture(served)
    server._set_root_dir(served)
    base = {"path": "", "depth": "max", "top": "max", "ext_rank": "dual"}

    async def run() -> list[dict[str, Any]]:
        async with inventory_harness(served) as harness:
            bodies: list[dict[str, Any]] = []
            for nodes in ("max", "3"):
                for ignored in ("include", "exclude"):
                    for encoding in ("ordinary", "compact"):
                        query = {**base, "nodes": nodes, "ignored": ignored}
                        if encoding == "compact":
                            query["encoding"] = "compact"
                        bodies.append(await _body(harness, query))
            return bodies

    bodies = asyncio.run(run())

    def ignored_paths(node: dict[str, Any]) -> list[str]:
        own = [node["path"]] if node.get("gitignored") else []
        return own + [path for child in node.get("children") or [] for path in ignored_paths(child)]

    # The include bodies draw ignored nodes and the exclude ones none, so each pair
    # decodes a different tree.
    def walk(node: dict[str, Any]) -> list[dict[str, Any]]:
        return [node, *(found for child in node.get("children") or [] for found in walk(child))]

    assert ignored_paths(bodies[0]["node"]), "the fixture serves no gitignored node"
    assert not ignored_paths(bodies[2]["node"])
    # The small budget leaves a folder unexpanded and a sibling in ``rest``, in both
    # encodings, so the decoder meets both.
    for small in bodies[4:]:
        folders = [node for node in walk(small["node"]) if node["type"] == "dir"]
        assert any(node["children"] is None for node in folders), small
        assert any("rest" in node for node in folders), small
    paths: list[str] = []
    for index, body in enumerate(bodies):
        written = tmp_path / f"rollup-{index}.json"
        written.write_text(json.dumps(body))
        paths.append(str(written))
    result = subprocess.run(
        ["node", str(BEHAVIOR_JS), str(REPO_ROOT), *paths],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"treemap rollup decode failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "treemap rollup decode OK" in result.stdout
