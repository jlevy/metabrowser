"""The GitHub status check: which ``gh``, its version, the signed-in account, and its scopes.

One bounded check, read three ways: ``metab --doctor`` prints it, ``GET
/api/plugin/github/status`` serves it to the page and the app, and the GitHub provider
reads it before a first clone, so a pull request that cannot be read without ``gh``
stops before the clone with the step that fixes it. Each answer has one
:data:`GithubStatusState`:

| State | Meaning | ``fix`` |
| --- | --- | --- |
| ``ok`` | signed in, and the token can read private repositories or gh reports no scopes | none |
| ``gh_missing`` | no ``gh`` on ``PATH`` | the install page |
| ``gh_too_old`` | this ``gh`` has no ``auth status --json`` | the install page |
| ``not_logged_in`` | no active github.com account, or GitHub refused its token | ``gh auth login`` |
| ``missing_scope`` | signed in, but the token lacks :data:`REQUIRED_SCOPE` | ``gh auth refresh`` |
| ``network_error`` | gh could not reach GitHub, or did not answer in time | none |
| ``gh_failed`` | gh answered something else | ``gh auth status`` |

A token gh reports no scopes for, as for a fine-grained or GitHub App token, is ``ok``:
its access is per repository, which only the repository's own read can tell. Only
``gh_missing``, ``gh_too_old``, and ``not_logged_in`` stop work (:data:`SIGN_IN_STATES`):
a public repository clones without ``gh``, and offline a cached record still answers.

The answer is kept for :data:`GH_STATUS_TTL_S` per ``gh`` and configuration, and callers
in one event loop share a check in flight, so a page and the app asking at once run
``gh`` once. Like everything in :mod:`.gh`, it never reads, stores, or logs a token.
"""

from __future__ import annotations

import asyncio
import os
import time
import weakref
from dataclasses import dataclass, replace
from typing import Final, Literal

from metabrowser.builtin_plugins.github.gh import (
    GH_HOSTNAME,
    GhAccount,
    GhError,
    GhUnavailableError,
    gh_active_account,
    gh_executable,
    gh_version,
)
from metabrowser.cache.providers import ProviderStatus

# `gh auth status --active --hostname github.com --json hosts` asks GitHub about the
# active token. Measured 2026-11-18 with gh 2.98.0 on one macOS machine at a load average
# near 116: five runs took 0.61 to 0.65 s, and `gh --version` 0.07 to 0.26 s. Each
# deadline is about fifteen times the slowest run, so it bounds a hung gh, not a slow one.
GH_STATUS_TIMEOUT_S: Final[float] = 10.0
GH_VERSION_TIMEOUT_S: Final[float] = 5.0
# How long an answer is reused: the first-clone check and a failed clone's hint in one
# command share it, and a page and the app asking together run gh once, while a person who
# signs in and retries is told the new state within seconds.
GH_STATUS_TTL_S: Final[float] = 10.0
# The OAuth scope that lets a classic token read private repositories and their pull
# requests. Public ones need no scope.
REQUIRED_SCOPE: Final = "repo"
INSTALL_PAGE: Final = "https://cli.github.com/"
SIGN_IN_COMMAND: Final = f"gh auth login --hostname {GH_HOSTNAME}"
SCOPE_COMMAND: Final = f"gh auth refresh --hostname {GH_HOSTNAME} --scopes {REQUIRED_SCOPE}"
REPORT_COMMAND: Final = f"gh auth status --hostname {GH_HOSTNAME}"
# What gh reads its configuration and token from, besides the keychain: an answer is
# reused only while these and the gh found on PATH are the same. Only whether a token
# variable is set is compared, never its value.
_CONFIGURATION_ENV: Final = ("HOME", "XDG_CONFIG_HOME", "GH_CONFIG_DIR")
_TOKEN_ENV: Final = ("GH_TOKEN", "GITHUB_TOKEN")

type GithubStatusState = Literal[
    "ok",
    "gh_missing",
    "gh_too_old",
    "not_logged_in",
    "missing_scope",
    "network_error",
    "gh_failed",
]

SIGN_IN_STATES: Final[frozenset[str]] = frozenset({"gh_missing", "gh_too_old", "not_logged_in"})
"""The states only installing, updating, or signing in to ``gh`` can fix."""
# The states in which GitHub confirmed the token, so its scopes are known or known absent.
_CONFIRMED_STATES: Final[frozenset[str]] = frozenset({"ok", "missing_scope"})


