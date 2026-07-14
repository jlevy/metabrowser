"""MtimeCache-backed memoization for the browser's hot derived
projections.

The functions in this module are thin façades around the heavy
computations in :mod:`metabrowser.jsonl_view` and
:mod:`metabrowser.charts`. Each cache is an
:class:`metabrowser.mtime_cache.MtimeCache` keyed by absolute
path; the entry's mtime fingerprint is checked on every read so
a file edit invalidates the cached value automatically.

The ``CacheRead`` discriminator gives the caller three outcomes:

* ``hit``    — cached value reused; no recomputation
* ``miss``   — compute, ``update()`` the cache, return the fresh value
* ``absent`` — file vanished; return a domain-appropriate empty
  result without logging a parse error

The caches are reset by :func:`paths_safe.register_root_callback`
when the served root changes, so a worktree swap doesn't carry
stale entries forward.

This module exists separately from the underlying compute layer so cache-key
choice (per-file mtime) and eviction strategy live in one place.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from metabrowser.mtime_cache import MtimeCache
from metabrowser.paths_safe import register_root_callback

LOG = logging.getLogger(__name__)


# Cache sizes pinned at 256 each: typical browse session touches
# a few dozen distinct logs / charts; 256 covers comfortably
# above that without holding deep references for files the user
# closed minutes ago.
_PARSE_CACHE_MAX = 256
_AGENT_CHARTS_CACHE_MAX = 256


_PARSE_CACHE: MtimeCache[dict[str, Any]] = MtimeCache(max_size=_PARSE_CACHE_MAX, name="jsonl_parse")
_AGENT_CHARTS_CACHE: MtimeCache[Any] = MtimeCache(
    max_size=_AGENT_CHARTS_CACHE_MAX, name="agent_charts"
)


def parse_jsonl_file_cached(filepath: Path) -> dict[str, Any]:
    """Cached front-end for :func:`metabrowser.jsonl_view._parse_jsonl_file`.

    The underlying parse is single-pass over the file; on a 50 MB
    ``.jsonl`` it dominates the request budget for ``/api/file``
    and ``/api/charts`` calls. Caching the structured result by
    mtime collapses repeat fetches (page refresh, sibling chart
    request, tab switch) to a memcpy.

    File-vanished case: returns the empty parse shape so the
    caller can treat it as "no events" without re-raising.
    """

    cached = _PARSE_CACHE.read(filepath)
    if cached.hit and cached.value is not None:
        return cached.value
    if cached.absent:
        return {"events": [], "summary": {"total_events": 0}}
    # Deferred so tests monkeypatching `metabrowser.jsonl_view._parse_jsonl_file`
    # see the patched function (a top-level binding would capture the original).
    from metabrowser.jsonl_view import (  # noqa: PLC0415 -- test monkeypatch boundary
        _parse_jsonl_file,
    )

    fresh = _parse_jsonl_file(filepath)
    _PARSE_CACHE.update(filepath, fresh)
    return fresh


def extract_agent_charts_cached(filepath: Path) -> Any:
    """Cached :func:`metabrowser.charts.extract_agent_charts`."""

    cached = _AGENT_CHARTS_CACHE.read(filepath)
    if cached.hit:
        return cached.value
    if cached.absent:
        return None
    # Deferred so tests monkeypatching `metabrowser.charts.extract_agent_charts`
    # see the patched function (a top-level binding would capture the original).
    from metabrowser.charts import (  # noqa: PLC0415 -- test monkeypatch boundary
        extract_agent_charts,
    )

    fresh = extract_agent_charts(filepath)
    _AGENT_CHARTS_CACHE.update(filepath, fresh)
    return fresh


def invalidate_path(path: Path) -> None:
    """Drop cached entries for *path* across every projection.
    Called by the inventory's invalidation hook when an mtime
    change is detected; the next read re-derives.
    """

    _PARSE_CACHE.delete(path)
    _AGENT_CHARTS_CACHE.delete(path)


def _reset_all_caches() -> None:
    """Clear every projection cache. Wired to root-swap so a
    worktree change doesn't carry stale entries forward."""

    _PARSE_CACHE.cache.clear()
    _AGENT_CHARTS_CACHE.cache.clear()


register_root_callback(_reset_all_caches)


__all__ = [
    "extract_agent_charts_cached",
    "invalidate_path",
    "parse_jsonl_file_cached",
]
