"""The four built-in data hooks answer the same for a folder and a pin of it.

Each hook is served the same fixture twice: once from an attached filesystem
root, once from an immutable Git-revision pin of a tree with the same bytes.
Whatever a hook reports about the content itself has to match. What legitimately
differs is the address space -- an inventory path against a ``GitPath`` wire --
and the fingerprint, an mtime hash against a blob object id.

This is the regression guard for the content-reader port: a hook that reached
past it for a host path, or branched on the subject kind, would answer one of
these two and not the other.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from cachetools import LRUCache
from httpx2 import ASGITransport, AsyncClient

import metabrowser.builtin_plugins.structured as structured_sidekick
import metabrowser.builtin_plugins.structured.parser as structured_parser
from metabrowser import paths_safe
from metabrowser.git.tree_source import GitPath
from metabrowser.paths_safe import _set_root_dir
from metabrowser.server import app
from metabrowser.source import AttachedFilesystemSubject, attach_subject, reset_source_session
from tests.git_pin_harness import fast_import_store, overwrite_tree, pinned_client

LOG = (
    b'{"type":"system","subtype":"init","model":"claude-opus-4-20250514"}\n'
    b'{"type":"assistant","message":{"role":"assistant",'
    b'"content":[{"type":"text","text":"hello"}]}}\n'
)
CONFIG = b'{"name": "pin", "count": 2, "tags": ["a", "b"]}\n'
PATCH = (
    b"diff --git a/src/app.py b/src/app.py\n"
    b"--- a/src/app.py\n"
    b"+++ b/src/app.py\n"
    b"@@ -1,1 +1,1 @@\n"
    b"-old\n"
    b"+new\n"
    b"diff --git a/gone.txt b/gone.txt\n"
    b"deleted file mode 100644\n"
    b"--- a/gone.txt\n"
    b"+++ /dev/null\n"
    b"@@ -1,1 +0,0 @@\n"
    b"-bye\n"
)
BYTES = bytes(range(256)) * 4
FILES: dict[bytes, bytes] = {
    b"session.jsonl": LOG,
    b"config.json": CONFIG,
    b"change.patch": PATCH,
    b"refused.rej": PATCH,
    b"nul.bin": BYTES,
}

# Identity and fingerprint are the two fields that must differ between an
# inventory path and a pinned blob; everything else describes the content.
ADDRESS_FIELDS = frozenset({"path", "mtime_hash"})


@asynccontextmanager
async def _folder_client(tmp_path: Path) -> AsyncGenerator[AsyncClient, None]:
    root = tmp_path / "folder"
    root.mkdir()
    for name, body in FILES.items():
        (root / name.decode()).write_bytes(body)
    original = paths_safe.ROOT_DIR
    _set_root_dir(root)
    attach_subject(AttachedFilesystemSubject(root))
    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app, raise_app_exceptions=True)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                yield client
    finally:
        # A phase boundary, not teardown: the pin half of each test runs after this,
        # and must not find the folder still served. The folder's files are then
        # overwritten, so a pin read answered from them cannot agree by accident.
        reset_source_session()
        _set_root_dir(original)
        overwrite_tree(root)


def _wire(native: str) -> str:
    return GitPath.from_display(native).to_wire()


def _content_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in ADDRESS_FIELDS}


def _both(tmp_path: Path, route: str, native: str, **params: Any) -> tuple[Any, Any]:
    """Call one hook against a folder and against a pin of the same tree."""

    async def _run() -> tuple[Any, Any]:
        async with _folder_client(tmp_path) as client:
            folder = await client.get(route, params={"path": native, **params})
        store, commit = fast_import_store(tmp_path / "git", FILES)
        async with pinned_client(store, commit) as (client, _subject):
            pinned = await client.get(route, params={"path": _wire(native), **params})
        assert folder.status_code == 200, folder.text
        assert pinned.status_code == 200, pinned.text
        assert str(store) not in pinned.text
        return folder.json(), pinned.json()

    (tmp_path / "git").mkdir(parents=True, exist_ok=True)
    return asyncio.run(_run())


def test_binary_chunk_reports_the_same_window(tmp_path: Path) -> None:
    folder, pinned = _both(
        tmp_path, "/api/plugin/binary/chunk", "nul.bin", offset="300", limit="64"
    )
    assert base64.b64decode(folder["content_base64"]) == BYTES[300:364]
    assert _content_fields(folder) == _content_fields(pinned)
    assert folder["logical_size"] == len(BYTES)
    assert folder["path"] == "nul.bin"
    assert pinned["path"] == _wire("nul.bin")
    assert folder["mtime_hash"] != pinned["mtime_hash"]


def test_structured_parsed_reports_the_same_tree(tmp_path: Path) -> None:
    folder, pinned = _both(tmp_path, "/api/plugin/structured/parsed", "config.json")
    assert folder["parsed"] == {"name": "pin", "count": 2, "tags": ["a", "b"]}
    assert _content_fields(folder) == _content_fields(pinned)
    assert folder["size"] == len(CONFIG)


def test_structured_parsed_reports_the_stored_size_past_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past the parse cap both sources say ``truncated``, and ``size`` is the whole file's.

    Under a folder that is the size on disk; on a pin it is the blob's length. Neither
    is the number of bytes the bounded read returned.
    """

    cap = len(CONFIG) // 2
    monkeypatch.setattr(structured_sidekick, "STRUCTURED_PARSE_MAX_BYTES", cap)
    # A pin's payload is cached by blob id, and another test parses this blob whole.
    # This test's cache is its own, so neither reads what the other stored.
    monkeypatch.setattr(structured_parser, "_PAYLOAD_CACHE", LRUCache(maxsize=4))
    folder, pinned = _both(tmp_path, "/api/plugin/structured/parsed", "config.json")
    assert _content_fields(folder) == _content_fields(pinned)
    assert (folder["truncated"], folder["parsed"]) == (True, None)
    assert folder["size"] == pinned["size"] == len(CONFIG) > cap


