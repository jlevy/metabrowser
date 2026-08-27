"""The nav-container contract, server side.

A missing path whose nearest file ancestor is a container kind resolves
to that kind's envelope for the virtual path (arch-nav-containers.md);
everything else keeps the ordinary not-found behavior. The diff plugin
is the first container, so the cases run against real `.patch` files.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from metabrowser import server
from metabrowser.builtin_plugins.diff import sidekick
from metabrowser.diff.format import validate_document


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _request(path: str) -> Mock:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery({"path": path})
    request.headers = {}
    return request


def _api_file(path: str) -> tuple[int, dict[str, Any]]:
    response = asyncio.run(server.api_file(_request(path)))
    return response.status_code, json.loads(bytes(response.body))


PATCH = (
    "diff --git a/src/app.py b/src/app.py\n"
    "--- a/src/app.py\n"
    "+++ b/src/app.py\n"
    "@@ -1,1 +1,1 @@\n"
    "-old\n"
    "+new\n"
    "diff --git a/gone.txt b/gone.txt\n"
    "deleted file mode 100644\n"
    "--- a/gone.txt\n"
    "+++ /dev/null\n"
    "@@ -1,1 +0,0 @@\n"
    "-bye\n"
)


def test_virtual_child_resolves_to_the_container_kinds_envelope(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "change.patch").write_text(PATCH)
    status, body = _api_file("change.patch/src/app.py")
    assert status == 200
    assert body["kind"] == "diff"
    assert body["container"] == "change.patch"
    assert body["container_inner"] == "src/app.py"
    assert body["path"] == "change.patch/src/app.py"
    assert any(view["id"] == "diff" for view in body["views"])


def test_missing_file_under_a_real_directory_stays_not_found(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "docs").mkdir()
    status, _body = _api_file("docs/absent.md")
    assert status == 404


def test_child_of_a_non_container_file_stays_not_found(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "notes.md").write_text("# hi\n")
    status, _body = _api_file("notes.md/inner")
    assert status == 404


def test_escaping_virtual_path_stays_not_found(tmp_path: Path) -> None:
    served = tmp_path / "served"
    served.mkdir()
    (tmp_path / "outside.patch").write_text(PATCH)
    server._set_root_dir(served)
    status, _body = _api_file("../outside.patch/src/app.py")
    assert status == 404


def test_container_exts_expose_the_diff_kind() -> None:
    exts = server._container_exts()
    assert exts[".patch"]["kind"] == "diff"
    assert exts[".patch"]["children"] == "children"
    assert exts[".diff"]["plugin"] == "diff"


# ── The plugin's own halves of the contract ─────────────────────────


def _hook(handler: Any, path: str) -> tuple[int, dict[str, Any]]:
    response = handler(_request(path))
    return response.status_code, json.loads(bytes(response.body))


def test_children_hook_lists_change_entries_as_rows(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "change.patch").write_text(PATCH)
    status, body = _hook(sidekick.children_handler, "change.patch")
    assert status == 200
    rows = body["children"]
    assert [row["path"] for row in rows] == [
        "change.patch/src/app.py",
        "change.patch/gone.txt",
    ]
    assert rows[0]["badge"] == "M" and rows[1]["badge"] == "D"


def test_document_hook_narrows_to_one_change_for_a_virtual_path(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "change.patch").write_text(PATCH)
    status, body = _hook(sidekick.document_handler, "change.patch/src/app.py")
    assert status == 200
    document = validate_document(body)
    assert document.manifest.totals.files == 1
    only = document.manifest.files[0]
    assert only.new is not None and only.new.path == "src/app.py"
    assert list(document.patches) == [only.id]


def test_one_row_per_path_groups_a_type_change(tmp_path: Path) -> None:
    """A patch spells file->symlink as delete+add at one path; the tree
    shows one row, and opening it shows both halves."""
    server._set_root_dir(tmp_path)
    (tmp_path / "typed.patch").write_text(
        "diff --git a/cfg b/cfg\n"
        "deleted file mode 100644\n"
        "--- a/cfg\n"
        "+++ /dev/null\n"
        "@@ -1,1 +0,0 @@\n"
        "-real contents\n"
        "diff --git a/cfg b/cfg\n"
        "new file mode 120000\n"
        "--- /dev/null\n"
        "+++ b/cfg\n"
        "@@ -0,0 +1,1 @@\n"
        "+target/cfg\n"
    )
    _status, body = _hook(sidekick.children_handler, "typed.patch")
    rows = body["children"]
    assert [row["path"] for row in rows] == ["typed.patch/cfg"]
    assert rows[0]["badge"] == "T"
    _status, doc_body = _hook(sidekick.document_handler, "typed.patch/cfg")
    document = validate_document(doc_body)
    assert document.manifest.totals.files == 2
    assert {c.kind.value for c in document.manifest.files} == {"deleted", "added"}


def test_document_hook_rejects_an_unknown_inner_path(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "change.patch").write_text(PATCH)
    status, _body = _hook(sidekick.document_handler, "change.patch/absent.py")
    assert status == 404
