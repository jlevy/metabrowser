"""Resolve and report what a provider web URL selected, for the one-shot CLI modes.

The one-shot modes read the mirror as it is: a ref or commit the mirror does not have
is reported not found rather than fetched, which keeps transcripts deterministic.
Serving resolves through the same :func:`~metabrowser.cache.resolve.resolve_selection`
and adds one background refresh.

A URL inside a pull request is the exception. Its record is opened first, through the
provider that owns the source: from the cache when a usable record is there, with no
call to gh or the network, and otherwise fetched once, which also brings the pull
request's commits, a fork's included, into the store. ``--no-serve`` fetches it every
time. A pull-request URL then pins the head commit. When the pull request cannot be
opened, the URL falls back to what it pinned before pull-request data existed: a commit
URL inside it pins that commit if the mirror has it, and a pull-request URL pins the
default branch, with the reason on the ``pull_request`` line.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.providers import (
    PullRequestFetch,
    PullRequestPin,
    PullRequestUnavailableError,
    open_pull_request,
)
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
from metabrowser.git.tree_source import GitPath, GitRevisionSubject

LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CliResolution:
    """The commit a URL pins, and the pull request it is inside, if any.

    ``pull_unavailable`` is why a pull request the URL names could not be opened, when
    it could not; the pin then falls back to what the mirror answers without it.
    """

    resolved: ResolvedSelection
    pull: PullRequestPin | None = None
    pull_unavailable: str | None = None


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


async def _open_pull_request_for_cli(
    published: PublishedSource, number: int, *, fetch: PullRequestFetch
) -> PullRequestPin | str:
    """The pull request's pin, or why it could not be opened."""

    with maybe_cli_logging():
        try:
            return await open_pull_request(published, number, fetch=fetch)
        except PullRequestUnavailableError as exc:
            LOG.debug("pull request %s could not be opened: %s", number, exc)
            return str(exc)


async def resolve_for_cli(
    published: PublishedSource,
    selection: RepositorySelection,
    *,
    fetch: PullRequestFetch = "if_missing",
) -> CliResolution:
    """Resolve *selection* in the published store, or raise a path-free ``CLIError``.

    A URL inside a pull request opens its record first, fetching as *fetch* allows. When
    it cannot be opened (no signed-in ``gh``, say), a commit URL inside it still pins a
    commit the mirror has and a pull-request URL pins the default branch, and the
    report says why.
    """

    pull: PullRequestPin | None = None
    unavailable: str | None = None
    if selection.pull_request is not None:
        opened = await _open_pull_request_for_cli(published, selection.pull_request, fetch=fetch)
        if isinstance(opened, str):
            unavailable = opened
        else:
            pull = opened
        if pull is not None and selection.kind == "pull_request":
            resolved = ResolvedSelection(
                via="pull_request", name=str(pull.number), ref=pull.ref, commit=pull.head
            )
            return CliResolution(resolved, pull)
    target = repository_store_target(git_dir=published.git_dir)
    with maybe_cli_logging():
        try:
            resolution = await resolve_selection(
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
    if isinstance(resolution, UnresolvedSelection):
        message = unresolved_message(published.source.normalized, selection, resolution)
        if unavailable is not None:
            message += f"; {unavailable}"
        raise CLIError(message)
    return CliResolution(resolution, pull, unavailable)


async def require_selected_path(
    subject: GitRevisionSubject, source_url: str, resolved: ResolvedSelection
) -> None:
    """Refuse a URL whose path is not in the pinned tree."""

    if not resolved.path:
        return
    path = GitPath(resolved.path)
    if await subject.tree_source.resolve_path(path) is None:
        where = resolved.name or resolved.commit[:12]
        raise CLIError(f"{path.display()} is not in {source_url} at {where} (path_not_found)")


async def resolve_and_check_for_cli(
    published: PublishedSource,
    selection: RepositorySelection,
    *,
    fetch: PullRequestFetch = "if_missing",
) -> CliResolution:
    """Resolve *selection*, then prove its path is in the pinned tree and let go of it."""

    resolution = await resolve_for_cli(published, selection, fetch=fetch)
    resolved = resolution.resolved
    if not resolved.path:
        return resolution
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
    return resolution


def _pin_label(resolved: ResolvedSelection) -> str:
    if resolved.via == "default":
        return f"default branch {resolved.name}"
    if resolved.via == "commit":
        return "commit"
    if resolved.via == "pull_request":
        return f"pull request {resolved.name} head"
    return f"{resolved.via} {resolved.name}"


def selection_lines(selection: RepositorySelection, resolution: CliResolution) -> list[str]:
    """``key: value`` lines naming what the URL selected; none for a bare repository URL."""

    if selection.kind == "repository":
        return []
    resolved = resolution.resolved
    lines = [f"selection: {selection.kind}", f"pin: {resolved.commit} ({_pin_label(resolved)})"]
    if resolved.path:
        lines.append(f"path: {GitPath(resolved.path).display()}")
    if selection.lines is not None:
        lines.append(f"lines: {selection.lines.fragment()}")
    if selection.plain:
        lines.append("plain: true")
    if resolution.pull is not None:
        lines.append(f"pull_request: {resolution.pull.number} ({resolution.pull.summary})")
    elif resolution.pull_unavailable is not None and selection.pull_request is not None:
        fallback = "; the pin is the default branch" if selection.kind == "pull_request" else ""
        lines.append(
            f"pull_request: {selection.pull_request} "
            f"(not opened: {resolution.pull_unavailable}{fallback})"
        )
    return lines


__all__ = [
    "CliResolution",
    "require_selected_path",
    "resolve_and_check_for_cli",
    "resolve_for_cli",
    "selection_lines",
    "unresolved_message",
]
