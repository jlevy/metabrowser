"""A served checkout's own branches, tags, and committed revisions, read without touching it.

A folder that is a repository's root shows everything a mirror does and more: any branch
or tag of the checkout, the checked-out one included, can be shown as a mirror shows one,
as a pinned revision read from Git objects, while the working tree stays a separate
choice, the one a folder opens on
(``docs/project/architecture/arch-source-sessions-and-pins.md``, "Revisions of a
Checkout"). :class:`CheckoutRevisions` is that for one served root. The source routes ask
it what a mirror's session answers for a mirror: the refs to list, and to serve another
selection.

**Nothing here writes the checkout.** Showing a revision is ``for-each-ref``,
``rev-parse``, ``cat-file``, and ``ls-tree`` with ``--git-dir`` naming the checkout's Git
directory, and nothing else: no ``checkout``, ``switch``, ``reset``, ``stash``, or
``fetch``, no index, no ``HEAD`` or ref written. The commands run under the store policies
(``git/process.py``), so no optional lock is taken and a partial clone's missing object is
``object_unavailable``, never fetched into the reader's ``.git``. Those policies leave
the checkout's local configuration in effect, so a revision's ``diff`` and ``show`` also
refuse every driver it names (``GitLocation.diff_driver_args``), which would run a
program and could write a ``refs/notes/textconv/`` ref.
``tests/test_checkout_revisions.py`` compares every file under the checkout, its ``.git``
included, before and after.

**Where a revision is read from.** The checkout's own Git directory, in place. A linked
worktree's objects and refs are its main repository's, so the directory read is the
common one. One exception: the origin's branches and tags are listed and served from the
store Metabrowser keeps beside the checkout, once it exists (``checkout_store.py``,
:attr:`CheckoutRevisions.origin`), as Metabrowser last fetched them. That store borrows
the checkout's objects and is read with no Git process in the checkout.

**Which checkouts.** The chooser follows the open root: it is offered when the served
root is a repository's root and Git itself accepts it, by the discovery the Commits tab
uses (:func:`metabrowser.git.repo.repo_info`). The directory read through ``--git-dir`` is
the one that same Git names (``rev-parse --git-common-dir``), never a second reading of
the ``.git`` pointer, which can disagree with Git's: so a repository Git refuses for its
ownership is not read, and no other directory than the one Git accepted is.

**Which Git.** One the acquisition floor admits (:func:`require_acquisition_git`). A
checkout can be a partial clone, and ``GIT_NO_LAZY_FETCH`` is then all that keeps a
revision's read from fetching into the reader's ``.git``; only an admitted Git is known
to read it. A mirror's store has no promisor remote, so for it the variable is defense in
depth; a checkout has no such second line. On an older Git the chooser refuses with
:class:`CheckoutGitUnsupportedError`, which names the release needed, and the folder's
working tree is served as before. A partial clone needs more than the floor: see
:data:`PARTIAL_CLONE_GIT_MINIMUM`.

**Trust.** A revision's pages run under the untrusted profile whatever the folder was
opened with, as every pin's do: the profile is the subject's that a request resolved
(:func:`metabrowser.capabilities.capabilities_for`), so nothing is set or cleared here.

Serving a revision replaces the session's subject, as a mirror's pin switch does, so the
switch is server-wide and lasts until the working tree is chosen again or the server
stops. The folder's inventory and watcher keep running underneath, which is why returning
needs no scan.

**From the command line.** ``metab PATH --ref NAME`` opens the folder on that branch or
tag: :func:`open_on_ref` tells the next application lifespan, which makes the same switch
a page's selector does, once, as it starts (:func:`lifespan_checkout`). Every mode that
runs the application takes it, serving, ``--api``, ``--show``, and ``--check-api``, so a
revision of a checkout is read from a terminal by the routes a page reads it by.

This module is imported by every server, so the revision tree source and the resolver are
imported where a revision is first asked for, as a pin's other modules are.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, cast

from metabrowser.content_errors import ContentReadError
from metabrowser.git.process import (
    ACQUISITION_NEWEST_PATCHED,
    ACQUISITION_PATCHED_TRACKS,
    STORE_READ_POLICY,
    GitCommandError,
    GitError,
    GitLocation,
    UnsupportedGitVersionError,
    failure_detail,
    require_acquisition_git,
    run_git,
    run_git_at,
)
from metabrowser.invisible_chars import display_segment
from metabrowser.mirror_refresh import (
    PROBED_REF_PREFIX,
    CheckoutOwnRef,
    FreshnessFields,
    MirrorRef,
    MirrorSession,
    RefKind,
    SelectionError,
    SelectionRefMovedError,
    follow_served_ref,
    follows_moves,
)
from metabrowser.paths_safe import register_root_callback, tilde_path
from metabrowser.repository_context import is_checkout_root
from metabrowser.source import (
    SourceSession,
    SubjectNotOpenError,
    UnsupportedSourceCapabilityError,
    as_git_revision_subject,
    fail_subject_open,
    get_source_session,
    replace_owned_subject,
    restore_filesystem_subject,
)

if TYPE_CHECKING:
    from metabrowser.git.process import RepositoryStoreTarget
    from metabrowser.git.tree_source import GitRevisionSubject
    from metabrowser.git.wire import GitHead
    from metabrowser.source import RepositorySubject

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CheckoutDisplay:
    """What a page shows of the checkout a revision is read from. Display text, never an input.

    ``name`` is the folder's name, as the navigation heading of its working tree shows it,
    and ``location`` its path with the home directory as ``~``. A control or invisible
    character in either is already replaced.
    """

    name: str
    location: str


def _shown(text: str) -> str:
    return display_segment(text.encode("utf-8", "surrogateescape"))


def _display(root: Path) -> CheckoutDisplay:
    try:
        location = tilde_path(root, Path.home().resolve())
    except (OSError, RuntimeError):
        location = str(root)
    return CheckoutDisplay(name=_shown(root.name or str(root)), location=_shown(location))


def checkout_ref_name(ref: str | None) -> str | None:
    """The name a reader knows a checkout's ref by, or ``None`` for no ref.

    ``main`` for the branch ``refs/heads/main`` and ``v1`` for the tag ``refs/tags/v1``. A
    remote-tracking branch keeps its remote, ``origin/topic`` for
    ``refs/remotes/origin/topic``, since a checkout has a branch of its own by the bare
    name; a mirror, which holds only its origin's branches, drops it
    (:func:`metabrowser.git.tree_source.ref_short_name`). Any other ref keeps its full
    spelling.
    """

    if ref is None:
        return None
    for prefix in ("refs/heads/", "refs/tags/", "refs/remotes/"):
        if ref.startswith(prefix) and len(ref) > len(prefix):
            return ref.removeprefix(prefix)
    return ref


# The refs of a checkout that a revision served under one follows when it moves: its own
# branches, which the reader's commit moves, its remote-tracking branches, which the
# reader's fetch moves, and its tags. Only a selection that names the ref, as ``ref`` or
# as ``under``, follows it. A commit opened by its ID alone never moves: it is served
# under no ref, or under the one last served while it is that ref's tip, so that the
# selector still names the ref, and then too it stays. The working tree is no revision
# (:meth:`CheckoutRevisions.observe`).
FOLLOWED_CHECKOUT_REFS: Final = ("refs/heads/", "refs/remotes/", "refs/tags/")

# How often a visible page on one of the checkout's own refs asks where that ref is
# (``probe_every_s`` in its status; the ask is ``POST /api/source/refresh`` with
# ``{"for": "page"}``). The ask names the checkout's ref state
# (:func:`metabrowser.git.ref_state.ref_state`), one ``stat`` per ref file and no Git
# process, and runs Git only when that state changed. A hidden page asks nothing, so a
# folder nobody looks at costs nothing.
#
# Measured 2026-11-22 on macOS, Git 2.50.1, in process, at a load average of 320 to 350,
# so the minimum is the figure nearest an idle machine's (median, minimum, in ms):
#
#   naming the ref state, 10 loose refs               1.5 to 3.1   0.35 to 0.78
#   naming the ref state, 1,000 loose refs                  12.4           6.2
#   one Git read of the ref (what a poll by Git costs)  43 to 46          14.5
#   the whole ask, no ref moved (TestClient)                 6.8           2.8
#   GET /api/source/status, for comparison                   2.5           0.8
#   the whole ask when the branch moved: read, open, serve   313           164
#
# So one ask costs a few milliseconds, a tenth or less of one Git process, and what it
# adds is a rate: a visible page sends one every interval in place of the status poll it
# would send every ``SLOW_POLL_MS`` (``static/source-freshness.js``), many times as
# often. At this interval that is about 0.1% of one processor for an ordinary
# repository; at ``MAX_REF_ENTRIES`` loose refs the state takes about 75 ms
# (``git/ref_state.py``), under 4% at this interval, and past it there is no state and
# each ask is one Git read. Several visible pages read no more often than
# :data:`CHECKOUT_REFS_FLOOR_S`. Two seconds is under the five of a probe of an origin
# (``STORE_PROBE_S``), which costs a network round trip, and is the wait a reader has
# between a commit in a terminal and the page that shows it.
#
# The alternative was the folder's watcher. It was not measured, because it cannot see a
# ref move as it is: ``watchfiles.DefaultFilter`` drops everything under ``.git``
# (``watch_backends.py``), so following by it means a second recursive watch, of the Git
# directory, which for a linked worktree is outside the served root, kept open whether or
# not a page shows a branch. The poll needs no new watch and stops with the page.
CHECKOUT_REFS_POLL_S: Final = 2.0
# The shortest gap the server keeps between two readings of the checkout's refs, however
# many visible pages ask: an ask inside it is answered from memory, so several pages read
# at most twice an interval between them. Half an interval, so one page's ask, which a
# timer can send a little early, still reads, as ``STORE_PROBE_FLOOR_S`` is below
# ``STORE_PROBE_S`` for a mirror's probe.
CHECKOUT_REFS_FLOOR_S: Final = CHECKOUT_REFS_POLL_S / 2

# The first release whose ``GIT_NO_LAZY_FETCH`` also has a partial clone's missing object
# read as missing. From 2.45.0 Git turns ``fetch_if_missing`` off at setup when the
# variable is set (environment.c; setup.c later). An admitted 2.43.7 or 2.44.4 has only
# the security releases' backport, which refuses the fetch (promisor-remote.c) and then
# ends the process: "could not fetch <oid> from promisor remote". So there a revision of a
# blobless clone could not list its tree: nothing was fetched, and the tree route failed
# untyped, "truncated cat-file header", in CI's admitted-git (2.43.7) job on 2026-11-18
# (#559). Read from Git's source at v2.43.7, v2.44.4, v2.45.0, v2.45.4, and v2.50.1.
PARTIAL_CLONE_GIT_MINIMUM: Final = (2, 45, 0)


def partial_clone_version_label() -> str:
    """The admitted releases that read a partial clone's missing object as missing."""

    track = ".".join(str(part) for part in PARTIAL_CLONE_GIT_MINIMUM[:2])
    first = ".".join(str(part) for part in ACQUISITION_PATCHED_TRACKS[track])
    newest = ".".join(str(part) for part in ACQUISITION_NEWEST_PATCHED)
    return f"{first} or a patched release at least {newest} on a newer track"


