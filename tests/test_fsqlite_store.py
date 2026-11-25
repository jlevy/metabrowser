"""fsqlite stores read as a guest: the marker, the pointer, the snapshot, and the routes.

The format rules are the fsqlite specification's
(https://github.com/jlevy/fsqlite/blob/main/docs/fsql-format-spec.md) as ``builtin_plugins/fsqlite/store.py`` cites them; the
routes are checked through ``/api/plugin/fsqlite/*`` with the server's own plugins and a
real reader pool. The CLI transcripts are in ``tests/golden/cli-api-fsqlite.tryscript.md``.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.fsqlite import reader, sidekick, source, store
from metabrowser.builtin_plugins.fsqlite.store import (
    CURRENT_MAX_BYTES,
    CURRENT_MAX_VERSION,
    PENDING_SCAN_MAX,
    PendingCount,
    Snapshot,
    SnapshotGone,
    StoreError,
    count_pending,
    parse_current,
    parse_marker,
    read_snapshot,
    snapshot_name,
    store_generation,
)
from metabrowser.builtin_plugins.sqlite.database import Database
from metabrowser.plugin_loader.classify import collect_folder_markers
from metabrowser.plugin_loader.static_assets import build_plugin_routes
from metabrowser.source import reset_source_session
from metabrowser.sqlite_access import SqliteAccessError
from metabrowser.table_source import TableInfo
from tests.sqlite_guest_scenarios import create, hot_journal

STORE_ID = "550e8400-e29b-41d4-a716-446655440000"
MARKER = (
    '{"format": "fsqlite", "format_version": "f1.0", "required_features": [], '
    f'"store_id": "{STORE_ID}"}}'
)


def _snapshot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.executescript(
            f"PRAGMA application_id = {store.FSQLITE_APPLICATION_ID};"
            "CREATE TABLE applied_tx (tx_id TEXT PRIMARY KEY NOT NULL, applied_at TEXT NOT NULL);"
            "CREATE TABLE fsqlite_meta (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL);"
            "CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL);"
        )
        connection.executemany(
            "INSERT INTO fsqlite_meta VALUES (?, ?)",
            [
                ("format_version", "f1.0"),
                ("store_id", STORE_ID),
                ("schema_hash", "0123456789abcdef"),
                ("tool_version", "fixture"),
            ],
        )
    finally:
        connection.close()


def _store(root: Path, *, current: str = "1", versions: tuple[int, ...] = (1,)) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "fsqlite.json").write_text(MARKER)
    (root / "current").write_text(current)
    for version in versions:
        _snapshot(root / "snapshots" / snapshot_name(version))
    return root


def _listing(root: Path) -> dict[str, tuple[int, int, int]]:
    """Every entry under *root* with its identity, size, and modification time."""
    found: dict[str, tuple[int, int, int]] = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        found[str(path.relative_to(root))] = (info.st_ino, info.st_size, info.st_mtime_ns)
    return found


# ── The pointer ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "version"),
    [
        (b"0", 0),
        (b"2", 2),
        (b"000042", 42),
        (b" \t7\r\n\v\f", 7),
        (str(CURRENT_MAX_VERSION).encode(), CURRENT_MAX_VERSION),
        (b"1".rjust(CURRENT_MAX_BYTES), 1),
    ],
)
def test_the_pointer_parses_trimmed_ascii_digits(raw: bytes, version: int) -> None:
    assert parse_current(raw) == version


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b" \n",
        b"-1",
        b"+1",
        b"1.0",
        b"1e3",
        b"0x10",
        b"1 2",
        b"\xef\xbb\xbf1",  # a byte order mark is not whitespace
        b"\xc2\xa01",  # nor is a no-break space
        "١".encode(),  # an Arabic-Indic digit is not an ASCII digit
        str(CURRENT_MAX_VERSION + 1).encode(),
        b"1".rjust(CURRENT_MAX_BYTES + 1),
    ],
)
def test_anything_else_is_corrupt_never_version_zero(raw: bytes) -> None:
    with pytest.raises(StoreError) as caught:
        parse_current(raw)
    assert caught.value.state == "corrupt"


def test_a_malformed_pointer_is_quoted_short_and_escaped() -> None:
    with pytest.raises(StoreError) as caught:
        parse_current(b"\x00\\abc" + b"x" * 40)
    message = str(caught.value)
    assert "\\x00\\x5cabc" in message
    assert message.count("x") < 40
    assert "…" in message


def test_snapshot_names_are_twelve_zero_padded_digits() -> None:
    assert snapshot_name(0) == "000000000000.fsqlite.sqlite"
    assert snapshot_name(42) == "000000000042.fsqlite.sqlite"


# ── The marker ───────────────────────────────────────────────


def test_a_valid_marker_ignores_unknown_fields() -> None:
    marker = parse_marker(MARKER[:-1].encode() + b', "extra": 1}')
    assert (marker.format_version, marker.store_id, marker.required_features) == (
        "f1.0",
        STORE_ID,
        (),
    )


@pytest.mark.parametrize(
    "document",
    [
        b"not json",
        b"[]",
        b'{"format": "other", "format_version": "f1.0", "required_features": [], "store_id": "%s"}',
        b'{"format": "fsqlite", "format_version": "1.0", "required_features": [], "store_id": "%s"}',
        b'{"format": "fsqlite", "format_version": "f01.0", "required_features": [], "store_id": "%s"}',
        b'{"format": "fsqlite", "format_version": "f1.0", "store_id": "%s"}',
        b'{"format": "fsqlite", "format_version": "f1.0", "required_features": ["a", "a"], "store_id": "%s"}',
        b'{"format": "fsqlite", "format_version": "f1.0", "required_features": [1], "store_id": "%s"}',
        b'{"format": "fsqlite", "format_version": "f1.0", "required_features": [], "store_id": "nope"}',
        b'{"format": "fsqlite", "format_version": "f1.0", "required_features": [], "store_id": "550e8400e29b41d4a716446655440000"}',
    ],
)
def test_a_malformed_marker_is_invalid(document: bytes) -> None:
    raw = document.replace(b"%s", STORE_ID.encode())
    with pytest.raises(StoreError) as caught:
        parse_marker(raw)
    assert caught.value.state == "invalid"


@pytest.mark.parametrize(
    ("version", "features"),
    [("f2.0", "[]"), ("f1.1", "[]"), ("f1.0", '["sharding"]')],
)
def test_a_valid_marker_this_reader_does_not_know_is_unsupported(
    version: str, features: str
) -> None:
    raw = (
        f'{{"format": "fsqlite", "format_version": "{version}", '
        f'"required_features": {features}, "store_id": "{STORE_ID}"}}'
    ).encode()
    with pytest.raises(StoreError) as caught:
        parse_marker(raw)
    assert caught.value.state == "unsupported"


def test_an_oversized_marker_is_invalid_without_parsing() -> None:
    with pytest.raises(StoreError) as caught:
        parse_marker(b" " * (store.MARKER_MAX_BYTES + 1))
    assert caught.value.state == "invalid"


# ── Pending envelopes ────────────────────────────────────────


@pytest.mark.parametrize(("name", "state"), [("fsqlite.json", "invalid"), ("current", "corrupt")])
@pytest.mark.timeout(5)
def test_store_metadata_read_refuses_a_fifo(tmp_path: Path, name: str, state: str) -> None:
    fifo = tmp_path / name
    os.mkfifo(fifo)
    with pytest.raises(StoreError) as refused:
        if name == "fsqlite.json":
            store.read_marker(fifo)
        else:
            store.read_current(fifo)
    assert refused.value.state == state
    # The page says the file cannot be read; the operating system's words are detail.
    assert "not a regular file" in refused.value.detail


def test_an_unreadable_store_file_is_named_in_the_detail() -> None:
    """The page says the store cannot be read; the detail, for `metab --api`, says which
    of its files failed and why, without the folder it sits in (review A8 on #801)."""
    denied = PermissionError(13, "Permission denied", "/stores/demo/fsqlite.json")
    assert sidekick._unreadable(denied) == {
        "state": "invalid",
        "message": "This store cannot be read.",
        "detail": "fsqlite.json: Permission denied",
    }
    assert sidekick._unreadable(OSError("no such device"))["detail"] == "no such device"


def test_pending_envelopes_are_counted_by_their_commit_marker(tmp_path: Path) -> None:
    pending = tmp_path / "tx" / "pending"
    for name in ("1-a.txn", "2-b.txn", "3-c.txn"):
        (pending / name).mkdir(parents=True)
    (pending / "1-a.txn" / "COMMITTED").touch()
    (pending / "2-b.txn" / "COMMITTED").touch()
    # Transients and stray files are not envelopes.
    (pending / ".work-w-0123456789.sqlite").touch()
    (pending / "4-d.txn.tmp").mkdir()
    (pending / "5-e.txn").touch()
    assert count_pending(pending) == PendingCount(committed=2, uncommitted=1, complete=True)
    assert count_pending(tmp_path / "absent") == PendingCount(0, 0, True)
    assert count_pending(None) == PendingCount(0, 0, True)


def test_a_pending_scan_stops_at_its_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "PENDING_SCAN_MAX", 3)
    for index in range(5):
        (tmp_path / f"{index}.txn").mkdir()
    counted = count_pending(tmp_path)
    assert counted.complete is False
    assert counted.uncommitted == 3
    assert PENDING_SCAN_MAX > 3


