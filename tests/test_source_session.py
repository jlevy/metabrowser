"""Active repository subject, content source, and one-session lifecycle."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from starlette.testclient import TestClient

from metabrowser.paths_safe import ROOT_DIR, _set_root_dir
from metabrowser.plugin_api import (
    UnsupportedSourceCapabilityError,
    content_source,
    open_content,
    require_source_capability,
    resolve_path,
    served_root,
    source_capabilities,
)
from metabrowser.source import (
    FILESYSTEM_CAPABILITIES,
    AttachedFilesystemSubject,
    ContentHandle,
    ContentSource,
    SourceCapabilities,
    attach_subject,
    get_source_session,
    reset_source_session,
)
from tests.test_inventory_coordinator import _coordinator, _FakeBackend


@dataclass(frozen=True, slots=True)
class _EmptyContent:
    def resolve(self, identity: str) -> ContentHandle | None:
        return None


_MEMORY_CAPABILITIES = SourceCapabilities(
    navigation=False,
    index=False,
    recency=False,
    ignore=False,
    watcher=False,
    activity=False,
    mutation=False,
)
_EMPTY_CONTENT = _EmptyContent()


@dataclass(frozen=True, slots=True)
class _MemorySubject:
    kind: str = "test_memory"
    identity: str = "memory:test"
    capabilities: SourceCapabilities = _MEMORY_CAPABILITIES
    content: ContentSource = _EMPTY_CONTENT
    filesystem_root: Path | None = None


def _with_root(tmp_path: Path) -> Path:
    original = ROOT_DIR
    _set_root_dir(tmp_path)
    return original


def test_filesystem_subject_preserves_root_containment(tmp_path: Path) -> None:
    original = _with_root(tmp_path)
    try:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "100%.html").write_text("<p>ok</p>\n")
        outside = tmp_path.parent / "secret.txt"
        outside.write_text("no\n")

        session = get_source_session()
        assert isinstance(session.subject, AttachedFilesystemSubject)
        assert session.subject.kind == "attached_filesystem"
        assert session.capabilities == FILESYSTEM_CAPABILITIES
        assert session.lease.held
        assert session.subject.filesystem_root == tmp_path.resolve()

        handle = session.content.resolve("docs/100%25.html")
        assert handle is not None
        assert handle.path == tmp_path / "docs" / "100%.html"
        assert handle.is_file

        assert session.content.resolve("../secret.txt") is None
        assert resolve_path("docs/100%25.html") == tmp_path / "docs" / "100%.html"
        assert resolve_path("../secret.txt") is None
        assert served_root() == tmp_path
        assert open_content("docs/100%25.html").disk_path == tmp_path / "docs" / "100%.html"
        assert source_capabilities() == FILESYSTEM_CAPABILITIES
        require_source_capability("recency")
        require_source_capability("ignore")
        require_source_capability("watcher")
        require_source_capability("activity")
        require_source_capability("mutation")
        require_source_capability("navigation")
        require_source_capability("index")
    finally:
        _set_root_dir(original)


def test_replacing_the_root_releases_the_previous_lease(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    original = _with_root(first)
    try:
        first_session = get_source_session()
        first_generation = first_session.generation
        first_lease = first_session.lease
        assert first_lease.held
        _set_root_dir(second)
        second_session = get_source_session()
        assert second_session is not first_session
        assert second_session.generation == first_generation + 1
        assert not first_lease.held
        assert second_session.lease.held
        assert second_session.subject.filesystem_root == second.resolve()
    finally:
        _set_root_dir(original)


def test_one_active_subject_and_legacy_hooks_gate_non_filesystem(tmp_path: Path) -> None:
    original = _with_root(tmp_path)
    try:
        memory = _MemorySubject()
        session = attach_subject(memory)
        assert get_source_session() is session
        assert session.subject is memory
        assert content_source() is memory.content
        try:
            resolve_path("readme.md")
            raise AssertionError("resolve_path must refuse a non-filesystem subject")
        except UnsupportedSourceCapabilityError as exc:
            assert exc.capability == "filesystem"
        try:
            served_root()
            raise AssertionError("served_root must refuse a non-filesystem subject")
        except UnsupportedSourceCapabilityError as exc:
            assert exc.capability == "filesystem"
        try:
            open_content("readme.md")
            raise AssertionError("open_content must refuse a non-filesystem subject")
        except UnsupportedSourceCapabilityError as exc:
            assert exc.capability == "filesystem"
        for name in (
            "navigation",
            "index",
            "recency",
            "ignore",
            "watcher",
            "activity",
            "mutation",
        ):
            try:
                require_source_capability(name)
                raise AssertionError(f"{name} must be unsupported")
            except UnsupportedSourceCapabilityError as exc:
                assert exc.capability == name
    finally:
        reset_source_session()
        _set_root_dir(original)


def test_coordinator_open_subject_matches_filesystem_open(tmp_path: Path) -> None:
    async def _run() -> None:
        backend = _FakeBackend()
        coordinator = _coordinator(backend)
        subject = AttachedFilesystemSubject(tmp_path)
        version = await coordinator.open_subject(subject)
        assert version.engine.session == f"engine-{tmp_path.name}"
        assert backend.events == [f"open:{tmp_path.name}"]
        await coordinator.close()

    asyncio.run(_run())


def test_coordinator_open_subject_requires_index_and_a_filesystem_root(
    tmp_path: Path,
) -> None:
    async def _run() -> None:
        backend = _FakeBackend()
        coordinator = _coordinator(backend)
        try:
            await coordinator.open_subject(_MemorySubject())
            raise AssertionError("index-less subject must not open")
        except UnsupportedSourceCapabilityError as exc:
            assert exc.capability == "index"

        indexed = _MemorySubject(
            capabilities=SourceCapabilities(
                navigation=True,
                index=True,
                recency=False,
                ignore=False,
                watcher=False,
                activity=False,
                mutation=False,
            )
        )
        try:
            await coordinator.open_subject(indexed)
            raise AssertionError("non-filesystem subject must not open")
        except UnsupportedSourceCapabilityError as exc:
            assert exc.capability == "filesystem"
        assert backend.events == []

    asyncio.run(_run())


def test_recent_and_activity_routes_report_unsupported_capabilities(
    tmp_path: Path,
) -> None:
    from metabrowser.server import app

    original = _with_root(tmp_path)
    try:
        attach_subject(_MemorySubject())
        with TestClient(app) as client:
            recent = client.get("/api/recent")
            assert recent.status_code == 409
            assert recent.json()["code"] == "unsupported_for_subject"
            assert recent.json()["capability"] == "recency"
            activity = client.get("/api/activity")
            assert activity.status_code == 409
            assert activity.json()["code"] == "unsupported_for_subject"
            assert activity.json()["capability"] == "activity"
            tree = client.get("/api/tree")
            assert tree.status_code == 409
            assert tree.json()["code"] == "unsupported_for_subject"
            assert tree.json()["capability"] == "navigation"
            events = client.get("/api/events")
            assert events.status_code == 409
            assert events.json()["code"] == "unsupported_for_subject"
            assert events.json()["capability"] == "watcher"
    finally:
        reset_source_session()
        _set_root_dir(original)


def test_file_and_raw_keep_filesystem_bytes(tmp_path: Path) -> None:
    from metabrowser.server import app

    (tmp_path / "note.txt").write_text("hello\n")
    original = _with_root(tmp_path)
    try:
        with TestClient(app) as client:
            file_body = client.get("/api/file", params={"path": "note.txt"})
            assert file_body.status_code == 200
            assert file_body.json()["path"] == "note.txt"
            raw = client.get("/raw", params={"path": "note.txt"})
            assert raw.status_code == 200
            assert raw.content == b"hello\n"
    finally:
        _set_root_dir(original)
