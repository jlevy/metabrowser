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
common one. The plan says when Metabrowser's cache would be read instead; nothing here
does that yet.

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
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

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
    MirrorRef,
    RefKind,
    SelectionError,
    SelectionRefMovedError,
)
from metabrowser.paths_safe import register_root_callback, tilde_path
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


# The first release whose ``GIT_NO_LAZY_FETCH`` also has a partial clone's missing object
# read as missing. From 2.45.0 Git turns ``fetch_if_missing`` off at setup when the
# variable is set (environment.c; setup.c later). An admitted 2.43.7 or 2.44.4 has only
# the security releases' backport, which refuses the fetch (promisor-remote.c) and then
# ends the process: "could not fetch <oid> from promisor remote". So there a revision of a
# blobless clone could not list its tree: nothing was fetched, and the tree route failed
# untyped, "truncated cat-file header", in CI's admitted-git (2.43.7) job on 2026-11-18
# (#559). Read from Git's source at v2.43.7, v2.44.4, v2.45.0, v2.45.4, and v2.50.1.
PARTIAL_CLONE_GIT_MINIMUM: Final = (2, 45, 0)


def _partial_clone_version_label() -> str:
    """The admitted releases that read a partial clone's missing object as missing."""

    track = ".".join(str(part) for part in PARTIAL_CLONE_GIT_MINIMUM[:2])
    first = ".".join(str(part) for part in ACQUISITION_PATCHED_TRACKS[track])
    newest = ".".join(str(part) for part in ACQUISITION_NEWEST_PATCHED)
    return f"{first} or a patched release at least {newest} on a newer track"


class CheckoutGitUnsupportedError(ContentReadError):
    """The host's Git is not one a checkout's revisions are read with.

    The message names the release needed and no path, so a route and ``--ref`` say it as
    it is. *partial_clone* is the stricter need of a checkout that names a promisor
    remote (:data:`PARTIAL_CLONE_GIT_MINIMUM`).
    """

    code = "unsupported_git"
    http_status = 409

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
        # that ref's tip: View file on a commit's diff goes to the commit and back.
        self._last_ref: str | None = None
        # Whether the checkout's history stops at a shallow boundary, read when a revision
        # is served so that the status route still reads nothing.
        self.shallow = False
        # The host's Git version once the floor admitted it; asked again until it does.
        self._git_version: tuple[int, int, int] | None = None

    def serves(self, subject: object) -> bool:
        """Whether *subject* is the revision this checkout attached."""

        return subject is not None and subject is self._served

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
                _partial_clone_version_label(),
                partial_clone=True,
            )
        return target, context.head

    async def list_refs(self, kind: RefKind) -> tuple[str | None, tuple[MirrorRef, ...]]:
        """The ref ``HEAD`` is on, and the checkout's refs of *kind* that name a commit.

        Its branches, tags, or remote-tracking branches. Branches list the checked-out one
        first, marked as ``default`` is on a mirror. ``HEAD``'s ref is ``None`` when it is
        detached.
        """

        from metabrowser.cache.resolve import CHECKOUT_REFS, list_mirror_refs

        target, head = await self._repository()
        listed = await list_mirror_refs(
            target,
            kind,
            default_ref=head["ref"] if kind == "branch" else None,
            namespaces=CHECKOUT_REFS,
        )
        return head["ref"], listed

    async def switch_pin(
        self, *, ref: str | None, oid: str | None, under: str | None = None
    ) -> tuple[bool, SourceSession]:
        """Serve the commit a selection names; ``False`` when it is already served.

        The selection is resolved in the checkout's refs alone. Raises a
        :class:`~metabrowser.mirror_refresh.SelectionError` for one the checkout cannot
        serve; nothing is fetched for one it lacks.
        """

        from metabrowser.cache.repository_store import object_type
        from metabrowser.cache.resolve import CHECKOUT_REFS, resolve_pin
        from metabrowser.git.tree_source import GitObjectUnavailableError, git_revision_subject

        async with self._switching:
            target, head = await self._repository()
            current = self._current()
            if current is not None and current.ref is not None:
                self._last_ref = current.ref
            kept = tuple(dict.fromkeys(r for r in (under, self._last_ref) if r is not None))
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
            if (
                current is not None
                and current.commit_oid == resolved.commit_oid
                and current.ref == resolved.ref
            ):
                return False, get_source_session()
            if await object_type(target, resolved.commit_oid) != "commit":
                raise GitObjectUnavailableError(resolved.commit_oid)
            subject = await git_revision_subject(
                target=target,
                commit_oid=resolved.commit_oid,
                store_identity=f"checkout:{target.git_dir}",
                ref=resolved.ref,
            )
            self.shallow = await asyncio.to_thread(_has_boundary, target.git_dir)
            self._served = subject
            session = await replace_owned_subject(subject)
            return True, session

    async def serve_working_tree(self) -> tuple[bool, SourceSession]:
        """Serve the folder again; ``False`` when the working tree is already served."""

        async with self._switching:
            if self._current() is None:
                return False, get_source_session()
            self._served = None
            return True, await restore_filesystem_subject(self.root)

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
        try:
            is_checkout = (root / ".git").exists()
        except OSError:
            is_checkout = False
        held = _held = _Held(root, CheckoutRevisions(root) if is_checkout else None)
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


async def _open_named_ref(ref: str) -> None:
    """Serve *ref* of the served checkout, or fail the startup with a message to print."""

    checkout = checkout_revisions()
    if checkout is None:
        raise fail_subject_open(NOT_A_CHECKOUT)
    try:
        await checkout.switch_pin(ref=ref, oid=None)
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
    "NOT_A_CHECKOUT",
    "PARTIAL_CLONE_GIT_MINIMUM",
    "CheckoutDisplay",
    "CheckoutGitUnsupportedError",
    "CheckoutRevisions",
    "checkout_ref_name",
    "checkout_revisions",
    "lifespan_checkout",
    "open_on_ref",
]