@dataclass(frozen=True, slots=True)
class GithubStatus:
    """One answer of the GitHub status check, as the route and ``--doctor --json`` serve it.

    ``message`` says what is true, naming the fix in words; ``fix`` is the one command to
    run, or the page to install ``gh`` from, or ``None`` when nothing the user runs fixes
    it. ``gh_version`` is ``None`` when the check did not ask for it or gh named none.
    """

    state: GithubStatusState
    message: str
    fix: str | None = None
    gh_path: str | None = None
    gh_version: str | None = None
    account: str | None = None
    token_source: str | None = None
    scopes: tuple[str, ...] | None = None

    @property
    def stops_github_work(self) -> bool:
        """Whether work that needs ``gh`` cannot start until the user fixes it."""

        return self.state in SIGN_IN_STATES

    def to_json(self) -> dict[str, object]:
        return {
            "host": GH_HOSTNAME,
            "state": self.state,
            "message": self.message,
            "fix": self.fix,
            "gh_path": self.gh_path,
            "gh_version": self.gh_version,
            "account": self.account,
            "token_source": self.token_source,
            "scopes": list(self.scopes) if self.scopes is not None else None,
        }

    def lines(self) -> tuple[str, ...]:
        """The section ``metab --doctor`` prints: the state and message, then details."""

        if self.gh_path is None:
            where = "not found on PATH"
        else:
            version = f"version {self.gh_version}" if self.gh_version else "version unknown"
            where = f"{self.gh_path} ({version})"
        lines = [f"github: {self.state}: {self.message}", f"  gh: {where}"]
        if self.account is not None:
            source = f" (token from {self.token_source})" if self.token_source else ""
            lines.append(f"  account: {self.account}{source}")
        if self.state in _CONFIRMED_STATES:
            scopes = ", ".join(self.scopes) if self.scopes is not None else "not reported"
            lines.append(f"  scopes: {scopes}")
        if self.fix is not None:
            lines.append(f"  fix: {self.fix}")
        return tuple(lines)


def _environment_token(account: GhAccount) -> str | None:
    """The environment variable gh read the token from, when it was one of its own."""

    source = account.token_source
    return source if source in _TOKEN_ENV else None


def _signed_in(path: str, account: GhAccount) -> GithubStatus:
    """The status of an account gh named: confirmed, refused, offline, or short a scope."""

    login = account.login
    found = GithubStatus(
        "ok",
        f"GitHub CLI is signed in to {GH_HOSTNAME} as {login}.",
        gh_path=path,
        account=login,
        token_source=account.token_source,
        scopes=account.scopes,
    )
    from_env = _environment_token(account)
    problem = account.problem
    if problem is not None and problem.state == "not_logged_in":
        fix = (
            f"replace the token in {from_env}, or unset it and run {SIGN_IN_COMMAND}"
            if from_env
            else SIGN_IN_COMMAND
        )
        message = f"GitHub refused gh's token for {login}. To sign in again: {fix}."
        return replace(found, state="not_logged_in", message=message, fix=fix)
    if problem is not None and problem.state == "network_error":
        message = f"gh is signed in as {login} but could not check its token: {_sentence(problem)}"
        return replace(found, state="network_error", message=message)
    if problem is not None:
        return replace(found, state="gh_failed", message=_sentence(problem), fix=REPORT_COMMAND)
    if account.scopes is not None and REQUIRED_SCOPE not in account.scopes:
        fix = (
            f"give {from_env} a token with the {REQUIRED_SCOPE} scope, "
            f"or unset it and run {SIGN_IN_COMMAND}"
            if from_env
            else SCOPE_COMMAND
        )
        message = (
            f"GitHub CLI is signed in to {GH_HOSTNAME} as {login}, but its token lacks "
            f"the {REQUIRED_SCOPE} scope, so it reads public repositories only. "
            f"To read private ones: {fix}."
        )
        return replace(found, state="missing_scope", message=message, fix=fix)
    return found


def _sentence(exc: GhError) -> str:
    text = str(exc)
    return text if text.endswith(".") else f"{text}."