# ── Generation ───────────────────────────────────────────────


def test_the_generation_names_the_version_and_moves_with_a_publish(tmp_path: Path) -> None:
    root = _store(tmp_path / "s", current="1", versions=(1, 2))
    marker, current = root / "fsqlite.json", root / "current"
    first = store_generation(marker, current, 1)
    assert first.startswith("1-")
    assert store_generation(marker, current, 1) == first
    # A publish renames a new pointer over the old one: a new identity, even when the
    # bytes repeat after a repair.
    replacement = root / "current.0123456789.tmp"
    replacement.write_text("1")
    os.replace(replacement, current)
    assert store_generation(marker, current, 1) != first
    assert store_generation(marker, current, 2).startswith("2-")


# ── Resolving the snapshot ───────────────────────────────────


def _locate(root: Path) -> store.Locate:
    def locate(name: str) -> Path | None:
        path = root / "snapshots" / name
        return path if path.exists() else None

    return locate


def test_a_snapshot_collected_before_the_open_sends_the_read_back_to_the_pointer(
    tmp_path: Path,
) -> None:
    root = _store(tmp_path / "s", current="1", versions=(1, 2))
    seen: list[int] = []

    def read(snapshot: Snapshot) -> int:
        seen.append(snapshot.version)
        if snapshot.version == 1:
            # Garbage collection takes version 1 after a publish of version 2.
            (root / "current").write_text("2")
            (root / "snapshots" / snapshot_name(1)).unlink()
            raise SnapshotGone
        return snapshot.version

    value, snapshot = read_snapshot(root / "current", _locate(root), read)
    assert (value, snapshot.version, snapshot.attempts) == (2, 2, 2)
    assert seen == [1, 2]


