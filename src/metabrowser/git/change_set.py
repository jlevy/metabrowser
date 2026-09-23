"""Check that a store's change set is present before a blob-reading diff runs.

The open-repository plan's lazy-fetch decision ("Blobless acquisition and the
offline guarantee") runs every store read with ``GIT_NO_LAZY_FETCH=1``.
That keeps a read off the network, but on a store that is still converging a
command that reads blobs — ``--numstat``, rename detection, a patch — then
fails as an ordinary Git error. The decision also has the diff paths check
first: list the change set with ``--raw --no-renames``, which reads no blob,
and look up every blob it names in one batch ``info``. A missing blob is then a
typed ``object_unavailable`` naming it.

``--no-renames`` is required because rename detection reads blobs. ``-M`` and
``-C`` without ``--find-copies-harder`` compare only blobs that set already
names, so the check covers commit detail, the comparison manifest, and patches;
the plan measured that in 40 of 40 comparisons.

Nothing here requests a missing blob. Reporting it ``deferred`` while fetching
it belongs to the object-job port that convergence adds; until that exists,
``object_unavailable`` is the honest answer. A filesystem worktree is not
checked, because only a worktree-free store runs without lazy fetch.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from metabrowser.git.process import GitLocation, RepositoryStoreTarget, run_git_at
from metabrowser.git.tree_source import require_store_objects

_BLOB_MODES: Final[frozenset[bytes]] = frozenset({b"100644", b"100755", b"120000"})
_RAW_ARGS: Final[tuple[str, ...]] = ("-z", "--raw", "--no-abbrev", "--no-renames")


def change_set_blob_oids(raw: bytes) -> tuple[str, ...]:
    """Blob object IDs on either side of ``--raw -z --no-renames`` records.

    Each record is one metadata token and, without rename detection, exactly
    one path token, which is skipped so a path that starts with ``:`` is never
    read as a record. Gitlinks name commits in another repository and are not
    looked up; an all-zero ID is an absent side.
    """

    oids: list[str] = []
    seen: set[str] = set()
    tokens = raw.split(b"\0")
    index = 0
    while index < len(tokens):
        record = tokens[index].lstrip(b"\n")
        index += 1
        if not record.startswith(b":"):
            continue
        index += 1
        fields = record[1:].split(b" ")
        if len(fields) < 5:
            continue
        for mode, oid_raw in ((fields[0], fields[2]), (fields[1], fields[3])):
            if mode not in _BLOB_MODES or not oid_raw.strip(b"0"):
                continue
            oid = oid_raw.decode("ascii", errors="replace")
            if oid not in seen:
                seen.add(oid)
                oids.append(oid)
    return tuple(oids)


async def _require_listed_blobs(location: GitLocation, args: Sequence[str]) -> None:
    target = location.target
    if not isinstance(target, RepositoryStoreTarget):
        return
    raw = await run_git_at(args, location)
    await require_store_objects(target, change_set_blob_oids(raw))


async def require_commit_blobs(location: GitLocation, revision: str) -> None:
    """Check the blobs ``show -M -C --diff-merges=first-parent`` would read."""

    await _require_listed_blobs(
        location,
        ["show", *_RAW_ARGS, "--diff-merges=first-parent", "--format=", revision],
    )


async def require_comparison_blobs(location: GitLocation, endpoints: Sequence[str]) -> None:
    """Check the blobs ``diff -M -C`` between *endpoints* would read."""

    await _require_listed_blobs(location, ["diff", *_RAW_ARGS, *endpoints])


__all__ = [
    "change_set_blob_oids",
    "require_commit_blobs",
    "require_comparison_blobs",
]
