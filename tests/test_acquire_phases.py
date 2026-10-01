"""A first clone reports its phases and its progress, and a provider can refuse it first.

The progress is Git's own, read from the fetch's stderr. A stand-in for a slow fetch
shows what a log and a terminal get from it: the fetch's Git first runs a shell fragment
that writes records as a slow transfer would, then fetches for real, so the records
cross the same pipe, the same reader, and the same reporter as Git's. The test's clock
moves a second for each stand-in record, so nothing here waits.
"""

from __future__ import annotations

import asyncio
import io
import os
import signal
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache.acquire import RepositoryTooLargeError, acquire_source
from metabrowser.cache.urls import GitSource, classify_root_argument
from metabrowser.cli import acquire_cli, clone_report
from metabrowser.cli.clone_report import CloneReport
from metabrowser.errors import CLIError
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    GitTimeoutError,
    UnsupportedGitVersionError,
    run_git,
)
from metabrowser.git.progress import GitProgress
from tests.github_origin import github_origin
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]


def _source(tmp_path: Path) -> GitSource:
    source = classify_root_argument(f"file://{github_origin(tmp_path).resolve()}")
    assert isinstance(source, GitSource)
    return source


def test_a_first_clone_reports_each_phase_and_a_hit_reports_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    source = _source(tmp_path)
    phases: list[str] = []
    progress: list[GitProgress] = []
    asyncio.run(
        acquire_source(
            source, home=tmp_path / "home", on_phase=phases.append, on_progress=progress.append
        )
    )
    assert phases == [
        "reading the default branch",
        "fetching every object",
        "validating",
        "publishing",
        "done",
    ]
    # Git's own records of this fetch, as numbers. Which stages a small fetch reports
    # varies with the Git release; the origin always counts what it sends.
    counted = [record for record in progress if record.stage == "counting" and record.finished]
    assert len(counted) == 1 and counted[0].remote
    assert counted[0].done == counted[0].total and counted[0].done > 0
    hit: list[object] = []
    asyncio.run(
        acquire_source(source, home=tmp_path / "home", on_phase=hit.append, on_progress=hit.append)
    )
    assert hit == []


def test_the_fetch_asks_git_for_progress_only_when_it_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--progress`` on a fetch nobody reads would fill the kept stderr with records."""

    _allow_installed_git(monkeypatch)
    source = _source(tmp_path)
    fetches: list[tuple[bool, bool]] = []
    real_run_git = acquire_module.run_git

    async def recording_run_git(args: list[str], **kwargs: Any) -> bytes:
        if "fetch" in args:
            fetches.append(("--progress" in args, kwargs.get("on_progress") is not None))
        else:
            assert "--progress" not in args and kwargs.get("on_progress") is None
        return await real_run_git(args, **kwargs)

    monkeypatch.setattr(acquire_module, "run_git", recording_run_git)
    asyncio.run(acquire_source(source, home=tmp_path / "quiet"))
    asyncio.run(acquire_source(source, home=tmp_path / "read", on_progress=lambda _record: None))
    assert fetches == [(False, False), (True, True)]


# ── A stand-in for a slow or hostile fetch ──────────────────────────

WHERE = "~/.metabrowser/cache"
_SLOW_RECORDS = 35
# A record a "second" for 35 seconds, each a megabyte further on.
_SLOW = (
    f"i=1; while [ $i -le {_SLOW_RECORDS} ]; do "
    f"printf 'Receiving objects: %3d%% (%d/{_SLOW_RECORDS}), %d.00 MiB | 1.00 MiB/s\\r' "
    f"$((i * 100 / {_SLOW_RECORDS})) $i $i >&2; i=$((i + 1)); done"
)
# What an origin, or a Git that is not Git, could write where progress goes: a screen
# clear and a fake prompt, a record carrying a title-setting escape, a one-character
# CSI, a bell, a megabyte-long line whose tail is shaped like a record, and a record
# that claims the impossible.
_HOSTILE = (
    r"printf '\033[2J\033[Hremote: you@host:~$ rm -rf /\n' >&2; "
    r"printf 'Receiving objects:  50%% (1/2)\033]0;owned\007\r' >&2; "
    r"printf '\233[31mResolving deltas:  10%% (1/10)\r' >&2; "
    r"printf 'remote: \007\010\010\010 press return\n' >&2; "
    "head -c 1048576 /dev/zero | tr '\\0' 'A' >&2; "
    r"printf 'Receiving objects:  99%% (99/100)\r' >&2; "
    r"printf 'Receiving objects: 4294967295%% (1/2)\r' >&2"
)
_HOSTILE_MARKS = ("\x1b", "\x9b", "\x07", "\x08", "rm -rf", "owned", "press return", "AAAA", "99%")


def _fetch_after(monkeypatch: pytest.MonkeyPatch, prelude: str, *, then_fetch: bool = True) -> None:
    """Have the fetch's Git run the shell fragment *prelude* on its way to fetching.

    The fragment's stderr is the fetch's stderr. With *then_fetch* false the stand-in
    fails where the fetch would have started.
    """

    real_args = acquire_module.mirror_fetch_args
    after = 'exec git "$@"' if then_fetch else "exit 1"

    def args(remote_url: str, *, prune: bool, progress: bool = False) -> list[str]:
        fetch = real_args(remote_url, prune=prune, progress=progress)
        return ["-c", f"alias.standin=!f() {{ {prelude}; {after}; }}; f", "standin", *fetch]

    monkeypatch.setattr(acquire_module, "mirror_fetch_args", args)


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _Terminal(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.frames: list[str] = []

    def isatty(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self.frames.append(text)
        return super().write(text)


def _clone_slowly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stream: io.StringIO
) -> tuple[str, list[GitProgress]]:
    """Clone through the slow stand-in, reporting to *stream*; the URL and Git's records."""

    _allow_installed_git(monkeypatch)
    _fetch_after(monkeypatch, _SLOW)
    clock = _Clock()
    monkeypatch.setattr(clone_report, "_monotonic", clock)
    source = _source(tmp_path)
    report = CloneReport(source.normalized, WHERE, stream=stream)
    records: list[GitProgress] = []

    def a_second_a_record(record: GitProgress) -> None:
        records.append(record)
        if record.total == _SLOW_RECORDS:
            clock.now += 1
        report.progress(record)

    asyncio.run(
        acquire_source(
            source, home=tmp_path / "home", on_phase=report.phase, on_progress=a_second_a_record
        )
    )
    return source.normalized, records


