"""Open a pinned Git revision for the CLI: in-process inspection or serving.

A ``file://`` or ``https://`` source, or a GitHub web URL, is acquired or reused, the
commit its URL selects is resolved in the mirror (its default branch's commit when it
selects none), and ``open_revision`` pins it. ``--show``, ``--api``, and
``--check-api`` attach its ``GitRevisionSubject`` and drive the same ASGI stack the
browser uses without binding a port, and report the selection on stderr. Serve mode
proves the pin opens, then hands the server an opener so the application lifespan opens
it again in the serving event loop and closes it at shutdown, and opens the browser at
the selected path. Every mode also hands the server the store as a mirror, so
``/api/source/status`` reports freshness and ``/api/source/refresh`` and
``/api/source/pin`` act on it; only serve mode refreshes a stale mirror on its own.

A pull-request URL pins the pull request's head, read from its cached record or, when
there is none, fetched once first; it falls back to the default branch, or a commit
URL's commit, when the pull request cannot be opened. Every mode hands the server the
pull request too, which ``/api/plugin/github/pull`` reads and the mirror's refresh
keeps fresh.

A ref or commit the mirror does not have stops a one-shot mode, which never fetches.
Serve mode serves the default branch instead, fetches once in the background, and
switches to the selection if the fetch brought it; ``/api/source/status`` reports that
as ``selection_state``. Every mode runs under the forced untrusted profile, and a
terminal hangup or ``SIGTERM`` during acquisition cancels it like Ctrl-C. ssh stays
closed.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import typer

from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.providers import served_pull_request_for
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.resolve import ResolvedSelection, UnresolvedSelection
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.cli.acquire_cli import _ACQUIRE_CLI_ERRORS, acquire_for_cli
from metabrowser.cli.asgi_client import INDEX_READY_TIMEOUT_S
from metabrowser.cli.common import apply_log_level, maybe_cli_logging
from metabrowser.cli.hangup import run_cancelling_on_hangup
from metabrowser.cli.plugin_paths import apply_extra_plugin_dirs
from metabrowser.cli.selection import (
    PullOpen,
    open_pull_for_cli,
    pending_selection_opener,
    require_selected_path,
    resolve_in_mirror,
    selection_banner,
    selection_lines,
    selection_view_href,
    unresolved_message,
)
from metabrowser.cli.serve import serve_until_interrupted, stop_on_interrupt
from metabrowser.cli.show_cli import git_wire_candidates
from metabrowser.dotenv import load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.git.process import GitError, GitTimeoutError, GitUnavailableError
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitPathError,
    GitRevisionSubject,
    ref_short_name,
    split_git_container_wire,
)
from metabrowser.mirror_refresh import CompanionRefresh, serve_mirror
from metabrowser.source import (
    SubjectOpenError,
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


def _require_acquired_transport(source: GitSource, *, mode: str) -> None:
    if source.transport in {"file", "https"}:
        return
    if mode == "check-api":
        raise CLIError(
            f"{source.transport} Git sources are not opened yet "
            f"({source.normalized}). Check a local directory or a file:// or https:// source."
        )
    if mode == "show":
        raise CLIError(
            f"{source.transport} Git sources are not opened yet "
            f"({source.normalized}). Show a local directory, or --show a path "
            "on a file:// or https:// source."
        )
    if mode == "serve":
        raise CLIError(
            f"{source.transport} Git sources are not served yet "
            f"({source.normalized}). Serve a file:// or https:// source or a local "
            "directory; ssh stays closed."
        )
    raise CLIError(
        f"{source.transport} Git sources are not served yet "
        f"({source.normalized}). Inspect cache state with --api /api/cache/..."
    )


@dataclass(frozen=True, slots=True)
class _Selected:
    """A published source and the commit its URL selects in the mirror.

    ``resolved`` is ``None`` for a source with no URL selection and for a selection the
    mirror does not have yet (``pending``), when the default branch is served. ``pull``
    is the pull request the URL names, opened or not, and ``companion`` what the server
    keeps fresh for it.
    """

    published: PublishedSource
    commit: str
    ref: str | None
    resolved: ResolvedSelection | None
    pending: bool
    pull: PullOpen | None = None
    companion: CompanionRefresh | None = None

    @property
    def selection(self) -> RepositorySelection | None:
        return self.published.source.selection


async def _select(source: GitSource, *, allow_pending: bool) -> _Selected:
    """Acquire *source*, open the pull request it names, and resolve its selection.

    With *allow_pending*, a ref or commit a fetch could bring is not an error: the
    default branch is selected and ``pending`` is set. A mirror this call just cloned
    was fetched a moment ago, so there a missing selection is not found at once rather
    than waiting on a second fetch.
    """

    published = await acquire_for_cli(source)
    selection = source.selection
    if selection is None or selection.kind == "repository":
        return _Selected(
            published, published.default_revision, published.default_remote_ref, None, False
        )
    pull: PullOpen | None = None
    companion: CompanionRefresh | None = None
    if selection.pull_request is not None:
        pull = await open_pull_for_cli(published, selection.pull_request, fetch="if_missing")
        companion = await served_pull_request_for(published, selection.pull_request)
        head = pull.resolution() if selection.kind == "pull_request" else None
        if head is not None:
            return _Selected(published, head.commit, head.ref, head, False, pull, companion)
    resolution = await resolve_in_mirror(published, selection)
    if isinstance(resolution, UnresolvedSelection):
        if allow_pending and resolution.needs_fetch and not published.fetched:
            return _Selected(
                published,
                published.default_revision,
                published.default_remote_ref,
                None,
                True,
                pull,
                companion,
            )
        message = unresolved_message(published.source.normalized, selection, resolution)
        if pull is not None and pull.unavailable is not None:
            message += f"; {pull.unavailable}"
        raise CLIError(message)
    return _Selected(
        published, resolution.commit, resolution.ref, resolution, False, pull, companion
    )


def _revision_opener(selected: _Selected) -> Callable[[], Awaitable[GitRevisionSubject]]:
    """Open the selected pin, labelled with the ref it came from."""

    published = selected.published
    return functools.partial(
        open_revision,
        home=published.home,
        store_key=published.store_key,
        commit_oid=selected.commit,
        store_identity=published.store_id,
        ref=selected.ref,
    )


def _serving_opener(selected: _Selected) -> Callable[[], Awaitable[GitRevisionSubject]]:
    """The opener the server's lifespan calls, failing with the same path-free message.

    Serve mode has opened the pin once already, but the lifespan reads the store again
    in the serving loop, and it can fail in between: a removed store, a Git timeout.
    That failure reaches the command as :class:`SubjectOpenError`, whose message is
    the one ``--show`` and ``--api`` print; Git's own text is logged at debug and
    kept out of the exception, so no traceback Starlette formats can carry a path.
    """

    opener = _revision_opener(selected)

    async def open_to_serve() -> GitRevisionSubject:
        try:
            return await opener()
        except _PIN_CLI_ERRORS as exc:
            LOG.debug("opening the pinned revision to serve it failed: %s", exc)
            raise SubjectOpenError(_pin_failure_message(exc)) from None

    return open_to_serve


async def _open_pin(selected: _Selected) -> GitRevisionSubject:
    """Open the selected pin and prove its path, mapping failures to ``CLIError``."""

    # Before the server module attaches its handler: see ``acquire_for_cli``.
    with maybe_cli_logging():
        try:
            subject = await _revision_opener(selected)()
        except _PIN_CLI_ERRORS as exc:
            LOG.debug("opening the pinned revision failed: %s", exc)
            raise CLIError(_pin_failure_message(exc)) from exc
    if selected.resolved is not None:
        try:
            await require_selected_path(
                subject, selected.published.source.normalized, selected.resolved
            )
        except BaseException:
            await subject.aclose()
            raise
    return subject


@asynccontextmanager
async def _one_shot_pin(
    source: GitSource, *, refresh_requested: bool = False
) -> AsyncGenerator[PublishedSource]:
    """Serve the selected pin in this process for one command, then close it.

    The store is also served as a mirror without a refresh of its own, so a one-shot
    command reaches the network only through an explicit ``POST /api/source/refresh``.
    Whatever pin is served at the end -- the selected one, or one a
    ``POST /api/source/pin`` switched to -- is closed. The selection is reported on
    stderr, so the route's envelope on stdout stays the only thing a pipe reads.

    With *refresh_requested*, the command's own request is that refresh, so a URL
    selection the mirror lacks waits for it as it would in a server: the default
    branch is served, and the selection once the fetch brings it.
    """

    selected = await _select(source, allow_pending=refresh_requested)
    # One command is one session: nothing a server configured earlier in this process
    # opens a second pin beside this one, and the generation starts at 1.
    reset_source_session()
    try:
        attach_owned_subject(await _open_pin(selected))
        selection = source.selection
        serve_mirror(
            StoreMirror.from_published(selected.published),
            pull_request=selected.pull.number if selected.pull is not None else None,
            pending_selection=(
                pending_selection_opener(selected.published, selection)
                if selected.pending and selection is not None
                else None
            ),
            companion=selected.companion,
        )
        if selection is not None and selected.resolved is not None:
            for line in selection_lines(selection, selected.resolved, pull=selected.pull):
                typer.echo(line, err=True)
        elif selection is not None and selected.pending:
            typer.echo(
                f"selection: {selection.kind} (not in the mirror yet; the refresh fetches it)",
                err=True,
            )
        yield selected.published
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
    """Acquire a source, attach the pin its URL selects, and ``--show``."""

    _require_acquired_transport(source, mode="show")
    _require_untrusted_profile(allow_edits=allow_edits)
    apply_log_level(log_level)
    from metabrowser.cli.show_cli import ashow_active

    async def _run() -> None:
        async with _one_shot_pin(source) as published:
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

    # The one route that fetches, asked with a body: a selection the mirror lacks waits
    # for that refresh instead of failing before it can run.
    refresh_requested = data is not None and route.split("?", 1)[0] == "/api/source/refresh"

    async def _run() -> None:
        async with _one_shot_pin(source, refresh_requested=refresh_requested) as published:
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


def run_pin_api_check(
    source: GitSource,
    *,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Acquire a source, attach the pin its URL selects, and ``--check-api``."""

    _require_acquired_transport(source, mode="check-api")
    _require_untrusted_profile(allow_edits=allow_edits)
    load_dotenv_chain()
    from metabrowser.capabilities import apply_capabilities
    from metabrowser.cli.check_api import arun_api_check_active

    apply_capabilities(untrusted=True, no_active_content=no_active_content, allow_edits=False)
    apply_log_level(log_level)
    apply_extra_plugin_dirs(plugins_dir)

    async def _run() -> None:
        async with _one_shot_pin(source):
            await arun_api_check_active(label=source.normalized, index_timeout_s=index_timeout_s)

    run_cancelling_on_hangup(_run())