def test_a_snapshot_missing_at_the_lookup_reads_the_pointer_again(tmp_path: Path) -> None:
    root = _store(tmp_path / "s", current="1", versions=(2,))
    looked: list[str] = []

    def locate(name: str) -> Path | None:
        looked.append(name)
        if len(looked) == 1:
            (root / "current").write_text("2")
        return _locate(root)(name)

    value, snapshot = read_snapshot(root / "current", locate, lambda found: found.name)
    assert value == snapshot_name(2)
    assert snapshot.attempts == 2


def test_a_pointer_naming_a_missing_snapshot_twice_is_corrupt(tmp_path: Path) -> None:
    root = _store(tmp_path / "s", current="3", versions=(1,))
    with pytest.raises(StoreError) as caught:
        read_snapshot(root / "current", _locate(root), lambda found: found)
    assert caught.value.state == "corrupt"
    assert "version 3" in str(caught.value)


def test_a_missing_pointer_is_corrupt(tmp_path: Path) -> None:
    root = _store(tmp_path / "s")
    (root / "current").unlink()
    for current in (root / "current", None):
        with pytest.raises(StoreError) as caught:
            read_snapshot(current, _locate(root), lambda found: found)
        assert caught.value.state == "corrupt"


def test_reserved_tables_are_grouped_as_internal() -> None:
    tables = [
        TableInfo("notes", "notes", "tables", True),
        TableInfo("applied_tx", "applied_tx", "tables", True),
        TableInfo("fsqlite_meta", "fsqlite_meta", "tables", True),
        TableInfo("recent", "recent", "views", False),
    ]
    assert [(table.id, table.group) for table in source.group_reserved(tables)] == [
        ("notes", "tables"),
        ("applied_tx", "internal"),
        ("fsqlite_meta", "internal"),
        ("recent", "views"),
    ]


