"""Whether a merge base computed on a store with a shallow boundary can be trusted.

A shallow boundary cuts edges out of the commit graph, and ``git merge-base`` on the cut
graph can answer a commit that is a common ancestor there but not the best one in the full
graph, with no error. A reviewer's replica got A1 where the truth is A4, and Files changed
then showed the base branch's own change as the pull request's. So an answer on such a
store is believed only when it is certain by construction:

Let *M* be the local answer. *M* is certain when every boundary commit reachable from
either tip is reachable from *M*: ``rev-list <left> <right> ^<M>`` names no commit in the
store's ``shallow`` file. Take any common ancestor *X* in the full graph and walk a
full-graph path from a tip toward it on the cut graph. Either the path stays visible, so
*X* is a common ancestor on the cut graph and cannot be a proper descendant of *M* there,
or it meets a boundary commit *B* first, and *B* is reachable from *M*, so *X*, an ancestor
of *B*, is an ancestor of *M*. If *X* were a full-graph descendant of *M*, a path from *X*
down to *M* would either stay visible, contradicting *M* being best on the cut graph, or
meet a boundary *B* reachable from *X* and hence from the tips, so *M* reaches *B* while
*B* reaches *M*, a cycle. The argument uses only that the cut graph is a subgraph of the
full one, which holds for any boundary file, a crafted one included: a boundary can make
an answer uncertain, never certain and wrong.

An empty answer on a shallow store is uncertain, not "no common history". And an answer
that is one of the two tips is certain whatever the check would say: that tip is an
ancestor of the other in the full graph too, and no common ancestor can be below it.
"""

from __future__ import annotations

import asyncio
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from metabrowser.git.process import (
    STORE_READ_POLICY,
    GitCommandError,
    GitError,
    RepositoryStoreTarget,
    run_git,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.repository_context import read_bounded_text

# A ``shallow`` file holds one object ID a line; the measured checkout has 17 of them, and
# this bound holds about 200,000. One that is larger is an answer nobody can trust.
MAX_BOUNDARY_BYTES: Final = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class MergeBaseAnswer:
    """What ``merge-base`` said, and whether that can be believed.

    ``merge_base`` is ``None`` when Git named no commit. That means the two share no
    history only when ``certain``; on a shallow store it says nothing.
    """

    merge_base: str | None
    certain: bool


def read_boundary(git_dir: Path) -> frozenset[str] | None:
    """The commits at which the store's history stops: empty when it is not shallow.

    ``None`` when there is a ``shallow`` file this cannot read, which callers take as an
    answer that cannot be trusted. Reads through the link to a lender's, when it is one.
    Blocking and bounded.
    """

    path = git_dir / "shallow"
    try:
        status = os.stat(path)
    except FileNotFoundError:
        return frozenset()
    except OSError:
        return None
    if not stat.S_ISREG(status.st_mode):
        return None
    text = read_bounded_text(path, MAX_BOUNDARY_BYTES)
    if text is None:
        return None
    oids = text.split()
    if not all(is_full_revision(oid) for oid in oids):
        return None
    return frozenset(oids)


async def merge_base_answer(
    target: RepositoryStoreTarget, left: str, right: str
) -> MergeBaseAnswer:
    """The merge base of two full commit IDs in a store, and whether it is certain.

    On a store that is not shallow this is ``git merge-base`` and its exit status as ever:
    one means no common history, and any other failure is raised. On a shallow store, any
    failure is an answer that cannot be believed rather than an error. The boundary is
    read before and after, because it can be a link to a checkout that deepens meanwhile.
    """

    boundary = await asyncio.to_thread(read_boundary, target.git_dir)
    try:
        out = await run_git(["merge-base", left, right], target=target, policy=STORE_READ_POLICY)
    except GitCommandError as exc:
        if boundary == frozenset():
            if exc.returncode != 1:
                raise
            return MergeBaseAnswer(None, certain=True)
        return MergeBaseAnswer(None, certain=False)
    merge_base = out.decode("ascii", errors="replace").strip()
    if not is_full_revision(merge_base):
        return MergeBaseAnswer(None, certain=boundary == frozenset())
    if boundary == frozenset() or merge_base in {left, right}:
        return MergeBaseAnswer(merge_base, certain=True)
    if boundary is None:
        return MergeBaseAnswer(merge_base, certain=False)
    try:
        reached = await run_git(
            ["rev-list", left, right, f"^{merge_base}"], target=target, policy=STORE_READ_POLICY
        )
    except GitError:
        return MergeBaseAnswer(merge_base, certain=False)
    if await asyncio.to_thread(read_boundary, target.git_dir) != boundary:
        return MergeBaseAnswer(merge_base, certain=False)
    above = boundary.intersection(reached.decode("ascii", errors="replace").split())
    return MergeBaseAnswer(merge_base, certain=not above)


__all__ = ["MAX_BOUNDARY_BYTES", "MergeBaseAnswer", "merge_base_answer", "read_boundary"]
