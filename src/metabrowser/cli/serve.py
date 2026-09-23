"""Serve mode: launch a local web server to browse a directory's files.

This is the default operation of the ``metab`` CLI: ``metab ./path/to/directory``
serves that directory. Argument parsing and mode selection live in
:mod:`metabrowser.cli.main`; this module owns only the serve
implementation.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import threading
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from types import FrameType
from typing import NoReturn, override

import typer
import uvicorn

from metabrowser.build_version import build_state
from metabrowser.cli.common import apply_log_level, validate_contained_path
from metabrowser.cli.exit_codes import INTERRUPTED_EXIT_CODE
from metabrowser.cli.http_readiness import wait_for_http_ok_then
from metabrowser.cli.plugin_paths import apply_extra_plugin_dirs
from metabrowser.dotenv import load_dotenv_chain as _load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.server_utils import find_available_local_port, port_search_range
from metabrowser.source import subject_open_failure
from metabrowser.view_routes import format_view_href


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url, new=2)
    except (webbrowser.Error, OSError) as exc:
        typer.echo(f"Could not auto-open browser ({exc}); visit {url} manually.", err=True)


def _wait_for_http_ok_then_open(
    host: str,
    port: int,
    url: str,
    *,
    timeout_s: float = 10.0,
) -> None:
    """Poll the index route until it serves HTTP OK, then open the URL.

    Polls every 50 ms up to ``timeout_s``. A bare TCP accept is not
    enough: the probe requires a non-error HTTP response from the index
    route, preventing auto-open before uvicorn is ready.
    On timeout or 4xx/5xx, print the URL and leave the browser closed.
    """
    wait_for_http_ok_then(
        host,
        port,
        url,
        on_ready=lambda: _open_browser(url),
        on_error=lambda message: typer.echo(message, err=True),
        timeout_s=timeout_s,
    )


def _shutdown_noise_filter(record: logging.LogRecord) -> bool:
    """Drop Uvicorn's expected cancellation records during local shutdown.

    Serving cancels open SSE streams on Ctrl-C. Uvicorn reports those expected
    cancellations as errors even though no actionable server failure occurred.
    """
    if record.exc_info is not None and isinstance(record.exc_info[1], asyncio.CancelledError):
        return False
    return "timeout graceful shutdown exceeded" not in record.getMessage()


def _subject_open_failure_filter(_record: logging.LogRecord) -> bool:
    """Hold back Uvicorn's report of a served subject that did not open.

    Starlette formats the lifespan's exception into a traceback, and Uvicorn logs
    it and "Application startup failed". The failure already carries a message fit
    to print, which the command reports once the server has stopped, so while it
    stands nothing else from Uvicorn is worth a reader's attention.
    """
    return subject_open_failure() is None


# Acknowledgement for the first Ctrl-C, so the interrupt is visibly
# registered. Without it the terminal shows a bare ``^C`` and nothing
# else while the server takes a couple of hundred milliseconds to stop,
# which reads as a hang and invites a second Ctrl-C.
_STOPPING_NOTICE = b"Stopping Metabrowser.\n"


def _write_stopping_notice() -> None:
    """Announce the interrupt with a raw write to stderr.

    Called from a signal handler, which runs between bytecodes in the
    main thread while it may be part-way through a buffered write of its
    own. ``sys.stderr.write`` would take that same non-reentrant stream
    lock and deadlock; a bare ``os.write`` takes no Python-level lock.
    A closed or full stderr is not worth failing a shutdown over.
    """
    with contextlib.suppress(OSError):
        os.write(2, _STOPPING_NOTICE)


def _stop_now(_sig: int, _frame: FrameType | None) -> NoReturn:
    """Stop the process on the spot, reporting the interrupt exit code.

    This is a local, single-user, read-only file browser. There are no
    in-flight requests whose completion is worth a reader's wait, and
    nothing buffered that a graceful close would flush, so one Ctrl-C ends
    it immediately rather than starting a shutdown the reader then waits
    on. Anything still connected is a browser tab that sees its socket
    close, which is what stopping the server means.
    """
    _write_stopping_notice()
    os._exit(INTERRUPTED_EXIT_CODE)


class _QuietForceExitServer(uvicorn.Server):
    """Uvicorn server that stops on the first interrupt."""

    interrupted: bool = False

    @override
    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        if sig == signal.SIGINT:
            self.interrupted = True
            _stop_now(sig, frame)
        super().handle_exit(sig, frame)


def _run_until_interrupted(uvicorn_server: _QuietForceExitServer) -> bool:
    """Serve until the server stops. True when a Ctrl-C stopped it.

    ``_stop_now`` is installed for the whole run, so one Ctrl-C ends the
    process at any moment in it. Three windows have to be covered, and
    only the middle one is uvicorn's:

    * Before ``capture_signals`` takes effect, uvicorn is still building
      the event loop and starting the app — which includes the inventory
      walk. This window is seconds long on a large tree, and it is the
      one that regressed: holding ``SIG_IGN`` here made a Ctrl-C in it
      vanish, because ``SIG_IGN`` discards a signal rather than deferring
      it. The press left no trace and the server came up and served on.
    * During serving, uvicorn's own handler runs and calls ``handle_exit``
      above, which stops immediately.
    * After ``run()`` returns, ``capture_signals`` restores whatever was
      installed when it started — ours — and re-raises the signal it
      captured (uvicorn 0.49). That re-raise lands on ``_stop_now``, so a
      repeat Ctrl-C arriving in the couple of hundred milliseconds before
      exit stops the process instead of reaching Python's default
      handler, where it used to raise ``KeyboardInterrupt`` inside
      ``threading._shutdown`` — an "Exception ignored on threading
      shutdown" traceback, since an AnyIO worker thread is non-daemon and
      gets joined there — or kill the process outright for exit ``-2``.

    Installing a handler rather than ``SIG_IGN`` covers the first and
    third windows with the same object, so no window is left deaf.
    """
    previous = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _stop_now)
    try:
        uvicorn_server.run()
    finally:
        # This flag is a protocol boolean. Do not treat foreign truthy
        # sentinel values as proof that a signal was observed.
        if uvicorn_server.interrupted is not True:
            signal.signal(signal.SIGINT, previous)
    return uvicorn_server.interrupted is True


def run_serve(
    root: Path,
    *,
    path: str = "",
    port: int,
    host: str = "127.0.0.1",
    no_open: bool = False,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    untrusted: bool = False,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Serve ``root`` (a directory, or a file resolved to parent + selection).

    If ``root`` is a file, automatically split into parent directory plus a
    ``--path`` selection. An explicit ``path`` deep-links a file within the
    root directory.
    """
    # First, before anything that starts a thread or opens a watcher: from here
    # to process exit, one Ctrl-C stops serving.
    #
    # Serving brings up an fsevents watcher and worker threads, and until this
    # handler is in place an interrupt takes the default path — KeyboardInterrupt
    # to the console entry point, which returns 130 and then blocks in
    # interpreter shutdown joining those threads. Measured on a large tree, a
    # press in the first few hundred milliseconds left the process alive and
    # serving. Installing the handler at the top of the mode, rather than around
    # `run()` further down, is what leaves no window where serving has started
    # and the interrupt has nowhere to land.
    signal.signal(signal.SIGINT, _stop_now)

    # Dotenv is operator configuration for the entire command. Apply it before
    # log-level selection so a file-supplied level reaches the first log line,
    # consistently with walk mode. Path expansion no longer depends on it:
    # ``HOME`` is not a name a file may set.
    _load_dotenv_chain()

    from metabrowser.capabilities import apply_capabilities

    apply_capabilities(
        untrusted=untrusted,
        no_active_content=no_active_content,
        allow_edits=allow_edits,
    )

    # Must run before ``from metabrowser import server`` below — the
    # server module configures logging at import time from the env var.
    apply_log_level(log_level)

    # Resolve file-as-ROOT shorthand before server initialization.
    resolved = root.expanduser().resolve()
    if resolved.is_file():
        if path:
            raise typer.BadParameter(
                f"{resolved} is a file — cannot combine with --path. "
                "Use the parent directory as ROOT instead.",
                param_hint="--path",
            )
        path = resolved.name
        resolved = resolved.parent

    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")

    apply_extra_plugin_dirs(plugins_dir)

    selected_path = validate_contained_path(resolved, path) if path else None

    # Always print a canonical `/view/` URL. The bare origin only redirects
    # there, so emitting it would hand out a second spelling of the root.
    logical_path = ""
    if selected_path is not None:
        logical_path = selected_path.relative_to(resolved).as_posix()
        if selected_path.is_dir() and logical_path:
            logical_path += "/"

    def attach_root() -> None:
        from metabrowser import server

        server._set_root_dir(resolved)

    serve_until_interrupted(
        served=str(resolved),
        view_href=format_view_href(logical_path),
        host=host,
        port=port,
        no_open=no_open,
        attach=attach_root,
    )


