"""Resolve and report what a provider web URL selected, for the CLI.

Every mode reads the mirror as it is. The one-shot modes report a ref or commit the
mirror does not have as not found rather than fetching, which keeps transcripts
deterministic. Serve mode instead serves the default branch, fetches once in the
background, and switches to the selection if the fetch brought it; the opener it hands
the server for that is :func:`pending_selection_opener`.

A URL inside a pull request is the exception. Its record is opened first, through the
provider that owns the source (:func:`open_pull_for_cli`): from the cache when a usable
record is there, with no call to gh or the network, and otherwise fetched once, which
also brings the pull request's commits, a fork's included, into the store;
``--no-serve`` fetches it every time. A pull-request URL then pins the head, labelled
``refs/pull/<n>/head``. When the pull request cannot be opened, the URL falls back to
what it pins without pull-request data -- the default branch, or the commit a commit URL
names if the mirror has it -- and the ``pull_request`` line says why. A pull request the
provider says only installing or signing in to its tools can open stops the command
instead, with that step (``PullRequestUnavailableError.blocking``), since the fallback
would show something other than what the URL asked for.

A Changes tab URL that anchors one file names it by a hash the provider resolves against
the pull request's changed files, from the cache and the store alone, after the open. A
file it names opens at ``/pull/<n>/files/<path>``; an anchor it cannot resolve is not an
error, and the URL opens the Changes tab itself, with the ``file`` line saying why.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.providers import (
    PullRequestFetch,
    PullRequestFile,
    PullRequestPin,
    PullRequestUnavailableError,
    open_pull_request,
    pull_request_file,
)
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.resolve import (
    ResolvedSelection,
    UnresolvedSelection,
    resolve_selection,
)
from metabrowser.cache.urls import FileAnchor, RepositorySelection
from metabrowser.cli.common import maybe_cli_logging
from metabrowser.cli.selection_href import selection_view_href
from metabrowser.commit_ids import short_commit
from metabrowser.errors import CLIError
from metabrowser.git.process import GitError, repository_store_target
from metabrowser.git.tree_source import GitPath, GitRevisionSubject
from metabrowser.invisible_chars import display_segment
from metabrowser.mirror_refresh import OpenedSelection, SelectionOpener

LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PullOpen:
    """A pull request a URL names: its pin, or why it could not be opened.

    ``file`` is the changed file the URL's anchor names, or why none, for a URL with one.
    """

    number: int
    pin: PullRequestPin | None
    unavailable: str | None
    file: PullRequestFile | None = None

    @property
    def file_path(self) -> str:
        """The path of the changed file the URL's anchor names; empty for none."""

        return (self.file.path or "") if self.file is not None else ""

    def resolution(self) -> ResolvedSelection | None:
        """The pull request's head as a resolved selection, when it opened."""

        if self.pin is None:
            return None
        return ResolvedSelection(
            via="pull_request", name=str(self.number), ref=self.pin.ref, commit=self.pin.head
        )

    def note(self, *, fallback: bool) -> str:
        """What the ``pull_request`` line and banner say about it."""

        if self.pin is not None:
            return self.pin.summary
        where = "; the pin is the default branch" if fallback else ""
        return f"not opened: {self.unavailable}{where}"


async def open_pull_for_cli(
    published: PublishedSource,
    number: int,
    *,
    fetch: PullRequestFetch,
    anchor: FileAnchor | None = None,
) -> PullOpen:
    """Open pull request *number*; a failure is kept as the reason.

    A failure only installing or signing in can fix is raised as a ``CLIError`` that
    names the step, rather than kept for a fallback. With *anchor*, the changed file it
    names is then resolved from what the open left in the cache, whether or not the pull
    request opened.
    """

    with maybe_cli_logging():
        pin: PullRequestPin | None = None
        unavailable: str | None = None
        try:
            pin = await open_pull_request(published, number, fetch=fetch)
        except PullRequestUnavailableError as exc:
            LOG.debug("pull request %s could not be opened: %s", number, exc)
            if exc.blocking:
                raise CLIError(str(exc)) from exc
            unavailable = str(exc)
        file = None if anchor is None else await pull_request_file(published, number, anchor)
    return PullOpen(number=number, pin=pin, unavailable=unavailable, file=file)


