"""The GitHub status check: which ``gh``, its version, the signed-in account, and its scopes.

One bounded check, read three ways: ``metab --doctor`` prints it, ``POST
/api/plugin/github/status`` serves it (a POST, since it runs ``gh``), and the GitHub
provider reads it before a first clone, so a pull request that cannot be read without
``gh`` stops before the clone with the step that fixes it. Each answer has one
:data:`GithubStatusState`:

| State | Meaning | ``fix`` |
| --- | --- | --- |
| ``ok`` | signed in, and the token can read private repositories or gh reports no scopes | none |
| ``gh_missing`` | no ``gh`` on ``PATH`` | the install page |
| ``gh_too_old`` | this ``gh`` is older than :data:`GH_MINIMUM`, or has no ``auth status --json`` | the upgrade for how it was installed (:func:`gh_upgrade_fix`) |
| ``not_logged_in`` | no active github.com account, or GitHub refused its token | ``gh auth login``, or replacing a refused token in ``GH_TOKEN`` or ``GITHUB_TOKEN`` |
| ``missing_scope`` | signed in, but the token lacks :data:`REQUIRED_SCOPE` | ``gh auth refresh`` |
| ``network_error`` | gh could not reach GitHub, or did not answer in time | none |
| ``gh_failed`` | gh answered something else | ``gh auth status`` |

A token gh reports no scopes for, as for a fine-grained or GitHub App token, is ``ok``:
its access is per repository, which only the repository's own read can tell. Only
``gh_missing``, ``gh_too_old``, and ``not_logged_in`` stop work (:data:`SIGN_IN_STATES`):
a public repository clones without ``gh``, and offline a cached record still answers.

:data:`GH_MINIMUM` is the only ``gh`` minimum: a report that reads ``gh --version``
compares it, and a check that does not falls back on ``gh auth status --json`` refusing
the flag, which a ``gh`` below the minimum does. The app reads ``gh_minimum`` from
``metab --doctor --json`` and never declares one of its own.

The answer is kept for :data:`GH_STATUS_TTL_S` per ``gh`` and configuration, and callers
in one event loop share a check in flight, so a page and the app asking at once run
``gh`` once. :func:`forget_github_status`, which a ``fresh`` request calls, starts a new
check rather than join or keep one that began before it. Like everything in :mod:`.gh`,
it never reads, stores, or logs a token.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
import weakref
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from typing import Any, Final, Literal

from metabrowser.builtin_plugins.github.gh import (
    ENVIRONMENT_TOKENS,
    GH_HOSTNAME,
    SIGN_IN_COMMAND,
    GhAccount,
    GhError,
    GhTokenRefusedError,
    GhUnavailableError,
    gh_active_account,
    gh_executable,
    gh_version,
    replace_token_step,
)
from metabrowser.cache.providers import ProviderStatus
from metabrowser.tool_install import install_method

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
# The oldest gh metab works with. 2.81.0 (2025-10-01) added `gh auth status --json`
# (cli/cli#11544, read from the v2.81.0 release notes on 2026-11-18), which
# `gh_active_account` runs for the account, its token source, and its scopes, and which
# every check before GitHub work and every report runs. The other commands metab runs are
# older: `gh auth status --active` arrived in 2.57.0 (cli/cli#9520), and `gh api` with
# `--hostname`, `--method`, `--include`, `-H`, and `--jq`, and `gh api graphql`, before it.
# Raise it, with the reason here, when metab starts to run something a newer gh added.
GH_MINIMUM: Final[tuple[int, int, int]] = (2, 81, 0)
GH_MINIMUM_LABEL: Final = ".".join(str(part) for part in GH_MINIMUM)
# The upgrade of a gh that Homebrew or MacPorts installed. Any other is updated from
# INSTALL_PAGE, which names every installer.
GH_UPGRADE_COMMANDS: Final = {"homebrew": "brew upgrade gh", "macports": "sudo port upgrade gh"}
# The release numbers at the start of the version `gh --version` names.
_RELEASE = re.compile(r"^([0-9]+)\.([0-9]+)(?:\.([0-9]+))?")
SCOPE_COMMAND: Final = f"gh auth refresh --hostname {GH_HOSTNAME} --scopes {REQUIRED_SCOPE}"
REPORT_COMMAND: Final = f"gh auth status --hostname {GH_HOSTNAME}"
# What gh reads its configuration and token from, besides the keychain: an answer is
# reused only while these and the gh found on PATH are the same. Only whether a token
# variable is set is compared, never its value.
_CONFIGURATION_ENV: Final = ("HOME", "XDG_CONFIG_HOME", "GH_CONFIG_DIR")

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
            "gh_minimum": GH_MINIMUM_LABEL,
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
            where = f"{self.gh_path} ({version}; needs {GH_MINIMUM_LABEL} or later)"
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


def gh_upgrade_fix(path: str) -> str:
    """The step that updates the gh at *path*: its package manager's upgrade, or the
    install page for one installed any other way."""

    return GH_UPGRADE_COMMANDS.get(install_method(path), INSTALL_PAGE)


def gh_below_minimum(version: str | None) -> bool:
    """Whether *version*, as ``gh --version`` names it, is older than :data:`GH_MINIMUM`.

    A version without release numbers is not judged: the ``auth status --json`` probe
    still finds a gh that lacks the flag.
    """

    match = _RELEASE.match(version) if version is not None else None
    if match is None:
        return False
    found = (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))
    return found < GH_MINIMUM


def _too_old(path: str, version: str | None) -> GithubStatus:
    """The status of a gh older than :data:`GH_MINIMUM`, by its version or by the probe."""

    fix = gh_upgrade_fix(path)
    found = f"GitHub CLI {version}" if version is not None else "This GitHub CLI"
    message = (
        f"{found} cannot report the signed-in account; Metabrowser needs gh "
        f"{GH_MINIMUM_LABEL} or later. To update it: {fix}."
    )
    return GithubStatus("gh_too_old", message, fix, gh_path=path, gh_version=version)


def _environment_token(account: GhAccount) -> str | None:
    """The environment variable gh read the token from, when it was one of its own."""

    source = account.token_source
    return source if source in ENVIRONMENT_TOKENS else None


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
        fix = replace_token_step(from_env) if from_env else SIGN_IN_COMMAND
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
        return _too_old(path, None)
    if isinstance(exc, GhTokenRefusedError):
        return GithubStatus(
            "not_logged_in", message, exc.fix, gh_path=path, token_source=exc.variable
        )
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
# Bumped by forget_github_status: a check that started before is neither joined nor kept,
# since it may have run before the reader signed in.
_generation = 0
# The checks in flight, per event loop: a task belongs to the loop that made it, and the
# CLI and a server each run their own. Callers asking for the same answer at once await
# one task.
type _FlightKey = tuple[object, ...]
_in_flight: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, dict[_FlightKey, asyncio.Task[Any]]
] = weakref.WeakKeyDictionary()


def _key() -> _Key:
    path = gh_executable()
    configuration = tuple(os.environ.get(name) for name in _CONFIGURATION_ENV)
    tokens = tuple("set" if os.environ.get(name) else None for name in ENVIRONMENT_TOKENS)
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
    """Drop every kept answer, so the next check runs gh again rather than join or keep
    one already running."""

    global _kept, _generation
    _kept = None
    _versions.clear()
    _generation += 1


async def _once[T](key: _FlightKey, run: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """*run*'s answer, from the one task in this event loop running it for *key*.

    A caller that is cancelled leaves the task to the others; it ends within its own
    deadline.
    """

    loop = asyncio.get_running_loop()
    tasks = _in_flight.setdefault(loop, {})
    task = tasks.get(key)
    if task is None or task.done():
        task = loop.create_task(run())
        tasks[key] = task
    try:
        return await asyncio.shield(task)
    finally:
        if task.done() and tasks.get(key) is task:
            del tasks[key]


async def _sign_in() -> GithubStatus:
    global _kept
    key = _key()
    kept = _kept
    if kept is not None and kept.key == key and time.monotonic() - kept.at < GH_STATUS_TTL_S:
        return kept.status
    generation = _generation
    status = await _once(("auth", generation, *key), _check)
    if generation == _generation:
        _kept = _Kept(key, time.monotonic(), status)
    return status


async def _read_version() -> str | None:
    try:
        return await gh_version(timeout_s=GH_VERSION_TIMEOUT_S)
    except GhError:
        return None


async def _version(path: str) -> str | None:
    known = _versions.get(path)
    if known is not None and time.monotonic() - known[0] < GH_STATUS_TTL_S:
        return known[1]
    generation = _generation
    version = await _once(("version", generation, path), _read_version)
    if generation == _generation:
        _versions[path] = (time.monotonic(), version)
    return version


async def github_status(*, version: bool = True) -> GithubStatus:
    """The GitHub status check, from a fresh kept answer or one run of ``gh``.

    With *version*, ``gh --version`` is read too, which only the reports need; the checks
    before work leave it out, so they run gh once. A version older than
    :data:`GH_MINIMUM` makes the answer ``gh_too_old`` whatever ``gh auth status`` said.
    """

    status = await _sign_in()
    if not version or status.gh_path is None:
        return status
    found = await _version(status.gh_path)
    if gh_below_minimum(found):
        return _too_old(status.gh_path, found)
    return replace(status, gh_version=found)


async def doctor_status() -> ProviderStatus:
    """The ``github`` section of ``metab --doctor``: the route's answer, and its text."""

    status = await github_status()
    return ProviderStatus(name="github", report=status.to_json(), lines=status.lines())


__all__ = [
    "GH_MINIMUM",
    "GH_MINIMUM_LABEL",
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
    "gh_below_minimum",
    "gh_upgrade_fix",
    "github_status",
    "kept_github_status",
]