def stop_on_interrupt() -> None:
    """From here to process exit, one Ctrl-C stops the process; see ``_stop_now``.

    For a mode that does work of its own before serving, such as acquiring a Git
    source, and installs the handler once that work is done.
    """

    signal.signal(signal.SIGINT, _stop_now)


def serve_until_interrupted(
    *,
    served: str,
    view_href: str,
    host: str,
    port: int,
    no_open: bool,
    attach: Callable[[], None],
    banner: Sequence[str] = (),
) -> None:
    """Print the banner and serve until the process is stopped.

    The caller has installed the interrupt handler and applied dotenv, the
    capability block, the log level, and plugin directories. *attach* selects
    what the server serves once its module is loaded; *served* names it in the
    banner, followed by any *banner* lines.
    """

    # Server import performs logging setup and plugin discovery. Keep it after
    # dotenv loading, CLI log-level application, and plugin-dir merging so all
    # startup configuration is visible on the first import.
    from metabrowser import kpress_adapter, server

    # The shell requests these assets on every load. Resolve them before the
    # inventory lifespan starts so a render-blocking request never owns the
    # deferred KPress import while the initial walk is competing for the CPU.
    try:
        kpress_adapter.prepare_browser_assets()
    except (ImportError, kpress_adapter.KPressAssetNotFoundError) as exc:
        raise CLIError(f"KPress cannot provide the browser shell's assets: {exc}") from exc

    try:
        actual_port = find_available_local_port(host, port_search_range(port))
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc

    attach()

    # A concrete --host is a trusted name the operator chose; permit it at
    # the Host-validation boundary. Wildcard binds accept every interface,
    # so the printed URL, readiness probe, and auto-open use loopback
    # (which the allowlist always permits) instead of an unroutable
    # 0.0.0.0-style name.
    server._register_allowed_host(host)
    display_host = "127.0.0.1" if host in server._WILDCARD_BIND_HOSTS else host
    url = f"http://{display_host}:{actual_port}{view_href}"

    # A checkout says so here too. This is the line someone reads while
    # deciding which build they are looking at — during a side-by-side
    # comparison it is the only line on screen that can say.
    state = build_state()
    typer.echo(f"Serving {served} at {url}" + (f"  [dev build: {state}]" if state else ""))
    for line in banner:
        typer.echo(line)
    if server._LOADED_PLUGINS:
        names = ", ".join(p.name for p in server._LOADED_PLUGINS)
        typer.echo(f"Plugins: {names}")

    # Race fix: open the browser only AFTER uvicorn is accepting
    # connections. The poll-then-open helper runs on a daemon thread
    # so uvicorn keeps signal handling in the main thread (Ctrl-C
    # still works).
    if not no_open:
        threading.Thread(
            target=_wait_for_http_ok_then_open,
            args=(display_host, actual_port, url),
            daemon=True,
        ).start()

    # Browser tabs hold open SSE streams, so cancel in-flight local requests rather
    # than waiting indefinitely for graceful shutdown after Ctrl-C.
    uvicorn_logger = logging.getLogger("uvicorn.error")
    original_uvicorn_log_level = uvicorn_logger.level
    uvicorn_logger.addFilter(_shutdown_noise_filter)
    uvicorn_logger.addFilter(_subject_open_failure_filter)
    try:
        uvicorn_server = _QuietForceExitServer(
            uvicorn.Config(
                server.app,
                host=host,
                port=actual_port,
                log_level="warning",
                timeout_graceful_shutdown=0,
            )
        )
        if _run_until_interrupted(uvicorn_server):
            raise typer.Exit(code=INTERRUPTED_EXIT_CODE)
        # Uvicorn returns normally when the application's startup fails, so an
        # unchecked return would report success for a server that never listened.
        if uvicorn_server.started is False:
            failure = subject_open_failure()
            raise CLIError(
                str(failure)
                if failure is not None
                else "the server did not start; the log above says why"
            )
    finally:
        uvicorn_logger.removeFilter(_shutdown_noise_filter)
        uvicorn_logger.removeFilter(_subject_open_failure_filter)
        uvicorn_logger.setLevel(original_uvicorn_log_level)
