"""A folder's published collection snapshot. Reads and refreshes run in a worker."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from metabrowser.ignore_filter import IgnoreMode, make_ignore_filter
from metabrowser.plugin_api import (
    PluginCacheUnavailableError,
    plugin_cache_directory,
    register_root_callback,
)

if TYPE_CHECKING:
    from softschema.collection import CollectionScan

LOG = logging.getLogger(__name__)
_FORMAT = "softschema-collection-v2"
_REFRESH_SECONDS = 3.0
_INDEX_LIMIT = 4
# Leave time for the CLI's 30-second request deadline to return the index state.
INDEX_WAIT_SECONDS = 20.0
_WORKERS = ThreadPoolExecutor(max_workers=1, thread_name_prefix="softschema-collection")
_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class CollectionVersion:
    snapshot: CollectionScan | None = None
    generation: str = "indexing"
    indexing: bool = True
    cache_available: bool | None = None
    failed: bool = False


class CollectionIndex:
    def __init__(self, root: Path, served_root: Path) -> None:
        self.root = root
        self.served_root = served_root
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._started = 0.0
        self._view = CollectionVersion()

    def request(self, *, wait: float | None = None) -> CollectionVersion:
        with self._lock:
            now = time.monotonic()
            if not self._stop.is_set() and (
                self._started == 0.0
                or (self._ready.is_set() and now - self._started >= _REFRESH_SECONDS)
            ):
                self._started = now
                self._ready.clear()
                self._view = replace(self._view, indexing=True)
                _WORKERS.submit(self._refresh)
        if wait is not None:
            self._ready.wait(wait)
        with self._lock:
            return self._view

    def stop(self) -> None:
        self._stop.set()

    def _refresh(self) -> None:
        from softschema.collection import scan_collection

        with self._lock:
            prior = self._view
        try:
            database = self._database()
            previous = prior.snapshot
            generation = prior.generation
            if previous is None and database is not None:
                saved = self._load(database)
                if saved is not None:
                    previous, generation = saved
                    with self._lock:
                        self._view = CollectionVersion(previous, generation, True, True)
            ignore = make_ignore_filter(self.served_root, IgnoreMode.default)
            prefix = self.root.relative_to(self.served_root)

            def ignored(path: str, is_directory: bool) -> bool:
                return self._stop.is_set() or ignore(prefix / path, is_dir=is_directory)

            if self._stop.is_set():
                return
            snapshot = scan_collection(
                self.root, previous=previous, ignore=ignored, ignore_id="default"
            )
            if self._stop.is_set():
                return
            changed = (
                previous is None
                or snapshot.added
                or snapshot.changed
                or snapshot.removed
                or snapshot.problems != previous.problems
                or snapshot.complete != previous.complete
                or snapshot.records != previous.records
                or snapshot.schemas != previous.schemas
            )
            if changed or generation == "indexing":
                raw = snapshot.snapshot_json()
                generation = hashlib.sha256(raw.encode()).hexdigest()[:24]
                if database is not None:
                    try:
                        self._save(database, raw, generation)
                    except sqlite3.Error:
                        database = None
            with self._lock:
                self._view = CollectionVersion(snapshot, generation, False, database is not None)
        except Exception:
            LOG.exception("SoftSchema collection refresh failed")
            with self._lock:
                self._view = replace(self._view, indexing=False, failed=True)
        finally:
            with self._lock:
                self._started = time.monotonic()
                self._ready.set()

    def _database(self) -> Path | None:
        key = "\0".join((_FORMAT, version("softschema"), str(self.served_root), str(self.root)))
        try:
            cache = plugin_cache_directory("softschema")
            return cache / (hashlib.sha256(key.encode()).hexdigest() + ".sqlite")
        except PluginCacheUnavailableError:
            return None

    @staticmethod
    def _load(path: Path) -> tuple[CollectionScan, str] | None:
        from contextlib import closing

        from softschema.collection import CollectionScan

        try:
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
                row = db.execute(
                    "SELECT contents, generation FROM snapshot WHERE id = 1"
                ).fetchone()
            return (CollectionScan.from_snapshot_json(row[0]), row[1]) if row else None
        except (sqlite3.Error, ValueError):
            return None

    @staticmethod
    def _save(path: Path, raw: str, generation: str) -> None:
        from contextlib import closing

        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS snapshot "
                "(id INTEGER PRIMARY KEY, contents TEXT, generation TEXT)"
            )
            db.execute("INSERT OR REPLACE INTO snapshot VALUES (1, ?, ?)", (raw, generation))


_INDEXES: OrderedDict[tuple[Path, Path], CollectionIndex] = OrderedDict()


def index_for(root: Path, served_root: Path) -> CollectionIndex:
    with _LOCK:
        key = (served_root, root)
        index = _INDEXES.get(key)
        if index is None:
            index = CollectionIndex(root, served_root)
            _INDEXES[key] = index
            if len(_INDEXES) > _INDEX_LIMIT:
                _, oldest = _INDEXES.popitem(last=False)
                oldest.stop()
        else:
            _INDEXES.move_to_end(key)
        return index


def has_collection(folder: Path) -> bool:
    with _LOCK:
        return any(folder.is_relative_to(root) for _, root in _INDEXES)


def _reset() -> None:
    with _LOCK:
        for index in _INDEXES.values():
            index.stop()
        _INDEXES.clear()


register_root_callback(_reset)
