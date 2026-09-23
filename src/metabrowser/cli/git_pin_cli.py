"""Open a pinned Git revision for the CLI: in-process inspection or serving.

``file://`` is acquired or reused, then ``open_revision`` pins the default
commit. ``--show`` and ``--api`` attach its ``GitRevisionSubject`` and drive
the same ASGI stack the browser uses without binding a port. Serve mode proves
the pin opens, then hands the server an opener so the application lifespan
opens it again in the serving event loop and closes it at shutdown. Every
mode also hands the server the store as a mirror, so ``/api/source/status``
reports freshness and ``/api/source/refresh`` and ``/api/source/pin`` act on
it; only serve mode refreshes a stale mirror on its own. Every mode runs under
the forced untrusted profile. https and ssh stay closed.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource
from metabrowser.cli.acquire_cli import _ACQUIRE_CLI_ERRORS, acquire_for_cli
from metabrowser.cli.asgi_client import INDEX_READY_TIMEOUT_S
from metabrowser.cli.common import apply_log_level, maybe_cli_logging
from metabrowser.cli.plugin_paths import apply_extra_plugin_dirs
from metabrowser.cli.serve import serve_until_interrupted, stop_on_interrupt
from metabrowser.cli.show_cli import display_git_path
from metabrowser.dotenv import load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.git.process import GitError, GitTimeoutError, GitUnavailableError
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitPath,
    GitPathError,
    GitRevisionSubject,
    ref_short_name,
)
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.source import (
    attach_owned_subject,
    close_owned_subject,
    reset_source_session,
    serve_subject_opener,
)
from metabrowser.view_routes import VIEW_ROUTE_PREFIX

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
    if mode == "check-api":
        raise CLIError(
            f"{source.transport} Git sources are not opened yet "
            f"({source.normalized}). Check a local directory or a file:// source."
        )
    if mode == "show":
        raise CLIError(
            f"{source.transport} Git sources are not opened yet "
            f"({source.normalized}). Show a local directory, or acquire a "
            "file:// source and --show a path on that pin."
        )
    if mode == "serve":
        raise CLIError(
            f"{source.transport} Git sources are not served yet "
            f"({source.normalized}). Serve a file:// source or a local directory; "
            "https and ssh stay closed."
        )
    raise CLIError(
        f"{source.transport} Git sources are not served yet "
        f"({source.normalized}). Inspect cache state with --api /api/cache/..."
    )


def _revision_opener(published: PublishedSource) -> Callable[[], Awaitable[GitRevisionSubject]]:
    """Open the default pin of *published*, labelled with the ref it came from."""

    return functools.partial(
        open_revision,
        home=published.home,
        store_key=published.store_key,
        commit_oid=published.default_revision,
        store_identity=published.store_id,
        ref=published.default_remote_ref,
    )


async def _open_pin(published: PublishedSource) -> GitRevisionSubject:
    """Open the default pin, mapping failures to a path-free ``CLIError``."""

    # Before the server module attaches its handler: see ``acquire_for_cli``.
    with maybe_cli_logging():
        try:
            return await _revision_opener(published)()
        except _PIN_CLI_ERRORS as exc:
            LOG.debug("opening the pinned revision failed: %s", exc)
            raise CLIError(_pin_failure_message(exc)) from exc


@asynccontextmanager
async def _file_pin(source: GitSource) -> AsyncGenerator[PublishedSource]:
    """Serve the default pin in this process for one command, then close it.

    The store is also served as a mirror without a refresh of its own, so a one-shot
    command reaches the network only through an explicit ``POST /api/source/refresh``.
    Whatever pin is served at the end -- the default, or one a ``POST /api/source/pin``
    switched to -- is closed.
    """

    published = await acquire_for_cli(source)
    try:
        attach_owned_subject(await _open_pin(published))
        serve_mirror(StoreMirror.from_published(published))
        yield published
    finally:
        serve_mirror(None)
        await close_owned_subject()
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
        async with _file_pin(source) as published:
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
        async with _file_pin(source) as published:
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


def run_pin_api_check(
    source: GitSource,
    *,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Acquire a ``file://`` source, attach its default pin, and ``--check-api``."""

    _require_file_source(source, mode="check-api")
    _require_untrusted_profile(allow_edits=allow_edits)
    load_dotenv_chain()
    from metabrowser.capabilities import apply_capabilities
    from metabrowser.cli.check_api import arun_api_check_active

    apply_capabilities(untrusted=True, no_active_content=no_active_content, allow_edits=False)
    apply_log_level(log_level)
    apply_extra_plugin_dirs(plugins_dir)

    async def _run() -> None:
        async with _file_pin(source):
            await arun_api_check_active(label=source.normalized, index_timeout_s=index_timeout_s)

    asyncio.run(_run())


