"""The diff plugin's data hooks: patch files, container children, comparisons."""

from __future__ import annotations

import asyncio
import gzip
import json
import os
import threading
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from metabrowser import server
from metabrowser.builtin_plugins.diff import sidekick
from metabrowser.diff.adapters import git as git_adapter
from metabrowser.diff.adapters.git import PatchHydration
from metabrowser.diff.format import validate_document
from metabrowser.source import ContentHandle, FilesystemContentSource
from tests.diff_fixture_repo import build_diff_fixture, git


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _request(path: str) -> Any:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery({"path": path})
    request.headers = {}
    return request


def _document(path: str) -> tuple[int, dict[str, Any]]:
    response = asyncio.run(sidekick.document_handler(_request(path)))
    return response.status_code, json.loads(bytes(response.body))


def _children(path: str) -> tuple[int, dict[str, Any]]:
    response = asyncio.run(sidekick.children_handler(_request(path)))
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


def _commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD").decode().strip()


def test_a_comparison_deleting_an_empty_file_keeps_its_files(tmp_path: Path) -> None:
    """Any pull request deleting an empty file once answered 404 for the whole comparison."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    (root / "kept.txt").write_text("old\n")
    (root / "pkg").mkdir()
    (root / "pkg/__init__.py").write_text("")
    (root / "logo.bin").write_bytes(b"\x00\x01\x02")
    base = _commit(root, "base")
    (root / "kept.txt").write_text("new\n")
    (root / "pkg/__init__.py").unlink()
    (root / "logo.bin").unlink()
    target = _commit(root, "target")
    server._set_root_dir(root)

    status, body = _comparison(left=base, right=target, base_policy="merge_base")

    assert status == 200, body
    document = validate_document(body)
    changes = {(c.new or c.old).path: c for c in document.manifest.files}  # pyright: ignore[reportOptionalMemberAccess]
    assert changes["pkg/__init__.py"].kind.value == "deleted"
    assert changes["pkg/__init__.py"].availability.value == "ready"
    assert document.patches[changes["pkg/__init__.py"].id].hunks == ()
    assert changes["logo.bin"].availability.value == "binary"
    assert document.patches[changes["kept.txt"].id].hunks
    assert document.resolved.warnings == ()


def test_a_file_the_diff_did_not_produce_is_named_and_the_rest_are_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    base, target = build_diff_fixture(root)
    server._set_root_dir(root)
    real = sidekick.GitDiffSource.hydrate

    async def loses_one(self: Any, resolved: Any, file_ids: Any, **kwargs: Any) -> PatchHydration:
        whole = await real(self, resolved, file_ids, **kwargs)
        first, *rest = file_ids
        patches = {file_id: whole.patches[file_id] for file_id in rest}
        return PatchHydration(patches=patches, left_out=(first,))

    monkeypatch.setattr(sidekick.GitDiffSource, "hydrate", loses_one)
    status, body = _comparison(left=base, right=target)

    assert status == 200, body
    document = validate_document(body)
    lost = next(c for c in document.manifest.files if c.availability.value == "failed")
    assert lost.id not in document.patches
    assert len(document.patches) > 1
    path = (lost.new or lost.old).path  # pyright: ignore[reportOptionalMemberAccess]
    assert document.resolved.warnings == (
        f"1 file(s) could not be read from the produced diff: {path}",
    )


def test_a_file_past_the_bound_says_so_and_the_rest_are_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    (root / "keep.txt").write_text("keep\n")
    base = _commit(root, "base")
    (root / "a.txt").write_text("a\n" * 200)
    (root / "big.txt").write_text("big line\n" * 1000)
    (root / "c.txt").write_text("c\n" * 200)
    target = _commit(root, "target")
    server._set_root_dir(root)
    monkeypatch.setattr(git_adapter, "MAX_FILE_PATCH_BYTES", 1000)

    status, body = _comparison(left=base, right=target)

    assert status == 200, body
    document = validate_document(body)
    states = {(c.new or c.old).path: c.availability.value for c in document.manifest.files}  # pyright: ignore[reportOptionalMemberAccess]
    assert states == {"a.txt": "ready", "big.txt": "too_large", "c.txt": "deferred"}
    assert list(document.patches) == [next(c.id for c in document.manifest.files)]
    assert document.manifest.totals.additions == 1400, "counts come from the manifest"

    status, alone = _comparison(left=base, right=target, file="c.txt")
    assert status == 200, alone
    assert validate_document(alone).manifest.files[0].availability.value == "ready"
    status, alone = _comparison(left=base, right=target, file="big.txt")
    assert status == 200, alone
    too_large = validate_document(alone)
    assert too_large.manifest.files[0].availability.value == "too_large"
    assert too_large.patches == {}


# ── Event-loop discipline ───────────────────────────────────────

# The content reader's nearest-container walk mirrors the server's
# nearest-file-ancestor rule, so it stats one entry per path level before
# anything is parsed. On a cold or networked filesystem that is real latency,
# and the module contract says filesystem work runs in the thread pool.


def _thread_of_resolve_path(
    handler: Any, path: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, list[int], int]:
    """Run one handler; report the loop thread, where resolution ran, and the status."""

    real = FilesystemContentSource.resolve
    seen: list[int] = []

    def _record(self: FilesystemContentSource, requested: str) -> ContentHandle | None:
        seen.append(threading.get_ident())
        return real(self, requested)

    monkeypatch.setattr(FilesystemContentSource, "resolve", _record)

    async def _run() -> tuple[int, int]:
        response = await handler(_request(path))
        return threading.get_ident(), response.status_code

    loop_ident, status = asyncio.run(_run())
    return loop_ident, seen, status


def test_document_hook_resolves_the_patch_off_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "change.patch").write_text(PATCH)
    loop_ident, seen, status = _thread_of_resolve_path(
        sidekick.document_handler, "change.patch", monkeypatch
    )
    assert status == 200
    assert seen, "path resolution never ran"
    assert loop_ident not in seen


def test_children_hook_resolves_the_patch_off_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "change.patch").write_text(PATCH)
    loop_ident, seen, status = _thread_of_resolve_path(
        sidekick.children_handler, "change.patch", monkeypatch
    )
    assert status == 200
    assert seen, "path resolution never ran"
    assert loop_ident not in seen


def test_children_hook_lists_one_row_per_changed_path(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "change.patch").write_text(PATCH)
    status, body = _children("change.patch")
    assert status == 200
    assert [child["name"] for child in body["children"]] == ["a.txt"]


def test_children_hook_reports_a_missing_file(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    status, body = _children("absent.patch")
    assert status == 404
    assert body["error"] == "diff_children"
    assert str(tmp_path) not in json.dumps(body)


# ── Which files the hooks read ──────────────────────────────────────
#
# The kind system decides which files open in the Diff view, and a plugin may add
# match rules to the ``diff`` kind, so the document hook does not check the name of
# the file it is given. The container contract is a different question: a virtual
# child resolves only inside a file this plugin's own extensions claim.


def test_document_hook_parses_a_file_whatever_it_is_called(tmp_path: Path) -> None:
    """0.11.0 parsed any file it was given; a name was never a reason for a 404."""

    server._set_root_dir(tmp_path)
    (tmp_path / "change.rej").write_text(PATCH)
    (tmp_path / "notes.md").write_text("# not a diff\n")

    status, body = _document("change.rej")
    assert status == 200, body
    document = validate_document(body)
    assert [change.kind.value for change in document.manifest.files] == ["modified"]
    assert document.patches["f1"].hunks[0].lines[0].text == "old"

    status, body = _document("notes.md")
    assert status == 200, body
    document = validate_document(body)
    assert document.manifest.totals.files == 0
    assert any("no diff sections" in warning for warning in document.resolved.warnings)


def test_children_and_virtual_children_need_a_patch_name(tmp_path: Path) -> None:
    """The container contract stays scoped to ``.patch`` and ``.diff``, as in 0.11.0."""

    server._set_root_dir(tmp_path)
    (tmp_path / "change.rej").write_text(PATCH)

    status, body = _children("change.rej")
    assert (status, body["error"]) == (404, "diff_children")
    status, body = _document("change.rej/a.txt")
    assert (status, body["error"]) == (404, "diff_document")


def test_a_compressed_patch_is_read_as_the_patch_it_holds(tmp_path: Path) -> None:
    """``change.patch.gz`` is the ``diff`` kind, and the hooks read its decoded text.

    The content reader compares the logical extension, which is why the container
    walk is given suffixes and not a name to match. 0.11.0 parsed the compressed
    bytes and answered that it recognized no diff.
    """

    server._set_root_dir(tmp_path)
    (tmp_path / "change.patch.gz").write_bytes(gzip.compress(PATCH.encode()))

    status, body = _document("change.patch.gz")
    assert status == 200, body
    assert validate_document(body).patches["f1"].hunks[0].lines[0].text == "old"
    status, body = _children("change.patch.gz")
    assert status == 200, body
    assert [child["path"] for child in body["children"]] == ["change.patch.gz/a.txt"]
    status, body = _document("change.patch.gz/a.txt")
    assert status == 200, body
    assert validate_document(body).manifest.totals.files == 1


@pytest.mark.parametrize("name", ["locked.patch", "locked.txt"])
def test_a_file_that_cannot_be_opened_is_a_404_naming_no_host_path(
    name: str, tmp_path: Path
) -> None:
    """A file without read permission answers the hook's own 404.

    0.11.0 let the ``PermissionError`` reach the dispatcher, which answered the
    degraded ``plugin_error`` envelope with the file's absolute path in ``detail`` and
    logged a traceback.
    """

    server._set_root_dir(tmp_path)
    target = tmp_path / name
    target.write_text(PATCH)
    target.chmod(0)
    if os.access(target, os.R_OK):
        # A superuser reads it anyway; there is nothing to refuse.
        return

    status, body = _document(name)
    assert status == 404
    assert body == {
        "error": "diff_document",
        "message": "This file is not available.",
        "path": name,
    }
    assert str(tmp_path) not in json.dumps(body)

    status, body = _children(name)
    assert (status, body["error"], body["path"]) == (404, "diff_children", name)
    assert str(tmp_path) not in json.dumps(body)


def test_a_compressed_file_that_cannot_be_decoded_is_the_same_404(tmp_path: Path) -> None:
    """There is no patch to read in it. ``/api/file`` shows such a file as bytes."""

    server._set_root_dir(tmp_path)
    (tmp_path / "broken.patch.gz").write_bytes(b"not a gzip stream")

    status, body = _document("broken.patch.gz")
    assert (status, body["error"]) == (404, "diff_document")
    status, body = _children("broken.patch.gz")
    assert (status, body["error"]) == (404, "diff_children")
