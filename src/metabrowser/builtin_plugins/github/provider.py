"""The GitHub repository provider: reducer, ``gh`` credential helper, size check, context,
and the head a pull-request URL pins.

Core reaches this class only through
:class:`~metabrowser.cache.providers.RepositoryProvider`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from metabrowser.builtin_plugins.github.gh import GhError, gh_executable, run_gh
from metabrowser.builtin_plugins.github.pulls import PullDataError, open_pull_request
from metabrowser.builtin_plugins.github.urls import (
    CANONICAL_HOST,
    GithubUrlReducer,
    parse_repository_url,
)
from metabrowser.cache.acquire import RepositoryTooLargeError
from metabrowser.cache.providers import PullRequestUnavailableError
from metabrowser.git.process import GIT_ACQUISITION_TIMEOUT_S
from metabrowser.git.wire import is_full_revision
from metabrowser.repository_context import RepositoryContext

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.cache.providers import PullRequestFetch, PullRequestPin
    from metabrowser.cache.urls import GitSource, ProviderUrlReducer

log = logging.getLogger(__name__)

_GITHUB_HTTPS: Final = f"https://{CANONICAL_HOST}/"

# A first clone whose ``repos/<o>/<r>`` size (kilobytes, as GitHub reports it) exceeds
# this is refused before it starts rather than killed at GIT_ACQUISITION_TIMEOUT_S.
# Measured 2026-09-23 on one macOS machine (Git 2.50.1, load average 36 to 103), full
# fetches of every branch and tag, in GitHub-reported kilobytes per second of wall
# clock: flask 4,010, requests 5,160, mypy 3,500, and django 4,120 and 14,200 on two
# runs. The slowest, 3,500 KB/s, would move about 3.1 GB in the 900 s deadline; a third
# of that leaves room for a slower network and for server-side pack preparation, and is
# rounded down to 1,000,000 KB.
MAX_FIRST_CLONE_KB: Final[int] = 1_000_000
_SIZE_OUTPUT_MAX_BYTES: Final[int] = 64


def _single_quoted(text: str) -> str:
    """POSIX shell single quotes, since Git runs a ``!`` helper through ``sh -c``."""

    return "'" + text.replace("'", "'\"'\"'") + "'"


def credential_helper_args(gh_path: str) -> tuple[str, ...]:
    """Clear every configured helper, then let ``gh`` answer for github.com alone.

    Git asks a helper only after the server challenges, so a public repository is
    fetched anonymously without anyone deciding its visibility first.
    """

    return (
        "-c",
        "credential.helper=",
        "-c",
        f"credential.{_GITHUB_HTTPS.rstrip('/')}.helper=!{_single_quoted(gh_path)} auth git-credential",
    )


def _is_github_remote(url: str) -> bool:
    return url.startswith(_GITHUB_HTTPS)


def _unavailable(published: PublishedSource, number: int, exc: PullDataError) -> str:
    """``<what failed> (<state>)``, naming the pull request, for the CLI to print."""

    text = str(exc)
    where = f"pull request {number} of {published.source.normalized}"
    if where not in text:
        text = f"{where}: {text}"
    return f"{text} ({exc.state})"


class GithubProvider:
    """The built-in :class:`~metabrowser.cache.providers.RepositoryProvider` for GitHub."""

    def __init__(self) -> None:
        self._reducer = GithubUrlReducer()

    @property
    def reducer(self) -> ProviderUrlReducer:
        return self._reducer

    def git_config(self, remote_url: str) -> tuple[str, ...]:
        if not _is_github_remote(remote_url):
            return ()
        gh = gh_executable()
        return credential_helper_args(gh) if gh is not None else ()

    def credential_hint(self, source_url: str) -> str | None:
        if not _is_github_remote(source_url):
            return None
        if gh_executable() is None:
            return "if it is private, install GitHub CLI (gh) and sign in with gh auth login"
        return "if it is private, sign in with gh auth login to an account that can read it"

    async def check_first_clone(self, source: GitSource) -> None:
        parsed = parse_repository_url(source.normalized)
        if parsed is None or gh_executable() is None:
            return
        owner, repository = parsed
        try:
            out = await run_gh(
                ["api", "--hostname", "github.com", f"repos/{owner}/{repository}", "--jq", ".size"],
                max_bytes=_SIZE_OUTPUT_MAX_BYTES,
            )
        except GhError as exc:
            # Signed out, offline, or a repository the API cannot see: the clone itself
            # reports what is wrong, so the check steps aside.
            log.debug("skipped the size check for %s: %s", source.normalized, exc)
            return
        text = out.decode("ascii", errors="replace").strip()
        if not text.isdigit():
            log.debug("skipped the size check for %s: unexpected answer", source.normalized)
            return
        size_kb = int(text)
        if size_kb > MAX_FIRST_CLONE_KB:
            raise RepositoryTooLargeError(
                source.normalized,
                detail=(
                    f"GitHub reports {size_kb:,} KB and a first clone is limited to "
                    f"{MAX_FIRST_CLONE_KB:,} KB, about what fits in "
                    f"{GIT_ACQUISITION_TIMEOUT_S:g} s"
                ),
            )

    async def pull_request(
        self, published: PublishedSource, number: int, *, fetch: PullRequestFetch
    ) -> PullRequestPin | None:
        if parse_repository_url(published.source.normalized) is None:
            return None
        try:
            return await open_pull_request(published, number, fetch=fetch)
        except PullDataError as exc:
            raise PullRequestUnavailableError(
                exc.state, _unavailable(published, number, exc)
            ) from exc

    def repository_context(
        self, source_url: str, *, revision: str, branch: str | None
    ) -> RepositoryContext | None:
        parsed = parse_repository_url(source_url)
        if parsed is None or not is_full_revision(revision) or len(revision) != 40:
            return None
        owner, name = parsed
        return RepositoryContext(
            branch=branch,
            host=CANONICAL_HOST,
            name=name,
            owner=owner,
            revision=revision,
            served_prefix="",
        )


__all__ = ["MAX_FIRST_CLONE_KB", "GithubProvider", "credential_helper_args"]
