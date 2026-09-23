"""Attach a leased Git pin for in-process CLI inspection.

``file://`` is acquired or reused, then ``lease_revision`` plus
``git_revision_subject`` become the process subject. ``--show`` and ``--api``
drive the same ASGI stack the browser uses. Nothing binds a port. https and
ssh stay closed. Serving acquired Git stays later.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.repository_store import RevisionLease, lease_revision
from metabrowser.cache.urls import GitSource
from metabrowser.cli.acquire_cli import _ACQUIRE_CLI_ERRORS, acquire_for_cli
from metabrowser.cli.asgi_client import INDEX_READY_TIMEOUT_S
from metabrowser.cli.common import apply_log_level
from metabrowser.errors import CLIError
from metabrowser.git.process import GitError, GitTimeoutError, GitUnavailableError
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitPathError,
    GitRevisionSubject,
    git_revision_subject,
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


def _require_file_source(source: GitSource, *, mode: str) -> None:
    if source.transport == "file":
        return
    if mode == "show":
        raise CLIError(
            f"{source.transport} Git sources are not opened yet "
            f"({source.normalized}). Show a local directory, or acquire a "
            "file:// source and --show a path on that pin."
        )
    raise CLIError(
        f"{source.transport} Git sources are not served yet "
        f"({source.normalized}). Inspect cache state with --api /api/cache/..."
    )


@asynccontextmanager
async def _leased_file_pin(source: GitSource) -> AsyncGenerator[PublishedSource]:
    published = await acquire_for_cli(source)
    lease: RevisionLease | None = None
    subject: GitRevisionSubject | None = None
    try:
        try:
            lease = await lease_revision(
                home=published.home,
                store_key=published.store_key,
                commit_oid=published.default_revision,
            )
            subject = await git_revision_subject(
                target=lease.target,
                commit_oid=published.default_revision,
                store_identity=published.store_id,
            )
        except _PIN_CLI_ERRORS as exc:
            LOG.debug("opening the pinned revision failed: %s", exc)
            raise CLIError(_pin_failure_message(exc)) from exc
        attach_subject(subject)
        yield published
    finally:
        if subject is not None:
            await subject.aclose()
        if lease is not None:
            lease.release()
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
    """Acquire a ``file://`` source, attach its default pin, and ``--show``."""

    _require_file_source(source, mode="show")
    _require_untrusted_profile(allow_edits=allow_edits)
    apply_log_level(log_level)
    from metabrowser.cli.show_cli import ashow_active

    async def _run() -> None:
        async with _leased_file_pin(source) as published:
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

    asyncio.run(_run())


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
    """Acquire a ``file://`` source, attach its default pin, and ``--api``."""

    if not route.startswith("/api/"):
        raise CLIError(f"route must begin with /api/; got {route}")
    _require_file_source(source, mode="api")
    _require_untrusted_profile(allow_edits=allow_edits)
    apply_log_level(log_level)
    from metabrowser.cli.api_cli import aissue_on_active_session

    async def _run() -> None:
        async with _leased_file_pin(source) as published:
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

    asyncio.run(_run())