class CheckoutGitUnsupportedError(ContentReadError):
    """The host's Git is not one a checkout's revisions are read with.

    The message names the release needed and no path: ``--ref`` says it as it is, and a
    route answers it as ``detail`` beside ``reader_message`` (:func:`content_error_wire`).
    *partial_clone* is the stricter need of a checkout that names a promisor remote
    (:data:`PARTIAL_CLONE_GIT_MINIMUM`).
    """

    code = "unsupported_git"
    http_status = 409
    reader_message = "Git on this machine is too old to show this checkout's branches and tags."

    def __init__(self, detected: str | None, required: str, *, partial_clone: bool = False) -> None:
        found = "no git is on PATH" if detected is None else f"this is {detected or 'unknown'}"
        super().__init__(
            f"showing a branch or tag of a partial clone needs Git {required}, which reads "
            f"an object the clone lacks as missing and never fetches it; {found}"
            if partial_clone
            else f"showing a branch or tag of a checkout needs Git {required}, which is "
            f"known never to fetch into it; {found}"
        )
        self.detected = detected
        self.required = required


def _monotonic() -> float:
    """The clock :data:`CHECKOUT_REFS_FLOOR_S` is kept on; a test moves it."""

    return time.monotonic()


def _admitted_git() -> tuple[int, int, int]:
    """The host's Git version; :class:`CheckoutGitUnsupportedError` unless the floor admits it."""

    try:
        return require_acquisition_git()
    except UnsupportedGitVersionError as exc:
        raise CheckoutGitUnsupportedError(exc.detected, exc.required) from None