@dataclass(frozen=True, slots=True)
class _ServablePin:
    """A selected pin that opened, and the address to launch the browser at."""

    selected: _Selected
    view_href: str


async def _prove_servable(source: GitSource, *, path: str) -> _ServablePin:
    """Acquire, open the selected pin once, and resolve where to open, then close it.

    The subject is not kept: its batch readers belong to this event loop, and the
    server runs its own. Opening here reports a failure with the same path-free
    message as ``--show`` and ``--api``, before anything is printed or bound.
    ``--path`` wins over the URL's own path.
    """

    selected = await _select(source, allow_pending=True)
    subject = await _open_pin(selected)
    try:
        if path:
            view_href = await _selection_href(subject, path)
        elif source.selection is not None and selected.resolved is not None:
            view_href = selection_view_href(source.selection, selected.resolved)
        else:
            view_href = VIEW_ROUTE_PREFIX
        return _ServablePin(selected=selected, view_href=view_href)
    finally:
        await subject.aclose()


async def _selection_href(subject: GitRevisionSubject, path: str) -> str:
    """The canonical `/view/` address of ``--path`` in the pin.

    The spelling is read the way ``--show`` reads it: a display path first, with a
    leading `/` or `./` and a trailing `/` dropped, then a GitPath wire. A directory
    gets a trailing slash, as folder serving prints one. A wire (`g1-` plus unpadded
    base64url per segment) needs no quoting.
    """

    for wire in git_wire_candidates(path, from_route=False):
        git_path, inner = split_git_container_wire(wire)
        if inner:
            continue
        try:
            entry = await subject.tree_source.resolve_path(git_path)
        except _PIN_CLI_ERRORS as exc:
            raise CLIError(_pin_failure_message(exc)) from exc
        if entry is None:
            continue
        slash = "/" if entry.is_tree and git_path.segments else ""
        return VIEW_ROUTE_PREFIX + git_path.to_wire() + slash
    raise CLIError(f"--path target is not in the pinned revision: {path}")


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
    """Acquire a source and serve the pin its URL selects until interrupted.

    The untrusted profile is forced exactly as for ``--show`` and ``--api``:
    ``--untrusted`` is implied, an environment enable is ignored, and
    ``--allow-edits`` is refused. The banner names the source, the pinned commit with
    the ref it was resolved from, and what the URL selected, including a pull request.
    """

    _require_acquired_transport(source, mode="serve")
    _require_untrusted_profile(allow_edits=allow_edits)
    # Dotenv first, as in filesystem serve mode, so a file-supplied log level
    # reaches the first log line. A dotenv file contributes only its allowlist.
    load_dotenv_chain()
    from metabrowser.capabilities import apply_capabilities

    apply_capabilities(untrusted=True, no_active_content=no_active_content, allow_edits=False)
    apply_log_level(log_level)
    apply_extra_plugin_dirs(plugins_dir)
    # Acquisition reacts to Ctrl-C, a hangup, and SIGTERM as it does under --no-serve:
    # staging is abandoned and the command exits. Only then does serving take over.
    servable = run_cancelling_on_hangup(_prove_servable(source, path=path))
    stop_on_interrupt()
    selected = servable.selected
    ref = ref_short_name(selected.ref)
    revision = selected.commit + (f" ({ref})" if ref else "")
    serve_until_interrupted(
        served=selected.published.source.normalized,
        view_href=servable.view_href,
        host=host,
        port=port,
        no_open=no_open,
        attach=functools.partial(_serve_selected, selected),
        banner=(
            f"Revision: {revision}",
            *selection_banner(selected.selection, selected.resolved, pull=selected.pull),
        ),
    )


def _serve_selected(selected: _Selected) -> None:
    """Hand the server the pin to open and the mirror to keep fresh."""

    selection = selected.selection
    serve_subject_opener(_serving_opener(selected))
    serve_mirror(
        StoreMirror.from_published(selected.published),
        serving=True,
        pull_request=selection.pull_request if selection is not None else None,
        pending_selection=(
            pending_selection_opener(selected.published, selection)
            if selected.pending and selection is not None
            else None
        ),
        companion=selected.companion,
    )
