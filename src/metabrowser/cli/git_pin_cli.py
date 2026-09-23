"""Attach a pinned Git revision for in-process CLI inspection.

A ``file://`` or ``https://`` source is acquired or reused, the commit its URL selects
is resolved in the mirror (the default branch when the URL selects none, the head for a
pull request, whose record is fetched once when none is cached), and ``open_revision``
pins it; its ``GitRevisionSubject`` becomes the process subject, attached with the
published source so routes can find what the URL selected.
``--show`` and ``--api`` drive the same ASGI stack the browser uses, and what the URL
selected is reported on stderr. Nothing binds a port. ssh stays closed. Serving
acquired Git stays later.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import typer

from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.resolve import ResolvedSelection
from metabrowser.cache.urls import GitSource
from metabrowser.cli.acquire_cli import _ACQUIRE_CLI_ERRORS, acquire_for_cli
from metabrowser.cli.asgi_client import INDEX_READY_TIMEOUT_S
from metabrowser.cli.common import apply_log_level, maybe_cli_logging
from metabrowser.cli.hangup import run_cancelling_on_hangup
from metabrowser.cli.selection import require_selected_path, resolve_for_cli, selection_lines
from metabrowser.errors import CLIError
from metabrowser.git.process import GitError, GitTimeoutError, GitUnavailableError
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitPathError,
    GitRevisionSubject,
)
from metabrowser.source import attach_subject, reset_source_session

LOG = logging.getLogger(__name__)

_PIN_CLI_ERRORS = (
    *_ACQUIRE_CLI_ERRORS,
    GitError,
    GitPathError,
)


def _pin_failure_message(exc: Exception) -> str:
    """A path-free message for a failure after acquisition, while opening the pin.

    Most ``GitError`` messages carry the argument vector or the store's Git
    directory, so only types whose text is path-free by construction pass through.
    """
    if isinstance(exc, GitObjectUnavailableError | GitPathError) or not isinstance(exc, GitError):
        return str(exc)
    if isinstance(exc, GitTimeoutError):
        return "Git did not finish opening the pinned revision in time and was stopped"
    if isinstance(exc, GitUnavailableError):
        return "Git could not open the cached repository store; see --log-level debug"
    return (
        "a Git command failed while opening the pinned revision "
        "(--log-level debug shows Git's own message)"
    )


def _require_untrusted_profile(*, allow_edits: bool) -> None:
    """Acquired content is third-party, so a pin always runs under the untrusted profile.

    Nothing lifts it: ``--untrusted`` is implied, an environment enable is ignored
    because the profile is passed as an explicit flag, and ``--allow-edits`` is
    refused rather than dropped so the operator learns their flag had no effect.
    """
    if allow_edits:
        raise CLIError(
            "--allow-edits is not available on an acquired Git source; "
            "acquired content always runs under the untrusted profile"
        )


def _require_acquired_transport(source: GitSource, *, mode: str) -> None:
    if source.transport in {"file", "https"}:
        return
    if mode == "show":
        raise CLIError(
            f"{source.transport} Git sources are not opened yet "
            f"({source.normalized}). Show a local directory, or --show a path "
            "on a file:// or https:// source."
        )
    raise CLIError(
        f"{source.transport} Git sources are not served yet "
        f"({source.normalized}). Inspect cache state with --api /api/cache/..."
    )


@asynccontextmanager
async def _pin(source: GitSource) -> AsyncGenerator[PublishedSource]:
    published = await acquire_for_cli(source)
    commit = published.default_revision
    report: list[str] = []
    resolved: ResolvedSelection | None = None
    if source.selection is not None:
        resolution = await resolve_for_cli(published, source.selection)
        resolved = resolution.resolved
        commit = resolved.commit
        report = selection_lines(source.selection, resolution)
    subject: GitRevisionSubject | None = None
    try:
        # Before the server module attaches its handler: see ``acquire_for_cli``.
        with maybe_cli_logging():
            try:
                subject = await open_revision(
                    home=published.home,
                    store_key=published.store_key,
                    commit_oid=commit,
                    store_identity=published.store_id,
                )
            except _PIN_CLI_ERRORS as exc:
                LOG.debug("opening the pinned revision failed: %s", exc)
                raise CLIError(_pin_failure_message(exc)) from exc
        if resolved is not None:
            await require_selected_path(subject, published.source.normalized, resolved)
        # stderr, so the route's envelope on stdout stays the only thing a pipe reads.
        for line in report:
            typer.echo(line, err=True)
        attach_subject(subject, published=published)
        yield published
    finally:
        if subject is not None:
            await subject.aclose()
        reset_source_session()


def run_show_after_acquire(
    source: GitSource,
    *,
    path: str,
    fmt: str = "text",
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Acquire a source, attach the pin its URL selects, and ``--show``."""

    _require_acquired_transport(source, mode="show")
    _require_untrusted_profile(allow_edits=allow_edits)
    apply_log_level(log_level)
    from metabrowser.cli.show_cli import ashow_active

    async def _run() -> None:
        async with _pin(source) as published:
            await ashow_active(
                path=path,
                fmt=fmt,
                plugins_dir=plugins_dir,
                log_level=log_level,
                index_timeout_s=index_timeout_s,
                normalize_root=published.git_dir,
                filesystem_root=None,
                untrusted=True,
                no_active_content=no_active_content,
                allow_edits=False,
            )

    run_cancelling_on_hangup(_run())


def run_pin_api(
    source: GitSource,
    *,
    route: str,
    fmt: str = "json",
    data: Path | None = None,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Acquire a source, attach the pin its URL selects, and ``--api``."""

    if not route.startswith("/api/"):
        raise CLIError(f"route must begin with /api/; got {route}")
    _require_acquired_transport(source, mode="api")
    _require_untrusted_profile(allow_edits=allow_edits)
    apply_log_level(log_level)
    from metabrowser.cli.api_cli import aissue_on_active_session

    async def _run() -> None:
        async with _pin(source) as published:
            await aissue_on_active_session(
                route=route,
                fmt=fmt,
                data=data,
                plugins_dir=plugins_dir,
                log_level=log_level,
                index_timeout_s=index_timeout_s,
                normalize_root=published.git_dir,
                untrusted=True,
                no_active_content=no_active_content,
                allow_edits=False,
            )

    run_cancelling_on_hangup(_run())