# ── The routes ───────────────────────────────────────────────


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    server._set_root_dir(tmp_path)
    plugins = [plugin for plugin in server._LOADED_PLUGINS if plugin.name == "fsqlite"]
    with TestClient(Starlette(routes=build_plugin_routes(plugins))) as test_client:
        yield test_client


def _get(client: TestClient, route: str, path: str) -> tuple[int, dict[str, Any]]:
    response = client.get(f"/api/plugin/fsqlite/{route}", params={"path": path})
    return response.status_code, response.json()


def test_the_marker_is_the_store_kind_and_its_folder_is_badged(tmp_path: Path) -> None:
    root = _store(tmp_path / "s")
    assert server._classify_content_kind(root / "fsqlite.json", ".json") == "sqlite-store"
    assert "fsqlite.json" in collect_folder_markers(server._PLUGIN_KIND_RULES)
    # A file merely named fsqlite.json stays structured data.
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "fsqlite.json").write_text('{"format": "parquet"}')
    assert server._classify_content_kind(tmp_path / "other" / "fsqlite.json", ".json") == (
        "structured"
    )


def test_info_reads_the_snapshot_current_names_and_touches_nothing(
    client: TestClient, tmp_path: Path
) -> None:
    root = _store(tmp_path / "s", current="2\n", versions=(1, 2))
    (root / "tx" / "pending" / "1-a.txn").mkdir(parents=True)
    (root / "tx" / "pending" / "1-a.txn" / "COMMITTED").touch()
    before = _listing(root)
    status, body = _get(client, "info", "s/fsqlite.json")
    assert status == 200, body
    assert "error" not in body
    assert body["generation"].startswith("2-")
    assert body["store"] == {
        "format_version": "f1.0",
        "store_id": STORE_ID,
        "required_features": [],
        "pending": {"committed": 1, "uncommitted": 0, "complete": True},
        "version": 2,
        "snapshot": snapshot_name(2),
        "attempts": 1,
    }
    snapshot = body["snapshot"]
    assert snapshot["access"]["mode"] == "immutable"
    assert snapshot["database"]["application_name"] == "fsqlite snapshot"
    assert _listing(root) == before