def unresolved_message(
    source_url: str, selection: RepositorySelection, unresolved: UnresolvedSelection
) -> str:
    """A path-free message for a selection the mirror cannot answer."""

    reason = unresolved.reason
    if reason == "commit_not_found" and selection.commit is not None:
        text = f"the mirror of {source_url} has no commit {selection.commit}"
    elif reason == "commit_ambiguous" and selection.commit is not None:
        text = f"{selection.commit} names more than one commit in {source_url}; use more digits"
    elif reason == "not_a_commit":
        text = f"the URL names an object in {source_url} that is not a commit"
    elif reason == "invalid_ref":
        text = "the URL does not name a valid ref or commit"
    else:
        text = (
            f"the mirror of {source_url} has no branch, tag, or commit that begins the URL's path"
        )
    return f"{text} ({reason})"


async def resolve_in_mirror(
    published: PublishedSource, selection: RepositorySelection
) -> ResolvedSelection | UnresolvedSelection:
    """Resolve *selection* in the published store; a Git failure is a path-free error."""

    target = repository_store_target(git_dir=published.git_dir)
    with maybe_cli_logging():
        try:
            return await resolve_selection(
                target,
                selection,
                default_ref=published.default_remote_ref,
                default_revision=published.default_revision,
            )
        except GitError as exc:
            LOG.debug("resolving the URL selection failed: %s", exc)
            raise CLIError(
                "a Git command failed while resolving the URL in the mirror "
                "(--log-level debug shows Git's own message)"
            ) from exc


async def resolve_for_cli(
    published: PublishedSource, selection: RepositorySelection, *, pull: PullOpen | None = None
) -> ResolvedSelection:
    """Resolve *selection* in the published store, or raise a path-free ``CLIError``.

    *pull* is the pull request the URL names, already opened: its head when it opened
    and the URL names the pull request itself, and otherwise the mirror's answer.
    """

    head = None if pull is None or selection.kind != "pull_request" else pull.resolution()
    if head is not None:
        return head
    resolution = await resolve_in_mirror(published, selection)
    if isinstance(resolution, UnresolvedSelection):
        message = unresolved_message(published.source.normalized, selection, resolution)
        if pull is not None and pull.unavailable is not None:
            message += f"; {pull.unavailable}"
        raise CLIError(message)
    return resolution


def _missing_path_message(source_url: str, resolved: ResolvedSelection) -> str:
    where = display_ref(resolved.name) if resolved.name else short_commit(resolved.commit)
    return f"{GitPath(resolved.path).display()} is not in {source_url} at {where} (path_not_found)"


async def require_selected_path(
    subject: GitRevisionSubject, source_url: str, resolved: ResolvedSelection
) -> None:
    """Refuse a URL whose path is not in the pinned tree."""

    if resolved.path and await subject.tree_source.resolve_path(GitPath(resolved.path)) is None:
        raise CLIError(_missing_path_message(source_url, resolved))


async def resolve_and_check_for_cli(
    published: PublishedSource, selection: RepositorySelection, *, pull: PullOpen | None = None
) -> ResolvedSelection:
    """Resolve *selection*, then prove its path is in the pinned tree and let go of it."""

    resolved = await resolve_for_cli(published, selection, pull=pull)
    if not resolved.path:
        return resolved
    try:
        subject = await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=resolved.commit,
            store_identity=published.store_id,
        )
    except GitError as exc:
        LOG.debug("opening the pinned revision failed: %s", exc)
        raise CLIError(
            "a Git command failed while opening the pinned revision "
            "(--log-level debug shows Git's own message)"
        ) from exc
    try:
        await require_selected_path(subject, published.source.normalized, resolved)
    finally:
        await subject.aclose()
    return resolved


def pending_selection_opener(
    published: PublishedSource, selection: RepositorySelection
) -> SelectionOpener:
    """What the server asks after the fetch a selection waited for: its pin, or ``None``.

    ``None`` means the selection is still not in the mirror, or its path is not at the
    commit it names. The subject is opened in the serving loop, labelled with its ref,
    with the ``/view/`` address the selection opens at.
    """

    async def open_selection() -> OpenedSelection | None:
        resolution = await resolve_selection(
            repository_store_target(git_dir=published.git_dir),
            selection,
            default_ref=published.default_remote_ref,
            default_revision=published.default_revision,
        )
        if isinstance(resolution, UnresolvedSelection):
            return None
        subject = await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=resolution.commit,
            store_identity=published.store_id,
            ref=resolution.ref,
        )
        if (
            resolution.path
            and await subject.tree_source.resolve_path(GitPath(resolution.path)) is None
        ):
            await subject.aclose()
            return None
        return OpenedSelection(
            subject,
            selection_view_href(selection, resolution.path, commit=resolution.commit),
        )

    return open_selection