def _git_true(entry: bytes) -> bool:
    """A ``config --null --get-regexp`` entry's value, read as ``git_config_bool`` reads it.

    A key with no value is true; ``false``, ``no``, ``off``, and an empty value are false;
    an integer is true unless it is zero, with Git's ``k``, ``m``, and ``g`` units. A value
    Git would refuse counts as true, so it refuses the revision rather than serving it.
    """

    _key, separator, value = entry.partition(b"\n")
    if not separator:
        return True
    word = value.strip().lower()
    if word in {b"false", b"no", b"off", b""}:
        return False
    try:
        return int(word.rstrip(b"kmg"), 0) != 0
    except ValueError:
        return True


async def _names_a_promisor(target: RepositoryStoreTarget) -> bool:
    """Whether the repository's own configuration makes it a partial clone.

    What makes Git fetch lazily: ``extensions.partialClone``, a ``remote.<name>.promisor``
    that is true, or a ``remote.<name>.partialCloneFilter`` alone, which makes its remote
    a promisor too (``promisor_remote_config`` in ``promisor-remote.c``). Read under the
    store policy, as the revision's reads are, so the reader's own configuration counts
    for none of them.
    """

    try:
        raw = await run_git(
            [
                "config",
                "--null",
                "--get-regexp",
                r"^(extensions\.partialclone|remote\..*\.(promisor|partialclonefilter))$",
            ],
            target=target,
            policy=STORE_READ_POLICY,
        )
    except GitCommandError as exc:
        if exc.returncode == 1:
            # No such key: an ordinary repository.
            return False
        raise
    for entry in raw.split(b"\0"):
        key = entry.partition(b"\n")[0]
        if key == b"extensions.partialclone" or key.endswith(b".partialclonefilter"):
            return True
        if key.endswith(b".promisor") and _git_true(entry):
            return True
    return False


async def _common_git_directory(root: Path) -> Path | None:
    """The Git directory holding *root*'s objects and refs, as Git itself names it.

    Asked of the Git that accepted the root, in the root, so its ownership check and its
    reading of a ``.git`` pointer are the ones that decide. ``--git-common-dir`` is
    relative to the working directory unless it is absolute; joining keeps an absolute
    answer as it is.
    """

    try:
        raw = await run_git_at(["rev-parse", "--git-common-dir"], GitLocation.filesystem(root))
    except GitError as exc:
        log.debug("no Git directory for the served checkout: %s", failure_detail(exc))
        return None
    named = os.fsdecode(raw).rstrip("\n")
    if not named or "\n" in named:
        return None
    common = (root / named).resolve()
    return common if common.is_dir() else None


