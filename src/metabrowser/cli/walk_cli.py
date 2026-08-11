"""Walk mode: run the inventory walker and dump the result, no server.

Selected with ``metab ROOT --walk``. Runs the *same* walker and tree
builder the server uses, with no HTTP server and no browser. The web UI
only renders what these produce, so this is the full walk, analyze, and
build pipeline under test. Argument parsing lives in
:mod:`metabrowser.cli.main`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import typer

from metabrowser.cli.common import apply_log_level, validate_contained_path
from metabrowser.dotenv import load_dotenv_chain as _load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.walk import DETAIL_LEVELS, FORMATS, dump_tree, stream_dump_lines, walk_report


def validate_format(value: str) -> str:
    """Click callback: reject a ``--format`` outside the walker's formats."""
    if value not in FORMATS:
        raise typer.BadParameter(f"must be one of {', '.join(FORMATS)}")
    return value


def validate_detail(value: str) -> str:
    """Click callback: reject a ``--detail`` outside the report levels."""
    if value not in DETAIL_LEVELS:
        raise typer.BadParameter(f"must be one of {', '.join(DETAIL_LEVELS)}")
    return value


def run_walk(
    root: Path,
    *,
    fmt: str = "text",
    stream: bool = False,
    subpath: str = "",
    detail: str = "all",
    max_depth: int,
    max_files: int,
    log_level: str = "",
) -> None:
    """Walk ``root`` with the inventory walker and dump the result."""
    _load_dotenv_chain()
    apply_log_level(log_level)
    with _walk_logging():
        _run_walk(root, fmt, stream, subpath, detail, max_depth, max_files)


def _run_walk(
    root: Path,
    fmt: str,
    stream: bool,
    subpath: str,
    detail: str,
    max_depth: int,
    max_files: int,
) -> None:
    """Execute a validated walk while the command logging scope is active."""

    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")
    if fmt not in FORMATS:
        raise CLIError(f"invalid --format {fmt!r}; expected one of {', '.join(FORMATS)}")
    if subpath and (fmt == "text" or stream):
        raise typer.BadParameter(
            "requires --format json or yaml with --all-at-once",
            param_hint="--path",
        )
    if subpath:
        target = validate_contained_path(resolved, subpath)
        if not target.is_dir():
            raise CLIError(f"--path target is not a directory: {target}")

    if fmt == "text":
        if detail not in DETAIL_LEVELS:
            raise CLIError(
                f"invalid --detail {detail!r}; expected one of {', '.join(DETAIL_LEVELS)}"
            )
        typer.echo(
            walk_report(resolved, detail=detail, max_depth=max_depth, max_files=max_files),
            nl=False,
        )
        return

    if stream:
        # True streaming: print each record as the walker yields it.
        async def _emit() -> None:
            async for line in stream_dump_lines(
                resolved, fmt=fmt, max_depth=max_depth, max_files=max_files
            ):
                typer.echo(line)

        asyncio.run(_emit())
        return

    typer.echo(
        dump_tree(resolved, fmt=fmt, subpath=subpath, max_depth=max_depth, max_files=max_files),
        nl=False,
    )


@contextmanager
def _walk_logging() -> Generator[None]:
    """Scope a stderr handler to one walk invocation.

    Attach the handler at the configured level so ``--walk --log-level debug``
    prints walker traces. Mirrors ``server._setup_perf_logging`` but stays
    lightweight (no server/plugin import). Restore process-global logger state
    so repeated in-process commands never retain a closed standard-error
    stream.
    """

    level_name = os.environ.get("METABROWSER_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger = logging.getLogger("metabrowser")
    previous_level = logger.level
    previous_propagate = logger.propagate
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s | %(message)s", datefmt="%H:%M:%S")
    )
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    try:
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate
