"""Resolve and report what a provider web URL selected, for the CLI.

Every mode reads the mirror as it is. The one-shot modes report a ref or commit the
mirror does not have as not found rather than fetching, which keeps transcripts
deterministic. Serve mode instead serves the default branch, fetches once in the
background, and switches to the selection if the fetch brought it; the opener it hands
the server for that is :func:`pending_selection_opener`.
"""

from __future__ import annotations

import logging
from typing import Final

from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.resolve import (
    ResolvedSelection,
    UnresolvedSelection,
    resolve_selection,
)
from metabrowser.cache.urls import RepositorySelection
from metabrowser.cli.common import maybe_cli_logging
from metabrowser.errors import CLIError
from metabrowser.git.process import GitError, repository_store_target
from metabrowser.git.tree_source import GitPath, GitRevisionSubject, display_segment
from metabrowser.mirror_refresh import OpenedSelection, SelectionOpener
from metabrowser.view_routes import VIEW_ROUTE_PREFIX

LOG = logging.getLogger(__name__)

_PULL_REQUEST_NOTE: Final = "pull-request data is not fetched yet"


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
    published: PublishedSource, selection: RepositorySelection
) -> ResolvedSelection:
    """Resolve *selection* in the published store, or raise a path-free ``CLIError``."""

    resolution = await resolve_in_mirror(published, selection)
    if isinstance(resolution, UnresolvedSelection):
        raise CLIError(unresolved_message(published.source.normalized, selection, resolution))
    return resolution


def _missing_path_message(source_url: str, resolved: ResolvedSelection) -> str:
    where = _shown(resolved.name) if resolved.name else resolved.commit[:12]
    return f"{GitPath(resolved.path).display()} is not in {source_url} at {where} (path_not_found)"


async def require_selected_path(
    subject: GitRevisionSubject, source_url: str, resolved: ResolvedSelection
) -> None:
    """Refuse a URL whose path is not in the pinned tree."""

    if resolved.path and await subject.tree_source.resolve_path(GitPath(resolved.path)) is None:
        raise CLIError(_missing_path_message(source_url, resolved))


async def resolve_and_check_for_cli(
    published: PublishedSource, selection: RepositorySelection
) -> ResolvedSelection:
    """Resolve *selection*, then prove its path is in the pinned tree and let go of it."""

    resolved = await resolve_for_cli(published, selection)
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
        return OpenedSelection(subject, selection_view_href(selection, resolution))

    return open_selection


def selection_view_href(selection: RepositorySelection, resolved: ResolvedSelection) -> str:
    """The `/view/` address a served URL selection opens at, with its line anchor.

    The browser keeps the fragment; highlighting the lines is separate work.
    """

    if selection.kind not in {"tree", "blob"} or not resolved.path:
        return VIEW_ROUTE_PREFIX
    href = VIEW_ROUTE_PREFIX + GitPath(resolved.path).to_wire()
    if selection.kind == "tree":
        href += "/"
    if selection.kind == "blob" and selection.lines is not None:
        href += "#" + selection.lines.fragment()
    return href


def _shown(name: str) -> str:
    """A ref name from the origin, with control characters a terminal would act on replaced."""

    return display_segment(name.encode("utf-8", "surrogateescape"))


def _pin_label(resolved: ResolvedSelection) -> str:
    name = _shown(resolved.name or "")
    if resolved.via == "default":
        return f"default branch {name}"
    if resolved.via == "commit":
        return "commit"
    return f"{resolved.via} {name}"


def selection_lines(selection: RepositorySelection, resolved: ResolvedSelection) -> list[str]:
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
    if selection.pull_request is not None:
        note = _PULL_REQUEST_NOTE
        if selection.kind == "pull_request":
            note += "; the pin is the default branch"
        lines.append(f"pull_request: {selection.pull_request} ({note})")
    return lines


def selection_banner(
    selection: RepositorySelection | None, resolved: ResolvedSelection | None
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
        where = GitPath(resolved.path).display() if resolved.path else ""
        anchor = f"#{selection.lines.fragment()}" if selection.lines is not None else ""
        lines.append(f"Selection: {selection.kind} {where}{anchor}".rstrip())
    if selection.pull_request is not None:
        lines.append(f"Pull request: {selection.pull_request} ({_PULL_REQUEST_NOTE})")
    return lines


__all__ = [
    "pending_selection_opener",
    "require_selected_path",
    "resolve_and_check_for_cli",
    "resolve_for_cli",
    "resolve_in_mirror",
    "selection_banner",
    "selection_lines",
    "selection_view_href",
    "unresolved_message",
]