def test_agent_log_charts_report_the_same_tallies(tmp_path: Path) -> None:
    folder, pinned = _both(tmp_path, "/api/plugin/agent-log/charts", "session.jsonl")
    assert folder["summary"]["metadata"]["adapter"] == "claude"
    # The charts payload carries no address fields at all, so it matches whole.
    assert folder == pinned


def test_diff_document_reports_the_same_change_set(tmp_path: Path) -> None:
    folder, pinned = _both(tmp_path, "/api/plugin/diff/document", "change.patch")
    assert [change["kind"] for change in folder["manifest"]["files"]] == ["modified", "deleted"]
    assert folder == pinned


def test_diff_children_list_the_same_rows(tmp_path: Path) -> None:
    folder, pinned = _both(tmp_path, "/api/plugin/diff/children", "change.patch")
    rows = [(row["name"], row["badge"]) for row in folder["children"]]
    assert rows == [("src/app.py", "M"), ("gone.txt", "D")]
    assert rows == [(row["name"], row["badge"]) for row in pinned["children"]]
    # Child addresses stay in each source's own space, rooted at the request.
    assert folder["children"][0]["path"].startswith("change.patch/")
    assert pinned["children"][0]["path"].startswith(f"{_wire('change.patch')}/")


def test_diff_document_narrows_to_one_inner_path_on_both(tmp_path: Path) -> None:
    async def _run() -> tuple[Any, Any]:
        async with _folder_client(tmp_path) as client:
            folder = await client.get(
                "/api/plugin/diff/document", params={"path": "change.patch/src/app.py"}
            )
        store, commit = fast_import_store(tmp_path / "git", FILES)
        async with pinned_client(store, commit) as (client, _subject):
            pinned = await client.get(
                "/api/plugin/diff/document",
                params={"path": f"{_wire('change.patch')}/src/app.py"},
            )
        return folder, pinned

    (tmp_path / "git").mkdir(parents=True, exist_ok=True)
    folder, pinned = asyncio.run(_run())
    assert folder.status_code == 200, folder.text
    assert pinned.status_code == 200, pinned.text
    assert [change["kind"] for change in folder.json()["manifest"]["files"]] == ["modified"]
    assert folder.json() == pinned.json()


