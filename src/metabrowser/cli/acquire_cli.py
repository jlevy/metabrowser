"""Acquire a classified ``file://`` or ``https://`` source from the CLI without serving it.

``--no-serve`` publishes into the application home and prints logical identity, plus
what a provider web URL pointed at. ``--api /api/cache/…`` acquires as a side effect,
then issues the route against an empty throwaway root so cache inspection cannot expose
origin objects through ``/api/tree``. Non-cache ``--api`` / ``--show`` of a pin is
``git_pin_cli``. ssh stays closed. Acquired content is never served on a listening port.
A first clone reports its phases on a terminal, and a terminal hangup cancels it like
Ctrl-C.
"""

from __future__ import annotations

import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Final

import typer

from metabrowser.cache.acquire import (
    AcquisitionError,
    PhaseReporter,
    PublishedSource,
    acquire_source,
)
from metabrowser.cache.atomic import RecordError
from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError
from metabrowser.cache.locks import LockBusyError
from metabrowser.cache.urls import GitSource
from metabrowser.cli.asgi_client import INDEX_READY_TIMEOUT_S
from metabrowser.cli.common import apply_log_level, maybe_cli_logging
from metabrowser.cli.hangup import run_cancelling_on_hangup
from metabrowser.cli.selection import resolve_and_check_for_cli, selection_lines
from metabrowser.errors import CLIError
from metabrowser.git.process import (
    GIT_ACQUISITION_TIMEOUT_S,
    GitError,
    GitOutputTooLargeError,
    GitTimeoutError,
    GitUnavailableError,
    UnsupportedGitVersionError,
)
from metabrowser.home import ApplicationHomeError, PrivateStorageError, application_home

LOG = logging.getLogger(__name__)

_ACQUIRE_CLI_ERRORS = (
    AcquisitionError,
    ApplicationHomeError,
    FutureLayoutFormatError,
    LayoutError,
    LockBusyError,
    PrivateStorageError,
)
# A record the current contracts refuse is, before v0.12 is released, almost always one
# an earlier development build wrote; those records are not migrated.
_UNREADABLE_RECORD: Final = (
    "the repository cache holds a record this build cannot read, such as one an earlier "
    "v0.12 development build wrote; nothing was published. Move the cache directory aside, "
    "or set METABROWSER_HOME to a different directory"
)


def _git_failure_message(exc: GitError) -> str:
    """A path-free message for *exc*.

    Only the version refusal is written for a user. Every other ``GitError`` message
    carries the argument vector, which names the staging path, or an ``OSError`` text.
    A Git failure always abandons staging before it reaches here, so nothing was
    published.
    """
    if isinstance(exc, UnsupportedGitVersionError):
        return str(exc)
    if isinstance(exc, GitTimeoutError):
        return (
            f"Git did not finish within {GIT_ACQUISITION_TIMEOUT_S:g} s and was stopped; "
            "nothing was published"
        )
    if isinstance(exc, GitOutputTooLargeError):
        return "Git produced more output than acquisition accepts; nothing was published"
    if isinstance(exc, GitUnavailableError):
        return "Git could not be run; check that git is installed and on PATH"
    return (
        "a Git command failed during acquisition; nothing was published "
        "(--log-level debug shows Git's own message)"
    )


def is_cache_inspect_route(route: str) -> bool:
    """Return True when *route* is a read-only ``/api/cache/`` inspection path."""

    path = route.split("?", 1)[0]
    return path.startswith("/api/cache/")


def _is_cache_inspect_route(route: str) -> bool:
    return is_cache_inspect_route(route)


def terminal_phase_reporter(source: GitSource) -> PhaseReporter | None:
    """Report a first clone's phases and elapsed time on stderr, when it is a terminal.

    Like Git's own progress, nothing is written to a pipe or a file, so a captured
    transcript is unchanged by how long a clone took.
    """

    if not sys.stderr.isatty():
        return None
    started = time.monotonic()

    def report(phase: str) -> None:
        elapsed = time.monotonic() - started
        typer.echo(f"cloning {source.normalized}: {phase} ({elapsed:.1f} s)", err=True)

    return report


async def acquire_for_cli(source: GitSource) -> PublishedSource:
    """Publish *source* into ``METABROWSER_HOME``, mapping failures to ``CLIError``.

    Every CLI entry point that acquires goes through here — ``--no-serve``, cache
    ``--api``, and the Git-pin ``--show`` / ``--api`` modes — so none of them lets a
    raw ``GitError`` reach the user with its argument vector or staging path.
    """
    try:
        # The server's handler is not attached yet on these paths, so an explicit
        # ``--log-level`` needs its own, or Git's failure text is never printed.
        with maybe_cli_logging():
            return await acquire_source(
                source, home=application_home(), on_phase=terminal_phase_reporter(source)
            )
    except _ACQUIRE_CLI_ERRORS as exc:
        raise CLIError(str(exc)) from exc
    except RecordError as exc:
        LOG.debug("unreadable cache record %s: %s", exc.path, exc)
        raise CLIError(_UNREADABLE_RECORD) from exc
    except GitError as exc:
        raise CLIError(_git_failure_message(exc)) from exc


def acquire_published_source(source: GitSource) -> PublishedSource:
    """Publish *source* into ``METABROWSER_HOME`` and return the alias."""

    return run_cancelling_on_hangup(acquire_for_cli(source))


def run_no_serve(root: Path | GitSource, *, log_level: str = "") -> None:
    """Acquire a Git source and print its slug, store, revision, and URL selection."""

    apply_log_level(log_level)
    if isinstance(root, Path):
        raise CLIError("ROOT is a local path; --no-serve acquires a file:// or https:// Git source")
    published = acquire_published_source(root)
    typer.echo(f"acquired: {published.source.normalized}")
    typer.echo(f"slug: {published.slug}")
    typer.echo(f"store: {published.store_id}")
    typer.echo(f"revision: {published.default_revision}")
    if root.selection is not None:
        # After the identity lines: the store is published even when the URL's ref is
        # not in it, and the error that follows says so.
        resolved = run_cancelling_on_hangup(resolve_and_check_for_cli(published, root.selection))
        for line in selection_lines(root.selection, resolved):
            typer.echo(line)


def run_api_after_acquire(
    source: GitSource,
    *,
    route: str,
    fmt: str = "json",
    data: Path | None = None,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    untrusted: bool = False,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Acquire *source*, then issue a cache route against an empty ASGI root."""

    if not route.startswith("/api/"):
        raise CLIError(f"route must begin with /api/; got {route}")
    if not _is_cache_inspect_route(route):
        raise CLIError(
            f"{source.transport} Git sources are not served yet "
            f"({source.normalized}). Inspect cache state with --api /api/cache/..."
        )
    apply_log_level(log_level)
    acquire_published_source(source)
    from metabrowser.cli.api_cli import run_api

    with tempfile.TemporaryDirectory() as tmp:
        run_api(
            Path(tmp),
            route=route,
            fmt=fmt,
            data=data,
            plugins_dir=plugins_dir,
            log_level=log_level,
            index_timeout_s=index_timeout_s,
            untrusted=untrusted,
            no_active_content=no_active_content,
            allow_edits=allow_edits,
        )
