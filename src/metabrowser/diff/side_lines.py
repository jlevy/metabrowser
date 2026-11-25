"""A run of one side's lines: the unchanged lines a diff's hunks leave out.

A comparison's patch carries each hunk with a few lines of context; the unchanged lines
between two hunks, and before the first and after the last, are in the side's content
alone. The diff view asks for them when the reader opens the bar a hunk's separator draws
(``view=lines`` on the comparison route, ``builtin_plugins/diff/sidekick.py``), so a
comparison pays nothing for them until then.

A line is cut as the patch parser cuts one (``adapters/patch_file.py``): at each ``\\n``,
a carriage return kept in it, and decoded as UTF-8 with U+FFFD for a byte that is not, so
a line read here is the context line Git would have written for it.

A run is asked for from its first line (:func:`side_lines`), for a gap the page opens
downward from a hunk, or up to the line before one (:func:`side_lines_before`), for a gap
it opens upward to one; either way an answer cut short by its byte bound keeps the lines
nearest the hunk. Neither makes an object for a line it does not answer: the run's first
line is found by counting newlines (:func:`_line_offset`), so a side of many short lines
costs a scan, not a list of them.
"""

from __future__ import annotations

from dataclasses import dataclass

# The bytes of line text one answer carries at most, so one press of a gap's bar is one
# ask and draws at most this much text. A run stops at the line that would pass it, and the
# page leaves the rest behind the bar's nested step. Measured 2026-11-25 in headless Chrome
# on a Mac at a load average near 230, opening a gap through the production view
# (diff-view.js, `renderGapFold`) with an answer of lines 1 KiB, 16 KiB, and 64 KiB long,
# past the syntax bound and so drawn plain: 512 KiB was drawn 42-74 ms after the click,
# with no task of 50 ms; 1 MiB took 85-149 ms, with a task of 82-84 ms where one batch of
# rows held it all; 2 MiB took 179-186 ms, with a task of 148-182 ms. A run keeps at least
# one line, so a reader is never stuck, and one line past the bound is answered whole, up
# to the side's own bound: a line of 1 MiB was drawn in 98-107 ms, and one of 4 MiB in
# 424-487 ms, each in one task.
MAX_LINES_ANSWER_BYTES = 512 * 1024

# Bytes counted for newlines at a time while finding where a run starts. `bytes.count`
# runs over each chunk at C speed; only the chunk that holds the run's start is walked
# newline by newline, which is at most this many steps. Measured 2026-11-25 on a Mac at a
# load average near 230, a run of 1,000 lines from the middle of a 16 MiB side of 2-byte
# lines took 12-20 ms and held no line it did not answer, where splitting the whole side
# took 70-82 ms and made a line object for each of its 5.6 million lines; of 40-byte
# lines, 10-13 ms against 32-38 ms.
_SEEK_CHUNK_BYTES = 16 * 1024


@dataclass(frozen=True)
class SideLines:
    """Lines *start* onward of one side, 1-based, and how long the side is.

    *line_count* is the side's lines in all, so a page that asked for the lines after the
    last hunk learns where the file ends. *ends_with_newline* says whether its last line
    ends with one, as a patch's ``\\ No newline at end of file`` says it does not.
    """

    start: int
    lines: tuple[str, ...]
    line_count: int
    ends_with_newline: bool


def side_lines(content: bytes, start: int, count: int) -> SideLines:
    """Up to *count* lines of *content* from line *start* (1-based), within
    :data:`MAX_LINES_ANSWER_BYTES` of text, cut short at the far end. A *start* past the
    last line answers none."""

    if start < 1 or count < 1:
        raise ValueError("start and count are positive")
    total = _line_count(content)
    spans = _spans(content, start, min(count, total - start + 1))
    taken = 0
    kept = 0
    for begin, stop in spans:
        if kept and taken + stop - begin > MAX_LINES_ANSWER_BYTES:
            break
        taken += stop - begin
        kept += 1
    return _answer(content, start, spans[:kept], total)


def side_lines_before(content: bytes, end: int, count: int) -> SideLines:
    """Up to *count* lines of *content* before line *end* (1-based), within
    :data:`MAX_LINES_ANSWER_BYTES` of text, cut short at the far end, so the line before
    *end* is always among them. The run stops at the side's last line where *end* is past
    it, and an *end* of 1 answers none, from line 1."""

    if end < 1 or count < 1:
        raise ValueError("end and count are positive")
    total = _line_count(content)
    last = min(end - 1, total)
    first = max(1, end - count)
    spans = _spans(content, first, last - first + 1)
    taken = 0
    kept = 0
    for begin, stop in reversed(spans):
        if kept and taken + stop - begin > MAX_LINES_ANSWER_BYTES:
            break
        taken += stop - begin
        kept += 1
    return _answer(content, last - kept + 1, spans[len(spans) - kept :], total)


def _line_count(content: bytes) -> int:
    """The lines of *content*: one a newline, and one more for a last line with none."""

    return content.count(b"\n") + (1 if content and not content.endswith(b"\n") else 0)


def _line_offset(content: bytes, number: int) -> int:
    """Where line *number* (1-based) starts, just past the newline before it, or the end of
    *content* where it has fewer lines."""

    wanted = number - 1
    position = 0
    size = len(content)
    while wanted > 0 and position < size:
        chunk_end = min(position + _SEEK_CHUNK_BYTES, size)
        found = content.count(b"\n", position, chunk_end)
        if found < wanted:
            wanted -= found
            position = chunk_end
            continue
        while wanted > 0:
            position = content.index(b"\n", position) + 1
            wanted -= 1
    return min(position, size)


def _spans(content: bytes, start: int, count: int) -> list[tuple[int, int]]:
    """Where each of *count* lines from *start* begins and ends in *content*, its newline
    left out, with no line copied."""

    spans: list[tuple[int, int]] = []
    if count < 1:
        return spans
    position = _line_offset(content, start)
    size = len(content)
    while len(spans) < count and position < size:
        newline = content.find(b"\n", position)
        stop = size if newline < 0 else newline
        spans.append((position, stop))
        position = stop + 1
    return spans


def _answer(content: bytes, start: int, spans: list[tuple[int, int]], total: int) -> SideLines:
    return SideLines(
        start=start,
        lines=tuple(content[begin:stop].decode("utf-8", "replace") for begin, stop in spans),
        line_count=total,
        ends_with_newline=content.endswith(b"\n"),
    )


__all__ = ["MAX_LINES_ANSWER_BYTES", "SideLines", "side_lines", "side_lines_before"]
