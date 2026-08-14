"""Filesystem-path helpers shared by the walker and the watcher.

Single home for the visibility filter and extension derivation so the
walker (boot scan + ``rewalk_subtree``) and the watcher
(file-event handler) can never diverge on whether a path is visible
or how its extension is computed. The senior review of the file-
watching layer flagged divergence on both as silent-bug producers:

* The walker used :func:`is_visible` (single name); the watcher used
  ``_is_visible_segment`` (every segment). A watcher event on
  ``a/.hidden/b/file`` passed the walker's check inside
  ``rewalk_subtree`` because ``walk_tree`` filters per-name only.
* The walker used :func:`derive_ext` (bounded compound-tail heuristic for
  ``.runbook.md`` / ``.tar.gz``); the watcher used a simple
  last-dot suffix. Downstream code matching on ``ext`` silently
  miscategorized files depending on which producer created the entry.

Keeping these in one module makes both invariants discoverable and
forces any future producer to use the canonical implementation.
"""

from __future__ import annotations

from metabrowser.constants import LOGS_DIR, STATE_DIR

# Hidden directories KPress / the dev shell carry visibly even though
# they start with a dot. Anything else dot-prefixed is treated as
# hidden by both walker and watcher. The names come from
# ``metabrowser.constants`` so the tree builder (which reads the same
# constants) and the walker/watcher (which read this module) can never
# disagree on the allowlist.
_VISIBLE_HIDDEN = frozenset({LOGS_DIR, STATE_DIR})

# Bounds aggregate and filter cardinality while retaining common compound
# formats such as source maps, declaration files, and compressed artifacts.
_MAX_LOGICAL_EXTENSION_COMPONENTS = 2


def is_visible(name: str) -> bool:
    """Single-name visibility check.

    Returns ``True`` for ordinary names and the small allowlist of
    hidden directories the dev shell exposes by convention.
    """

    if not name.startswith("."):
        return True
    return name in _VISIBLE_HIDDEN


def is_visible_segment(rel_path: str) -> bool:
    """Per-segment visibility for a posix-style relative path.

    Used by the watcher to decide whether a deep file event lives
    under a hidden ancestor; equivalent to applying :func:`is_visible`
    to every segment.
    """

    if not rel_path:
        return True
    return all(is_visible(seg) for seg in rel_path.split("/"))


def derive_ext(name: str) -> str:
    """Return the bounded compound-tail extension for *name*.

    At most the final two eligible components are retained: ``archive.tar.gz``
    becomes ``.tar.gz``, ``bundle.umd.min.js.map`` becomes ``.js.map``, and
    ``types.d.ts.map`` becomes ``.ts.map``. This keeps suffix tallies stable
    without losing common compound formats.

    A component is eligible only when it is short, lowercase, and
    alphanumeric. Dotfiles have no extension.
    """

    if not name or name.startswith("."):
        return ""
    parts = name.split(".")
    if len(parts) <= 1:
        return ""
    # A "tail segment" is short, lowercase, alphanumeric. Folds
    # ``.runbook.md`` / ``.tar.gz`` / ``.html5`` but stops at the
    # first segment that breaks the pattern.
    tail_parts: list[str] = []
    for part in reversed(parts[1:][-_MAX_LOGICAL_EXTENSION_COMPONENTS:]):
        if 0 < len(part) <= 12 and part.islower() and part.isalnum():
            tail_parts.append(part)
        else:
            break
    if not tail_parts:
        return ""
    return "." + ".".join(reversed(tail_parts))