@pytest.mark.parametrize(
    ("change", "state"),
    [
        ("pointer", "corrupt"),
        ("missing", "corrupt"),
        ("marker", "unsupported"),
    ],
)
def test_info_names_the_state_of_a_store_it_cannot_show(
    client: TestClient, tmp_path: Path, change: str, state: str
) -> None:
    root = _store(tmp_path / "s")
    if change == "pointer":
        (root / "current").write_text("one")
    elif change == "missing":
        (root / "current").write_text("9")
    else:
        (root / "fsqlite.json").write_text(MARKER.replace("f1.0", "f9.0"))
    status, body = _get(client, "info", "s/fsqlite.json")
    assert status == 200, body
    assert body["error"]["state"] == state
    assert "snapshot" not in body


def test_children_are_the_snapshot_tables_with_the_reserved_ones_muted(
    client: TestClient, tmp_path: Path
) -> None:
    root = _store(tmp_path / "s")
    status, body = _get(client, "children", "s/fsqlite.json")
    assert status == 200
    assert body == {
        "children": [
            {"name": "applied_tx", "path": "s/fsqlite.json/applied_tx", "muted": True},
            {"name": "fsqlite_meta", "path": "s/fsqlite.json/fsqlite_meta", "muted": True},
            {"name": "notes", "path": "s/fsqlite.json/notes"},
        ],
        "version": 1,
        "snapshot": snapshot_name(1),
    }
    (root / "current").write_text("")
    status, body = _get(client, "children", "s/fsqlite.json")
    assert status == 200
    assert body["children"] == []
    assert body["error"]["state"] == "corrupt"


def test_schema_answers_for_the_snapshot_or_one_table(client: TestClient, tmp_path: Path) -> None:
    root = _store(tmp_path / "s")
    status, body = _get(client, "schema", "s/fsqlite.json")
    assert status == 200, body
    assert body["type"] == "fsqlite_schema"
    assert body["table"] is None
    assert body["generation"].startswith("1-")
    assert {entry["table"] for entry in body["objects"]} == {"applied_tx", "fsqlite_meta", "notes"}
    status, body = _get(client, "schema", "s/fsqlite.json/notes")
    assert status == 200, body
    assert body["table"] == "notes"
    assert [entry["segment"] for entry in body["objects"] if entry["type"] == "table"] == ["notes"]
    status, body = _get(client, "schema", "s/fsqlite.json/absent")
    assert (status, body["code"]) == (404, "table_not_found")
    (root / "fsqlite.json").write_text(MARKER.replace("f1.0", "f9.0"))
    status, body = _get(client, "schema", "s/fsqlite.json")
    assert status == 200
    assert body["error"]["state"] == "unsupported"
    assert "objects" not in body


def test_info_answers_at_a_table_address_for_its_store(client: TestClient, tmp_path: Path) -> None:
    _store(tmp_path / "s")
    status, body = _get(client, "info", "s/fsqlite.json/notes")
    assert status == 200, body
    assert body["store"]["version"] == 1
    # Children are asked of the store itself, never of one of its tables.
    status, _body = _get(client, "children", "s/fsqlite.json/notes")
    assert status == 404


# ── The table source ─────────────────────────────────────────


@pytest.fixture
def app_client(tmp_path: Path) -> Iterator[TestClient]:
    """The whole application, whose table routes serve the store's [[table_source]]."""
    reset_source_session()
    server._set_root_dir(tmp_path)
    with TestClient(server.app) as test_client:
        yield test_client


def _table(client: TestClient, route: str, **params: str) -> tuple[int, dict[str, Any]]:
    response = client.get(f"/api/plugin/table/{route}", params=params)
    return response.status_code, response.json()