class CheckoutRevisions:
    """One served checkout: its refs, and switching between a revision and the working tree."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.display = _display(root)
        # Switches are serialized, as a mirror's are, so two requests end with one served.
        self._switching = asyncio.Lock()
        self._served: GitRevisionSubject | None = None
        # The ref last served, which a commit pinned by ID is opened under when it is still
        # that ref's tip: View file on a commit's diff goes to the commit and back, and the
        # selector names the ref. Such a pin never follows it (``_by_id``).
        self._last_ref: str | None = None
        # Whether the checkout's history stops at a shallow boundary, read when a revision
        # is served so that the status route still reads nothing.
        self.shallow = False
        # Where the revision served was read from, the store Metabrowser keeps of the
        # origin or the checkout itself, and ``None`` on the working tree; and whether
        # this checkout could have such a store, as of the last switch.
        self.read_from: Literal["origin", "checkout"] | None = None
        self.kept_store = False
        # The host's Git version once the floor admitted it; asked again until it does.
        self._git_version: tuple[int, int, int] | None = None
        # The ref the revision of the checkout's own is served under and that ref's commit
        # as last read, ``None`` for a ref that is gone; and the checkout's ref state when
        # it was read, so asking again while no ref moved runs no Git (:meth:`observe`).
        self._tip: tuple[str, str | None] | None = None
        self._refs_state: str | None = None
        # Whether the revision served was asked for by its commit ID alone, which never
        # moves, even served under the ref whose tip it is.
        self._by_id = False
        # When the refs were last read, on :func:`_monotonic`, for
        # :data:`CHECKOUT_REFS_FLOOR_S`; and whether the last reading of the served ref
        # failed, so a failure that lasts is warned of once.
        self._read_at: float | None = None
        self._read_failing = False

    def serves(self, subject: object) -> bool:
        """Whether *subject* is a revision this checkout's server shows of its repository.

        One it attached from the checkout's own Git directory, or one read from the store
        Metabrowser keeps of the checkout's origin (:attr:`origin`).
        """

        if subject is None:
            return False
        if subject is self._served:
            return True
        origin = self.origin
        if origin is None:
            return False
        pin = as_git_revision_subject(cast("RepositorySubject", subject))
        return pin is not None and origin.owns(pin)

    @property
    def origin(self) -> MirrorSession | None:
        """The session of Metabrowser's store of this checkout's origin, once it exists.

        ``metabrowser/checkout_store.py`` makes it. With it, the origin's branches and
        tags are listed and served from that store, as Metabrowser last fetched them, and
        the checkout's own remote-tracking branches of the origin are not read.
        """

        held = _origin
        return held[1] if held is not None and held[0] == self.root else None

    async def _of_origin(
        self, origin: MirrorSession, *, ref: str | None, oid: str | None, under: str | None
    ) -> tuple[bool, str | None]:
        """Whether a selection is read from the origin's store, and the ref to ask it for.

        A full ref of one of the origin's branches is, and a tag the store holds, which
        is the origin's; a tag only the checkout has is the checkout's. A commit named by
        its ID is read where the page asking is: from the store while one of its
        revisions is served, so the way to a commit's file and back stays in it.

        A short name, as ``--ref`` gives one, is read in a checkout's order, a branch,
        then a tag, then a remote-tracking branch, with the origin's taken from the
        store: the checkout's own branch of that name wins, then a tag the store holds,
        then a tag only the checkout has, then ``origin/<branch>`` as the store has it.
        The second value is then the full ref the store is asked for. Anything else, a
        commit ID or another remote's branch among them, is the checkout's.
        """

        from metabrowser.cache.resolve import is_valid_ref_name, ref_tips

        named = under if oid is not None else ref
        if named is None:
            return oid is not None and origin.served() is not None, ref
        if named.startswith(PROBED_REF_PREFIX):
            return True, ref
        if named.startswith("refs/tags/"):
            return await origin.mirror.ref_tip(named) is not None, ref
        if oid is not None or named.startswith("refs/") or named == "HEAD":
            return False, ref
        tag = f"refs/tags/{named}"
        if not is_valid_ref_name(tag):
            # Revision syntax, or no name at all: the checkout's resolver refuses it.
            return False, ref
        target, _head = await self._repository()
        own_branch = f"refs/heads/{named}"
        branch = (
            PROBED_REF_PREFIX + named.removeprefix(_ORIGIN_NAME)
            if named.startswith(_ORIGIN_NAME)
            else None
        )
        # One read of each repository, at once, and the order applied to what they hold:
        # this is on the pin route's path, before the switch resolves the name again.
        own, stored = await asyncio.gather(
            ref_tips(target, [own_branch, tag]),
            origin.mirror.ref_tips([tag] if branch is None else [tag, branch]),
        )
        if own_branch in own:
            return False, ref
        if tag in stored:
            return True, tag
        if tag in own:
            return False, ref
        if branch is not None and branch in stored:
            return True, branch
        return False, ref

    async def _open_origin(self) -> bool:
        """Open the store of this checkout's origin, if it keeps one; whether it could have one.

        ``checkout_store.py`` says how. A cached store is adopted with no network, so a
        selection made as the application starts, ``--ref``'s, reads the origin's refs from
        it. ``False`` for a checkout that keeps no store, and before any is set up.
        """

        held = _origin_opener
        if held is None or held[0] != self.root:
            return False
        return await held[1]()

    async def _repository(self) -> tuple[RepositoryStoreTarget, GitHead]:
        """The checkout's Git directory as a read-only store target, and its ``HEAD``.

        Raises :class:`UnsupportedSourceCapabilityError` when Git does not accept the
        served root as a repository's root, so the routes answer what a plain folder does,
        and :class:`CheckoutGitUnsupportedError` when the host's Git is below the floor, or
        below :data:`PARTIAL_CLONE_GIT_MINIMUM` for a partial clone.
        """

        from metabrowser.git.process import repository_store_target
        from metabrowser.git.repo import repo_info

        version = self._git_version
        if version is None:
            version = await asyncio.to_thread(_admitted_git)
            self._git_version = version
        context, _info = await repo_info(self.root)
        if context is None:
            raise UnsupportedSourceCapabilityError("refs")
        git_dir = await _common_git_directory(self.root)
        if git_dir is None:
            raise UnsupportedSourceCapabilityError("refs")
        target = await asyncio.to_thread(repository_store_target, git_dir=git_dir)
        # Asked only of a Git that needs asking, so a newer one runs nothing more.
        if version < PARTIAL_CLONE_GIT_MINIMUM and await _names_a_promisor(target):
            raise CheckoutGitUnsupportedError(
                "git version " + ".".join(str(part) for part in version),
                partial_clone_version_label(),
                partial_clone=True,
            )
        return target, context.head

    async def list_refs(
        self, kind: RefKind, *, origin_default_ref: str | None = None
    ) -> tuple[str | None, tuple[MirrorRef, ...]]:
        """The ref ``HEAD`` is on, and the checkout's refs of *kind* that name a commit.

        Its branches, tags, or remote-tracking branches. The checked-out branch is
        marked independently of listing priority. ``HEAD``'s ref is ``None`` when detached.
        *origin_default_ref* is the default read from the origin's mirror, when kept.

        Once Metabrowser keeps a store of the checkout's origin (:attr:`origin`), the
        origin's refs are read from it and not from the checkout (:func:`_with_origin`).
        """

        from metabrowser.cache.resolve import CHECKOUT_REFS, list_mirror_refs

        target, head = await self._repository()
        listed = await list_mirror_refs(
            target,
            kind,
            default_ref=head["ref"] if kind == "branch" else None,
            namespaces=CHECKOUT_REFS,
            origin_default_ref=origin_default_ref,
        )
        origin = self.origin
        if origin is not None and kind != "branch":
            # The origin's own, as Metabrowser last fetched them into its store: its
            # branches where the checkout lists remote-tracking ones, its default branch
            # first and marked, and its tags.
            theirs = await origin.mirror.list_refs(
                "branch" if kind == "remote" else "tag",
                default_ref=await origin.mirror.default_ref() if kind == "remote" else None,
            )
            listed = _with_origin(listed, theirs, kind)
        return head["ref"], listed

    async def switch_pin(
        self, *, ref: str | None, oid: str | None, under: str | None = None
    ) -> tuple[bool, SourceSession]:
        """Serve the commit a selection names; ``False`` when it is already served.

        The selection is resolved in the checkout's refs alone. Raises a
        :class:`~metabrowser.mirror_refresh.SelectionError` for one the checkout cannot
        serve; nothing is fetched for one it lacks.

        A selection that names a ref, as *ref* or as *under*, follows it
        (:meth:`observe`); one that names only a commit, *oid*, never moves, even when it
        is served under the ref last served because it is that ref's tip. Asking for the
        revision already served in the other way changes only that, and answers ``False``.
        """

        from metabrowser.cache.resolve import CHECKOUT_REFS, resolve_pin
        from metabrowser.git.ref_state import ref_state

        self.kept_store = await self._open_origin()
        origin = self.origin
        from_store, asked = (
            await self._of_origin(origin, ref=ref, oid=oid, under=under)
            if origin is not None
            else (False, ref)
        )
        if origin is not None and from_store:
            async with self._switching:
                # The store's session resolves, opens, and attaches it, as a mirror's does;
                # the revision is the store's, so none of the checkout's is served now.
                changed, session = await origin.switch_pin(ref=asked, oid=oid, under=under)
                self._served = None
                self._tip = None
                self._by_id = False
                self.read_from = "origin"
                return changed, session
        async with self._switching, self._origin_pin():
            target, head = await self._repository()
            current = self._current()
            if current is not None and current.ref is not None:
                self._last_ref = current.ref
            kept = tuple(dict.fromkeys(r for r in (under, self._last_ref) if r is not None))
            # Named before the ref is read, so a ref that moves between the two is read
            # again at the next ask and never taken for unmoved.
            state = await ref_state(GitLocation.filesystem(self.root))
            resolved = await resolve_pin(
                target,
                ref=ref,
                oid=oid,
                default_ref=head["ref"],
                keep_refs=kept,
                namespaces=CHECKOUT_REFS,
            )
            if under is not None and resolved.ref != under:
                raise SelectionRefMovedError(f"{under} is no longer at that commit")
            by_id = oid is not None and under is None
            if (
                current is not None
                and current.commit_oid == resolved.commit_oid
                and current.ref == resolved.ref
            ):
                if current is self._served:
                    # The same revision, asked for by its ref or by its ID: only whether
                    # it follows changes.
                    self._hold(resolved.ref, resolved.commit_oid, state, by_id=by_id)
                return False, get_source_session()
            subject = await _open_revision(target, resolved.commit_oid, resolved.ref)
            self.shallow = await asyncio.to_thread(_has_boundary, target.git_dir)
            self._served = subject
            self.read_from = "checkout"
            self._hold(resolved.ref, resolved.commit_oid, state, by_id=by_id)
            session = await replace_owned_subject(subject)
            return True, session

    def _hold(self, ref: str | None, commit: str, state: str | None, *, by_id: bool) -> None:
        """Record how the revision served was asked for, and its ref as just resolved.

        The ref was resolved under *state*, named before, so the pin is that ref's tip as
        of *state*. A pin asked for by its ID alone follows nothing, so no tip is kept.
        """

        self._by_id = by_id
        self._tip = (ref, commit) if ref is not None and not by_id else None
        self._refs_state = state
        self._read_at = _monotonic()
        self._read_failing = False

    async def serve_working_tree(self) -> tuple[bool, SourceSession]:
        """Serve the folder again; ``False`` when the working tree is already served."""

        async with self._switching, self._origin_pin():
            if self._current() is None:
                return False, get_source_session()
            self._served = None
            self._tip = None
            self._by_id = False
            self.read_from = None
            return True, await restore_filesystem_subject(self.root)

    # ── Following a branch ──────────────────────────────────────

    def _follows(self, subject: GitRevisionSubject) -> bool:
        """Whether *subject* is the checkout's own revision, asked for by a ref that follows."""

        return (
            subject is self._served
            and not self._by_id
            and follows_moves(subject.ref, FOLLOWED_CHECKOUT_REFS)
        )

    def _followed(self) -> GitRevisionSubject | None:
        """The revision served that follows its ref (:meth:`_follows`), or ``None``."""

        subject = self._current()
        return subject if subject is not None and self._follows(subject) else None

    def _unmoved(self, subject: GitRevisionSubject, state: str | None) -> bool:
        """Whether *subject*'s ref was last read under *state*, so it has not moved since."""

        seen = self._tip
        return (
            state is not None
            and state == self._refs_state
            and seen is not None
            and seen[0] == subject.ref
        )

    def _serve(self, subject: GitRevisionSubject) -> None:
        """Take *subject* as the revision served, before it is attached, as a switch does."""

        self._served = subject

    async def observe(self) -> bool | None:
        """Read where the served ref is in the checkout, and follow it there.

        A revision served under one of the checkout's own branches, remote-tracking
        branches, or tags (:data:`FOLLOWED_CHECKOUT_REFS`), and asked for by that ref,
        reads the ref, not one commit of it, as a mirror's pin does
        (``arch-mirror-acquisition-and-refresh.md``, "Following a Branch"): when the
        reader's commit or fetch moved it, its new tip is served in its place under a new
        generation, by the step a mirror follows with
        (:func:`~metabrowser.mirror_refresh.follow_served_ref`). Nothing is fetched and
        nothing is written: the move is read from the checkout's refs.

        The checkout's ref state is named first, with no Git process and without the
        locks a switch takes, and the ref is read, with one Git process and under those
        locks, only when that state is not the one it was last read under. A repository
        with more loose refs than one state may walk has no state, and its ref is read at
        every ask. An ask within :data:`CHECKOUT_REFS_FLOOR_S` of the last reading,
        another visible page's, is answered from memory.

        ``None`` when nothing that follows is served: the working tree, a commit opened by
        its ID, or a revision read from the store of the origin, which that store's
        session follows. ``False`` when it answered from memory: no ref moved since the
        last reading, that reading is under the floor old, or it failed. ``True`` when the
        ref was read again, moved or not.
        """

        from metabrowser.cache.resolve import ref_tip
        from metabrowser.git.ref_state import ref_state

        # Before the locks: an ask with nothing to read, or whose refs did not move, waits
        # for no switch, and the store's probe that the same ask makes waits for none.
        before = self._followed()
        if before is None:
            return None
        at = _monotonic()
        if self._read_at is not None and at - self._read_at < CHECKOUT_REFS_FLOOR_S:
            return False
        self._read_at = at
        state = await ref_state(GitLocation.filesystem(self.root))
        if self._unmoved(before, state):
            return False
        # Under the locks a switch is made under: a reader's switch that ran meanwhile
        # is what is served now, and this follows only what it finds.
        async with self._switching, self._origin_pin():
            subject = self._followed()
            if subject is None or subject.ref is None:
                return None
            if self._unmoved(subject, state):
                # A switch, or another page's ask, read the ref under this state meanwhile.
                return False
            ref = subject.ref
            target = subject.command_target
            try:
                tip = await ref_tip(target, ref)
            except GitError as exc:
                # Read again at the next ask; what is served stays. A failure that lasts,
                # as when the checkout's Git directory is removed under an open page, is
                # warned of once, and then at debug until a reading succeeds.
                if self._read_failing:
                    log.debug("the served ref still could not be read: %s", failure_detail(exc))
                else:
                    self._read_failing = True
                    log.warning("the served ref could not be read: %s", failure_detail(exc))
                return False
            self._read_failing = False
            self._tip = (ref, tip)
            self._refs_state = state
            if tip is None:
                # The ref is gone: its last commit stays served, and status reports none.
                return True
            moved = await follow_served_ref(
                subject,
                self._tip,
                follows=lambda name: follows_moves(name, FOLLOWED_CHECKOUT_REFS),
                open_tip=lambda name: _open_revision(target, tip, name),
                on_open=self._serve,
            )
            if moved is not None:
                self.shallow = await asyncio.to_thread(_has_boundary, target.git_dir)
            return True

    def freshness_fields(
        self, subject: GitRevisionSubject, store: FreshnessFields
    ) -> FreshnessFields:
        """The freshness half of the status of a revision read from the checkout itself.

        *store* is what the store of the checkout's origin says of itself, or that there
        is none: nothing is fetched into a checkout, so only that store is refreshable.
        A revision that follows its ref (:meth:`_follows`) adds ``follows``, the ref's
        commit as last read as ``latest``, ``None`` for a ref that is gone, and how often
        a visible page asks where the ref is, ``probe_every_s``. A commit opened by its ID
        adds nothing, under a ref or not. From memory alone.
        """

        if not self._follows(subject):
            return store
        tip = self._tip
        latest = tip[1] if tip is not None and tip[0] == subject.ref else None
        return {
            **store,
            "follows": True,
            "latest": latest,
            "probe_every_s": CHECKOUT_REFS_POLL_S,
        }

    def _origin_pin(self) -> contextlib.AbstractAsyncContextManager[object]:
        """The origin store's own pin lock, held while this checkout switches what is served.

        The store's session follows a served origin branch when a fetch moves it, under
        that lock, and reads what is served there. Taken after this checkout's own
        lock, as the switch to an origin branch takes them, so the two never cross.
        """

        origin = self.origin
        return origin.pin_switch() if origin is not None else contextlib.nullcontext()

    def _current(self) -> GitRevisionSubject | None:
        """The revision of this checkout the session serves now, or ``None`` on the folder."""

        try:
            subject = as_git_revision_subject(get_source_session().subject)
        except SubjectNotOpenError:
            return None
        return subject if self.serves(subject) else None

    async def aclose(self) -> None:
        """Leave the folder served and the revision's readers closed. For shutdown."""

        await self.serve_working_tree()


