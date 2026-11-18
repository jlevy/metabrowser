"""A served checkout's own branches, tags, and committed revisions, read without touching it.

A folder that is a repository's root is in folder mode, and folder mode is a superset of
mirror mode: any branch or tag of the checkout, the checked-out one included, can be shown
as a mirror shows one, as a pinned revision read from Git objects, while the working tree
stays a separate choice, the one a folder opens on
(``docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md``, "Open
Modes"). :class:`CheckoutRevisions` is that for one served root. The source routes ask it
what a mirror's session answers for a mirror: the refs to list, and to serve another
selection.

**Nothing here writes the checkout.** Showing a revision is ``for-each-ref``,
``rev-parse``, ``cat-file``, and ``ls-tree`` with ``--git-dir`` naming the checkout's Git
directory, and nothing else: no ``checkout``, ``switch``, ``reset``, ``stash``, or
``fetch``, no index, no ``HEAD`` or ref written. The commands run under the store policies
(``git/process.py``), so no optional lock is taken and a partial clone's missing object is
``object_unavailable``, never fetched into the reader's ``.git``.
``tests/test_checkout_revisions.py`` compares every file under the checkout, its ``.git``
included, before and after.

**Where a revision is read from.** The checkout's own Git directory, in place. A linked
worktree's objects and refs are its main repository's, so the directory read is the
common one. The plan says when Metabrowser's cache would be read instead; nothing here
does that yet.

**Which checkouts.** One whose root is the served root and that Git itself accepts, by the
discovery the Commits tab uses (:func:`metabrowser.git.repo.repo_info`): a subdirectory's
revision would show files outside the folder the reader chose, and a repository Git
refuses for its ownership is not read through ``--git-dir`` either.

**Trust.** A revision's pages run under the untrusted profile whatever the folder was
opened with (:func:`metabrowser.capabilities.serve_checkout_revision`), set in the step
that attaches the revision and cleared in the step that attaches the folder again.

Serving a revision replaces the session's subject, as a mirror's pin switch does, so the
switch is server-wide and lasts until the working tree is chosen again or the server
stops. The folder's inventory and watcher keep running underneath, which is why returning
needs no scan.

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

from metabrowser.invisible_chars import display_segment
from metabrowser.mirror_refresh import (
    MirrorRef,
    RefKind,
    SelectionRefMovedError,
)
from metabrowser.paths_safe import tilde_path
from metabrowser.repository_context import resolve_common_dir, resolve_git_dir
from metabrowser.source import (
    SourceSession,
    SubjectNotOpenError,
    UnsupportedSourceCapabilityError,
    as_git_revision_subject,
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
    remote-tracking branch keeps its remote, ``origin/main`` for
    ``refs/remotes/origin/main``, since a checkout has a branch of its own by the bare
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
            # Attached, and the untrusted profile put in effect, before anything else runs.
            session = await replace_owned_subject(subject, checkout_revision=True)
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


@asynccontextmanager
async def lifespan_checkout(app: Any) -> AsyncGenerator[None]:
    """Own what a server keeps for its checkout, and leave the folder served at exit.

    Entered last and so left first: a revision still served at shutdown is detached, and
    its batch readers closed, while the rest of the application is still up.
    """

    app.state.source_checkout = None
    try:
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
    "CheckoutDisplay",
    "CheckoutRevisions",
    "checkout_ref_name",
    "checkout_revisions",
    "lifespan_checkout",
]
