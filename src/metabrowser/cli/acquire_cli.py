"""Acquire a classified ``file://`` source from the CLI without serving it.

``--no-serve`` publishes into the application home and prints logical identity.
``--api /api/cache/…`` acquires as a side effect, then issues the route against an
empty throwaway root so cache inspection cannot expose origin objects through
``/api/tree``. Non-cache ``--api`` / ``--show`` of a ``file://`` pin is
``git_pin_cli``. https and ssh stay closed. Acquired content is never served
on a listening port.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import typer

from metabrowser.cache.acquire import AcquisitionError, PublishedSource, acquire_file_source
from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError
from metabrowser.cache.locks import LockBusyError
from metabrowser.cache.urls import GitSource
from metabrowser.cli.asgi_client import INDEX_READY_TIMEOUT_S
from metabrowser.cli.common import apply_log_level
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

_ACQUIRE_CLI_ERRORS = (
    AcquisitionError,
    ApplicationHomeError,
    FutureLayoutFormatError,
    LayoutError,
    LockBusyError,
    PrivateStorageError,
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


async def acquire_for_cli(source: GitSource) -> PublishedSource:
    """Publish *source* into ``METABROWSER_HOME``, mapping failures to ``CLIError``.

    Every CLI entry point that acquires goes through here — ``--no-serve``, cache
    ``--api``, and the Git-pin ``--show`` / ``--api`` modes — so none of them lets a
    raw ``GitError`` reach the user with its argument vector or staging path.
    """
    try:
        return await acquire_file_source(source, home=application_home())
    except _ACQUIRE_CLI_ERRORS as exc:
        raise CLIError(str(exc)) from exc
    except GitError as exc:
        raise CLIError(_git_failure_message(exc)) from exc


def acquire_published_source(source: GitSource) -> PublishedSource:
    """Publish *source* into ``METABROWSER_HOME`` and return the alias."""

    return asyncio.run(acquire_for_cli(source))


def run_no_serve(root: Path | GitSource, *, log_level: str = "") -> None:
    """Acquire a ``file://`` Git source and print slug, store, and strategy."""

    apply_log_level(log_level)
    if isinstance(root, Path):
        raise CLIError("ROOT is a local path; --no-serve acquires a file:// Git source")
    published = acquire_published_source(root)
    typer.echo(f"acquired: {published.source.normalized}")
    typer.echo(f"slug: {published.slug}")
    typer.echo(f"store: {published.store_id}")
    typer.echo(f"strategy: {published.strategy}")
    typer.echo(f"revision: {published.default_revision}")


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
