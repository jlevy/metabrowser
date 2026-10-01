"""What a clone says on stderr: where it goes, how far it has got, and that it is done.

The clock is the test's own, so "ten seconds later" is an assignment and nothing here
waits. ``tests/test_acquire_phases.py`` drives the same report from a real Git child.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import io
import os
import re
import threading
from pathlib import Path

import pytest

from metabrowser.cli import clone_report
from metabrowser.cli.clone_report import (
    LOG_INTERVAL_S,
    REDRAW_INTERVAL_S,
    CloneReport,
    cache_directory_display,
    describe_progress,
    format_age,
    format_elapsed,
    format_size,
)
from metabrowser.git.progress import GitProgress

URL = "https://github.com/owner/repo"
WHERE = "~/.metabrowser/cache"
MIB = 1024 * 1024


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class Terminal(io.StringIO):
    """A stream that says it is a terminal and records each write as one frame."""

    def __init__(self) -> None:
        super().__init__()
        self.frames: list[str] = []

    def isatty(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self.frames.append(text)
        return super().write(text)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(clone_report, "_monotonic", clock)
    return clock


def _receiving(done: int, total: int = 100) -> GitProgress:
    return GitProgress("receiving", done, total, done * MIB, MIB)


# ── Without a terminal ──────────────────────────────────────────────


def test_a_log_gets_the_destination_once_a_line_every_interval_and_the_end(clock: Clock) -> None:
    log = io.StringIO()
    report = CloneReport(URL, WHERE, stream=log)
    report.phase("reading the default branch")
    clock.now += 1.5
    report.phase("fetching every object")
    # A record a second for 35 seconds, as a slow transfer writes them.
    for done in range(1, 36):
        clock.now += 1
        report.progress(_receiving(done))
    report.phase("validating")
    report.phase("publishing")
    report.phase("done")
    assert log.getvalue() == (
        f"cloning {URL} into {WHERE}\n"
        f"cloning {URL}: receiving objects: 9%, 9.0 MiB at 1.0 MiB/s (10 s)\n"
        f"cloning {URL}: receiving objects: 19%, 19.0 MiB at 1.0 MiB/s (20 s)\n"
        f"cloning {URL}: receiving objects: 29%, 29.0 MiB at 1.0 MiB/s (30 s)\n"
        f"cloned {URL} in 36 s (35.0 MiB)\n"
    )


def test_a_quick_clone_writes_only_its_two_lines(clock: Clock) -> None:
    log = io.StringIO()
    report = CloneReport(URL, WHERE, stream=log)
    for phase in ("reading the default branch", "fetching every object"):
        report.phase(phase)
    for done in range(1, 101):
        clock.now += (LOG_INTERVAL_S - 1) / 100
        report.progress(_receiving(done))
    for phase in ("validating", "publishing", "done"):
        report.phase(phase)
    assert log.getvalue() == (f"cloning {URL} into {WHERE}\ncloned {URL} in 9.0 s (100.0 MiB)\n")


def test_a_stalled_transfer_still_writes_a_line_every_interval(clock: Clock) -> None:
    """With nothing new from Git, the tick repeats the numbers under a growing time."""

    log = io.StringIO()
    report = CloneReport(URL, WHERE, stream=log)
    report.phase("fetching every object")
    clock.now += 2
    report.progress(_receiving(40))
    for _ in range(25):
        clock.now += 1
        report.tick()
    status = "receiving objects: 40%, 40.0 MiB at 1.0 MiB/s"
    assert log.getvalue() == (
        f"cloning {URL} into {WHERE}\n"
        f"cloning {URL}: {status} (10 s)\n"
        f"cloning {URL}: {status} (20 s)\n"
    )


def test_a_cache_hit_writes_nothing_until_asked(clock: Clock) -> None:
    log = io.StringIO()
    report = CloneReport(URL, WHERE, stream=log)
    clock.now += 60
    report.tick()
    report.close()
    assert log.getvalue() == ""


def test_what_comes_next_ends_the_last_line(clock: Clock) -> None:
    log = io.StringIO()
    report = CloneReport(URL, WHERE, then="starting the server", stream=log)
    report.phase("reading the default branch")
    clock.now += 0.25
    report.phase("done")
    assert log.getvalue().splitlines()[-1] == f"cloned {URL} in 0.2 s; starting the server"


# ── On a terminal ───────────────────────────────────────────────────


def test_a_terminal_rewrites_one_line_and_does_not_flood(clock: Clock) -> None:
    terminal = Terminal()
    report = CloneReport(URL, WHERE, stream=terminal)
    report.phase("reading the default branch")
    report.phase("fetching every object")
    # A thousand records in ten seconds: Git writes one for every percent of every stage.
    for done in range(1, 1001):
        clock.now += 0.01
        report.progress(_receiving(done, 1000))
    report.phase("validating")
    report.phase("done")

    written = terminal.getvalue()
    first, rest = written.split("\n", 1)
    assert first == f"cloning {URL} into {WHERE}"
    status, last = rest.rsplit("\r", 1)
    assert last == f"cloned {URL} in 10 s (1000.0 MiB)\n"
    # Every status is drawn over the one before: a carriage return, never a new line.
    assert "\n" not in status
    redraws = [frame for frame in terminal.frames if frame.startswith("\r")]
    assert redraws[0] == "\rreading the default branch (0.0 s)"
    shape = re.compile(r"\rreceiving objects: \d+%, [\d.]+ MiB at 1\.0 MiB/s \(\d\.\d s\) *")
    assert len([frame for frame in redraws if shape.fullmatch(frame)]) > 50
    # At most one redraw a REDRAW_INTERVAL_S, plus one for each of the three phases
    # and the one that clears the line: a tenth of the records, not all of them.
    assert len(redraws) <= 10 / REDRAW_INTERVAL_S + 4
    assert len(redraws) < 1000 / 5


def test_a_shorter_status_blanks_what_the_longer_one_left(clock: Clock) -> None:
    terminal = Terminal()
    report = CloneReport(URL, WHERE, stream=terminal)
    report.phase("fetching every object")
    clock.now += 1
    report.progress(GitProgress("receiving", 5, 10, 5 * MIB, MIB))
    long = "receiving objects: 50%, 5.0 MiB at 1.0 MiB/s (1.0 s)"
    assert terminal.frames[-1] == "\r" + long
    clock.now += 1
    report.progress(GitProgress("resolving", 1, 10))
    short = "resolving deltas: 10% (2.0 s)"
    assert terminal.frames[-1] == "\r" + short + " " * (len(long) - len(short))
    report.phase("done")
    # The line is cleared before the last one is written over it.
    assert terminal.frames[-2:] == [
        "\r" + " " * len(short) + "\r",
        f"cloned {URL} in 2.0 s (5.0 MiB)\n",
    ]


def test_a_status_wider_than_the_terminal_is_cut_not_wrapped(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(clone_report, "_columns", lambda _stream: 20)
    terminal = Terminal()
    report = CloneReport(URL, WHERE, stream=terminal)
    report.phase("reading the default branch")
    assert terminal.frames[-1] == "\rreading the default"
    assert len(terminal.frames[-1]) - 1 == 19


def test_a_failure_leaves_the_status_and_ends_its_line(clock: Clock) -> None:
    terminal = Terminal()
    report = CloneReport(URL, WHERE, stream=terminal)
    report.phase("fetching every object")
    clock.now += 3
    report.progress(_receiving(40))
    report.close()
    assert terminal.getvalue().endswith("\rreceiving objects: 40%, 40.0 MiB at 1.0 MiB/s (3.0 s)\n")
    # Nothing was drawn before a refusal that came first, so nothing is ended.
    untouched = Terminal()
    CloneReport(URL, WHERE, stream=untouched).close()
    assert untouched.getvalue() == ""


def test_the_tick_keeps_the_time_counting_through_a_phase_without_progress(clock: Clock) -> None:
    terminal = Terminal()
    report = CloneReport(URL, WHERE, stream=terminal)
    report.phase("reading the default branch")
    for _ in range(3):
        clock.now += 1
        report.tick()
    assert [frame for frame in terminal.frames if frame.startswith("\r")] == [
        "\rreading the default branch (0.0 s)",
        "\rreading the default branch (1.0 s)",
        "\rreading the default branch (2.0 s)",
        "\rreading the default branch (3.0 s)",
    ]


def test_ticking_runs_only_while_the_clone_does(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(clone_report, "TICK_S", 0.001)
    terminal = Terminal()
    report = CloneReport(URL, WHERE, stream=terminal)

    async def clone() -> int:
        async with report.ticking():
            report.phase("reading the default branch")
            during = len(terminal.frames)
            while len(terminal.frames) < during + 3:
                clock.now += 1
                await asyncio.sleep(0.001)
            report.phase("done")
        after = len(terminal.frames)
        await asyncio.sleep(0.02)
        return len(terminal.frames) - after

    assert asyncio.run(asyncio.wait_for(clone(), timeout=30)) == 0


# ── A stream that cannot be written ─────────────────────────────────


@pytest.mark.skipif(os.name != "posix", reason="a full pipe is staged with POSIX descriptors")
def test_a_status_that_would_block_is_dropped(clock: Clock) -> None:
    """A pipe nobody reads must not hold up the loop that awaits Git."""

    reader, writer = os.pipe()
    os.set_blocking(writer, False)
    try:
        while True:
            os.write(writer, b"x" * 65536)
    except BlockingIOError as full:
        assert full.errno in {errno.EAGAIN, errno.EWOULDBLOCK}
    os.set_blocking(writer, True)
    stream = os.fdopen(writer, "w", encoding="utf-8")
    report = CloneReport(URL, WHERE, stream=stream)
    # White box: start as a clone that has written its first line, which a full pipe
    # would not have let it write.
    report._cloning = True  # pyright: ignore[reportPrivateUsage]
    clock.now += LOG_INTERVAL_S
    shown = threading.Thread(target=report.progress, args=(_receiving(40),), daemon=True)
    shown.start()
    shown.join(timeout=5)
    returned = not shown.is_alive()
    # Empty the pipe, which unblocks a write that did not return: a failure here
    # fails and does not hang.
    os.set_blocking(reader, False)
    drained = b""
    with contextlib.suppress(BlockingIOError):
        while chunk := os.read(reader, 1 << 20):
            drained += chunk
    shown.join(timeout=5)
    os.close(reader)
    with contextlib.suppress(OSError):
        stream.close()
    assert returned, "a status write blocked on a full pipe"
    assert drained.strip(b"x") == b""


def test_a_closed_stream_does_not_fail_the_clone(clock: Clock) -> None:
    stream = io.StringIO()
    report = CloneReport(URL, WHERE, stream=stream)
    stream.close()
    report.phase("fetching every object")
    clock.now += LOG_INTERVAL_S
    report.progress(_receiving(40))
    report.phase("done")
    report.cache_hit(None)


# ── A cache hit ─────────────────────────────────────────────────────


def test_a_cache_hit_says_where_and_how_old(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clone_report, "canonical_now", lambda: "2026-09-17T15:00:00Z")
    log = io.StringIO()
    report = CloneReport(URL, WHERE, stream=log)
    report.cache_hit("2026-09-17T12:00:00Z")
    report.cache_hit(None)
    report.cache_hit("not a time")
    hit = f"using the clone of {URL} cached in {WHERE}"
    assert log.getvalue() == f"{hit}, fetched 3 hours ago\n{hit}\n{hit}\n"


# ── The words ───────────────────────────────────────────────────────


def test_sizes_times_and_ages_read_as_a_person_says_them() -> None:
    assert [
        format_size(size) for size in (0, 1, 1023, 1024, 1536, MIB, 742 * MIB, 3 * 1024**3)
    ] == [
        "0 bytes",
        "1 byte",
        "1023 bytes",
        "1.0 KiB",
        "1.5 KiB",
        "1.0 MiB",
        "742.0 MiB",
        "3.00 GiB",
    ]
    assert [format_elapsed(seconds) for seconds in (0, 1.26, 9.99, 10, 104.9)] == [
        "0.0 s",
        "1.2 s",
        "9.9 s",
        "10 s",
        "104 s",
    ]
    assert [format_age(age) for age in (-5, 0, 59, 60, 119, 3600, 7200, 47 * 3600, 48 * 3600)] == [
        "less than a minute ago",
        "less than a minute ago",
        "less than a minute ago",
        "1 minute ago",
        "1 minute ago",
        "1 hour ago",
        "2 hours ago",
        "47 hours ago",
        "2 days ago",
    ]


def test_each_stage_is_described_in_fixed_words_and_numbers() -> None:
    assert describe_progress(GitProgress("enumerating", 95681, remote=True)) == (
        "the origin is enumerating objects: 95,681"
    )
    assert describe_progress(GitProgress("compressing", 1, 9, remote=True)) == (
        "the origin is compressing objects: 11%"
    )
    assert describe_progress(GitProgress("receiving", 1, 4)) == "receiving objects: 25%"
    assert describe_progress(GitProgress("receiving", 1, 4, 2048)) == (
        "receiving objects: 25%, 2.0 KiB"
    )
    assert describe_progress(GitProgress("unpacking", 3, 3, 220, 1024, True)) == (
        "unpacking objects: 100%, 220 bytes at 1.0 KiB/s"
    )
    assert describe_progress(GitProgress("checking", 12)) == "checking connectivity: 12"


def test_the_destination_is_the_cache_directory_with_the_home_as_a_tilde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path / "user"))
    assert cache_directory_display(tmp_path / "user" / ".metabrowser") == str(
        Path("~") / ".metabrowser" / "cache"
    )
    # A home elsewhere, as METABROWSER_HOME names one, is shown as it is.
    assert cache_directory_display(tmp_path / "elsewhere") == str(tmp_path / "elsewhere" / "cache")
    # A control character in the path does not reach the terminal.
    assert cache_directory_display(tmp_path / "a\x1b[2Jb") == str(tmp_path / "a�[2Jb" / "cache")
