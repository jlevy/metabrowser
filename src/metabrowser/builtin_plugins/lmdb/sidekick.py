"""Python sidekick for the built-in ``lmdb`` plugin.

Three handlers, all read-only, all paginated. Mounted under
``/api/plugin/lmdb/<route>``:

- ``keys``: list keys in an LMDB env (optionally filtered by prefix), with
  a short ``valuePreview`` per row.
- ``entry``: fetch one key's full value, decoded via the value-decoder
  chain (custom decoders → utf8 → JSON → msgpack → hex).
- ``stats``: env metadata (entry count, page size, depth, etc.) plus the
  set of named subdbs the env carries.

Path resolution goes through :func:`metabrowser.paths_safe._safe_path` to
keep operators inside the served root; the env can be either a directory
(the dataset convention) or a path to ``data.mdb`` itself.
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, Any

from starlette.responses import JSONResponse

from metabrowser.lmdb_reader import LmdbReader, decode_value
from metabrowser.paths_safe import _safe_path

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.requests import Request

LOG = logging.getLogger(__name__)


# Caps. The keys endpoint paginates aggressively so a 1 M-key index does
# not blow up a single response. The entry endpoint streams a single
# value back; values that fit in MAX_INLINE_VALUE_BYTES are JSON-encoded
# (base64 for binary), bigger values are truncated with a flag.
_DEFAULT_KEYS_LIMIT = 200
_MAX_KEYS_LIMIT = 1000
_VALUE_PREVIEW_BYTES = 120
_MAX_INLINE_VALUE_BYTES = 256 * 1024  # 256 KiB; bigger values get truncated


def _resolve_env_path(raw_path: str) -> Path | None:
    """Resolve a served-root-relative path to an LMDB env directory.

    The classifier marks a folder containing ``data.mdb`` as kind
    ``lmdb-database``. The marker file is what the client clicks, but the
    LMDB env IS the parent folder. So we accept either:

    - A path to the folder itself (preferred).
    - A path to the ``data.mdb`` file (we walk to its parent).
    """
    target = _safe_path(raw_path)
    if target is None:
        return None
    if target.is_file() and target.name == "data.mdb":
        target = target.parent
    if not target.is_dir():
        return None
    if not (target / "data.mdb").is_file():
        return None
    return target


def _parse_bytes_param(raw: str | None) -> bytes | None:
    """Decode a query param that may be hex or empty."""
    if raw is None or raw == "":
        return None
    try:
        return bytes.fromhex(raw)
    except ValueError:
        # Caller passed a non-hex string; treat as raw utf-8 so simple
        # text keys still work without hex-encoding ergonomics.
        return raw.encode("utf-8")


def _encode_key_for_wire(key: bytes) -> str:
    return key.hex()


def _value_preview(decoded: Any, decoder_used: str) -> str:
    """A short, JSON-safe stringification of the decoded value."""
    if decoder_used == "hex":
        # Already a hex string (truncated).
        text = str(decoded)
    else:
        try:
            import json  # noqa: PLC0415 -- guarded import (optional dep / circular)

            text = json.dumps(decoded, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = repr(decoded)
    if len(text) > _VALUE_PREVIEW_BYTES:
        text = text[:_VALUE_PREVIEW_BYTES] + "…"
    return text


def keys_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/lmdb/keys``.

    Params: ``path`` (env folder), ``subdb`` (default main), ``prefix``
    (hex bytes), ``cursor`` (hex bytes), ``limit`` (default 200, cap 1000).
    Returns ``{keys: [{subdb, key, valuePreview, valueSize, decoderUsed}],
    nextCursor}``.
    """
    raw_path = request.query_params.get("path", "")
    env_dir = _resolve_env_path(raw_path)
    if env_dir is None:
        return JSONResponse({"error": "lmdb env not found", "path": raw_path}, status_code=404)

    subdb = request.query_params.get("subdb", "") or None
    prefix = _parse_bytes_param(request.query_params.get("prefix"))
    cursor = _parse_bytes_param(request.query_params.get("cursor"))
    raw_limit = request.query_params.get("limit", str(_DEFAULT_KEYS_LIMIT))
    try:
        limit = max(1, min(int(raw_limit), _MAX_KEYS_LIMIT))
    except ValueError:
        limit = _DEFAULT_KEYS_LIMIT

    rows: list[dict[str, Any]] = []
    next_cursor_hex: str | None = None
    try:
        with LmdbReader(str(env_dir)) as reader:
            keys, next_cursor = reader.iter_keys(
                subdb=subdb, prefix=prefix, cursor=cursor, limit=limit
            )
            for k in keys:
                value = reader.get(k.key, subdb=subdb) or b""
                decoded, decoder = decode_value(k.subdb, k.key, value)
                rows.append(
                    {
                        "subdb": k.subdb,
                        "key": _encode_key_for_wire(k.key),
                        "valuePreview": _value_preview(decoded, decoder),
                        "valueSize": len(value),
                        "decoderUsed": decoder,
                    }
                )
            if next_cursor is not None:
                next_cursor_hex = next_cursor.hex()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("lmdb keys handler failed: %s", exc)
        return JSONResponse({"error": str(exc), "path": raw_path}, status_code=500)

    return JSONResponse({"keys": rows, "nextCursor": next_cursor_hex})