def _with_origin(
    mine: tuple[MirrorRef, ...], theirs: tuple[MirrorRef, ...], kind: RefKind
) -> tuple[MirrorRef, ...]:
    """A checkout's list of *kind* with its origin's refs taken from the origin's store.

    *theirs* are the store's: the origin's branches for the list of remote-tracking
    branches, each named ``origin/<branch>`` as the checkout names it, in place of the
    checkout's own ``refs/remotes/origin/*``, which say only where the origin was when
    the reader last fetched; and the origin's tags for the list of tags. The refs only
    the checkout has stay: another remote's branches, and a tag the origin lacks. The
    checkout's ``origin/*`` is not a second list. In one listing order
    (``in_listing_order`` in ``cache/resolve.py``).

    Each of the origin's branches says where the checkout's own ``origin/<branch>`` is
    when that is another commit, or that the checkout has none
    (:func:`_own_difference`), so a branch the reader has not fetched is visible.
    """

    from metabrowser.cache.resolve import in_listing_order

    if kind == "remote":
        # The checkout's own ``origin/*``, by the ref the store keeps the same branch
        # under: a mirror's ref for its origin's branch is a checkout's for it too.
        readers = {entry.ref: entry for entry in mine if entry.ref.startswith(PROBED_REF_PREFIX)}
        origin = tuple(
            MirrorRef(
                name=f"origin/{entry.name}",
                ref=entry.ref,
                commit=entry.commit,
                default=entry.default,
                committed_at=entry.committed_at,
                checkout=_own_difference(readers.get(entry.ref), entry.commit),
                notable=entry.notable,
            )
            for entry in theirs
        )
        own = tuple(entry for entry in mine if entry.ref not in readers)
    else:
        origin = theirs
        held = {entry.ref for entry in theirs}
        own = tuple(entry for entry in mine if entry.ref not in held)
    return in_listing_order((*origin, *own))