def test_a_slow_fetch_writes_a_line_every_interval_to_a_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = io.StringIO()
    url, records = _clone_slowly(tmp_path, monkeypatch, log)
    assert len([record for record in records if record.total == _SLOW_RECORDS]) == _SLOW_RECORDS
    assert log.getvalue() == (
        f"cloning {url} into {WHERE}\n"
        f"cloning {url}: receiving objects: 28%, 10.0 MiB at 1.0 MiB/s (10 s)\n"
        f"cloning {url}: receiving objects: 57%, 20.0 MiB at 1.0 MiB/s (20 s)\n"
        f"cloning {url}: receiving objects: 85%, 30.0 MiB at 1.0 MiB/s (30 s)\n"
        f"cloned {url} in 35 s (35.0 MiB)\n"
    )


def test_a_slow_fetch_redraws_one_line_on_a_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    terminal = _Terminal()
    url, records = _clone_slowly(tmp_path, monkeypatch, terminal)
    written = terminal.getvalue()
    first, rest = written.split("\n", 1)
    assert first == f"cloning {url} into {WHERE}"
    status, last = rest.rsplit("\r", 1)
    assert last == f"cloned {url} in 35 s (35.0 MiB)\n"
    # Two lines in all. Every status between them is drawn over the last.
    assert "\n" not in status
    redraws = [frame for frame in terminal.frames if frame.startswith("\r")]
    assert "\rreceiving objects: 57%, 20.0 MiB at 1.0 MiB/s (20 s)" in redraws
    # No more redraws than there was news: a record or a phase each, and the clearing.
    assert _SLOW_RECORDS <= len(redraws) <= len(records) + 5


@pytest.fixture
def cli_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An application home for the CLI's own acquisition, with its clock standing still."""

    _allow_installed_git(monkeypatch)
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    monkeypatch.setattr(clone_report, "_monotonic", float)
    return home


def _acquire_for_cli(
    source: GitSource, stream: io.StringIO, monkeypatch: pytest.MonkeyPatch, **options: Any
) -> None:
    monkeypatch.setattr("sys.stderr", stream)
    asyncio.run(acquire_cli.acquire_for_cli(source, **options))


