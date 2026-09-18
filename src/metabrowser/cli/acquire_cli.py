"""Acquire a classified ``file://`` source from the CLI without serving it.

``--no-serve`` publishes into the application home and prints logical identity.
``--api /api/cache/…`` acquires as a side effect, then issues the route against an
empty throwaway root so ``/api/tree`` cannot expose the cache or the origin.
https and ssh stay closed. Acquired content is never served.
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
from metabrowser.git.process import UnsupportedGitVersionError
from metabrowser.home import ApplicationHomeError, PrivateStorageError, application_home

_ACQUIRE_CLI_ERRORS = (
    AcquisitionError,
    ApplicationHomeError,
    FutureLayoutFormatError,
    LayoutError,
    LockBusyError,
    PrivateStorageError,
    UnsupportedGitVersionError,
)


def _is_cache_inspect_route(route: str) -> bool:
    """Return True when *route* is a read-only ``/api/cache/`` inspection path."""

    path = route.split("?", 1)[0]
    return path.startswith("/api/cache/")


def acquire_published_source(source: GitSource) -> PublishedSource:
    """Publish *source* into ``METABROWSER_HOME`` and return the alias."""

    try:
        return asyncio.run(acquire_file_source(source, home=application_home()))
    except _ACQUIRE_CLI_ERRORS as exc:
        raise CLIError(str(exc)) from exc


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
        )