def _own_difference(own: MirrorRef | None, commit: str) -> CheckoutOwnRef | None:
    """Where the checkout's own remote-tracking branch is, when not at *commit*; else ``None``.

    *own* is the checkout's ``refs/remotes/origin/<branch>`` and *commit* the same
    branch's in the store of the origin, as Metabrowser last fetched it. That the two
    differ is all this says, with the checkout's commit and its date. Which is ahead, and
    by how many commits, is not said: it needs a walk of the history between the two for
    each branch that differs, one Git process apiece with a cost the number of refs does
    not bound, where the whole listing is otherwise one ``for-each-ref`` of each
    repository, and the checkout's ref was already read by it. The two dates are in the
    row, and the page says which commit is the later.
    """

    if own is None:
        return CheckoutOwnRef(commit=None, committed_at=None)
    if own.commit == commit:
        return None
    return CheckoutOwnRef(commit=own.commit, committed_at=own.committed_at)


async def _open_revision(
    target: RepositoryStoreTarget, commit_oid: str, ref: str | None
) -> GitRevisionSubject:
    """Open commit *commit_oid* of the checkout at *target*, to be served under *ref*.

    Raises ``GitObjectUnavailableError`` when the checkout does not hold it as a commit.
    """

    from metabrowser.cache.repository_store import object_type
    from metabrowser.git.tree_source import GitObjectUnavailableError, git_revision_subject

    if await object_type(target, commit_oid) != "commit":
        raise GitObjectUnavailableError(commit_oid)
    return await git_revision_subject(
        target=target,
        commit_oid=commit_oid,
        store_identity=f"checkout:{target.git_dir}",
        ref=ref,
    )


