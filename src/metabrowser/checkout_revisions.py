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
uses (:func:`metabrowser.git.repo.repo_info`). A repository Git refuses for its ownership
is not read through ``--git-dir`` either.

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
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from metabrowser.content_errors import ContentReadError
from metabrowser.invisible_chars import display_segment
from metabrowser.mirror_refresh import (
    MirrorRef,
    RefKind,
    SelectionError,
    SelectionRefMovedError,
)
from metabrowser.paths_safe import tilde_path
from metabrowser.repository_context import resolve_common_dir, resolve_git_dir
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


def _common_git_directory(root: Path) -> Path | None:
    """The Git directory holding *root*'s objects and refs, or ``None``. Bounded file reads."""

    git_dir = resolve_git_dir(root)
    if git_dir is None:
        return None
    common = resolve_common_dir(git_dir)
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

    def serves(self, subject: object) -> bool:
        """Whether *subject* is the revision this checkout attached."""

        return subject is not None and subject is self._served

    async def _repository(self) -> tuple[RepositoryStoreTarget, GitHead]:
        """The checkout's Git directory as a read-only store target, and its ``HEAD``.

        Raises :class:`UnsupportedSourceCapabilityError` when Git does not accept the
        served root as a repository's root, so the routes answer what a plain folder does.
        """

        from metabrowser.git.process import repository_store_target
        from metabrowser.git.repo import repo_info

        context, _info = await repo_info(self.root)
        if context is None:
            raise UnsupportedSourceCapabilityError("refs")
        git_dir = await asyncio.to_thread(_common_git_directory, self.root)
        if git_dir is None:
            raise UnsupportedSourceCapabilityError("refs")
        target = await asyncio.to_thread(repository_store_target, git_dir=git_dir)
        return target, context.head

    async def head_ref(self) -> str | None:
        """The full ref ``HEAD`` is on, or ``None`` when it is detached."""

        _target, head = await self._repository()
        return head["ref"]

    async def list_refs(self, kind: RefKind) -> tuple[MirrorRef, ...]:
        """The checkout's branches, tags, or remote-tracking branches that name a commit.

        Branches list the checked-out one first, marked as ``default`` is on a mirror.
        """

        from metabrowser.cache.resolve import CHECKOUT_REFS, list_mirror_refs

        target, head = await self._repository()
        return await list_mirror_refs(
            target,
            kind,
            default_ref=head["ref"] if kind == "branch" else None,
            namespaces=CHECKOUT_REFS,
        )

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


def checkout_revisions(app: Any) -> CheckoutRevisions | None:
    """The served checkout's revisions, or ``None``: a plain folder, a mirror, or its pin.

    Decided once for a served root, from whether it holds a ``.git`` entry, which is the
    test the page's Commits tab is drawn by; Git's own answer comes with the first
    request that needs it. While one of the checkout's revisions is served the same
    object answers, so the page of a revision keeps its selector.
    """

    held = getattr(app.state, "source_checkout", None)
    try:
        subject = get_source_session().subject
    except SubjectNotOpenError:
        return None
    if as_git_revision_subject(subject) is not None:
        revisions = held.revisions if isinstance(held, _Held) else None
        return revisions if revisions is not None and revisions.serves(subject) else None
    root = subject.filesystem_root
    if root is None:
        return None
    if not isinstance(held, _Held) or held.root != root:
        try:
            is_checkout = (root / ".git").exists()
        except OSError:
            is_checkout = False
        held = _Held(root, CheckoutRevisions(root) if is_checkout else None)
        app.state.source_checkout = held
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


async def _open_named_ref(app: Any, ref: str) -> None:
    """Serve *ref* of the served checkout, or fail the startup with a message to print."""

    checkout = checkout_revisions(app)
    if checkout is None:
        raise fail_subject_open(NOT_A_CHECKOUT)
    try:
        await checkout.switch_pin(ref=ref, oid=None)
    except UnsupportedSourceCapabilityError:
        raise fail_subject_open(NOT_A_CHECKOUT) from None
    except SelectionError as exc:
        raise fail_subject_open(f"--ref {_shown(ref)}: {exc}") from None
    except ContentReadError as exc:
        # Git's own text can name the checkout's Git directory; only the code is said.
        log.debug("opening the checkout on a ref failed: %s", exc)
        raise fail_subject_open(f"--ref {_shown(ref)} could not be opened ({exc.code})") from None


@asynccontextmanager
async def lifespan_checkout(app: Any) -> AsyncGenerator[None]:
    """Own what a server keeps for its checkout, and leave the folder served at exit.

    Entered last and so left first: a revision still served at shutdown is detached, and
    its batch readers closed, while the rest of the application is still up. A ref named
    with ``--ref`` is opened here, once the folder and its inventory are up, by the switch
    the pin route makes.
    """

    global _open_on
    ref, _open_on = _open_on, None
    app.state.source_checkout = None
    try:
        if ref is not None:
            await _open_named_ref(app, ref)
        yield
    finally:
        held = getattr(app.state, "source_checkout", None)
        app.state.source_checkout = None
        if isinstance(held, _Held) and held.revisions is not None:
            try:
                await held.revisions.aclose()
            except Exception:
                log.warning("could not return to the working tree at shutdown", exc_info=True)


__all__ = [
    "NOT_A_CHECKOUT",
    "CheckoutDisplay",
    "CheckoutRevisions",
    "checkout_ref_name",
    "checkout_revisions",
    "lifespan_checkout",
    "open_on_ref",
]
