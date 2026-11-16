"""What pull requests' change sets sum to: one pull request's, or a stack's, accumulated.

A pull request's change set is its cached list of changed files, GitHub's or the one listed
from the local comparison, whichever its refresh last wrote (:mod:`.pull_files_route`): the
list its Pulls row discloses. A stack's change is its members' change sets accumulated, bottom
first, since a stack is the set of pull requests it consists of (the owner's decision on
review A of #484). One function sums both, so a stack of one pull request says what that pull
request's own row says: the Pulls row's brief change line (:mod:`.pull_files_summary`) and a
stack heading's (:mod:`.pull_stack_change`) are this one sum.

**One file, once.** A file is followed by its path, and across a rename: a member that
renames ``a`` to ``b`` carries what earlier members did to ``a`` over to ``b``. Its status is
composed from what the change sets did to it, in order:

- ``removed`` if the last that touches it removed it;
- otherwise ``added`` if the first that touches it added it (or copied it there);
- otherwise ``renamed`` if one renamed it;
- otherwise ``modified``.

So one list's ``copied`` is ``added``, and its ``changed`` and ``unchanged`` are ``modified``;
a file one layer adds and a later one edits is added, and a file several layers edit is
modified once. Its additions and deletions are each list's summed, as each layer's own counts
are what that layer wrote; a list with no count for a file, a binary one listed locally, makes
the totals inexact (``exact``) and counts it as nothing.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from metabrowser.builtin_plugins.github.pull_list import PullFileList


@dataclass(frozen=True, slots=True)
class ChangeSums:
    """What change sets sum to: their files by composed status, and their line totals.

    ``short`` says a list stopped short, at GitHub's most files or with a file left out, so the
    rest are not known and nothing else here is the whole.
    """

    files: int
    additions: int
    deletions: int
    exact: bool
    statuses: tuple[tuple[str, int], ...]
    short: bool


SHORT: Final = ChangeSums(files=0, additions=0, deletions=0, exact=False, statuses=(), short=True)


@dataclass(slots=True)
class _Touched:
    """What the change sets did to one file, as far as they have been read."""

    first: str
    last: str
    renamed: bool


def _composed(touched: _Touched) -> str:
    if touched.last == "removed":
        return "removed"
    if touched.first in {"added", "copied"}:
        return "added"
    return "renamed" if touched.renamed else "modified"


def accumulate(lists: Sequence[PullFileList]) -> ChangeSums:
    """What *lists*, one pull request's or a stack's members' bottom first, sum to."""

    files: dict[str, _Touched] = {}
    additions = deletions = 0
    exact = True
    for listed in lists:
        if listed.capped or listed.truncated:
            return SHORT
        for row in listed.rows:
            carried = None
            if row.status == "renamed" and row.previous_path is not None:
                carried = files.pop(row.previous_path, None)
            touched = files.get(row.path, carried)
            if touched is None:
                files[row.path] = _Touched(row.status, row.status, row.status == "renamed")
            else:
                touched.last = row.status
                touched.renamed = touched.renamed or row.status == "renamed"
                files[row.path] = touched
            if row.additions is None or row.deletions is None:
                exact = False
            additions += row.additions or 0
            deletions += row.deletions or 0
    counts = Counter(_composed(touched) for touched in files.values())
    return ChangeSums(
        files=len(files),
        additions=additions,
        deletions=deletions,
        exact=exact,
        statuses=tuple(sorted(counts.items())),
        short=False,
    )


__all__ = ["SHORT", "ChangeSums", "accumulate"]