def test_the_table_routes_read_the_snapshot_current_names_and_touch_nothing(
    app_client: TestClient, tmp_path: Path
) -> None:
    root = _store(tmp_path / "s", current="2", versions=(1, 2))
    connection = sqlite3.connect(root / "snapshots" / snapshot_name(2), isolation_level=None)
    try:
        connection.executescript("INSERT INTO notes VALUES (1, 'first'), (2, 'second');")
    finally:
        connection.close()
    generation = store_generation(root / "fsqlite.json", root / "current", 2)
    before = _listing(root)

    status, body = _table(app_client, "tables", path="s/fsqlite.json")
    assert status == 200, body
    assert body["generation"] == generation
    assert [(item["id"], item["group"], item["path"]) for item in body["tables"]] == [
        ("applied_tx", "internal", "s/fsqlite.json/applied_tx"),
        ("fsqlite_meta", "internal", "s/fsqlite.json/fsqlite_meta"),
        ("notes", "tables", "s/fsqlite.json/notes"),
    ]
    status, body = _table(app_client, "rows", path="s/fsqlite.json/notes")
    assert status == 200, body
    assert body["generation"] == generation
    assert [row["cells"]["title"] for row in body["rows"]] == ["first", "second"]
    status, body = _table(app_client, "schema", path="s/fsqlite.json/notes")
    assert status == 200, body
    assert [field["name"] for field in body["fields"]] == ["id", "title"]
    status, body = _table(app_client, "rows", path="s/fsqlite.json/absent")
    assert (status, body["code"]) == (404, "table_not_found")
    assert _listing(root) == before


@pytest.mark.parametrize(("change", "state"), [("marker", "unsupported"), ("pointer", "corrupt")])
def test_the_table_routes_refuse_a_store_they_cannot_read(
    app_client: TestClient, tmp_path: Path, change: str, state: str
) -> None:
    root = _store(tmp_path / "s")
    if change == "marker":
        (root / "fsqlite.json").write_text(MARKER.replace("f1.0", "f9.0"))
    else:
        (root / "current").write_text("one")
    status, body = _table(app_client, "tables", path="s/fsqlite.json")
    assert (status, body["code"], body["state"]) == (422, "source_unreadable", state)


@pytest.mark.parametrize(
    ("route", "path"),
    [
        ("fsqlite/info", "s/fsqlite.json"),
        ("fsqlite/children", "s/fsqlite.json"),
        ("fsqlite/schema", "s/fsqlite.json/notes"),
        ("table/tables", "s/fsqlite.json"),
        ("table/rows", "s/fsqlite.json/notes"),
    ],
)
def test_every_snapshot_read_retries_once_when_the_reader_finds_it_gone(
    app_client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    path: str,
) -> None:
    root = _store(tmp_path / "s", current="1", versions=(1, 2))
    real = source.snapshot_database
    opened: list[int] = []

    def collect_then_open(
        files: source.StoreFiles, snapshot: Snapshot, *, subject: str
    ) -> Database:
        opened.append(snapshot.version)
        if snapshot.version == 1:
            # A publish moved the pointer and garbage collection took version 1 after
            # the server read the pointer, before a reader opened the file.
            (root / "current").write_text("2")
            (root / "snapshots" / snapshot_name(1)).unlink()
        return real(files, snapshot, subject=subject)

    monkeypatch.setattr(source, "snapshot_database", collect_then_open)
    response = app_client.get(f"/api/plugin/{route}", params={"path": path})
    assert response.status_code == 200, response.json()
    assert opened == [1, 2]
    body = response.json()
    assert "error" not in body
    if route == "fsqlite/info":
        assert (body["store"]["version"], body["store"]["attempts"]) == (2, 2)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("PRAGMA application_id = 0", "application_id"),
        ("DELETE FROM fsqlite_meta WHERE key = 'store_id'", "store_id or format_version"),
        (
            "UPDATE fsqlite_meta SET value = '630e8400-e29b-41d4-a716-446655440000'"
            " WHERE key = 'store_id'",
            "store_id or format_version",
        ),
        (
            "UPDATE fsqlite_meta SET value = 'f2.0' WHERE key = 'format_version'",
            "store_id or format_version",
        ),
        ("DROP TABLE fsqlite_meta", "valid fsqlite_meta table"),
        ("DROP TABLE applied_tx", "valid applied_tx table"),
        ("ALTER TABLE applied_tx ADD COLUMN extra TEXT", "valid applied_tx table"),
        ("DELETE FROM fsqlite_meta WHERE key = 'schema_hash'", "schema_hash"),
        (
            "UPDATE fsqlite_meta SET value = 'ABCDEFGH01234567' WHERE key = 'schema_hash'",
            "schema_hash",
        ),
        ("DELETE FROM fsqlite_meta WHERE key = 'tool_version'", "tool_version"),
    ],
)
def test_an_unverified_snapshot_is_refused_by_every_store_route(
    app_client: TestClient, tmp_path: Path, change: str, message: str
) -> None:
    root = _store(tmp_path / "s")
    connection = sqlite3.connect(root / "snapshots" / snapshot_name(1), isolation_level=None)
    try:
        connection.execute(change)
    finally:
        connection.close()

    for route, path in (
        ("info", "s/fsqlite.json"),
        ("schema", "s/fsqlite.json/notes"),
        ("children", "s/fsqlite.json"),
    ):
        status, body = _get(app_client, route, path)
        assert status == 200, body
        assert body["error"]["state"] == "corrupt"
        assert message in body["error"]["message"]
        assert "snapshot" not in body and "objects" not in body
        if route == "children":
            assert body["children"] == []

    for route, path in (("tables", "s/fsqlite.json"), ("rows", "s/fsqlite.json/notes")):
        status, body = _table(app_client, route, path=path)
        assert (status, body["code"], body["state"]) == (422, "source_unreadable", "corrupt")
        assert message in body["error"]