def display_ref(name: str) -> str:
    """A ref name from the origin, as a line of output shows it.

    The origin chooses its ref names, and Git accepts one holding a C1 control or an
    invisible character, so a name is displayed as a path segment is: what a terminal
    would act on, and what a reader would not see, is U+FFFD.
    """

    return display_segment(name.encode("utf-8", "surrogateescape"))


def _pin_label(resolved: ResolvedSelection) -> str:
    name = display_ref(resolved.name or "")
    if resolved.via == "default":
        return f"default branch {name}"
    if resolved.via == "commit":
        return "commit"
    if resolved.via == "pull_request":
        return f"pull request {name} head"
    return f"{resolved.via} {name}"


def selection_lines(
    selection: RepositorySelection, resolved: ResolvedSelection, *, pull: PullOpen | None = None
) -> list[str]:
    """``key: value`` lines naming what the URL selected; none for a bare repository URL."""

    if selection.kind == "repository":
        return []
    lines = [f"selection: {selection.kind}", f"pin: {resolved.commit} ({_pin_label(resolved)})"]
    if resolved.path:
        lines.append(f"path: {GitPath(resolved.path).display()}")
    if selection.lines is not None:
        lines.append(f"lines: {selection.lines.fragment()}")
    if selection.plain:
        lines.append("plain: true")
    if selection.pull_tab:
        lines.append(f"tab: {selection.pull_tab}")
    lines.extend(_file_lines(selection, pull, label="file", line_label="diff_line"))
    if pull is not None:
        note = pull.note(fallback=selection.kind == "pull_request")
        lines.append(f"pull_request: {pull.number} ({note})")
    return lines


def selection_banner(
    selection: RepositorySelection | None,
    resolved: ResolvedSelection | None,
    *,
    pull: PullOpen | None = None,
) -> list[str]:
    """Serve mode's banner lines for a URL selection; *resolved* is ``None`` while pending."""

    if selection is None or selection.kind == "repository":
        return []
    lines: list[str] = []
    if resolved is None:
        lines.append(
            f"Selection: {selection.kind} not in the mirror yet; serving the default "
            "branch and fetching once in the background"
        )
    else:
        where = GitPath(resolved.path).display() if resolved.path else selection.pull_tab
        anchor = f"#{selection.lines.fragment()}" if selection.lines is not None else ""
        lines.append(f"Selection: {selection.kind} {where}{anchor}".rstrip())
    lines.extend(_file_lines(selection, pull, label="File", line_label="Diff line"))
    if pull is not None:
        note = pull.note(fallback=selection.kind == "pull_request")
        lines.append(f"Pull request: {pull.number} ({note})")
    return lines


def _file_lines(
    selection: RepositorySelection, pull: PullOpen | None, *, label: str, line_label: str
) -> list[str]:
    """What a Changes tab URL's file anchor opened: the file and its line, or why not.

    The Changes tab has no address for a line, so the line the anchor names is reported
    and the page opens at the file.
    """

    if selection.pull_file is None or pull is None or pull.file is None:
        return []
    if pull.file.path is None:
        return [f"{label}: not resolved: {pull.file.unresolved}; opening the Changes tab"]
    path = GitPath(tuple(segment.encode() for segment in pull.file.path.split("/")))
    lines = [f"{label}: {path.display()}"]
    if selection.pull_file.line:
        lines.append(
            f"{line_label}: {selection.pull_file.line} (the Changes tab opens at the file, "
            "not the line)"
        )
    return lines


__all__ = [
    "PullOpen",
    "display_ref",
    "open_pull_for_cli",
    "pending_selection_opener",
    "require_selected_path",
    "resolve_and_check_for_cli",
    "resolve_for_cli",
    "resolve_in_mirror",
    "selection_banner",
    "selection_lines",
    "unresolved_message",
]
