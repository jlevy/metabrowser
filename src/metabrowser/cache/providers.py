"""The built-in repository providers and the few places core asks them anything.

Core code names no provider and never branches on one. It asks the providers listed
here, through :class:`RepositoryProvider`, for four things: URL reducers for the root
argument, extra Git configuration for a remote URL (a credential helper), a check to run
before a first clone, and the ``repository_context`` of a mirrored source. The list is
fixed, as the built-in browser plugin directories are; there is no public registration
surface for the alpha.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from metabrowser.cache.urls import GitSource, ProviderUrlReducer
    from metabrowser.repository_context import RepositoryContext


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

    The integration point for serving a pin: the shell's pre-paint context comes from
    here for a Git revision subject, as :func:`discover_repository_context` supplies it
    for a served checkout.
    """

    for provider in installed_providers():
        context = provider.repository_context(source_url, revision=revision, branch=branch)
        if context is not None:
            return context
    return None


__all__ = [
    "RepositoryProvider",
    "check_first_clone",
    "installed_providers",
    "provider_credential_hint",
    "provider_git_config",
    "repository_context_for",
    "url_reducers",
]
