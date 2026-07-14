"""Read-only LMDB adapter for metabrowser core.

The built-in ``lmdb`` plugin (kind ``lmdb-database``) renders LMDB envs in
the browser; this module is the format-only surface it talks to. The split
keeps domain knowledge out of metabrowser core: callers pass bytes in and
get bytes (or a best-effort decoded value) out.

Higher-level plugins can teach the reader about their value schemas by
calling :func:`register_value_decoder` at plugin-load time. The registry
runs before the default decoder chain (utf-8 → JSON → msgpack → hex). The
chain returns the FIRST successful decode, falling through to a hex
preview when nothing else recognises the bytes.

LMDB envs surface as folders containing ``data.mdb`` + ``lock.mdb``. We
open them read-only with ``lock=False`` so a writer in another process
(e.g. the JS dataset writer) cannot block us.

Example::

    with LmdbReader("/path/to/blobs.index.lmdb") as reader:
        keys, next_cursor = reader.iter_keys(prefix=b"blob:", limit=200)
        for k in keys:
            value = reader.get(k.key)
            decoded, decoder = decode_value(k.subdb, k.key, value or b"")
            ...
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, NamedTuple, Self

import msgpack

LOG = logging.getLogger(__name__)


# ── Types ───────────────────────────────────────────────────────────


class LmdbStats(NamedTuple):
    """Subset of the stats LMDB returns on an env, normalised."""

    map_size: int
    psize: int
    depth: int
    branch_pages: int
    leaf_pages: int
    entries: int


class LmdbKey(NamedTuple):
    """One key plus the named subdb it lives in (empty string = main DB)."""

    subdb: str
    key: bytes


# Decoder protocol: predicate decides whether to claim a row; decode
# converts bytes to a JSON-safe Python value (str, int, float, bool, None,
# list, dict). Decoders MAY raise; ``decode_value`` catches and falls
# through.
ValuePredicate = Callable[[str, bytes, bytes], bool]  # (subdb, key, value) -> bool
ValueDecoder = Callable[[bytes], Any]


# ── Decoder registry ────────────────────────────────────────────────

_REGISTERED_DECODERS: list[tuple[ValuePredicate, ValueDecoder]] = []


def register_value_decoder(predicate: ValuePredicate, decode: ValueDecoder) -> None:
    """Register a value decoder.

    Higher-level plugins call this at plugin import to teach the LMDB reader
    about their value schemas. Registration order is preserved; later
    registrations take precedence over earlier ones. Decoders run BEFORE the
    default chain (utf-8 / JSON / msgpack / hex) and the first matching
    predicate whose decode succeeds wins.
    """
    _REGISTERED_DECODERS.append((predicate, decode))


def clear_value_decoders() -> None:
    """Test hook: drop every registered decoder. Production code never calls this."""
    _REGISTERED_DECODERS.clear()


def _try_utf8(value: bytes) -> Any:
    # ``decode("utf-8")`` succeeds on garbage that happens to be UTF-8;
    # the chain bias is on the caller's side, so we don't try to
    # heuristically reject "this looks like binary that decoded by luck."
    return value.decode("utf-8")


def _try_json(value: bytes) -> Any:
    return json.loads(value)


def _try_msgpack(value: bytes) -> Any:

    return msgpack.unpackb(value, raw=False, strict_map_key=False)


def _to_hex_preview(value: bytes, limit: int = 256) -> str:
    """Hex preview for raw binary; truncated past ``limit`` bytes."""
    if len(value) <= limit:
        return value.hex()
    return value[:limit].hex() + f"...({len(value) - limit} more bytes)"


def decode_value(subdb: str, key: bytes, value: bytes) -> tuple[Any, str]:
    """Decode a value through the registry + default chain.

    Returns ``(decoded, decoder_used)``. ``decoder_used`` is one of:
    a custom decoder's ``__name__``, ``"utf8"``, ``"json"``, ``"msgpack"``,
    or ``"hex"`` (always-succeeds fallback).
    """
    for predicate, decode in reversed(_REGISTERED_DECODERS):
        try:
            if predicate(subdb, key, value):
                decoded = decode(value)
                return decoded, getattr(decode, "__name__", "custom")
        except Exception:
            # Custom decoders are best-effort; fall through to the default chain.
            continue

    # Default chain. Order: msgpack is the most likely binary format we'll
    # see, so try it before utf-8 / JSON so binary msgpack maps don't
    # decode as garbage utf-8.
    for decoder, label in (
        (_try_msgpack, "msgpack"),
        (_try_utf8, "utf8"),
        (_try_json, "json"),
    ):
        try:
            return decoder(value), label
        except Exception:
            continue

    return _to_hex_preview(value), "hex"


# ── Reader ──────────────────────────────────────────────────────────


class LmdbReader:
    """Read-only wrapper around an LMDB environment.

    Opens the env with ``readonly=True`` and ``lock=False`` so a writer in
    another process cannot block us. ``max_dbs`` defaults to 32 to cover
    named subdbs without forcing the caller to know the count up front.
    """

    def __init__(self, path: str, max_dbs: int = 32) -> None:
        self._path = path
        self._max_dbs = max_dbs
        self._env: Any | None = None
        self._subdb_handles: dict[str, Any] = {}

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def open(self) -> None:
        try:
            import lmdb
        except ImportError as exc:
            raise RuntimeError(
                "lmdb support not installed; reinstall metabrowser to pick up the lmdb dep"
            ) from exc
        if self._env is not None:
            return
        # subdir=True is required when the env IS a directory (the dataset
        # convention writes data.mdb + lock.mdb under blobs.index.lmdb/). If
        # the caller hands us a path to data.mdb itself, point to its parent.
        env_path = self._path
        try:
            self._env = lmdb.open(
                env_path,
                readonly=True,
                lock=False,
                max_dbs=self._max_dbs,
                subdir=True,
            )
        except lmdb.Error:
            # Single-file env: caller pointed at data.mdb (or path is wrong).
            self._env = lmdb.open(
                env_path,
                readonly=True,
                lock=False,
                max_dbs=self._max_dbs,
                subdir=False,
            )

    def close(self) -> None:
        if self._env is not None:
            self._env.close()
            self._env = None
            self._subdb_handles.clear()

    def _require_env(self) -> Any:
        if self._env is None:
            raise RuntimeError("LmdbReader is not open; call .open() or use as a context manager")
        return self._env

    def _db(self, env: Any, subdb: str | None) -> Any:
        if not subdb:
            return None  # lmdb uses the main DB when db=None
        handle = self._subdb_handles.get(subdb)
        if handle is None:
            handle = env.open_db(subdb.encode("utf-8"), create=False)
            self._subdb_handles[subdb] = handle
        return handle

    def stats(self, subdb: str | None = None) -> LmdbStats:
        env = self._require_env()
        with env.begin(db=self._db(env, subdb)) as txn:
            stat = txn.stat()
        info = env.info()
        return LmdbStats(
            map_size=info["map_size"],
            psize=stat["psize"],
            depth=stat["depth"],
            branch_pages=stat["branch_pages"],
            leaf_pages=stat["leaf_pages"],
            entries=stat["entries"],
        )

    def subdbs(self) -> list[str]:
        """Enumerate named subdbs in the main DB.

        LMDB doesn't expose a "list named DBs" call; the convention is that
        each named subdb's name appears as a key in the main DB. We walk the
        main DB and return entries whose value points at a subdb root.
        """
        env = self._require_env()
        names: list[str] = []
        with env.begin() as txn:
            cursor = txn.cursor()
            for key, _value in cursor:
                # Try to open as a subdb; if it works the key is a subdb name.
                try:
                    env.open_db(key, txn=txn, create=False)
                    names.append(key.decode("utf-8", errors="replace"))
                except Exception:
                    continue
        return names

    def iter_keys(
        self,
        subdb: str | None = None,
        prefix: bytes | None = None,
        cursor: bytes | None = None,
        limit: int = 1000,
    ) -> tuple[list[LmdbKey], bytes | None]:
        """Walk keys, optionally filtered by ``prefix``, returning at most ``limit``.

        ``cursor`` is the raw key bytes to seek to before walking (the
        ``next_cursor`` returned by a previous call). ``None`` means start
        from the beginning (or the prefix's start).

        Returns ``(keys, next_cursor)``. ``next_cursor`` is the next key
        beyond the returned page, or ``None`` if the page exhausted the range.
        """
        if limit <= 0:
            return [], None
        env = self._require_env()
        db = self._db(env, subdb)
        subdb_name = subdb or ""
        out: list[LmdbKey] = []
        next_cursor: bytes | None = None
        with env.begin(db=db) as txn:
            c = txn.cursor()
            seek_target = cursor if cursor is not None else prefix
            if seek_target is None:
                if not c.first():
                    return [], None
            else:
                if not c.set_range(seek_target):
                    return [], None
            for raw_key in c.iternext(keys=True, values=False):
                if prefix is not None and not raw_key.startswith(prefix):
                    break
                if len(out) >= limit:
                    next_cursor = bytes(raw_key)
                    break
                out.append(LmdbKey(subdb=subdb_name, key=bytes(raw_key)))
        return out, next_cursor

    def get(self, key: bytes, subdb: str | None = None) -> bytes | None:
        env = self._require_env()
        db = self._db(env, subdb)
        with env.begin(db=db) as txn:
            raw = txn.get(key)
        if raw is None:
            return None
        return bytes(raw)
