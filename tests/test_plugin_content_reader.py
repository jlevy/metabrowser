"""The bounded content-reader port a third-party data hook uses.

Every assertion runs the same hook body against an attached filesystem root and
an immutable Git-revision pin. A hook that reaches for a private Git internal or
branches on the subject kind would pass on one of those and fail on the other,
which is exactly the gap this port closes.
"""

from __future__ import annotations

import asyncio
import gzip
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from metabrowser.git.tree_source import (
    GitBlobTooLargeError,
    GitObjectUnavailableError,
    GitPath,
    git_revision_subject,
)
from metabrowser.paths_safe import ROOT_DIR, _set_root_dir
from metabrowser.plugin_api import (
    ArtifactDecompressionLimitError,
    ContentReadError,
    ContentRef,
    ContentStat,
    ContentUnavailableError,
    ContentWindow,
    UnsupportedSourceCapabilityError,
    read_content_window,
    resolve_content,
    resolve_content_container,
    stat_content,
)
from metabrowser.source import (
    AttachedFilesystemSubject,
    attach_subject,
    reset_source_session,
)
from tests.git_pin_harness import fast_import_store

# 4 KiB of non-repeating-enough bytes: large enough that a window is a real
# slice of it and small enough to keep the fixture store tiny.
BODY = bytes(range(256)) * 16
PATCH = (
    b"diff --git a/src/app.py b/src/app.py\n"
    b"--- a/src/app.py\n"
    b"+++ b/src/app.py\n"
    b"@@ -1 +1 @@\n"
    b"-old\n"
    b"+new\n"
)
FILES: dict[bytes, bytes] = {
    b"note.bin": BODY,
    b"data.json": b'{"a": 1}\n',
    b"change.patch": PATCH,
    b"docs/inner.txt": b"inner\n",
}


def _on_filesystem(tmp_path: Path) -> Path:
    for name, body in FILES.items():
        target = tmp_path / name.decode()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    return tmp_path


async def _with_filesystem[T](
    tmp_path: Path, hook: Callable[[str], Awaitable[T]], identity: str
) -> T:
    original = ROOT_DIR
    _set_root_dir(_on_filesystem(tmp_path))
    try:
        attach_subject(AttachedFilesystemSubject(tmp_path))
        return await hook(identity)
    finally:
        reset_source_session()
        _set_root_dir(original)


async def _with_pin[T](tmp_path: Path, hook: Callable[[str], Awaitable[T]], identity: str) -> T:
    from metabrowser.git.process import repository_store_target

    store, commit = fast_import_store(tmp_path, FILES)
    subject = await git_revision_subject(
        target=repository_store_target(git_dir=store),
        commit_oid=commit,
        store_identity="content-reader-fixture",
    )
    attach_subject(subject)
    try:
        return await hook(identity)
    finally:
        await subject.aclose()
        reset_source_session()


def _wire(native: str) -> str:
    return GitPath.from_display(native).to_wire()


def _container_wire(native: str) -> str:
    """A container identity: a GitPath prefix plus an unencoded host inner."""

    outer, _, inner = native.partition("/")
    return f"{_wire(outer)}/{inner}" if inner else _wire(outer)


def _both[T](
    tmp_path: Path,
    hook: Callable[[str], Awaitable[T]],
    native: str,
    *,
    pinned_identity: Callable[[str], str] = _wire,
) -> tuple[T, T]:
    """Run one hook body on a filesystem root and on a pin of the same tree."""

    filesystem = asyncio.run(_with_filesystem(tmp_path / "fs", hook, native))
    pinned = asyncio.run(_with_pin(tmp_path / "git", hook, pinned_identity(native)))
    return filesystem, pinned


# ── The port itself ───────────────────────────────────────────────


def test_a_bounded_window_reads_the_same_bytes_on_both_source_kinds(tmp_path: Path) -> None:
    """The failing test this port exists for: one hook body, two source kinds."""

    async def hook(identity: str) -> tuple[ContentWindow, ContentWindow]:
        ref = await resolve_content(identity)
        assert ref is not None
        middle = await read_content_window(ref, offset=1000, max_bytes=64)
        tail = await read_content_window(ref, offset=len(BODY) - 32, max_bytes=64)
        return middle, tail

    for middle, tail in _both(tmp_path, hook, "note.bin"):
        assert middle.data == BODY[1000:1064]
        assert middle.offset == 1000
        assert middle.has_more is True
        assert tail.data == BODY[-32:]
        assert tail.has_more is False


