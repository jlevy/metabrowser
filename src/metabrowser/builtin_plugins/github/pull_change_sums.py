"""What one or more pull requests' own changed files accumulate to, said in brief.

A pull request's change set is its cached list of changed files (:mod:`.pull_list`,
``PullFileList``), the one its expanded row in the Pulls tab shows. :func:`accumulate` takes
one list, or several bottom first, as a stack's members, and says what they change
together: how many files, each counted once with one status, and their line totals, for a
stack's heading line (:mod:`.pull_stack_change`).

**One file, once.** A file is followed by its path, and across a rename: a list that
renames ``a`` to ``b`` carries what earlier lists did to ``a`` over to ``b``. Its status is
composed from what the lists did to it, in order:

- ``removed`` if the last list that touches it removed it;
- otherwise ``added`` if the first list that touches it added it (or copied it there);
- otherwise ``renamed`` if a list renamed it;
- otherwise ``modified``.

So a file one layer adds and a later one edits is added, a file a later layer deletes is
removed, and a file several layers edit is modified once. Its additions and deletions are
each list's summed, as each layer's own counts are what that layer wrote. A row with no
count, a binary file a local comparison listed, makes the totals inexact (``exact``), and
a list that stopped short, GitHub's most for one pull request (``capped``) or with a file
left out (``truncated``), makes the whole short (``short``), since the rest are not known.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_list import PullFileList


@dataclass(frozen=True, slots=True)
class ChangeSums:
    """What lists of changed files accumulate to: files by status, and line totals.

    ``statuses`` is each composed status, in a pull request's words, with how many files
    have it, by status name. ``short`` says a list stopped short, so the rest are not known.
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
    """What the lists did to one file, as far as they have been read."""

    first: str
    last: str
    renamed: bool


def _composed(touched: _Touched) -> str:
    if touched.last == "removed":
        return "removed"
    if touched.first in {"added", "copied"}:
        return "added"
    return "renamed" if touched.renamed else "modified"


def accumulate(lists: Iterable[PullFileList]) -> ChangeSums:
    """What *lists*, bottom first, accumulate to; see the module. Pure.

    Each list is folded in as it comes, and *lists* is read no further once one stops
    short, so a caller that reads them lazily holds one list at a time.
    """

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
