"""Git's progress reaches a caller as numbers, and nothing else on stderr reaches it at all.

The records here were written by Git 2.50.1 fetching github.com/cli/cli on 2026-10-01,
with stderr a pipe and ``LC_ALL=C``, as acquisition runs it.
"""

from __future__ import annotations

import pytest

from metabrowser.git.progress import (
    MAX_RECORD_BYTES,
    GitProgress,
    ProgressSplitter,
    parse_progress,
)

MIB = 1024 * 1024


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        (
            b"remote: Enumerating objects: 95681, done.        ",
            GitProgress("enumerating", 95681, finished=True, remote=True),
        ),
        (
            b"remote: Counting objects:   3% (1/33)        ",
            GitProgress("counting", 1, 33, remote=True),
        ),
        (
            b"remote: Compressing objects: 100% (9/9), done.        ",
            GitProgress("compressing", 9, 9, finished=True, remote=True),
        ),
        (b"Receiving objects:   0% (1/95681)", GitProgress("receiving", 1, 95681)),
        (
            b"Receiving objects:  27% (25834/95681), 22.78 MiB | 9.02 MiB/s",
            GitProgress("receiving", 25834, 95681, 2278 * MIB // 100, 902 * MIB // 100),
        ),
        (
            b"Receiving objects: 100% (95681/95681), 79.67 MiB | 13.78 MiB/s, done.",
            GitProgress("receiving", 95681, 95681, 7967 * MIB // 100, 1378 * MIB // 100, True),
        ),
        (
            b"Unpacking objects: 100% (3/3), 220 bytes | 1.00 KiB/s, done.",
            GitProgress("unpacking", 3, 3, 220, 1024, True),
        ),
        (
            b"Receiving objects:  50% (1/2), 1.20 GiB | 1 byte/s",
            GitProgress("receiving", 1, 2, 120 * 1024**3 // 100, 1),
        ),
        (b"Resolving deltas:  79% (52005/65829)", GitProgress("resolving", 52005, 65829)),
        (b"Checking connectivity: 95681, done.", GitProgress("checking", 95681, finished=True)),
    ],
)
def test_a_record_git_writes_is_read_as_numbers(record: bytes, expected: GitProgress) -> None:
    assert parse_progress(record) == expected


def test_percent_comes_from_the_counts_and_stays_within_bounds() -> None:
    assert GitProgress("receiving", 25834, 95681).percent == 27
    assert GitProgress("enumerating", 95681).percent is None
    # The origin's own records are its claim, and a claim cannot be past the end.
    assert parse_progress(b"remote: Counting objects: 999% (7/3)") == GitProgress(
        "counting", 7, 3, remote=True
    )
    assert GitProgress("counting", 7, 3, remote=True).percent == 100
    assert GitProgress("counting", 0, 0).percent is None


@pytest.mark.parametrize(
    "line",
    [
        # What Git writes beside progress: the origin's summary, and errors.
        b"remote: Total 95681 (delta 27), reused 24 (delta 24), pack-reused 95648 (from 2)",
        b"fatal: unable to access 'https://example.com/r.git/': Could not resolve host",
        b"error: RPC failed; curl 28 Operation too slow",
        # A record with anything a terminal would act on.
        b"\x1b[31mReceiving objects:  50% (1/2)",
        b"Receiving objects:  50% (1/2)\x1b[2J",
        b"Receiving objects:  50% (1/2)\x1b]0;title\x07",
        b"Receiving objects:  50% (1/2)\x9b2J",
        b"Receiving objects:  50% (1/2)\x08\x08\x08",
        b"Receiving objects:  50% (1/2)\x00",
        b"Receiving objects:  50% (1/2)\tdone",
        # A title Git does not print, a title with text added, and the wrong shape.
        b"Stealing objects:  50% (1/2)",
        b"remote: remote: Counting objects:  50% (1/2)",
        b"Receiving objects of mine:  50% (1/2)",
        b"Receiving objects:  50% (1/2), rm -rf",
        b"Receiving objects:  50% (1/2), 1.00 MiB | 1.00 MiB/s, done. more",
        b"Receiving objects:  50% (1/2), 1.000 MiB | 1.00 MiB/s",
        b"Receiving objects:  50% (1/2), 1.00 TiB | 1.00 MiB/s",
        b"Receiving objects: 5000% (1/2)",
        b"Receiving objects:  50% (-1/2)",
        b"Receiving objects:  50% (1/" + b"9" * 21 + b")",
        b"Receiving objects:  50%",
        b"Receiving objects: ",
        # More padding than Git writes, before the count or after the record.
        b"Receiving objects:    5% (1/20)",
        b"Receiving objects:  50% (1/2)" + b" " * 9,
        # A stage in the wrong mouth. Git prefixes every line the origin sends, so the
        # origin cannot say what arrived here, and this side does not count for it.
        b"remote: Receiving objects:  99% (99/100), 5.00 GiB | 1.00 GiB/s",
        b"remote: Unpacking objects: 100% (3/3), 5.00 GiB | 1.00 GiB/s, done.",
        b"remote: Resolving deltas:  50% (1/2)",
        b"remote: Checking connectivity: 12, done.",
        b"Enumerating objects: 3, done.",
        b"Counting objects:  50% (1/2)",
        b"Compressing objects:  50% (1/2)",
        # A size on a stage that moves no bytes.
        b"Resolving deltas:  50% (1/2), 1.00 MiB | 1.00 MiB/s",
        b"remote: Counting objects:  50% (1/2), 5.00 GiB | 1.00 GiB/s",
        b"",
        " Receiving objects:  50% (１/2)".encode(),
    ],
)
def test_anything_else_is_not_progress(line: bytes) -> None:
    assert parse_progress(line) is None


def test_no_record_is_as_long_as_the_bound_on_a_line() -> None:
    """The splitter stops holding a line at ``MAX_RECORD_BYTES``; no record is that long."""

    count = b"9" * 20
    amount = b"9999999999.99 bytes"
    longest = (
        b"Unpacking objects:   999% ("
        + count
        + b"/"
        + count
        + b"), "
        + amount
        + b" | "
        + amount
        + b"/s, done."
        + b" " * 8
    )
    assert parse_progress(longest) is not None
    assert len(longest) == 129 < MAX_RECORD_BYTES
    # Each bounded part is at its bound: one more of any is no record.
    for longer in (
        longest.replace(b":   999%", b":    999%"),
        longest.replace(b"999%", b"9999%"),
        longest.replace(b"(" + count, b"(9" + count),
        longest.replace(count + b")", count + b"9)"),
        longest.replace(b", 9999999999.99", b", 99999999999.99"),
        longest + b" ",
    ):
        assert len(longer) == 130
        assert parse_progress(longer) is None


def _split(*chunks: bytes, max_kept: int = 1 << 16) -> tuple[list[GitProgress], bytes]:
    seen: list[GitProgress] = []
    splitter = ProgressSplitter(seen.append, max_kept)
    for chunk in chunks:
        splitter.feed(chunk)
    return seen, splitter.finish()


def test_the_stream_is_split_into_records_and_the_text_to_keep() -> None:
    seen, kept = _split(
        b"remote: Enumerating objects: 3, done.        \n",
        # A record split across two reads, and two records in one read.
        b"Receiving objects:  33% (1/3)\rReceiving obj",
        b"ects:  66% (2/3)\rwarning: something Git said\n",
        b"Receiving objects: 100% (3/3), 220 bytes | 220 bytes/s, done.\n",
        b"fatal: early EOF",
    )
    assert [(record.stage, record.done) for record in seen] == [
        ("enumerating", 3),
        ("receiving", 1),
        ("receiving", 2),
        ("receiving", 3),
    ]
    # Everything that was not a record is kept as written, for the log and for
    # classifying a failure; no record is.
    assert kept == b"warning: something Git said\nfatal: early EOF"


def test_progress_does_not_use_up_the_text_that_is_kept() -> None:
    """A long fetch writes more progress than the cap holds; the error comes last."""

    record = b"Receiving objects:  50% (1/2), 22.78 MiB | 9.02 MiB/s\r"
    cap = 1024
    seen, kept = _split(record * 200, b"fatal: early EOF\n", max_kept=cap)
    assert len(record) * 200 > cap
    assert len(seen) == 200
    assert kept == b"fatal: early EOF\n"


def test_kept_text_is_capped() -> None:
    seen, kept = _split(b"x" * 600 + b"\n", b"y" * 600 + b"\n", max_kept=1000)
    assert seen == []
    assert kept == b"x" * 600 + b"\n" + b"y" * 399


def test_a_hostile_line_reaches_no_reporter() -> None:
    """Escapes, controls, and a long line whose tail looks like a record: all kept, none seen."""

    hostile = (
        b"\x1b[2J\x1b[Hremote: fake prompt $ \n"
        b"Receiving objects:  50% (1/2)\x1b]0;owned\x07\r"
        b"\x9b31mResolving deltas:  10% (1/10)\r"
        + b"A" * (MAX_RECORD_BYTES * 3)
        + b"\rReceiving objects:  99% (99/100)\r"
    )
    # Fed a byte at a time, so no boundary falls where it would help.
    seen, kept = _split(*(hostile[index : index + 1] for index in range(len(hostile))))
    assert [(record.stage, record.done, record.total) for record in seen] == [
        ("receiving", 99, 100)
    ]
    assert kept == hostile.removesuffix(b"Receiving objects:  99% (99/100)\r")


def test_the_tail_of_an_overlong_line_cannot_pass_for_a_record() -> None:
    """Git prefixes every line the origin sends; a long one must not shed its prefix."""

    record = b"Receiving objects:  99% (99/100)\r"
    # Every length of padding, so that wherever the long line is cut, one of them puts
    # the cut exactly where the record-shaped tail begins.
    for padding in range(MAX_RECORD_BYTES * 2, MAX_RECORD_BYTES * 3 + 2):
        line = b"remote: " + b"A" * padding + record
        for size in (1, 7, MAX_RECORD_BYTES, len(line)):
            pieces = [line[index : index + size] for index in range(0, len(line), size)]
            seen, kept = _split(*pieces)
            assert seen == [], (padding, size)
            assert kept == line
    line = b"remote: " + b"A" * (MAX_RECORD_BYTES * 2) + record
    # The line after it is read as usual.
    seen, kept = _split(line, b"Receiving objects:  10% (1/10)\r")
    assert [record.done for record in seen] == [1]
    assert kept == line


def test_an_unfinished_long_line_is_not_held_in_memory() -> None:
    seen: list[GitProgress] = []
    splitter = ProgressSplitter(seen.append, 100)
    for _ in range(1000):
        splitter.feed(b"A" * 1000)
        # Nothing waits for a line ending that a megabyte has not brought.
        assert splitter._pending == b""  # pyright: ignore[reportPrivateUsage]
    assert len(splitter.finish()) == 100
    assert seen == []