def _has_boundary(git_dir: Path) -> bool:
    try:
        return (git_dir / "shallow").stat().st_size > 0
    except OSError:
        return False


@dataclass(slots=True)
class _Held:
    """What was decided for one served root: its revisions, or that it has none."""

    root: Path
    revisions: CheckoutRevisions | None


# The session of Metabrowser's store of a served checkout's origin, and the root it is of.
# Set by ``checkout_store.py`` once the store exists, and dropped when a root is chosen.
_origin: tuple[Path, MirrorSession] | None = None


# How the store of a served checkout's origin is opened, and the root it is of: set by
# ``checkout_store.py`` while an application runs. It answers whether the checkout
# could have a store at all.
_origin_opener: tuple[Path, Callable[[], Awaitable[bool]]] | None = None
# A remote-tracking branch of the origin, as a reader names one.
_ORIGIN_NAME: Final = "origin/"


def set_origin_opener(root: Path, opener: Callable[[], Awaitable[bool]] | None) -> None:
    """Say how the store of the origin of the checkout at *root* is opened, or forget it."""

    global _origin_opener
    if opener is not None:
        _origin_opener = (root, opener)
    elif _origin_opener is not None and _origin_opener[0] == root:
        _origin_opener = None


def set_origin_session(root: Path, session: MirrorSession | None) -> None:
    """Say which session keeps the store of the origin of the checkout at *root*, or none."""

    global _origin
    if session is not None:
        _origin = (root, session)
    elif _origin is not None and _origin[0] == root:
        _origin = None


# What this process decided for its served root. One per process, as the source session
# is: a server serves one subject. Forgotten when a root is chosen and when the
# application stops, so nothing made in one event loop is used in another.
_held: _Held | None = None


