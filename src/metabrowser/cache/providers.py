"""The built-in repository providers and the few places core asks them anything.

Core code names no provider and never branches on one. It asks the providers listed
here, through :class:`RepositoryProvider`, for six things: URL reducers for the root
argument, extra Git configuration for a remote URL (a credential helper), a check to run
before a first clone, the ``repository_context`` of a mirrored source, the commit a
pull-request URL pins, and the pull request a server keeps fresh beside the mirror. The
list is fixed, as the built-in browser plugin directories are; there is no public
registration surface for the alpha.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.cache.urls import GitSource, ProviderUrlReducer
    from metabrowser.mirror_refresh import CompanionRefresh
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


class PullRequestUnavailableError(Exception):
    """A pull request's data could not be read or fetched; ``state`` says why.

    ``str()`` is written for the user and names no local path.
    """

    def __init__(self, state: str, message: str) -> None:
        super().__init__(message)
        self.state = state


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

    async def served_pull_request(
        self, published: PublishedSource, number: int
    ) -> CompanionRefresh | None:
        """What a server keeps fresh for pull request *number* of *published*.

        Return ``None`` for a source this provider does not own. It reads no network.
        """
        ...


@cache
def installed_providers() -> tuple[RepositoryProvider, ...]:
    """The built-in providers, imported on first use."""

    from metabrowser.builtin_plugins.github.provider import GithubProvider

    return (GithubProvider(),)


def url_reducers() -> tuple[ProviderUrlReducer, ...]:
    """Every provider's URL reducer, for ``classify_root_argument(reducers=)``."""

    return tuple(provider.reducer for provider in installed_providers())


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


async def served_pull_request_for(
    published: PublishedSource, number: int
) -> CompanionRefresh | None:
    """The pull request a server serves beside the mirror, from the provider that owns it."""

    for provider in installed_providers():
        served = await provider.served_pull_request(published, number)
        if served is not None:
            return served
    return None


__all__ = [
    "PullRequestFetch",
    "PullRequestPin",
    "PullRequestUnavailableError",
    "RepositoryProvider",
    "check_first_clone",
    "installed_providers",
    "open_pull_request",
    "provider_credential_hint",
    "provider_git_config",
    "served_pull_request_for",
    "repository_context_for",
    "url_reducers",
]
