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
from pathlib import Path
from types import FrameType
from typing import NoReturn, override

import typer
import uvicorn

from metabrowser.build_version import build_state
from metabrowser.cli.common import apply_log_level, validate_contained_path
from metabrowser.cli.exit_codes import INTERRUPTED_EXIT_CODE
from metabrowser.cli.http_readiness import wait_for_http_ok_then
from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.dotenv import load_dotenv_chain as _load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.server_utils import find_available_local_port, port_search_range
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
    # log-level selection, plugin discovery, or path expansion so values such
    # as HOME affect every bootstrap step consistently with walk mode.
    _load_dotenv_chain()

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

    # Normalize env/CLI plugin directories before the discovery layer first
    # runs at server-module import. This is the same path resolution and
    # validation used by the plugin modes.
    extra_plugin_dirs = resolve_extra_plugin_dirs(plugins_dir)
    os.environ["METABROWSER_PLUGINS_DIRS"] = os.pathsep.join(
        str(plugin_dir) for plugin_dir in extra_plugin_dirs
    )

    selected_path = validate_contained_path(resolved, path) if path else None

    # Server import performs logging setup and plugin discovery. Keep it after
    # dotenv loading, CLI log-level application, and plugin-dir merging so all
    # startup configuration is visible on the first import.
    from metabrowser import server

    try:
        actual_port = find_available_local_port(host, port_search_range(port))
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc

    server._set_root_dir(resolved)

    # A concrete --host is a trusted name the operator chose; permit it at
    # the Host-validation boundary. Wildcard binds accept every interface,
    # so the printed URL, readiness probe, and auto-open use loopback
    # (which the allowlist always permits) instead of an unroutable
    # 0.0.0.0-style name.
    server._register_allowed_host(host)
    display_host = "127.0.0.1" if host in server._WILDCARD_BIND_HOSTS else host

    # Always print a canonical `/view/` URL. The bare origin only redirects
    # there, so emitting it would hand out a second spelling of the root.
    logical_path = ""
    if selected_path is not None:
        logical_path = selected_path.relative_to(resolved).as_posix()
        if selected_path.is_dir() and logical_path:
            logical_path += "/"
    url = f"http://{display_host}:{actual_port}{format_view_href(logical_path)}"

    # A checkout says so here too. This is the line someone reads while
    # deciding which build they are looking at — during a side-by-side
    # comparison it is the only line on screen that can say.
    state = build_state()
    typer.echo(f"Serving {resolved} at {url}" + (f"  [dev build: {state}]" if state else ""))
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
    finally:
        uvicorn_logger.removeFilter(_shutdown_noise_filter)
        uvicorn_logger.setLevel(original_uvicorn_log_level)