@pytest.mark.parametrize("stream_type", [io.StringIO, _Terminal], ids=["log", "terminal"])
def test_hostile_progress_from_the_git_child_is_not_passed_through(
    stream_type: Callable[[], io.StringIO],
    tmp_path: Path,
    cli_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fetch_after(monkeypatch, _HOSTILE)
    source = _source(tmp_path)
    stream = stream_type()
    _acquire_for_cli(source, stream, monkeypatch)
    written = stream.getvalue()
    for mark in _HOSTILE_MARKS:
        assert mark not in written, mark
    lines = [line for line in written.replace("\r", "\n").split("\n") if line.strip()]
    assert lines[0] == f"cloning {source.normalized} into {cli_home}/cache"
    assert lines[-1] == f"cloned {source.normalized} in 0.0 s"
    # What is between them, on a terminal, is this module's own words and Git's numbers.
    for line in lines[1:-1]:
        assert line.isascii() and line.isprintable(), repr(line)
        assert len(line) < 80
    if stream_type is io.StringIO:
        assert len(lines) == 2


@pytest.mark.parametrize("stream_type", [io.StringIO, _Terminal], ids=["log", "terminal"])
def test_hostile_text_from_a_failed_fetch_is_in_no_message(
    stream_type: Callable[[], io.StringIO],
    tmp_path: Path,
    cli_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fetch_after(monkeypatch, _HOSTILE, then_fetch=False)
    source = _source(tmp_path)
    stream = stream_type()
    with pytest.raises(CLIError) as refused:
        _acquire_for_cli(source, stream, monkeypatch)
    assert str(refused.value) == "the fetch into staging failed"
    written = stream.getvalue()
    for mark in _HOSTILE_MARKS:
        assert mark not in written, mark
    destination = f"cloning {source.normalized} into {cli_home}/cache\n"
    if stream_type is io.StringIO:
        assert written == destination
    else:
        # The status the clone had reached stays on the terminal, and its line is
        # ended, so the error that follows starts on a line of its own.
        assert written.startswith(destination + "\r")
        *_, last = written.removeprefix(destination).split("\r")
        assert last.endswith("\n") and last.strip() == "fetching every object (0.0 s)"
    staging = cli_home / "cache" / "staging"
    assert list(staging.iterdir()) == []


def test_the_time_keeps_counting_while_git_reports_nothing(
    tmp_path: Path, cli_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fetch that is silent for a while, as a stalled one is: the status is redrawn."""

    monkeypatch.setattr(clone_report, "TICK_S", 0.02)
    monkeypatch.setattr(clone_report, "_monotonic", time.monotonic)
    _fetch_after(monkeypatch, "sleep 1")
    terminal = _Terminal()
    _acquire_for_cli(_source(tmp_path), terminal, monkeypatch)
    waiting = [frame for frame in terminal.frames if frame.startswith("\rfetching every object (")]
    # Drawn when the phase began, then again by the clock alone at least twice in the
    # second Git said nothing, each time with a later time.
    assert len(set(waiting)) >= 3, terminal.frames


def test_a_clone_reports_itself_once_and_a_hit_only_where_asked(
    tmp_path: Path, cli_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path)
    url, where = source.normalized, f"{cli_home}/cache"
    first = io.StringIO()
    _acquire_for_cli(source, first, monkeypatch, announce_hit=True, then="starting the server")
    assert first.getvalue() == (
        f"cloning {url} into {where}\ncloned {url} in 0.0 s; starting the server\n"
    )
    quiet = io.StringIO()
    _acquire_for_cli(source, quiet, monkeypatch)
    assert quiet.getvalue() == ""
    announced = io.StringIO()
    _acquire_for_cli(source, announced, monkeypatch, announce_hit=True, then="starting the server")
    assert announced.getvalue() == (
        f"using the clone of {url} cached in {where}, fetched less than a minute ago\n"
    )


@pytest.mark.skipif(os.name != "posix", reason="signals and process groups are POSIX-only")
def test_progress_neither_extends_the_deadline_nor_outlives_it(tmp_path: Path) -> None:
    """A Git that reports progress for ever is stopped at its deadline, helpers and all."""

    pid_file = tmp_path / "helper.pid"
    forever = (
        f"!sleep 60 & echo $! > '{pid_file}'; "
        "while :; do printf 'Receiving objects:  10%% (1/10)\\r' >&2; sleep 0.05; done"
    )
    seen: list[GitProgress] = []
    started = time.monotonic()
    with pytest.raises(GitTimeoutError):
        asyncio.run(
            run_git(
                ["-c", f"alias.forever={forever}", "forever"],
                cwd=tmp_path,
                policy=ACQUISITION_POLICY,
                timeout_s=2.0,
                on_progress=seen.append,
            )
        )
    assert time.monotonic() - started < 30
    assert seen and all(record == GitProgress("receiving", 1, 10) for record in seen)
    helper = int(pid_file.read_text())
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            os.kill(helper, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        os.kill(helper, signal.SIGKILL)
        pytest.fail("the helper outlived the deadline")


def test_a_provider_refusal_writes_nothing_and_runs_no_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    source = _source(tmp_path)

    async def too_large(checked: GitSource) -> None:
        raise RepositoryTooLargeError(checked.normalized, detail="measured")

    async def no_git(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("a refused first clone runs no Git")

    monkeypatch.setattr(acquire_module, "check_first_clone", too_large)
    monkeypatch.setattr(acquire_module, "_run", no_git)
    home = tmp_path / "home"
    with pytest.raises(RepositoryTooLargeError, match=r"\(too_large\); measured"):
        asyncio.run(acquire_source(source, home=home))
    assert not home.exists()


def test_a_below_floor_git_is_refused_before_any_provider_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def below_floor() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.43.0", "2.43.7")

    async def no_check(_source: GitSource) -> None:
        raise AssertionError("the provider check ran before the Git floor")

    monkeypatch.setattr(acquire_module, "require_acquisition_git", below_floor)
    monkeypatch.setattr(acquire_module, "check_first_clone", no_check)
    source = GitSource(transport="https", form="url", normalized="https://github.com/o/r")
    home = tmp_path / "home"
    with pytest.raises(UnsupportedGitVersionError):
        asyncio.run(acquire_source(source, home=home))
    assert not home.exists()
