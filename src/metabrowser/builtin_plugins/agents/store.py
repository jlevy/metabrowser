"""The catalog's on-disk cache: one owner-only JSON file per summarized session.

The directory is ``plugin_cache_directory("agents")``, which :mod:`metabrowser.plugin_api`
keeps owner-only; inside it each home has a subdirectory named from the agent and a hash
of the home's path, and each session one file named by the hash of its **key**. The key
is what the summary was computed from, so a stale file is never wrong, only unused:

- the agent and session id;
- every source file's home-relative path, size, and modification time in nanoseconds;
- the fast pass's last-activity time (a Codex summary also reads database rows that no
  source file's ``stat`` shows);
- each measure family's schema version.

A file that is absent, unreadable, too large, malformed, or of another format is a miss,
and the session is summarized again. Files are written atomically (a private temporary
file, then ``os.replace``), so a reader never sees half a summary and a crash leaves at
most a temporary file, which :meth:`SummaryStore.prune` removes.

Summaries store source paths relative to the home, so a cache survives the home moving
and holds no absolute path of its own.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import time
import uuid
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final

from metabrowser.plugin_api import PluginCacheUnavailableError, plugin_cache_directory

from . import claude, codex
from .model import Agent, DriftSummary, SessionSummary
from .readers import as_dict, as_int, as_list, as_str

PLUGIN_NAME: Final = "agents"

# The version of the entry file's own layout. A file of another format is a miss.
ENTRY_FORMAT: Final = 1

# The most bytes of one entry file read back. An entry is one summary: a few hundred bytes
# plus a child-id list, so this bounds a corrupted or hostile file, not a real one: 7.5
# times the largest real entry (8.5 KB, from a session with many children). The
# measurement record in `catalog.py` ("Measurements") gives the largest real entry.
MAX_ENTRY_BYTES: Final = 64 * 1024

_PRIVATE_FILE: Final = 0o600
_PRIVATE_DIRECTORY: Final = 0o700

# A temporary file older than this is a crashed write's leftover, safe to remove.
_TEMPORARY_MIN_AGE_SECONDS: Final = 60.0

_STATUSES: Final = ("running", "finished", "failed", "unknown")


def session_key(summary: SessionSummary, home: Path) -> str:
    """The cache key of a fast-pass *summary*: a hash of what the summary is computed from.

    *summary* is the fast pass's, whose ``source_paths`` are absolute and whose
    ``last_activity`` is the store's own update time for a Codex thread.
    """

    families = claude.FAMILY_VERSIONS if summary.agent == "claude" else codex.FAMILY_VERSIONS
    files: list[list[object]] = []
    for raw in summary.source_paths:
        path = Path(raw)
        try:
            info = path.stat()
            files.append([_home_relative(path, home), info.st_size, info.st_mtime_ns])
        except OSError:
            files.append([_home_relative(path, home), None, None])
    blob = json.dumps(
        [summary.agent, summary.session_id, files, summary.last_activity, sorted(families.items())],
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _home_relative(path: Path, home: Path) -> str:
    try:
        return path.relative_to(home).as_posix()
    except ValueError:
        return path.as_posix()


class SummaryStore:
    """The cache directory of one home. Methods never raise for a filesystem error.

    A failed write is counted in ``write_errors`` and the store stays usable, so a full
    disk degrades a pass to uncached rather than failing it.
    """

    def __init__(self, directory: Path, home: Path) -> None:
        self.directory = directory
        self.home = home
        self.write_errors = 0

    @classmethod
    def open(cls, agent: Agent, home: Path) -> SummaryStore | None:
        """The store of *home*, or ``None`` when no private cache directory can be made.

        Blocking: creates directories. Call it from the worker, never a request.
        """

        try:
            root = plugin_cache_directory(PLUGIN_NAME)
            digest = hashlib.sha256(str(home).encode()).hexdigest()[:16]
            directory = root / f"{agent}-{digest}"
            directory.mkdir(mode=_PRIVATE_DIRECTORY, exist_ok=True)
            os.chmod(directory, _PRIVATE_DIRECTORY)
        except (PluginCacheUnavailableError, OSError):
            return None
        return cls(directory, home)

    def load(self, key: str) -> tuple[SessionSummary, DriftSummary] | None:
        """The summary and drift stored under *key*, or ``None`` for any kind of miss."""

        path = self.directory / f"{key}.json"
        try:
            with path.open("rb") as handle:
                raw = handle.read(MAX_ENTRY_BYTES + 1)
        except OSError:
            return None
        if len(raw) > MAX_ENTRY_BYTES:
            return None
        try:
            entry = as_dict(json.loads(raw))
        except (ValueError, RecursionError):
            return None
        if entry is None or entry.get("format") != ENTRY_FORMAT or entry.get("key") != key:
            return None
        summary = _summary_from_json(as_dict(entry.get("summary")), self.home)
        drift = _drift_from_json(as_dict(entry.get("drift")))
        if summary is None or drift is None:
            return None
        return summary, drift

    def save(self, key: str, summary: SessionSummary, drift: DriftSummary) -> bool:
        """Write the entry atomically with owner-only permissions; False if it failed."""

        body = summary.to_json()
        body["source_paths"] = [_home_relative(Path(p), self.home) for p in summary.source_paths]
        text = json.dumps(
            {"format": ENTRY_FORMAT, "key": key, "summary": body, "drift": drift.to_json()},
            separators=(",", ":"),
        )
        temporary = self.directory / f"{key}.json.tmp-{uuid.uuid4().hex}"
        descriptor = -1
        created = False
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _PRIVATE_FILE)
            created = True
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                handle.write(text)
            os.replace(temporary, self.directory / f"{key}.json")
        except OSError:
            if descriptor >= 0:
                os.close(descriptor)
            if created:  # the name is unique, and only a file this call made is removed
                with contextlib.suppress(OSError):
                    os.unlink(temporary)
            self.write_errors += 1
            return False
        return True

    def prune(self, keep: Iterable[str]) -> int:
        """Delete entry files whose key is not in *keep*, and leftover temporary files.

        Returns how many files were removed. Called only after a pass has seen every
        session, so a key missing from *keep* names a session that changed or is gone.
        """

        wanted = {f"{key}.json" for key in keep}
        removed = 0
        try:
            with os.scandir(self.directory) as entries:
                found = [(e.name, e) for e in entries if e.is_file(follow_symlinks=False)]
        except OSError:
            return 0
        now = time.time()
        for name, entry in found:
            if name in wanted:
                continue
            if name.endswith(".json"):
                pass
            elif ".json.tmp-" in name:
                # A temporary file this young may be a write in progress.
                try:
                    if now - entry.stat().st_mtime < _TEMPORARY_MIN_AGE_SECONDS:
                        continue
                except OSError:
                    continue
            else:
                continue
            try:
                os.unlink(self.directory / name)
                removed += 1
            except OSError:
                continue
        return removed


def _summary_from_json(data: dict[str, object] | None, home: Path) -> SessionSummary | None:
    if data is None:
        return None
    agent = as_str(data.get("agent"))
    session_id = as_str(data.get("session_id"))
    status = as_str(data.get("status"))
    if agent not in ("claude", "codex") or session_id is None or status not in _STATUSES:
        return None
    versions = as_dict(data.get("family_versions")) or {}
    sources: list[str] = []
    for raw in as_list(data.get("source_paths")):
        text = as_str(raw)
        if text is None:
            return None
        sources.append(text if os.path.isabs(text) else str(home / text))
    return SessionSummary(
        agent=agent,
        session_id=session_id,
        title=as_str(data.get("title")),
        parent_id=as_str(data.get("parent_id")),
        child_ids=tuple(s for s in map(as_str, as_list(data.get("child_ids"))) if s),
        origin=as_str(data.get("origin")) or "human",
        cwd=as_str(data.get("cwd")),
        git_branch=as_str(data.get("git_branch")),
        started_at=_number(data.get("started_at")),
        ended_at=_number(data.get("ended_at")),
        last_activity=_number(data.get("last_activity")),
        size_bytes=as_int(data.get("size_bytes")) or 0,
        records=as_int(data.get("records")),
        replayed_records=as_int(data.get("replayed_records")) or 0,
        turns=as_int(data.get("turns")),
        models=tuple(s for s in map(as_str, as_list(data.get("models"))) if s),
        status=status,
        source_paths=tuple(sources),
        family_versions={k: v for k, v in versions.items() if isinstance(v, int)},
    )


def _drift_from_json(data: dict[str, object] | None) -> DriftSummary | None:
    if data is None:
        return None

    def counts(name: str) -> Mapping[str, int]:
        table = as_dict(data.get(name)) or {}
        return {k: v for k, v in table.items() if isinstance(v, int) and not isinstance(v, bool)}

    return DriftSummary(
        unknown_types=counts("unknown_types"),
        unexpected_columns=counts("unexpected_columns"),
        missing_columns=counts("missing_columns"),
        read_errors=counts("read_errors"),
        truncated=data.get("truncated") is True,
    )


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
