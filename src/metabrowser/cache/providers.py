"""The built-in repository providers and the few places core asks them anything.

Core code names no provider and never branches on one. It asks the providers listed
here, through :class:`RepositoryProvider`, for: URL reducers for the root argument, extra
Git configuration for a remote URL (a credential helper), what to say when a source was
not found or needs credentials (``credential_hint``), a check to run before a first
clone, the ``repository_context`` of a mirrored source, the commit a pull-request URL
pins, the changed file a pull-request URL's anchor names, and the pull requests a server
keeps fresh beside the mirror; and, for ``metab --doctor``, a report on the provider's
own tools (:func:`provider_statuses`). The list is fixed, as the built-in browser plugin
directories are; there is no public registration surface for the alpha.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.cache.urls import FileAnchor, GitSource, ProviderUrlReducer
    from metabrowser.mirror_refresh import PullRequestSet
    from metabrowser.repository_context import RepositoryContext

type PullRequestFetch = Literal["if_missing", "always"]
"""When opening a pull request may fetch: only without a usable record, or always."""


@dataclass(frozen=True, slots=True)
class PullRequestPin:
    """What a pull-request URL pins: its head commit and ref, and a line about its data."""

    number: int
    head: str
    ref: str
    summary: str


@dataclass(frozen=True, slots=True)
class PullRequestFile:
    """The changed file a pull-request URL's anchor names, or why none is named.

    ``path`` is the file's path in the pull request's comparison, which
    ``/pull/<n>/files/<path>`` addresses. Without one, ``unresolved`` says why for the
    user, ending in a ``(code)``, and the URL opens the Changes tab itself.
    """

    path: str | None
    unresolved: str | None = None


class PullRequestUnavailableError(Exception):
    """A pull request's data could not be read or fetched; ``state`` says why.

    ``str()`` is written for the user and names no local path. ``blocking`` is true when
    only the step it names, installing or signing in to the provider's own tools, can
    make the pull request readable, so an open stops there rather than falling back to
    the default branch.
    """

    def __init__(self, state: str, message: str, *, blocking: bool = False) -> None:
        super().__init__(message)
        self.state = state
        self.blocking = blocking


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    """What one provider's own tools report, as ``metab --doctor`` prints it.

    ``name`` is the key of its ``--doctor --json`` section, ``report`` that section,
    which the provider's own status route also serves, and ``lines`` its text.
    """

    name: str
    report: Mapping[str, object]
    lines: tuple[str, ...]


class RepositoryProvider(Protocol):
    """What one hosting provider contributes to acquisition and serving."""

    @property
    def reducer(self) -> ProviderUrlReducer:
        """The reducer for this provider's web URL spellings."""
        ...

    def git_config(self, remote_url: str) -> tuple[str, ...]:
        """Extra ``-c`` arguments for a Git command that talks to *remote_url*."""
        ...

    def credential_hint(self, source_url: str) -> str | None:
        """What to do when *source_url* was not found or needs credentials."""
        ...

    async def check_first_clone(self, source: GitSource) -> None:
        """Refuse a first clone of *source* before it starts, by raising.

        Raise :class:`~metabrowser.cache.acquire.AcquisitionError` or a subclass; do
        nothing for a source this provider does not own or cannot check.
        """
        ...

    def repository_context(
        self, source_url: str, *, revision: str, branch: str | None
    ) -> RepositoryContext | None:
        """The context that lets rendered links into *source_url* open locally."""
        ...

    async def pull_request(
        self, published: PublishedSource, number: int, *, fetch: PullRequestFetch
    ) -> PullRequestPin | None:
        """Pull request *number* of *published*, fetched as *fetch* allows.

        Return ``None`` for a source this provider does not own; raise
        :class:`PullRequestUnavailableError` when its data cannot be had.
        """
        ...

    async def pull_request_file(
        self, published: PublishedSource, number: int, anchor: FileAnchor
    ) -> PullRequestFile | None:
        """The changed file of pull request *number* that *anchor* names.

        Read from the cache and the store alone: it never fetches. Return ``None`` for a
        source this provider does not own.
        """
        ...

    def served_pull_requests(self, published: PublishedSource) -> PullRequestSet | None:
        """What a server keeps fresh for the pull requests of *published*, any of them.

        Return ``None`` for a source this provider does not own. It reads nothing.
        """
        ...


