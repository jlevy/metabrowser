"""The diff plugin's document hook: patch file in, valid wire document out."""

from __future__ import annotations

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


def _document(path: str) -> tuple[int, dict[str, Any]]:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery({"path": path})
    request.headers = {}
    response = sidekick.document_handler(request)
    return response.status_code, json.loads(bytes(response.body))


PATCH = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1,1 +1,1 @@\n-old\n+new\n"


def test_document_hook_returns_a_format_valid_document(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "change.patch").write_text(PATCH)
    status, body = _document("change.patch")
    assert status == 200
    document = validate_document(body)
    assert document.manifest.files[0].kind.value == "modified"
    assert document.patches["f1"].hunks[0].lines[0].text == "old"


def test_document_hook_reports_a_missing_file(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    status, body = _document("absent.patch")
    assert status == 404
    assert body["error"] == "diff_document"
    # Public-safe: the message carries no absolute local path.
    assert str(tmp_path) not in json.dumps(body)


def test_document_hook_refuses_escape_from_the_root(tmp_path: Path) -> None:
    served = tmp_path / "served"
    served.mkdir()
    outside = tmp_path / "outside.patch"
    outside.write_text(PATCH)
    server._set_root_dir(served)
    status, _body = _document("../outside.patch")
    assert status == 404


def test_malformed_patch_is_an_unsupported_document_not_an_error(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "broken.diff").write_text("--- a/x\n+++ b/x\n@@ -1,9 +1,1 @@\n-only\n")
    status, body = _document("broken.diff")
    assert status == 200
    document = validate_document(body)
    assert document.manifest.files[0].availability.value == "unsupported"


def test_unrecognizable_input_warns_instead_of_claiming_no_changes(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "prose.diff").write_text("this is not a diff at all\n")
    status, body = _document("prose.diff")
    assert status == 200
    document = validate_document(body)
    assert document.manifest.totals.files == 0
    assert any("no diff sections" in warning for warning in document.resolved.warnings)
