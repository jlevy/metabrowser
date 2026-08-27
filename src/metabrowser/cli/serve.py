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
from typing import override

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


class _QuietForceExitServer(uvicorn.Server):
    """Uvicorn server that exits immediately after a forced interrupt."""

    interrupted: bool = False

    @override
    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        if sig == signal.SIGINT and not self.interrupted:
            self.interrupted = True
            _write_stopping_notice()
        super().handle_exit(sig, frame)
        if self.force_exit:
            os._exit(INTERRUPTED_EXIT_CODE)


def _run_until_interrupted(uvicorn_server: _QuietForceExitServer) -> bool:
    """Serve until the server stops. True when a Ctrl-C stopped it.

    SIGINT is held at ``SIG_IGN`` around the run. Uvicorn's
    ``capture_signals`` saves whichever handler is installed when
    ``Server.run()`` starts, restores it on the way out, and then
    re-raises the signal it captured (uvicorn 0.49). Handing it
    ``SIG_IGN`` to save makes that re-raise a no-op, which settles two
    things:

    * The interrupt is reported by ``Server.interrupted`` rather than by
      a ``KeyboardInterrupt`` raised from inside ``run()``, so serve mode
      picks its own exit code instead of inheriting one.
    * Nothing is left to catch a repeat Ctrl-C during the couple of
      hundred milliseconds between that restore and process exit. With
      the default handler back in place, one arriving there raises
      ``KeyboardInterrupt`` inside ``threading._shutdown`` — measured as
      an "Exception ignored on threading shutdown" traceback, since an
      AnyIO worker thread is non-daemon and gets joined there — or, a
      little later, kills the process outright for exit ``-2`` instead
      of ``130``.

    The previous handler is put back only when serving ended for some
    other reason. After an interrupt the process is milliseconds from
    exiting and a further Ctrl-C has nothing left to interrupt, so
    restoring it there would reopen the window this closes.
    """
    previous = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
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
