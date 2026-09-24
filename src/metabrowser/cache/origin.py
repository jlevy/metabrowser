"""How a store talks to its origin: the ``ls-remote`` and ``fetch`` argument vectors.

Acquisition and refresh run the same two network commands, so their arguments are
built here and nowhere else: first ``ls-remote --symref`` to observe which branch the
origin's HEAD names, then one fetch of every branch and tag with explicit refspecs.
Branches land under ``refs/remotes/origin/`` and tags under ``refs/tags/``; Metabrowser
writes no ref of its own, and pruning those refspecs never touches any other namespace.

Only ``file://`` origins are fetched today, so the protocol allowlist admits exactly
that transport. HTTPS and its credential helper plug in here, through
:func:`origin_protocol_args`, rather than beside each caller.
"""

from __future__ import annotations

from typing import Final

from metabrowser.git.wire import is_full_revision

# Every refspec a store fetches. A branch is mirrored under the remote-tracking
# namespace so no local branch is invented; a tag keeps its own name.
MIRROR_REFSPECS: Final[tuple[str, ...]] = (
    "+refs/heads/*:refs/remotes/origin/*",
    "+refs/tags/*:refs/tags/*",
)
BRANCH_MIRROR_PREFIX: Final = "refs/remotes/origin/"
TAG_PREFIX: Final = "refs/tags/"


class OriginHeadError(Exception):
    """The origin did not advertise a usable HEAD."""


def origin_protocol_args() -> tuple[str, ...]:
    """Configuration that admits only the transports a store may fetch over.

    ``protocol.allow=never`` refuses everything, then each admitted transport is
    allowed by name. The isolated Git environment drops ``GIT_ALLOW_PROTOCOL``, which
    would otherwise replace every ``protocol.*`` setting.
    """

    return ("-c", "protocol.allow=never", "-c", "protocol.file.allow=always")


def ls_remote_head_args(remote: str) -> list[str]:
    """``ls-remote --symref`` for the origin's HEAD, naming *remote* after ``--``.

    *remote* is the classified URL before a store exists, and ``origin`` once the
    store's configuration names it.
    """

    return [*origin_protocol_args(), "ls-remote", "--symref", "--", remote, "HEAD"]


def mirror_fetch_args(*, remote: str = "origin", prune: bool) -> list[str]:
    """One fetch of every branch and tag into the mirror namespaces.

    Acquisition fetches into an empty staging store and needs neither flag below. A
    refresh passes ``prune`` for ``--prune --atomic``: a branch or tag deleted upstream
    leaves the mirror, and every ref updates together or none does, so a killed or
    failed fetch never leaves some refs moved and others not. Objects written before a
    failure stay, which is harmless because nothing references them yet. ``--quiet``
    keeps stderr to Git's errors, which a refresh with thousands of new refs would
    otherwise push past the bounded capture.
    """

    flags = ["--prune", "--atomic", "--quiet"] if prune else []
    return [
        *origin_protocol_args(),
        "fetch",
        *flags,
        "--no-write-fetch-head",
        remote,
        *MIRROR_REFSPECS,
    ]


def mirror_prune_args(*, remote: str = "origin") -> list[str]:
    """Delete the mirror refs whose branch or tag the origin no longer has, and nothing else.

    ``remote prune`` maps the origin's refs through the same refspecs a fetch uses,
    passed as configuration because the store configures none. It only deletes, so a
    refresh runs it before the atomic fetch when one transaction cannot both delete
    ``side`` and create ``side/x``.
    """

    refspecs = [arg for spec in MIRROR_REFSPECS for arg in ("-c", f"remote.{remote}.fetch={spec}")]
    return [*origin_protocol_args(), *refspecs, "remote", "prune", remote]


def parse_symref_head(stdout: bytes) -> tuple[str | None, str]:
    """The ref the origin's HEAD names, if any, and the object ID it resolves to.

    The ``HEAD`` pattern also matches any ref whose last component is HEAD, such as a
    clone's ``refs/remotes/origin/HEAD``. Only the ref named exactly HEAD counts.
    """

    ref: str | None = None
    oid: str | None = None
    for line in stdout.decode("ascii", errors="replace").splitlines():
        payload, _, name = line.partition("\t")
        if name != "HEAD":
            continue
        if payload.startswith("ref:"):
            ref = payload.removeprefix("ref:").strip()
        else:
            oid = payload.strip()
    if oid is None or not is_full_revision(oid):
        raise OriginHeadError("the source did not advertise HEAD")
    return ref, oid


def remote_tracking_ref(head_ref: str | None) -> str | None:
    """The mirror ref for the origin branch *head_ref*, or ``None`` when HEAD is no branch."""

    if head_ref is None or not head_ref.startswith("refs/heads/"):
        return None
    return BRANCH_MIRROR_PREFIX + head_ref.removeprefix("refs/heads/")


__all__ = [
    "BRANCH_MIRROR_PREFIX",
    "MIRROR_REFSPECS",
    "TAG_PREFIX",
    "OriginHeadError",
    "ls_remote_head_args",
    "mirror_fetch_args",
    "mirror_prune_args",
    "origin_protocol_args",
    "parse_symref_head",
    "remote_tracking_ref",
]
