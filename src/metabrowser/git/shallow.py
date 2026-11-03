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

A boundary cuts one more thing: a commit *at* the boundary is grafted into a root, so
``log``, ``show``, and ``<commit>^`` all answer as if it had no parent, and a diff of it
alone is taken against the empty tree, which shows a whole tree as added where the truth
is one commit's change. :func:`recorded_parents` reads the parents from the object itself,
which the graft never touches, so a reader of a shallow repository, a store or a served
checkout alike, is told that the parent is beyond the history here rather than shown a
root's diff.
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
    GitLocation,
    RepositoryStoreTarget,
    run_git,
    run_git_at,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.repository_context import read_bounded_text

# A ``shallow`` file holds one object ID a line; the measured checkout has 17 of them, and
# this bound holds about 200,000. One that is larger is an answer nobody can trust.
MAX_BOUNDARY_BYTES: Final = 8 * 1024 * 1024

# What a comparison of a boundary commit alone answers instead of a diff. The state name
# is in the text, as ``base_uncertain`` is in the merge-base refusal, so a reader of the
# route can tell it from an unknown revision.
PARENT_UNAVAILABLE: Final = (
    "this commit's parent is beyond the shallow history here, so what it changed cannot be "
    "shown (parent_unavailable); more history would settle it"
)


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


async def recorded_parents(location: GitLocation, oid: str) -> tuple[str, ...]:
    """The parents the commit object *oid* names, read from the object and never a graft.

    ``log --format=%P``, ``show``, and ``<oid>^`` answer through the repository's
    ``shallow`` file, which turns a boundary commit into a root. ``cat-file commit`` prints
    the object as stored, ``parent`` lines included, so a commit with none here is a root
    and one with some is at the boundary. *oid* is a full object ID.
    """

    if not is_full_revision(oid):
        raise ValueError("not a full commit ID")
    raw = await run_git_at(["cat-file", "commit", oid], location)
    header = raw.partition(b"\n\n")[0]
    parents: list[str] = []
    for line in header.split(b"\n"):
        if line.startswith(b"parent "):
            parent = line[len(b"parent ") :].decode("ascii", errors="replace")
            if is_full_revision(parent):
                parents.append(parent)
    return tuple(parents)


async def merge_base_answer(
    target: RepositoryStoreTarget, left: str, right: str
) -> MergeBaseAnswer:
    """The merge base of two full commit IDs in a store, and whether it is certain.

    On a store that is not shallow this is ``git merge-base`` and its exit status as ever:
    one means no common history, and any other failure is raised. On a shallow store, any
    failure is an answer that cannot be believed rather than an error. The boundary is
    read before and after Git ran, on every return, because it can be a link to a
    checkout that deepens or becomes shallow meanwhile: an answer Git computed on a
    boundary other than the one read cannot be believed.

    A store that borrows can lack a commit its lender collected, and Git before 2.45 ends
    a merge-base walk that meets one with the answer it gives for no common history, where
    later Git fails; the same early end in its reduction of several candidates can leave
    one that is not the best. So an answer is believed only after ``rev-list`` walks that
    fail on any commit they cannot read whatever the Git, and that show no common
    ancestor outside the answer's history: :func:`_best_common_ancestor`. On a store with
    no boundary that failure is raised.
    """

    boundary = await asyncio.to_thread(read_boundary, target.git_dir)
    try:
        out = await run_git(["merge-base", left, right], target=target, policy=STORE_READ_POLICY)
    except GitCommandError as exc:
        if boundary == frozenset() and await _boundary_still(target, boundary):
            if exc.returncode != 1:
                raise
            await _walk_readable(target, [left, right])
            return MergeBaseAnswer(None, certain=True)
        return MergeBaseAnswer(None, certain=False)
    merge_base = out.decode("ascii", errors="replace").strip()
    if not is_full_revision(merge_base):
        return MergeBaseAnswer(
            None, certain=boundary == frozenset() and await _boundary_still(target, boundary)
        )
    if merge_base in {left, right}:
        return MergeBaseAnswer(merge_base, certain=await _boundary_still(target, boundary))
    if boundary is None:
        return MergeBaseAnswer(merge_base, certain=False)
    try:
        best = await _best_common_ancestor(target, left, right, merge_base)
    except GitError:
        if boundary == frozenset():
            raise
        return MergeBaseAnswer(merge_base, certain=False)
    if not best:
        return MergeBaseAnswer(merge_base, certain=False)
    if boundary == frozenset():
        return MergeBaseAnswer(merge_base, certain=await _boundary_still(target, boundary))
    try:
        reached = await run_git(
            ["rev-list", left, right, f"^{merge_base}"], target=target, policy=STORE_READ_POLICY
        )
    except GitError:
        return MergeBaseAnswer(merge_base, certain=False)
    if not await _boundary_still(target, boundary):
        return MergeBaseAnswer(merge_base, certain=False)
    above = boundary.intersection(reached.decode("ascii", errors="replace").split())
    return MergeBaseAnswer(merge_base, certain=not above)


async def _walk_readable(target: RepositoryStoreTarget, revisions: list[str]) -> int:
    """How many commits the walk reaches; raises :class:`GitCommandError` on one it cannot read."""

    out = await run_git(
        ["rev-list", "--count", *revisions], target=target, policy=STORE_READ_POLICY
    )
    return int(out.decode("ascii", errors="replace").strip())


async def _best_common_ancestor(
    target: RepositoryStoreTarget, left: str, right: str, merge_base: str
) -> bool:
    """Whether every commit both tips reach is in *merge_base*'s history.

    Counted rather than listed, so the output stays one number however far the tips are
    from it: the tips share a commit outside that history exactly when what either
    reaches outside it is fewer than what each reaches added together. Then *merge_base*
    is not the best common ancestor, whatever Git said.
    """

    outside = f"^{merge_base}"
    either = await _walk_readable(target, [left, right, outside])
    each = await _walk_readable(target, [left, outside]) + await _walk_readable(
        target, [right, outside]
    )
    return either == each


async def _boundary_still(target: RepositoryStoreTarget, boundary: frozenset[str] | None) -> bool:
    """Whether the boundary is what was read before Git ran, so its answer was on that cut."""

    return await asyncio.to_thread(read_boundary, target.git_dir) == boundary


__all__ = [
    "MAX_BOUNDARY_BYTES",
    "PARENT_UNAVAILABLE",
    "MergeBaseAnswer",
    "merge_base_answer",
    "read_boundary",
    "recorded_parents",
]
