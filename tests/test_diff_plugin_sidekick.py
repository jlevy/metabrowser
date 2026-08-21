"""The diff plugin's data hooks: patch files, container children, comparisons."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from metabrowser import server
from metabrowser.builtin_plugins.diff import sidekick
from metabrowser.diff.format import validate_document
from tests.diff_fixture_repo import build_diff_fixture


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


# ── The comparison hook (Review finding R2 + S1) ────────────────────


def _comparison(**params: str) -> tuple[int, dict[str, Any]]:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery(dict(params))
    request.headers = {}
    response = asyncio.run(sidekick.comparison_handler(request))
    return response.status_code, json.loads(bytes(response.body))


def test_comparison_unknown_revision_is_a_404_not_a_500(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    build_diff_fixture(root)
    server._set_root_dir(root)
    status, body = _comparison(revision="no-such-revision")
    assert status == 404
    assert "no-such-revision" in body["message"]


def test_comparison_outside_a_repository_is_a_404(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    status, body = _comparison(revision="HEAD")
    assert status == 404
    assert "not the root of a Git repository" in body["message"]


def test_comparison_requires_a_revision_or_both_endpoints(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    status, _body = _comparison()
    assert status == 400


def test_comparison_hydrates_to_the_bound_and_defers_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _base, target = build_diff_fixture(root)
    server._set_root_dir(root)
    monkeypatch.setattr(sidekick, "MAX_HYDRATED_FILES", 2)
    status, body = _comparison(revision=target)
    assert status == 200
    document = validate_document(body)
    ready = [c for c in document.manifest.files if c.availability.value == "ready"]
    deferred = [c for c in document.manifest.files if c.availability.value == "deferred"]
    assert len(ready) == 2 and len(document.patches) == 2
    assert deferred, "files past the bound must be declared deferred, not dropped"
