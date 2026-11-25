"""A run of one side's lines: the unchanged lines a diff's hunks leave out.

A comparison's patch carries each hunk with a few lines of context; the unchanged lines
between two hunks, and before the first and after the last, are in the side's content
alone. The diff view asks for them when the reader opens the bar a hunk's separator draws
(``view=lines`` on the comparison route, ``builtin_plugins/diff/sidekick.py``), so a
comparison pays nothing for them until then.

A line is cut as the patch parser cuts one (``adapters/patch_file.py``): at each ``\\n``,
a carriage return kept in it, and decoded as UTF-8 with U+FFFD for a byte that is not, so
a line read here is the context line Git would have written for it.
"""

from __future__ import annotations

from dataclasses import dataclass

# The bytes of line text one answer carries at most. A run stops before the line that
# would pass it, keeping at least one, so a side of very long lines, as a minified file
# is, answers in several asks rather than in one large one. At this repository's mean of
# 40 bytes a line, 1 MiB is 26,000 lines, past what one ask holds (`DIFF_GAP_LINES` in
# settings.py), so only such long lines meet it.
MAX_LINES_ANSWER_BYTES = 1024 * 1024


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
    :data:`MAX_LINES_ANSWER_BYTES` of text. A *start* past the last line answers none."""

    if start < 1 or count < 1:
        raise ValueError("start and count are positive")
    pieces = content.split(b"\n")
    ends_with_newline = content.endswith(b"\n")
    if ends_with_newline or content == b"":
        # The empty piece after the last newline is not a line.
        pieces.pop()
    lines: list[str] = []
    taken = 0
    for raw in pieces[start - 1 : start - 1 + count]:
        if lines and taken + len(raw) > MAX_LINES_ANSWER_BYTES:
            break
        taken += len(raw)
        lines.append(raw.decode("utf-8", "replace"))
    return SideLines(
        start=start,
        lines=tuple(lines),
        line_count=len(pieces),
        ends_with_newline=ends_with_newline,
    )


__all__ = ["MAX_LINES_ANSWER_BYTES", "SideLines", "side_lines"]