def test_a_read_never_returns_more_than_its_maximum(tmp_path: Path) -> None:
    async def hook(identity: str) -> list[int]:
        ref = await resolve_content(identity)
        assert ref is not None
        return [
            len((await read_content_window(ref, offset=0, max_bytes=n)).data)
            for n in (1, 7, 4096, 99999)
        ]

    for lengths in _both(tmp_path, hook, "note.bin"):
        assert lengths == [1, 7, 4096, len(BODY)]


def test_stat_reports_the_validated_logical_size(tmp_path: Path) -> None:
    async def hook(identity: str) -> ContentStat:
        ref = await resolve_content(identity)
        assert ref is not None
        return await stat_content(ref)

    for stat in _both(tmp_path, hook, "note.bin"):
        assert stat.size == len(BODY)


def test_resolution_reports_a_fingerprint_that_tracks_the_bytes(tmp_path: Path) -> None:
    """A hook keys its own cache on this without knowing which source it is."""

    async def hook(identity: str) -> tuple[str, str]:
        first = await resolve_content(identity)
        second = await resolve_content(identity)
        assert first is not None and second is not None
        return first.fingerprint, second.fingerprint

    for before, after in _both(tmp_path, hook, "note.bin"):
        assert before
        assert before == after

    root = tmp_path / "changing"
    root.mkdir()
    target = root / "note.bin"
    target.write_bytes(BODY)
    original = ROOT_DIR
    _set_root_dir(root)

    async def fingerprints() -> tuple[str, str]:
        first = await resolve_content("note.bin")
        assert first is not None
        target.write_bytes(BODY + b"more")
        os.utime(target, (0, 0))
        second = await resolve_content("note.bin")
        assert second is not None
        return first.fingerprint, second.fingerprint

    try:
        attach_subject(AttachedFilesystemSubject(root))
        before, after = asyncio.run(fingerprints())
    finally:
        reset_source_session()
        _set_root_dir(original)
    assert before != after


def test_a_resolved_reference_echoes_a_client_usable_identity(tmp_path: Path) -> None:
    async def hook(identity: str) -> ContentRef:
        ref = await resolve_content(identity)
        assert ref is not None
        return ref

    filesystem, pinned = _both(tmp_path, hook, "data.json")
    assert filesystem.identity == "data.json"
    assert filesystem.logical_ext == ".json"
    assert pinned.identity == _wire("data.json")
    assert pinned.logical_ext == ".json"


def test_missing_and_non_file_identities_resolve_to_none(tmp_path: Path) -> None:
    async def hook(_identity: str) -> list[ContentRef | None]:
        return [await resolve_content(name) for name in ("", "docs", "nope.bin")]

    filesystem = asyncio.run(_with_filesystem(tmp_path / "fs", hook, ""))
    pinned = asyncio.run(_with_pin(tmp_path / "git", hook, ""))
    assert filesystem == [None, None, None]
    # The pin sees "docs" and "nope.bin" as non-GitPath wires, which is also a
    # refusal rather than a host-path escape.
    assert pinned == [None, None, None]

    async def pinned_tree(identity: str) -> ContentRef | None:
        return await resolve_content(identity)

    assert asyncio.run(_with_pin(tmp_path / "git2", pinned_tree, _wire("docs"))) is None


def test_a_container_identity_splits_into_content_and_inner_path(tmp_path: Path) -> None:
    async def hook(identity: str) -> tuple[str, str, bytes]:
        found = await resolve_content_container(identity, suffixes=(".patch", ".diff"))
        assert found is not None
        ref, inner = found
        window = await read_content_window(ref, offset=0, max_bytes=len(PATCH) + 1)
        return ref.identity, inner, window.data

    filesystem, pinned = _both(
        tmp_path, hook, "change.patch/src/app.py", pinned_identity=_container_wire
    )
    assert filesystem == ("change.patch", "src/app.py", PATCH)
    assert pinned[1:] == ("src/app.py", PATCH)
    assert pinned[0] == _wire("change.patch")