def test_a_pointer_can_resolve_through_an_in_store_symlink(
    app_client: TestClient, tmp_path: Path
) -> None:
    root = _store(tmp_path / "s")
    pointer = root / "current"
    pointer.rename(root / "pointer")
    pointer.symlink_to("pointer")
    status, body = _get(app_client, "info", "s/fsqlite.json")
    assert status == 200, body
    assert body["store"]["version"] == 1
    assert "error" not in body


def test_a_numbered_snapshot_cannot_link_to_another_generation(
    app_client: TestClient, tmp_path: Path
) -> None:
    root = _store(tmp_path / "s", versions=(1, 2))
    named = root / "snapshots" / snapshot_name(1)
    named.unlink()
    named.symlink_to(snapshot_name(2))
    status, body = _get(app_client, "info", "s/fsqlite.json")
    assert status == 200, body
    assert body["error"]["state"] == "corrupt"
    assert "linked snapshot" in body["error"]["message"]
    assert "snapshot" not in body
    status, body = _table(app_client, "rows", path="s/fsqlite.json/notes")
    assert (status, body["code"], body["state"]) == (422, "source_unreadable", "corrupt")


def test_a_published_snapshot_with_wal_frames_is_refused(
    app_client: TestClient, tmp_path: Path
) -> None:
    root = _store(tmp_path / "s")
    path = root / "snapshots" / snapshot_name(1)
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        assert connection.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)
        connection.execute("INSERT INTO notes VALUES (1, 'committed in the log')")
        assert path.with_name(path.name + "-wal").stat().st_size > 32
        before = _listing(root)

        status, body = _get(app_client, "info", "s/fsqlite.json")
        assert status == 200, body
        assert body["error"]["state"] == "corrupt"
        assert "-wal side file" in body["error"]["message"]
        assert "snapshot" not in body
        status, body = _table(app_client, "rows", path="s/fsqlite.json/notes")
        assert (status, body["code"], body["state"]) == (422, "source_unreadable", "corrupt")
        assert _listing(root) == before
    finally:
        connection.close()


