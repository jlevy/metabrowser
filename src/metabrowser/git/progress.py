"""Git's progress, read from a child's stderr as numbers and never as text.

``git fetch --progress`` reports where a transfer is on stderr: ``Receiving objects:
45% (43057/95681), 22.78 MiB | 9.02 MiB/s``, ended by a carriage return so a terminal
rewrites one line. Acquisition asks for it because nothing else it observes says how far
a fetch has got: the stall bound is curl's, inside Git's https helper, and this process
sees only the exit.

The stream is untrusted. The lines prefixed ``remote:`` are the origin's own bytes, and
Git's error text names local paths. So a record reaches a caller only as a
:class:`GitProgress`, built from a record that matches the one shape Git prints under
``LC_ALL=C``, and it carries a stage from a fixed list and integers. Everything else,
whatever it contains, stays in the text the runner keeps for its log, exactly as it did
before progress was read. Nothing in this module can be made to hand Git's or an
origin's text to a terminal.

:class:`ProgressSplitter` also keeps progress out of that kept text. A fetch that runs
for minutes writes more progress than the runner keeps of stderr, and the error that
explains a failure comes last.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal

type ProgressStage = Literal[
    "enumerating", "counting", "compressing", "receiving", "unpacking", "resolving", "checking"
]

# The titles a fetch prints (pack-objects on the origin, index-pack, unpack-objects, and
# the connectivity check here), spelled as Git 2.43 to 2.50 spell them under LC_ALL=C.
_STAGES: Final[dict[bytes, ProgressStage]] = {
    b"Enumerating objects": "enumerating",
    b"Counting objects": "counting",
    b"Compressing objects": "compressing",
    b"Receiving objects": "receiving",
    b"Unpacking objects": "unpacking",
    b"Resolving deltas": "resolving",
    b"Checking connectivity": "checking",
}
_UNITS: Final[dict[bytes, int]] = {
    b"byte": 1,
    b"bytes": 1,
    b"KiB": 1024,
    b"MiB": 1024**2,
    b"GiB": 1024**3,
}
# One amount as progress.c humanises it: "220 bytes", "22.78 MiB".
_AMOUNT: Final = rb"(\d{1,10})(?:\.(\d{2}))? (bytes?|KiB|MiB|GiB)"
# One whole record, without its line ending. A counted stage prints "NN% (done/total)"
# and an uncounted one a bare count; a transfer adds its size and rate; the last record
# of a stage adds ", done.". Git pads what the origin sent with up to eight spaces, in
# place of the erase sequence it sends a terminal.
_RECORD: Final = re.compile(
    rb"(remote: )?("
    + b"|".join(re.escape(title) for title in _STAGES)
    + rb"): +(?:\d{1,3}% \((\d{1,20})/(\d{1,20})\)|(\d{1,20}))"
    + rb"(?:, "
    + _AMOUNT
    + rb" \| "
    + _AMOUNT
    + rb"/s)?(, done\.)? {0,8}"
)
# Measured 2026-10-01 on a fetch of github.com/cli/cli with Git 2.50.1: the longest of
# its 255 progress records was 70 bytes with its line ending. A line longer than this
# bound is not progress, and is not held in memory while its end is awaited.
MAX_RECORD_BYTES: Final = 256
_LINE_END: Final = re.compile(rb"[\r\n]")


@dataclass(frozen=True, slots=True)
class GitProgress:
    """One progress record: a stage and how far it has got.

    ``total`` is ``None`` for a stage that counts without knowing its end, and the two
    transfer fields are ``None`` for a stage that moves no bytes. ``remote`` says the
    origin reported it, so a caller knows these numbers are the origin's claim.
    """

    stage: ProgressStage
    done: int
    total: int | None = None
    received_bytes: int | None = None
    bytes_per_second: int | None = None
    finished: bool = False
    remote: bool = False

    @property
    def percent(self) -> int | None:
        """How far through a counted stage, from the counts and within 0 to 100."""

        if not self.total:
            return None
        return max(0, min(100, self.done * 100 // self.total))


def _amount(whole: bytes, hundredths: bytes | None, unit: bytes) -> int:
    return (int(whole) * 100 + int(hundredths or b"0")) * _UNITS[unit] // 100


def parse_progress(record: bytes) -> GitProgress | None:
    """The progress *record* reports, or ``None`` when it is anything else.

    *record* is one line of a Git child's stderr without its line ending.
    """

    if len(record) > MAX_RECORD_BYTES:
        return None
    match = _RECORD.fullmatch(record)
    if match is None:
        return None
    remote, title, done, total, count = match.group(1, 2, 3, 4, 5)
    size, size_hundredths, size_unit = match.group(6, 7, 8)
    rate, rate_hundredths, rate_unit = match.group(9, 10, 11)
    return GitProgress(
        stage=_STAGES[title],
        done=int(count if done is None else done),
        total=None if total is None else int(total),
        received_bytes=None if size is None else _amount(size, size_hundredths, size_unit),
        bytes_per_second=None if rate is None else _amount(rate, rate_hundredths, rate_unit),
        finished=match.group(12) is not None,
        remote=remote is not None,
    )


class ProgressSplitter:
    """Split a Git child's stderr into progress records and the text to keep.

    Feed it the stream as it arrives. A complete line that is a progress record goes to
    *on_progress* and is dropped; every other byte is kept, up to *max_kept* bytes, as
    the capped stderr drain keeps it. A line longer than :data:`MAX_RECORD_BYTES` is
    kept, not parsed, to its end, so its tail cannot pass for a record.
    """

    def __init__(self, on_progress: Callable[[GitProgress], None], max_kept: int) -> None:
        self._on_progress = on_progress
        self._max_kept = max_kept
        self._kept: list[bytes] = []
        self._kept_bytes = 0
        self._pending = b""
        self._in_long_line = False

    def feed(self, chunk: bytes) -> None:
        data = self._pending + chunk
        start = 0
        for end in _LINE_END.finditer(data):
            line = data[start : end.end()]
            start = end.end()
            if self._in_long_line:
                self._in_long_line = False
                self._keep(line)
                continue
            progress = parse_progress(line[:-1])
            if progress is None:
                self._keep(line)
            else:
                self._on_progress(progress)
        self._pending = data[start:]
        if self._in_long_line or len(self._pending) > MAX_RECORD_BYTES:
            self._in_long_line = True
            self._keep(self._pending)
            self._pending = b""

    def finish(self) -> bytes:
        """The kept text, with whatever the stream ended on."""

        self._keep(self._pending)
        self._pending = b""
        return b"".join(self._kept)

    def _keep(self, data: bytes) -> None:
        room = self._max_kept - self._kept_bytes
        if room > 0 and data:
            self._kept.append(data[:room])
            self._kept_bytes += min(len(data), room)


__all__ = ["MAX_RECORD_BYTES", "GitProgress", "ProgressSplitter", "ProgressStage", "parse_progress"]
