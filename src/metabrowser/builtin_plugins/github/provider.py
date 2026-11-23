"""The GitHub repository provider: reducer, ``gh`` credential helper, first-clone checks,
context, the head a pull-request URL pins, the changed file its anchor names, and the
pull requests a server serves.

Before a first clone it runs the GitHub status check (:mod:`.gh_status`): a pull-request
URL that gh cannot read stops there, before anything is cloned, and a repository that
is then not found is explained from that answer, so a token without the ``repo`` scope
says so. A pull request that cannot be read for the same reasons later stops the open
rather than falling back to the default branch (``PullRequestUnavailableError.blocking``).

Core reaches this class only through
:class:`~metabrowser.cache.providers.RepositoryProvider`.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Final

from metabrowser.builtin_plugins.github.gh import (
    ENVIRONMENT_TOKENS,
    GhError,
    gh_executable,
    replace_token_step,
    run_gh,
)
from metabrowser.builtin_plugins.github.gh_status import (
    REQUIRED_SCOPE,
    SIGN_IN_COMMAND,
    SIGN_IN_STATES,
    GithubStatus,
    github_status,
    kept_github_status,
)
from metabrowser.builtin_plugins.github.pull_file_anchor import pull_file_for_anchor
from metabrowser.builtin_plugins.github.pulls import PullDataError, open_pull_request
from metabrowser.builtin_plugins.github.served_pull import ServedPulls
from metabrowser.builtin_plugins.github.urls import (
    CANONICAL_HOST,
    GithubCounterpartHost,
    GithubUrlReducer,
    parse_repository_url,
)
from metabrowser.cache.acquire import AcquisitionError, RepositoryTooLargeError
from metabrowser.cache.free_space import (
    FREE_SPACE_RESERVE_ENV,
    free_space_reserve_bytes,
    gigabytes,
    packed_bytes,
)
from metabrowser.cache.providers import PullRequestUnavailableError
from metabrowser.git.wire import is_full_revision
from metabrowser.repository_context import RepositoryContext

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.cache.providers import (
        CounterpartHost,
        PullRequestFetch,
        PullRequestFile,
        PullRequestPin,
        RefPulls,
    )
    from metabrowser.cache.urls import FileAnchor, GitSource, ProviderUrlReducer
    from metabrowser.mirror_refresh import PullRequestSet

log = logging.getLogger(__name__)

_GITHUB_HTTPS: Final = f"https://{CANONICAL_HOST}/"

_SIZE_OUTPUT_MAX_BYTES: Final[int] = 64


def _single_quoted(text: str) -> str:
    """POSIX shell single quotes, since Git runs a ``!`` helper through ``sh -c``."""

    return "'" + text.replace("'", "'\"'\"'") + "'"


# The helper runs as ``sh -c '<command> get'`` in acquisition Git's environment, which
# keeps every non-Git variable. These would redirect or log gh, or make it write colour
# or terminal output into the credential answer Git parses; they are cleared for it.
HELPER_UNSET_ENV: Final[tuple[str, ...]] = (
    "GH_DEBUG",
    "GH_HOST",
    "GH_REPO",
    "GH_PAGER",
    "DEBUG",
    "CLICOLOR_FORCE",
    "GH_FORCE_TTY",
)
HELPER_SET_ENV: Final[tuple[tuple[str, str], ...]] = (
    ("GH_PROMPT_DISABLED", "1"),
    ("GH_NO_UPDATE_NOTIFIER", "1"),
    ("NO_COLOR", "1"),
)


def credential_helper_args(gh_path: str, *, home: str | None = None) -> tuple[str, ...]:
    """Clear every configured helper, then let ``gh`` answer for github.com alone.

    Git asks a helper only after the server challenges, so a public repository is
    fetched anonymously without anyone deciding its visibility first. Acquisition Git
    runs with ``HOME=/dev/null`` so curl reads no ``.netrc``; *home*, the real one, is
    given back to ``gh`` alone, which needs it to find its own configuration.
    """

    assignments = [f"{name}={value}" for name, value in HELPER_SET_ENV]
    if home:
        assignments.append(f"HOME={_single_quoted(home)}")
    command = (
        f"unset {' '.join(HELPER_UNSET_ENV)}; "
        f"{' '.join(assignments)} {_single_quoted(gh_path)} auth git-credential"
    )
    return (
        "-c",
        "credential.helper=",
        "-c",
        f"credential.{_GITHUB_HTTPS.rstrip('/')}.helper=!{command}",
    )


def _is_github_remote(url: str) -> bool:
    return url.startswith(_GITHUB_HTTPS)


# The status states in which the size read cannot succeed: no gh, no account, or no
# network. In every other state it is asked, since a gh too old for the status check,
# or one whose answer the check could not type, may still read the API; a read that
# fails steps aside.
_NO_SIZE_READ_STATES: Final = frozenset({"gh_missing", "not_logged_in", "network_error"})


class GithubSignInRequiredError(AcquisitionError):
    """A pull-request URL whose first clone would be wasted: gh cannot read the pull
    request until it is installed, updated, or signed in, which the message names."""

    def __init__(self, source_url: str, number: int, status: GithubStatus) -> None:
        super().__init__(
            f"pull request {number} of {source_url} cannot be read: {status.message} "
            f"({status.state}); nothing was cloned"
        )
        self.state = status.state


def _status_hint(status: GithubStatus | None) -> str | None:
    """What a repository that was not found tells a reader, from the status check.

    ``None`` when there is no fresh answer, or it adds nothing to the generic hint.
    """

    if status is None:
        return None
    if status.state == "missing_scope":
        return (
            f"if it is private, gh's token for {status.account} lacks the "
            f"{REQUIRED_SCOPE} scope: {status.fix}"
        )
    if status.state == "not_logged_in":
        return f"if it is private, gh is not signed in: {status.fix}"
    if status.state == "gh_too_old":
        return f"if it is private, update GitHub CLI (gh): {status.fix}"
    if status.state == "ok":
        source = status.token_source
        step = replace_token_step(source) if source in ENVIRONMENT_TOKENS else SIGN_IN_COMMAND
        return (
            f"if it is private, gh is signed in as {status.account}, which cannot read it; "
            f"to use an account that can: {step}"
        )
    return None


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
        self._counterpart = GithubCounterpartHost()

    @property
    def reducer(self) -> ProviderUrlReducer:
        return self._reducer

    @property
    def counterpart(self) -> CounterpartHost:
        return self._counterpart

    def git_config(self, remote_url: str) -> tuple[str, ...]:
        if not _is_github_remote(remote_url):
            return ()
        gh = gh_executable()
        if gh is None:
            return ()
        return credential_helper_args(gh, home=os.environ.get("HOME"))

    def credential_hint(self, source_url: str) -> str | None:
        if not _is_github_remote(source_url):
            return None
        hint = _status_hint(kept_github_status())
        if hint is not None:
            return hint
        # The macOS app's GitHubFailureTests.swift holds these two lines as the CLI
        # prints them, so they change together.
        if gh_executable() is None:
            return "if it is private, install GitHub CLI (gh) and sign in with gh auth login"
        return "if it is private, sign in with gh auth login to an account that can read it"

    async def check_first_clone(self, source: GitSource, *, free_bytes: int | None) -> None:
        parsed = parse_repository_url(source.normalized)
        if parsed is None:
            return
        # The GitHub status check comes first, and its answer is kept for the hint a
        # failed clone adds. A public repository clones without gh, so only a pull
        # request, which gh alone can read, stops here.
        status = await github_status(version=False)
        selection = source.selection
        number = selection.pull_request if selection is not None else None
        if number is not None and status.stops_github_work:
            raise GithubSignInRequiredError(source.normalized, number, status)
        if status.state in _NO_SIZE_READ_STATES or gh_executable() is None:
            # No gh, signed out, or offline: the size read would fail too, and the clone
            # itself reports what is wrong.
            log.debug("skipped the size check for %s: %s", source.normalized, status.state)
            return
        if free_bytes is None:
            # The cache's volume could not be read, so no size would refuse the clone.
            log.debug("skipped the size check for %s: free space unknown", source.normalized)
            return
        owner, repository = parsed
        try:
            out = await run_gh(
                [
                    "api",
                    "--hostname",
                    CANONICAL_HOST,
                    "--method",
                    "GET",
                    f"repos/{owner}/{repository}",
                    "--jq",
                    ".size",
                ],
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
        needed = packed_bytes(size_kb)
        reserve = free_space_reserve_bytes()
        if needed + reserve > free_bytes:
            raise RepositoryTooLargeError(
                source.normalized,
                detail=(
                    f"GitHub reports {size_kb:,} KB, which can take {gigabytes(needed)}, and "
                    f"the cache's volume has {gigabytes(free_bytes)} free, of which metab "
                    f"leaves {gigabytes(reserve)}; free space on the volume, set "
                    f"METABROWSER_CACHE_DIR to one with more, or lower {FREE_SPACE_RESERVE_ENV}"
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
            message = _unavailable(published, number, exc)
            if exc.state == "not_found_or_private":
                # A cached mirror skips the first-clone check, so ask here; a fresh
                # answer from that check is reused rather than asked again.
                status = await github_status(version=False)
                if status.state == "missing_scope":
                    message += f"; {_status_hint(status)}"
            raise PullRequestUnavailableError(
                exc.state, message, blocking=exc.state in SIGN_IN_STATES
            ) from exc

    async def pull_request_file(
        self, published: PublishedSource, number: int, anchor: FileAnchor
    ) -> PullRequestFile | None:
        if parse_repository_url(published.source.normalized) is None:
            return None
        return await pull_file_for_anchor(published, number, anchor)

    def served_pull_requests(self, published: PublishedSource) -> PullRequestSet | None:
        if parse_repository_url(published.source.normalized) is None:
            return None
        return ServedPulls(published)

    async def ref_pulls(self, app: Any) -> RefPulls | None:
        from metabrowser.builtin_plugins.github.ref_pulls import served_ref_pulls

        return await served_ref_pulls(app)

    def repository_context(
        self, source_url: str, *, revision: str, branch: str | None
    ) -> RepositoryContext | None:
        parsed = parse_repository_url(source_url)
        if parsed is None or not is_full_revision(revision) or len(revision) != 40:
            return None
        owner, name = parsed
        return RepositoryContext(
            branch=branch,
            branch_on_origin=branch is not None,
            host=CANONICAL_HOST,
            name=name,
            owner=owner,
            revision=revision,
            served_prefix="",
        )


__all__ = [
    "GithubProvider",
    "GithubSignInRequiredError",
    "credential_helper_args",
]