@dataclass(frozen=True, slots=True)
class _ServablePin:
    """A published source whose default pin opened, and the selection to launch at."""

    published: PublishedSource
    view_href: str


async def _prove_servable(source: GitSource, *, path: str) -> _ServablePin:
    """Acquire, open the pin once, and resolve ``--path`` in it, then close it.

    The subject is not kept: its batch readers belong to this event loop, and the
    server runs its own. Opening here reports a failure with the same path-free
    message as ``--show`` and ``--api``, before anything is printed or bound.
    """

    published = await acquire_for_cli(source)
    subject = await _open_pin(published)
    try:
        if not path:
            return _ServablePin(published=published, view_href=VIEW_ROUTE_PREFIX)
        try:
            selected = display_git_path(path)
        except GitPathError as exc:
            raise CLIError(f"--path is not a path in this revision: {path}") from exc
        try:
            entry = await subject.tree_source.resolve_path(selected)
        except _PIN_CLI_ERRORS as exc:
            raise CLIError(_pin_failure_message(exc)) from exc
        if entry is None:
            raise CLIError(f"--path target is not in the pinned revision: {path}")
        return _ServablePin(published=published, view_href=_view_href(selected))
    finally:
        await subject.aclose()


def _view_href(path: GitPath) -> str:
    # A wire is `g1-` plus unpadded base64url per segment: nothing in it needs quoting.
    return VIEW_ROUTE_PREFIX + path.to_wire()


def run_serve_pin(
    source: GitSource,
    *,
    path: str = "",
    port: int,
    host: str = "127.0.0.1",
    no_open: bool = False,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Acquire a ``file://`` source and serve its default pin until interrupted.

    The untrusted profile is forced exactly as for ``--show`` and ``--api``:
    ``--untrusted`` is implied, an environment enable is ignored, and
    ``--allow-edits`` is refused. The banner names the source and the pinned
    commit with the ref it was resolved from.
    """

    _require_file_source(source, mode="serve")
    _require_untrusted_profile(allow_edits=allow_edits)
    # Dotenv first, as in filesystem serve mode, so a file-supplied log level
    # reaches the first log line. A dotenv file contributes only its allowlist.
    load_dotenv_chain()
    from metabrowser.capabilities import apply_capabilities

    apply_capabilities(untrusted=True, no_active_content=no_active_content, allow_edits=False)
    apply_log_level(log_level)
    apply_extra_plugin_dirs(plugins_dir)
    # Acquisition reacts to Ctrl-C as it does under --no-serve: staging is
    # abandoned and the command exits 130. Only then does serving take over.
    servable = asyncio.run(_prove_servable(source, path=path))
    stop_on_interrupt()
    published = servable.published
    ref = ref_short_name(published.default_remote_ref)
    revision = published.default_revision + (f" ({ref})" if ref else "")
    serve_until_interrupted(
        served=published.source.normalized,
        view_href=servable.view_href,
        host=host,
        port=port,
        no_open=no_open,
        attach=functools.partial(_serve_published, published),
        banner=(f"Revision: {revision}",),
    )


def _serve_published(published: PublishedSource) -> None:
    """Hand the server the pin to open and the mirror to keep fresh."""

    serve_subject_opener(_revision_opener(published))
    serve_mirror(StoreMirror.from_published(published), refresh_when_stale=True)