def test_a_hook_refuses_the_other_kind_of_identity(tmp_path: Path) -> None:
    """A GitPath wire under a folder, and an inventory path under a pin, are 404."""

    async def _run() -> list[int]:
        statuses: list[int] = []
        async with _folder_client(tmp_path) as client:
            statuses.append(
                (
                    await client.get(
                        "/api/plugin/structured/parsed", params={"path": _wire("config.json")}
                    )
                ).status_code
            )
        store, commit = fast_import_store(tmp_path / "git", FILES)
        async with pinned_client(store, commit) as (client, _subject):
            statuses.append(
                (
                    await client.get(
                        "/api/plugin/structured/parsed", params={"path": "config.json"}
                    )
                ).status_code
            )
        return statuses

    (tmp_path / "git").mkdir(parents=True, exist_ok=True)
    assert asyncio.run(_run()) == [404, 404]


def _diff_responses(tmp_path: Path, route: str, native: str, inner: str = "") -> tuple[Any, Any]:
    """One diff hook's response for *native*, or a virtual child of it, on both sources."""

    suffix = f"/{inner}" if inner else ""

    async def _run() -> tuple[Any, Any]:
        async with _folder_client(tmp_path) as client:
            folder = await client.get(route, params={"path": f"{native}{suffix}"})
        store, commit = fast_import_store(tmp_path / "git", FILES)
        async with pinned_client(store, commit) as (client, _subject):
            pinned = await client.get(route, params={"path": f"{_wire(native)}{suffix}"})
        assert str(store) not in pinned.text
        return folder, pinned

    (tmp_path / "git").mkdir(parents=True, exist_ok=True)
    return asyncio.run(_run())


@pytest.mark.parametrize(
    ("native", "kinds"),
    [("refused.rej", ["modified", "deleted"]), ("config.json", [])],
    ids=["a-diff-under-another-name", "a-file-holding-no-diff"],
)
def test_diff_document_parses_a_file_whatever_it_is_called_on_both(
    tmp_path: Path, native: str, kinds: list[str]
) -> None:
    """The document hook reads the file it is given; its name is the kind system's business.

    A plugin may add match rules to the ``diff`` kind, so ``/api/file`` can send the
    Diff view to a file that is not named ``.patch`` or ``.diff``, and the view's data
    request must not then answer 404. 0.11.0 parsed any file under a folder, and a pin
    answers as the folder does: the read is bounded the same way on both, and a pin
    serves every blob this hook can reach through ``/api/file`` already.
    """

    folder, pinned = _diff_responses(tmp_path, "/api/plugin/diff/document", native)
    assert (folder.status_code, pinned.status_code) == (200, 200), (folder.text, pinned.text)
    assert [change["kind"] for change in folder.json()["manifest"]["files"]] == kinds
    assert bool(folder.json()["resolved"]["warnings"]) is (not kinds)
    assert folder.json() == pinned.json()


def test_diff_container_stays_scoped_to_patch_names_on_both(tmp_path: Path) -> None:
    """Child rows and virtual children exist only inside ``.patch`` and ``.diff`` files."""

    children = _diff_responses(tmp_path / "rows", "/api/plugin/diff/children", "refused.rej")
    assert [response.status_code for response in children] == [404, 404]
    assert [response.json()["error"] for response in children] == ["diff_children"] * 2

    inner = _diff_responses(
        tmp_path / "inner", "/api/plugin/diff/document", "refused.rej", "src/app.py"
    )
    assert [response.status_code for response in inner] == [404, 404]
    assert [response.json()["error"] for response in inner] == ["diff_document"] * 2