@cache
def installed_providers() -> tuple[RepositoryProvider, ...]:
    """The built-in providers, imported on first use."""

    from metabrowser.builtin_plugins.github.provider import GithubProvider

    return (GithubProvider(),)


@cache
def url_reducers() -> tuple[ProviderUrlReducer, ...]:
    """Every provider's URL reducer, for ``classify_root_argument(reducers=)``.

    Each is imported alone, without its provider. A reducer reads a string, and its
    provider brings ``gh``, the pull-request records, and the mirror machinery, none of
    which classifying a ROOT needs: on 2026-11-17 importing the GitHub provider loaded 55
    more modules and took 0.77 s cold, against 7 modules and 14 ms for its reducer, and
    ``--present --dry-run`` classifies a ROOT and opens nothing.
    ``test_url_reducers_are_the_providers_reducers`` in ``tests/test_cache_urls.py`` holds
    this list to the providers'.
    """

    from metabrowser.builtin_plugins.github.urls import GithubUrlReducer

    return (GithubUrlReducer(),)


async def provider_statuses() -> tuple[ProviderStatus, ...]:
    """Every provider's status report, for ``metab --doctor``.

    Each is imported alone, without its provider, as :func:`url_reducers` imports each
    reducer: the doctor needs the status check, not the mirror machinery.
    """

    from metabrowser.builtin_plugins.github.gh_status import doctor_status

    return (await doctor_status(),)


def provider_git_config(remote_url: str) -> tuple[str, ...]:
    """Every provider's extra Git configuration for *remote_url*, in provider order."""

    return tuple(
        arg for provider in installed_providers() for arg in provider.git_config(remote_url)
    )


def provider_credential_hint(source_url: str) -> str | None:
    """The first provider hint for a source that was not found or needs credentials."""

    for provider in installed_providers():
        hint = provider.credential_hint(source_url)
        if hint:
            return hint
    return None


async def check_first_clone(source: GitSource) -> None:
    """Let every provider refuse a first clone of *source* before any fetch."""

    for provider in installed_providers():
        await provider.check_first_clone(source)


def repository_context_for(
    source_url: str, *, revision: str, branch: str | None
) -> RepositoryContext | None:
    """The ``repository_context`` of a pin of *source_url*, or ``None``.

    A served mirror answers the shell's pre-paint context from here for a Git revision
    subject, as :func:`discover_repository_context` does for a served checkout.
    """

    for provider in installed_providers():
        context = provider.repository_context(source_url, revision=revision, branch=branch)
        if context is not None:
            return context
    return None


async def open_pull_request(
    published: PublishedSource, number: int, *, fetch: PullRequestFetch
) -> PullRequestPin:
    """The pin of pull request *number* of *published*, from the provider that owns it."""

    for provider in installed_providers():
        pin = await provider.pull_request(published, number, fetch=fetch)
        if pin is not None:
            return pin
    raise PullRequestUnavailableError(
        "unsupported", f"{published.source.normalized} has no pull requests Metabrowser can read"
    )


async def pull_request_file(
    published: PublishedSource, number: int, anchor: FileAnchor
) -> PullRequestFile:
    """The changed file of pull request *number* that *anchor* names, from its provider."""

    for provider in installed_providers():
        found = await provider.pull_request_file(published, number, anchor)
        if found is not None:
            return found
    return PullRequestFile(
        None,
        f"{published.source.normalized} has no pull requests Metabrowser can read (unsupported)",
    )


def served_pull_requests_for(published: PublishedSource) -> PullRequestSet | None:
    """The pull requests a server serves beside the mirror, from the provider that owns it."""

    for provider in installed_providers():
        served = provider.served_pull_requests(published)
        if served is not None:
            return served
    return None


__all__ = [
    "ProviderStatus",
    "PullRequestFetch",
    "PullRequestFile",
    "PullRequestPin",
    "PullRequestUnavailableError",
    "RepositoryProvider",
    "check_first_clone",
    "installed_providers",
    "open_pull_request",
    "provider_credential_hint",
    "provider_git_config",
    "provider_statuses",
    "pull_request_file",
    "served_pull_requests_for",
    "repository_context_for",
    "url_reducers",
]
