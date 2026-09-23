"""Run ``gh`` with fixed arguments, an isolated environment, and hard bounds.

``gh`` owns GitHub authentication; Metabrowser never reads, stores, or logs a token.
Every run gets no stdin, prompts and update checks off, no colour, and no inherited
``GH_DEBUG``, ``GH_HOST``, or ``GH_REPO``; a deadline and an output cap; and its own
process group, so a timeout or cancellation kills anything it started. Its stdout is
never logged, because it can be private repository data.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from collections.abc import Sequence
from typing import Final

from metabrowser.git.process import terminate_git_process

log = logging.getLogger(__name__)

# One API read is a few kilobytes and answers in well under a second; these bound a
# hung or runaway gh, not a slow one.
GH_TIMEOUT_S: Final[float] = 15.0
GH_MAX_BYTES: Final[int] = 256 * 1024
_READ_CHUNK_BYTES: Final[int] = 64 * 1024
_STDERR_MAX_BYTES: Final[int] = 16 * 1024
_DROPPED_ENV: Final[tuple[str, ...]] = ("GH_DEBUG", "GH_HOST", "GH_REPO", "GH_PAGER", "DEBUG")


class GhError(Exception):
    """``gh`` could not answer. The message never carries its output."""


class GhUnavailableError(GhError):
    """No ``gh`` executable on ``PATH``."""


def gh_executable() -> str | None:
    """Absolute path of ``gh`` on ``PATH``, or ``None``. Looked up on every call."""

    found = shutil.which("gh")
    return os.path.abspath(found) if found else None


def gh_environment() -> dict[str, str]:
    """The environment every ``gh`` run gets."""

    env = {name: value for name, value in os.environ.items() if name not in _DROPPED_ENV}
    env.update(
        {
            "GH_PROMPT_DISABLED": "1",
            "GH_NO_UPDATE_NOTIFIER": "1",
            "GH_SPINNER_DISABLED": "1",
            "NO_COLOR": "1",
            "CLICOLOR": "0",
        }
    )
    return env


async def _read_capped(stream: asyncio.StreamReader | None, limit: int) -> tuple[bytes, bool]:
    if stream is None:
        return b"", False
    chunks: list[bytes] = []
    total = 0
    overflowed = False
    while chunk := await stream.read(_READ_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            overflowed = True
            continue
        chunks.append(chunk)
    return b"".join(chunks), overflowed


async def run_gh(
    args: Sequence[str], *, timeout_s: float = GH_TIMEOUT_S, max_bytes: int = GH_MAX_BYTES
) -> bytes:
    """Run ``gh`` with *args* and return its stdout, or raise :class:`GhError`."""

    exe = gh_executable()
    if exe is None:
        raise GhUnavailableError("gh is not on PATH")
    try:
        proc = await asyncio.create_subprocess_exec(
            exe,
            *args,
            stdin=subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=gh_environment(),
            start_new_session=os.name == "posix",
        )
    except OSError as exc:
        raise GhError(f"could not run gh: {exc.strerror}") from exc
    stdout_task = asyncio.ensure_future(_read_capped(proc.stdout, max_bytes))
    stderr_task = asyncio.ensure_future(_read_capped(proc.stderr, _STDERR_MAX_BYTES))
    try:
        (stdout, overflowed), (stderr, _), returncode = await asyncio.wait_for(
            asyncio.gather(stdout_task, stderr_task, proc.wait()), timeout=timeout_s
        )
    except TimeoutError:
        stdout_task.cancel()
        stderr_task.cancel()
        await terminate_git_process(proc)
        raise GhError(f"gh did not answer within {timeout_s:g} s") from None
    except asyncio.CancelledError:
        stdout_task.cancel()
        stderr_task.cancel()
        await terminate_git_process(proc)
        raise
    if overflowed:
        raise GhError(f"gh wrote more than {max_bytes} bytes")
    if returncode != 0:
        log.debug("gh %s exited %s: %s", args[0] if args else "", returncode, stderr[:512])
        raise GhError(f"gh exited {returncode}")
    return stdout


__all__ = [
    "GH_MAX_BYTES",
    "GH_TIMEOUT_S",
    "GhError",
    "GhUnavailableError",
    "gh_environment",
    "gh_executable",
    "run_gh",
]
