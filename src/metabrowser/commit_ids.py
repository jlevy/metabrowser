"""A commit's short ID, as every line that names a commit shows it.

One length wherever a line names a commit: a commit pin's name and window title, the
navigation heading, the ref chooser's button, a mirror's offer of a newer commit, a CLI
message, and the build's version line. The ID is cut from the full one, never asked of
Git, whose abbreviation grows in a large repository to stay unique; the full ID is always
a copy or a link away (docs/design-system.md, "Short Commit IDs"). The page's copy is
``shortCommit`` in ``static/formatters.js``, which ``tests/test_short_commit.py`` holds to
this one.

This module imports nothing of the package, so the version line can use it before the
server's modules load.
"""

from __future__ import annotations

from typing import Final

# Seven characters, as GitHub shows them.
SHORT_COMMIT_CHARS: Final = 7


def short_commit(commit: str) -> str:
    """*commit* as a line names it: its first :data:`SHORT_COMMIT_CHARS` characters."""

    return commit[:SHORT_COMMIT_CHARS]


__all__ = ["SHORT_COMMIT_CHARS", "short_commit"]
