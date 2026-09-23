"""The source-kind session runs production browser code on what the server serves.

The shell learns its subject kind from one inline block the server writes into
every page, ``window.METABROWSER_SOURCE_KIND`` beside
``window.METABROWSER_REPOSITORY_CONTEXT``. Everything downstream -- the plugin
SDK's ``sourceKind()``, path display, tree-row names, the live event stream,
index polling, Recent, and the filter controls -- branches on that global.

``tests/dom/source-kind-session.js`` exercises those branches, and
``tests/golden/cli-ui-source-kind.tryscript.md`` pins its transcript. So that
the session consumes the real server's output rather than a global a test set
by hand, its input is ``tests/fixtures/source-kind-shell.json``: for an
attached folder and for a Git pin of the same names, the source-kind block the
in-process application served at ``/view/`` and the SPA tree it answered at
``/api/tree?depth=2``, projected to name, path, type, and children. The first
test here rebuilds both subjects and fails when the fixture no longer matches.

Regenerate the fixture after an intended change, then the transcript:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_source_kind_session.py
    npx --no-install tryscript run --update tests/golden/cli-ui-source-kind.tryscript.md
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from httpx2 import ASGITransport, AsyncClient

from metabrowser.paths_safe import ROOT_DIR, _set_root_dir
from metabrowser.server import app
from metabrowser.source import AttachedFilesystemSubject, attach_subject, reset_source_session
from tests.git_pin_harness import fast_import_store, pinned_client

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_JS = REPO_ROOT / "tests" / "dom" / "source-kind-session.js"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "source-kind-shell.json"

# The same names under both subjects. A literal percent is where a folder's
# inventory identity escapes (``%25``) and a pin's display name does not. A
# directory named like a GitPath atom is where decoding it as a wire would
# corrupt a folder's name. ``docs/guide.md`` is one ordinary nested file.
FILES: dict[bytes, bytes] = {
    b"README.md": b"# Source kinds\n",
    b"50%-off.md": b"sale\n",
    b"g1-data/note.txt": b"not a wire\n",
    b"docs/guide.md": b"# Guide\n",
}

# A deadlock guard, not a speed budget: four entries walk in milliseconds, but a
# loaded host can take seconds to schedule the walker.
_INDEX_POLL_S = 0.05
_INDEX_POLLS = 1200

_SOURCE_KIND_BLOCK = re.compile(
    r"<script>(window\.METABROWSER_(?:SOURCE_KIND|REPOSITORY_CONTEXT)=[^<]*;)</script>"
)

posix_only = pytest.mark.skipif(os.name != "posix", reason="folder identities are POSIX bytes")
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")


@asynccontextmanager
async def _folder_client(root: Path) -> AsyncGenerator[AsyncClient]:
    original = ROOT_DIR
    _set_root_dir(root)
    attach_subject(AttachedFilesystemSubject(root))
    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app, raise_app_exceptions=True)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                yield client
    finally:
        reset_source_session()
        _set_root_dir(original)


def _project(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Name, path, type, and loaded children: what the session reads from a node."""

    projected: list[dict[str, Any]] = []
    for node in nodes:
        item: dict[str, Any] = {"name": node["name"], "path": node["path"], "type": node["type"]}
        if node.get("children"):
            item["children"] = _project(node["children"])
        projected.append(item)
    return projected


async def _wait_for_index(client: AsyncClient) -> None:
    """Settle the folder's walk first, as ``metab --api`` does for index-dependent routes.

    A tree requested mid-walk can omit nested children the finished listing has.
    """

    for _attempt in range(_INDEX_POLLS):
        progress = await client.get("/api/index/progress")
        assert progress.status_code == 200, progress.text
        if progress.json().get("status") in ("done", "truncated"):
            return
        await asyncio.sleep(_INDEX_POLL_S)
    pytest.fail("the folder inventory never finished its walk")


async def _observe(client: AsyncClient) -> dict[str, Any]:
    await _wait_for_index(client)
    shell = await client.get("/view/")
    assert shell.status_code == 200
    block = _SOURCE_KIND_BLOCK.findall(shell.text)
    assert len(block) == 2, block
    tree = await client.get("/api/tree?depth=2")
    assert tree.status_code == 200, tree.text
    return {"shell": block, "tree": _project(tree.json()["tree"])}


def _served(tmp_path: Path) -> dict[str, Any]:
    folder = tmp_path / "folder"
    for name, body in FILES.items():
        target = folder / name.decode()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    (tmp_path / "git").mkdir()
    store, commit = fast_import_store(tmp_path / "git", FILES)

    async def run() -> dict[str, Any]:
        async with _folder_client(folder) as client:
            filesystem = await _observe(client)
        async with pinned_client(store, commit) as (client, _subject):
            git_revision = await _observe(client)
        return {"filesystem": filesystem, "git_revision": git_revision}

    return asyncio.run(run())


@posix_only
def test_fixture_is_what_the_server_serves_for_each_source_kind(tmp_path: Path) -> None:
    served = _served(tmp_path)
    assert served["filesystem"]["shell"][0] == 'window.METABROWSER_SOURCE_KIND="filesystem";'
    assert served["git_revision"]["shell"][0] == 'window.METABROWSER_SOURCE_KIND="git_revision";'
    rendered = json.dumps(served, indent=2, ensure_ascii=False) + "\n"
    if os.environ.get("GOLDEN_UPDATE") == "1":
        FIXTURE.write_text(rendered, encoding="utf-8")
        return
    assert FIXTURE.read_text(encoding="utf-8") == rendered, (
        "the served shell or tree changed; regenerate with GOLDEN_UPDATE=1 "
        "and update tests/golden/cli-ui-source-kind.tryscript.md"
    )


def test_source_kind_session_agrees_with_the_served_kind() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SESSION_JS)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        f"source-kind session failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    observed = json.loads(result.stdout)
    assert [kind["sourceKind"] for kind in observed] == ["filesystem", "git_revision"]
    folder, pin = observed
    assert folder["gates"]["inventoryEvents"]["eventSourcesOpened"] == 1
    assert pin["gates"]["inventoryEvents"]["eventSourcesOpened"] == 0
    assert "recency" in folder["gates"]["navFilterControls"]
    assert "recency" not in pin["gates"]["navFilterControls"]
    assert sorted(row["location"] for row in folder["rows"]) == sorted(
        row["location"] for row in pin["rows"]
    )