def _forget() -> _Held | None:
    """Drop what was decided for the served root, and return it."""

    global _held
    held, _held = _held, None
    return held


def _forget_for_a_new_root() -> None:
    # Choosing a filesystem root is choosing to serve it, and its files.
    global _origin, _origin_opener
    _origin = None
    _origin_opener = None
    _forget()


register_root_callback(_forget_for_a_new_root)


def checkout_revisions() -> CheckoutRevisions | None:
    """The served checkout's revisions, or ``None``: a plain folder, a mirror, or its pin.

    Decided from whether the served root holds a ``.git`` entry, which is the test the
    page's Commits tab is drawn by; Git's own answer comes with the first request that
    needs it, and a root Git refuses then has its row removed by the page. A "yes" is
    kept for the root; a "no" is asked again, so a repository made later is found.
    While one of the checkout's revisions is served the same object answers, so the page
    of a revision keeps its selector.
    """

    global _held
    held = _held
    try:
        subject = get_source_session().subject
    except SubjectNotOpenError:
        return None
    if as_git_revision_subject(subject) is not None:
        revisions = held.revisions if held is not None else None
        return revisions if revisions is not None and revisions.serves(subject) else None
    root = subject.filesystem_root
    if root is None:
        return None
    if held is None or held.root != root or held.revisions is None:
        # A "no" is asked again each time, as the Commits tab's test is: a repository made
        # in a served folder gets its selector at the next page.
        held = _held = _Held(root, CheckoutRevisions(root) if is_checkout_root(root) else None)
    return held.revisions


# The ref ``--ref`` named for the next application lifespan; see :func:`open_on_ref`.
_open_on: str | None = None
# What ``--ref`` says of a root with no refs of its own to open.
NOT_A_CHECKOUT = (
    "--ref names a branch or tag of a checkout, and ROOT is not a Git repository's root"
)


def open_on_ref(ref: str | None) -> None:
    """Open the served checkout on *ref* when the application next starts, or on its files.

    *ref* is what ``metab PATH --ref NAME`` named: a branch, a tag, a remote-tracking
    branch such as ``origin/topic``, or a commit ID, resolved as a page's selection is and
    never as revision syntax. It is taken by one lifespan and then forgotten, so a later
    start in the same process opens the working tree unless it is said again.
    """

    global _open_on
    _open_on = ref


def _say_where(checkout: CheckoutRevisions, ref: str) -> None:
    """Say, on standard error, whether ``--ref`` read the origin's store or the checkout.

    Only for a checkout that could have a store of its origin, and only for one of the
    origin's refs: a ref read from the store, or a remote-tracking branch of the origin
    or a tag read from the checkout because there is no store yet. One line, beside the
    route's own output on standard output.
    """

    served = checkout._current()  # pyright: ignore[reportPrivateUsage]
    if served is None or not checkout.kept_store:
        return
    name = _shown(ref)
    if checkout.read_from == "origin":
        print(
            f"ref: {name} is read from Metabrowser's store of the origin, as last fetched",
            file=sys.stderr,
        )
    elif served.ref is not None and served.ref.startswith((PROBED_REF_PREFIX, "refs/tags/")):
        print(
            f"ref: {name} is read from the checkout; Metabrowser has no store of the "
            "origin with it",
            file=sys.stderr,
        )


async def _open_named_ref(ref: str) -> None:
    """Serve *ref* of the served checkout, or fail the startup with a message to print."""

    checkout = checkout_revisions()
    if checkout is None:
        raise fail_subject_open(NOT_A_CHECKOUT)
    try:
        await checkout.switch_pin(ref=ref, oid=None)
        _say_where(checkout, ref)
    except UnsupportedSourceCapabilityError:
        raise fail_subject_open(NOT_A_CHECKOUT) from None
    except SelectionError as exc:
        raise fail_subject_open(f"--ref {_shown(ref)}: {exc}") from None
    except CheckoutGitUnsupportedError as exc:
        raise fail_subject_open(f"--ref: {exc}") from None
    except ContentReadError as exc:
        # Git's own text can name the checkout's Git directory; only the code is said.
        log.debug("opening the checkout on a ref failed: %s", exc)
        raise fail_subject_open(f"--ref {_shown(ref)} could not be opened ({exc.code})") from None


@asynccontextmanager
async def lifespan_checkout() -> AsyncGenerator[None]:
    """Own what a server keeps for its checkout, and leave the folder served at exit.

    Entered last and so left first: a revision still served at shutdown is detached, and
    its batch readers closed, while the rest of the application is still up. A ref named
    with ``--ref`` is opened here, once the folder and its inventory are up, by the switch
    the pin route makes.
    """

    global _open_on
    ref, _open_on = _open_on, None
    _forget()
    try:
        if ref is not None:
            await _open_named_ref(ref)
        yield
    finally:
        held = _forget()
        if held is not None and held.revisions is not None:
            try:
                await held.revisions.aclose()
            except Exception:
                log.warning("could not return to the working tree at shutdown", exc_info=True)


__all__ = [
    "CHECKOUT_REFS_POLL_S",
    "FOLLOWED_CHECKOUT_REFS",
    "NOT_A_CHECKOUT",
    "PARTIAL_CLONE_GIT_MINIMUM",
    "CheckoutDisplay",
    "CheckoutGitUnsupportedError",
    "CheckoutRevisions",
    "checkout_ref_name",
    "checkout_revisions",
    "lifespan_checkout",
    "open_on_ref",
    "partial_clone_version_label",
    "set_origin_opener",
    "set_origin_session",
]