def entry_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/lmdb/entry``.

    Params: ``path``, ``subdb``, ``key`` (hex or utf-8). Returns
    ``{key, valueBytesB64, decoded, decoderUsed, size, truncated}``.
    """
    raw_path = request.query_params.get("path", "")
    env_dir = _resolve_env_path(raw_path)
    if env_dir is None:
        return JSONResponse({"error": "lmdb env not found", "path": raw_path}, status_code=404)
    subdb = request.query_params.get("subdb", "") or None
    raw_key = _parse_bytes_param(request.query_params.get("key"))
    if raw_key is None:
        return JSONResponse({"error": "missing 'key' param"}, status_code=400)

    try:
        with LmdbReader(str(env_dir)) as reader:
            value = reader.get(raw_key, subdb=subdb)
    except Exception as exc:  # noqa: BLE001
        LOG.warning("lmdb entry handler failed: %s", exc)
        return JSONResponse({"error": str(exc), "path": raw_path}, status_code=500)

    if value is None:
        return JSONResponse({"error": "key not found"}, status_code=404)

    truncated = False
    inline_bytes = value
    if len(value) > _MAX_INLINE_VALUE_BYTES:
        inline_bytes = value[:_MAX_INLINE_VALUE_BYTES]
        truncated = True
    decoded, decoder = decode_value(subdb or "", raw_key, value)
    return JSONResponse(
        {
            "key": raw_key.hex(),
            "valueBytesB64": base64.b64encode(inline_bytes).decode("ascii"),
            "decoded": decoded if _is_json_safe(decoded) else _value_preview(decoded, decoder),
            "decoderUsed": decoder,
            "size": len(value),
            "truncated": truncated,
        }
    )


def stats_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/lmdb/stats``.

    Params: ``path``. Returns
    ``{subdbs: [{name, entries, ...}], totalEntries, sizeBytes}``.
    """
    raw_path = request.query_params.get("path", "")
    env_dir = _resolve_env_path(raw_path)
    if env_dir is None:
        return JSONResponse({"error": "lmdb env not found", "path": raw_path}, status_code=404)
    try:
        with LmdbReader(str(env_dir)) as reader:
            main = reader.stats()
            subdb_names = reader.subdbs()
            per_subdb: list[dict[str, Any]] = [
                {
                    "name": "",
                    "entries": main.entries,
                    "depth": main.depth,
                }
            ]
            total = main.entries
            for name in subdb_names:
                try:
                    s = reader.stats(subdb=name)
                except Exception:  # noqa: BLE001
                    continue
                per_subdb.append({"name": name, "entries": s.entries, "depth": s.depth})
                total += s.entries
            size_bytes = main.map_size
    except Exception as exc:  # noqa: BLE001
        LOG.warning("lmdb stats handler failed: %s", exc)
        return JSONResponse({"error": str(exc), "path": raw_path}, status_code=500)

    return JSONResponse(
        {
            "subdbs": per_subdb,
            "totalEntries": total,
            "sizeBytes": size_bytes,
        }
    )


def _is_json_safe(value: Any) -> bool:
    """Quick check for whether a Python value will serialise cleanly to JSON.

    Used in the entry handler so structured decoded values (dict/list/str/...) are
    shipped as-is; weird Python objects (e.g. msgpack ExtType) fall back to a
    short string preview.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        return all(_is_json_safe(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_json_safe(v) for k, v in value.items())
    return False