def _refused(path: str | None, exc: GhError) -> GithubStatus:
    """The status of a check gh could not answer with an account."""

    message = _sentence(exc)
    if isinstance(exc, GhUnavailableError) or path is None:
        return GithubStatus("gh_missing", message, INSTALL_PAGE)
    if exc.state == "gh_too_old":
        return GithubStatus("gh_too_old", message, INSTALL_PAGE, gh_path=path)
    if exc.state == "not_logged_in":
        return GithubStatus("not_logged_in", message, SIGN_IN_COMMAND, gh_path=path)
    if exc.state == "network_error":
        return GithubStatus("network_error", message, None, gh_path=path)
    unexplained = f"gh auth status did not report an account; run {REPORT_COMMAND} to see why."
    return GithubStatus("gh_failed", unexplained, REPORT_COMMAND, gh_path=path)


async def _check() -> GithubStatus:
    """Run ``gh auth status`` once and type what it says."""

    path = gh_executable()
    if path is None:
        return _refused(None, GhUnavailableError())
    try:
        account = await gh_active_account(timeout_s=GH_STATUS_TIMEOUT_S)
    except GhError as exc:
        return _refused(path, exc)
    return _signed_in(path, account)


type _Key = tuple[str | None, ...]


@dataclass(frozen=True, slots=True)
class _Kept:
    key: _Key
    at: float
    status: GithubStatus


_kept: _Kept | None = None
_versions: dict[str, tuple[float, str | None]] = {}
# One check in flight per event loop: a task belongs to the loop that made it, and the CLI
# and a server each run their own.
_in_flight: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, tuple[_Key, asyncio.Task[GithubStatus]]
] = weakref.WeakKeyDictionary()


def _key() -> _Key:
    path = gh_executable()
    configuration = tuple(os.environ.get(name) for name in _CONFIGURATION_ENV)
    tokens = tuple("set" if os.environ.get(name) else None for name in _TOKEN_ENV)
    return (path, *configuration, *tokens)


def kept_github_status() -> GithubStatus | None:
    """The last answer, while it is fresh and gh and its configuration are unchanged.

    For a caller that cannot wait, such as the hint a failed clone's message adds; it
    never runs gh.
    """

    kept = _kept
    if kept is None or time.monotonic() - kept.at >= GH_STATUS_TTL_S or kept.key != _key():
        return None
    return kept.status


def forget_github_status() -> None:
    """Drop every kept answer, so the next check runs gh again."""

    global _kept
    _kept = None
    _versions.clear()


async def _sign_in() -> GithubStatus:
    global _kept
    key = _key()
    kept = _kept
    if kept is not None and kept.key == key and time.monotonic() - kept.at < GH_STATUS_TTL_S:
        return kept.status
    loop = asyncio.get_running_loop()
    running = _in_flight.get(loop)
    if running is None or running[0] != key or running[1].done():
        running = (key, loop.create_task(_check()))
        _in_flight[loop] = running
    task = running[1]
    try:
        status = await asyncio.shield(task)
    finally:
        if task.done() and _in_flight.get(loop) is running:
            del _in_flight[loop]
    _kept = _Kept(key, time.monotonic(), status)
    return status


async def _version(path: str) -> str | None:
    known = _versions.get(path)
    if known is not None and time.monotonic() - known[0] < GH_STATUS_TTL_S:
        return known[1]
    try:
        version = await gh_version(timeout_s=GH_VERSION_TIMEOUT_S)
    except GhError:
        version = None
    _versions[path] = (time.monotonic(), version)
    return version


async def github_status(*, version: bool = True) -> GithubStatus:
    """The GitHub status check, from a fresh kept answer or one run of ``gh``.

    With *version*, ``gh --version`` is read too, which only the reports need; the checks
    before work leave it out, so they run gh once.
    """

    status = await _sign_in()
    if not version or status.gh_path is None:
        return status
    return replace(status, gh_version=await _version(status.gh_path))


async def doctor_status() -> ProviderStatus:
    """The ``github`` section of ``metab --doctor``: the route's answer, and its text."""

    status = await github_status()
    return ProviderStatus(name="github", report=status.to_json(), lines=status.lines())


__all__ = [
    "GH_STATUS_TIMEOUT_S",
    "GH_STATUS_TTL_S",
    "GH_VERSION_TIMEOUT_S",
    "INSTALL_PAGE",
    "REQUIRED_SCOPE",
    "SCOPE_COMMAND",
    "SIGN_IN_COMMAND",
    "SIGN_IN_STATES",
    "GithubStatus",
    "GithubStatusState",
    "doctor_status",
    "forget_github_status",
    "github_status",
    "kept_github_status",
]