def test_a_container_refuses_a_suffix_it_does_not_claim(tmp_path: Path) -> None:
    async def hook(identity: str) -> Any:
        return await resolve_content_container(identity, suffixes=(".patch", ".diff"))

    for found in _both(tmp_path, hook, "data.json/src/app.py", pinned_identity=_container_wire):
        assert found is None


def test_a_container_without_an_inner_path_is_the_content_itself(tmp_path: Path) -> None:
    async def hook(identity: str) -> tuple[str, str]:
        found = await resolve_content_container(identity, suffixes=(".patch",))
        assert found is not None
        ref, inner = found
        return ref.identity, inner

    for _identity, inner in _both(tmp_path, hook, "change.patch"):
        assert inner == ""


# ── Filesystem-only facts the port still honors ───────────────────


def test_a_compressed_artifact_reads_its_logical_bytes(tmp_path: Path) -> None:
    root = tmp_path / "fs"
    root.mkdir()
    (root / "log.jsonl.gz").write_bytes(gzip.compress(BODY))
    original = ROOT_DIR
    _set_root_dir(root)

    async def hook() -> tuple[ContentStat, ContentWindow]:
        ref = await resolve_content("log.jsonl.gz")
        assert ref is not None
        assert ref.logical_ext == ".jsonl"
        return await stat_content(ref), await read_content_window(ref, offset=16, max_bytes=32)

    try:
        attach_subject(AttachedFilesystemSubject(root))
        stat, window = asyncio.run(hook())
    finally:
        reset_source_session()
        _set_root_dir(original)
    assert stat.size == len(BODY)
    assert window.data == BODY[16:48]
    assert window.has_more is True


def test_traversal_out_of_the_served_root_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "fs"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("no\n")
    original = ROOT_DIR
    _set_root_dir(root)
    try:
        attach_subject(AttachedFilesystemSubject(root))
        assert asyncio.run(resolve_content("../secret.txt")) is None
    finally:
        reset_source_session()
        _set_root_dir(original)


# ── One typed vocabulary for both kinds ───────────────────────────


def test_every_port_failure_is_one_catchable_family() -> None:
    for failure in (
        ContentUnavailableError,
        UnsupportedSourceCapabilityError,
        ArtifactDecompressionLimitError,
        GitObjectUnavailableError,
        GitBlobTooLargeError,
    ):
        assert issubclass(failure, ContentReadError), failure
    assert issubclass(GitObjectUnavailableError, ContentUnavailableError)


def test_failures_carry_a_code_and_a_status_a_hook_can_map() -> None:
    assert ContentUnavailableError("x").http_status == 404
    assert UnsupportedSourceCapabilityError("filesystem").http_status == 409
    assert ArtifactDecompressionLimitError("too big").http_status == 413
    assert GitObjectUnavailableError("a" * 40).http_status == 404
    assert GitBlobTooLargeError(oid="a" * 40, size=2, max_bytes=1).http_status == 413
    assert UnsupportedSourceCapabilityError("filesystem").code == "unsupported_for_subject"
    assert GitObjectUnavailableError("a" * 40).code == "object_unavailable"


def test_pin_route_statuses_agree_with_the_shared_vocabulary() -> None:
    """The route decorator and a hook must not disagree about one failure."""

    from metabrowser.git.content_routes import git_content_failure_response
    from metabrowser.git.process import GitTimeoutError

    for exc in (
        GitObjectUnavailableError("a" * 40),
        GitBlobTooLargeError(oid="a" * 40, size=2, max_bytes=1),
        GitTimeoutError(),
    ):
        assert git_content_failure_response(exc).status_code == exc.http_status


def test_the_port_refuses_a_subject_that_cannot_read_content(tmp_path: Path) -> None:
    from tests.test_source_session import _MemorySubject

    original = ROOT_DIR
    _set_root_dir(tmp_path)
    try:
        attach_subject(_MemorySubject())
        with pytest.raises(UnsupportedSourceCapabilityError) as caught:
            asyncio.run(resolve_content("note.bin"))
        assert caught.value.capability == "content"
    finally:
        reset_source_session()
        _set_root_dir(original)