def test_a_published_snapshot_with_a_hot_rollback_journal_is_refused(
    app_client: TestClient, tmp_path: Path
) -> None:
    root = _store(tmp_path / "s")
    path = root / "snapshots" / snapshot_name(1)
    # A killed writer can leave its uncommitted changes in the main file.
    create(path, mode="delete", rows=20_000)
    hot_journal(path)
    before = _listing(root)

    status, body = _get(app_client, "info", "s/fsqlite.json")
    assert status == 200, body
    assert body["error"]["state"] == "corrupt"
    assert "live SQLite -journal" in body["error"]["message"]
    assert "snapshot" not in body
    status, body = _table(app_client, "rows", path="s/fsqlite.json/t")
    assert (status, body["code"], body["state"]) == (422, "source_unreadable", "corrupt")
    assert _listing(root) == before


def test_a_zeroed_rollback_journal_does_not_hide_a_clean_snapshot(
    app_client: TestClient, tmp_path: Path
) -> None:
    root = _store(tmp_path / "s")
    snapshot = snapshot_name(1)
    (root / "snapshots" / (snapshot + "-journal")).write_bytes(bytes(512))
    status, body = _get(app_client, "info", "s/fsqlite.json")
    assert status == 200, body
    assert "error" not in body
    assert body["store"]["version"] == 1


def test_snapshot_identity_reports_an_older_sqlite_library_as_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reader.sqlite_access, "library_version", lambda: (3, 42, 0))
    with pytest.raises(SqliteAccessError, match="needs SQLite 3.43.0 or later") as refused:
        reader._identity_op({}, deadline=0)
    assert refused.value.state == "unsupported"
    assert "this reader uses SQLite" in refused.value.detail


@pytest.mark.parametrize(
    ("route", "operation"), [("rows", "sqlite_rows"), ("record", "sqlite_record")]
)
def test_collection_after_catalog_reports_a_retryable_error_for_the_whole_request(
    app_client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    operation: str,
) -> None:
    root = _store(tmp_path / "s", current="1", versions=(1, 2))
    old_snapshot = root / "snapshots" / snapshot_name(1)
    for version, title in ((1, "old"), (2, "new")):
        connection = sqlite3.connect(
            root / "snapshots" / snapshot_name(version), isolation_level=None
        )
        try:
            connection.execute("INSERT INTO notes VALUES (1, ?)", (title,))
        finally:
            connection.close()

    calls: list[str] = []
    real = Database.call

    def collect_then_query(
        database: Database, op: str, args: dict[str, Any], *, deadline: float
    ) -> Any:
        if database.file == old_snapshot:
            calls.append(op)
            if op == operation:
                assert "sqlite_catalog" in calls
                (root / "current").write_text("2")
                old_snapshot.unlink()
        return real(database, op, args, deadline=deadline)

    monkeypatch.setattr(Database, "call", collect_then_query)
    params = {"path": "s/fsqlite.json/notes"}
    if route == "record":
        params["key"] = "k.WzFd"
    status, body = _table(app_client, route, **params)
    assert (status, body["code"], body["state"]) == (409, "snapshot_moved", "changing")
    assert "Retry to open the current snapshot" in body["error"]
    assert "rows" not in body and "record" not in body

    status, body = _table(app_client, route, **params)
    assert status == 200, body
    assert body["generation"].startswith("2-")
    if route == "rows":
        assert body["rows"][0]["cells"]["title"] == "new"
    else:
        assert body["cells"]["title"] == "new"


def test_a_snapshot_opened_as_a_database_groups_the_reserved_tables_too(
    app_client: TestClient, tmp_path: Path
) -> None:
    _store(tmp_path / "s")
    status, body = _table(app_client, "tables", path=f"s/snapshots/{snapshot_name(1)}")
    assert status == 200, body
    assert {item["id"]: item["group"] for item in body["tables"]} == {
        "applied_tx": "internal",
        "fsqlite_meta": "internal",
        "notes": "tables",
    }


def test_a_path_that_is_not_a_marker_is_not_found(client: TestClient, tmp_path: Path) -> None:
    _store(tmp_path / "s")
    for path in ("s/current", "s/absent.json", "../escape/fsqlite.json"):
        status, body = _get(client, "info", path)
        assert status == 404, (path, body)
