"""Path safety + ROOT_DIR plumbing for the browser.

This module owns the served-root reference and every helper that decides
whether a request path is allowed (``_safe_path``) or how to display it
(``_rel_path``, ``_relativize``). It is deliberately minimal so that
``tree.py``, ``activity.py``, and ``proc_browser.py`` can all import it
without dragging the rest of the world along.

ROOT_DIR is mutable (set at startup, swapped during tests). Modules that
hold per-root state register a callback via ``register_root_callback``
which fires whenever ``_set_root_dir`` reassigns the root.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

# ── Globals ────────────────────────────────────────────────────────

ROOT_DIR: Path = Path()

# Cache of the resolved ROOT_DIR as a prefix string (with trailing separator).
# ROOT_DIR is set once at startup; ``_set_root_dir`` clears this cache so
# tests that swap roots still work.
_ROOT_PREFIX_CACHE: dict[Path, str] = {}

# Callbacks fired when ROOT_DIR is reassigned — modules that cache
# per-root state register here so a root swap invalidates their caches.
_set_root_callbacks: list[Callable[[], None]] = []


def register_root_callback(cb: Callable[[], None]) -> None:
    """Register a function to run whenever the served root changes."""
    _set_root_callbacks.append(cb)


def _set_root_dir(root_dir: Path) -> None:
    """Update the browser root and invalidate dependent caches."""
    globals()["ROOT_DIR"] = root_dir
    _ROOT_PREFIX_CACHE.clear()
    for cb in _set_root_callbacks:
        cb()


def _resolved_root_dir() -> Path:
    """Return the current resolved root directory."""
    return ROOT_DIR.resolve()


def _is_within(candidate: Path, root: Path) -> bool:
    """True iff ``candidate`` resolves to a path inside ``root``.

    Uses :meth:`pathlib.Path.is_relative_to` rather than
    ``str.startswith``: the bare prefix check would accept e.g. a target
    of ``/srv/data-secret/x`` against a root of ``/srv/data`` because
    one path string is a prefix of the other. ``is_relative_to`` walks
    the path components and avoids that confusion.
    """
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_path(requested: str) -> Path | None:
    """Resolve a requested path, ensuring it stays within ROOT_DIR.

    *requested* is a platform path, not a canonical inventory identity. The two differ
    only for names holding `%` or an undecodable byte, which is exactly where confusing
    them goes wrong: `/view/docs/100%25.md` is the human-facing URL for a file named
    `100%.md`, while that file's inventory identity is `100%25.md` and would arrive
    URL-encoded as `100%2525.md`. Callers holding an identity decode it first; this
    function stays the filesystem address.
    """
    if not requested:
        return ROOT_DIR
    resolved = (ROOT_DIR / requested).resolve()
    if not _is_within(resolved, ROOT_DIR.resolve()):
        return None
    return resolved


def _safe_subdir(requested: str) -> Path | None:
    """Like :func:`_safe_path` but require the resolved path to be a directory.

    Centralizing the containment and directory checks keeps route-level
    callers from performing unsafe string-prefix comparisons. Returns
    ``None`` if the resolved path is outside ROOT_DIR or not a directory.
    """
    target = _safe_path(requested)
    if target is None or not target.is_dir():
        return None
    return target


def _cached_root_prefix() -> str:
    """Return ``str(ROOT_DIR.resolve()) + os.sep``, cached per ROOT_DIR value."""
    cached = _ROOT_PREFIX_CACHE.get(ROOT_DIR)
    if cached is not None:
        return cached
    try:
        resolved = str(ROOT_DIR.resolve())
    except OSError:
        return ""
    prefix = resolved + os.sep if resolved else ""
    _ROOT_PREFIX_CACHE[ROOT_DIR] = prefix
    return prefix


def _rel_path(absolute: Path | str) -> str:
    """Return ``absolute`` as a string relative to ROOT_DIR.

    Fast path: lexical string trim against the cached resolved root. Falls
    back to :func:`_relativize` if the path isn't under the cached root
    (handles ROOT_DIR reassignment and edge cases). Called once per tree
    entry, so the fast path matters on large trees.
    """
    root_prefix = _cached_root_prefix()
    s = absolute if isinstance(absolute, str) else str(absolute)
    if root_prefix and s.startswith(root_prefix):
        return s[len(root_prefix) :]
    return _relativize(s) or ""


def _relativize(raw: str | None) -> str | None:
    """Normalize ``raw`` to a path relative to ROOT_DIR, for JSON responses.

    The single chokepoint every API response should funnel path strings
    through before sending them to the client. The client always treats
    paths as "relative to the browser root" — absolute paths leaking into
    a response expose filesystem layout and force the client to strip
    prefixes it shouldn't know about.

    Idempotent and defensive:
      - ``None`` / ``""`` pass through unchanged.
      - An already-relative string is returned as-is.
      - An absolute path under ROOT_DIR has the root prefix stripped.
      - An absolute path outside ROOT_DIR is returned as-is; we don't
        rewrite such paths because silently relativizing them against
        ROOT_DIR would produce a path like ``../other-pkg/file`` that
        doesn't resolve from the client's perspective.
    """
    if not raw:
        return raw
    candidate = Path(raw)
    if not candidate.is_absolute():
        return raw
    try:
        return str(candidate.relative_to(ROOT_DIR.resolve()))
    except ValueError:
        return raw
