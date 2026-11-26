"""Read a Swift source file as code, string literals, and comments, without a compiler.

``devtools/check_app_contract.py`` looks in the macOS app's sources for what the app says
to ``metab``: the flags in its argument lists, the routes it asks for, and the variables
it sets. Each of those is a string literal, and the same words in a comment are prose, so
a search of the whole file would count documentation as code and miss nothing only by
luck. This splits a file into the three, which is as much of Swift's grammar as the check
needs:

- a line comment and a block comment, which nests;
- a string literal, single-line or multi-line, with any number of ``#`` delimiters, whose
  interpolations (``\\( … )``) are read as code, so a literal inside one is found too; and
- an extended regex literal (``#/ … /#``), which may hold ``//`` and quotes.

A bare regex literal (``/ … /``) is not recognized, because telling one from a division
needs the grammar. The app's sources use only the extended form; one that held a quote or
``//`` would read as a string or a comment here, and the check's own tests hold what it
finds in the real sources.
"""

from __future__ import annotations

import functools
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final, Literal

SegmentKind = Literal["code", "string", "comment", "regex"]

_INTERPOLATION: Final = "\N{OBJECT REPLACEMENT CHARACTER}"


@dataclass(frozen=True, slots=True)
class Segment:
    """One run of a source file: its kind, its text, and the line it starts on.

    A string's text is its contents without the quotes, with each interpolation replaced
    by U+FFFC, so that the literal text on either side of one is not read as one word.
    """

    kind: SegmentKind
    text: str
    line: int


class _Lexer:
    def __init__(self, source: str) -> None:
        self.source = source
        self.segments: list[Segment] = []

    def _line(self, index: int) -> int:
        return self.source.count("\n", 0, index) + 1

    def code(self, start: int, closing: str | None) -> int:
        """Read code from *start* to the end, or to the *closing* parenthesis that ends an
        interpolation, and return the index after it."""

        source = self.source
        index = start
        run = start
        depth = 0

        def flush(end: int) -> None:
            if end > run:
                self.segments.append(Segment("code", source[run:end], self._line(run)))

        while index < len(source):
            char = source[index]
            if source.startswith("//", index):
                flush(index)
                end = source.find("\n", index)
                end = len(source) if end < 0 else end
                self.segments.append(Segment("comment", source[index:end], self._line(index)))
                index = run = end
            elif source.startswith("/*", index):
                flush(index)
                index = run = self._block_comment(index)
            elif char == '"' or (char == "#" and self._opens_string(index)):
                flush(index)
                index = run = self._string(index)
            elif char == "#" and self._opens_regex(index):
                flush(index)
                index = run = self._regex(index)
            elif closing and char == "(":
                depth += 1
                index += 1
            elif closing and char == closing:
                if depth == 0:
                    flush(index)
                    return index + 1
                depth -= 1
                index += 1
            else:
                index += 1
        flush(index)
        return index

    def _hashes(self, index: int) -> int:
        count = 0
        while index + count < len(self.source) and self.source[index + count] == "#":
            count += 1
        return count

    def _opens_string(self, index: int) -> bool:
        return self.source.startswith('"', index + self._hashes(index))

    def _opens_regex(self, index: int) -> bool:
        return self.source.startswith("/", index + self._hashes(index))

    def _block_comment(self, start: int) -> int:
        source = self.source
        depth = 0
        index = start
        while index < len(source):
            if source.startswith("/*", index):
                depth += 1
                index += 2
            elif source.startswith("*/", index):
                depth -= 1
                index += 2
                if depth == 0:
                    break
            else:
                index += 1
        self.segments.append(Segment("comment", source[start:index], self._line(start)))
        return index

    def _regex(self, start: int) -> int:
        hashes = self._hashes(start)
        closing = "/" + "#" * hashes
        end = self.source.find(closing, start + hashes + 1)
        end = len(self.source) if end < 0 else end + len(closing)
        self.segments.append(Segment("regex", self.source[start:end], self._line(start)))
        return end

    def _string(self, start: int) -> int:
        source = self.source
        hashes = self._hashes(start)
        index = start + hashes
        quotes = '"""' if source.startswith('"""', index) else '"'
        index += len(quotes)
        closing = quotes + "#" * hashes
        escape = "\\" + "#" * hashes
        text: list[str] = []
        # The string's own segment goes before those of its interpolations.
        slot = len(self.segments)
        self.segments.append(Segment("string", "", self._line(start)))
        while index < len(source):
            if source.startswith(closing, index):
                index += len(closing)
                break
            if source.startswith(escape, index):
                after = index + len(escape)
                if source.startswith("(", after):
                    text.append(_INTERPOLATION)
                    index = self.code(after + 1, ")")
                else:
                    text.append(source[index : after + 1])
                    index = after + 1
                continue
            if quotes == '"' and source[index] == "\n":
                break  # an unterminated literal ends with its line
            text.append(source[index])
            index += 1
        self.segments[slot] = Segment("string", "".join(text), self._line(start))
        return index


@functools.lru_cache(maxsize=512)
def segments(source: str) -> tuple[Segment, ...]:
    """*source* as its code, string literals, comments, and extended regex literals.

    Remembered by its text: the check asks for the code and for the literals of each of
    the app's files several times over, and a file is read a character at a time. Without
    this the check took 0.9 s, nearly all of it here (measured 2026-11-18).
    """

    lexer = _Lexer(source)
    lexer.code(0, None)
    return tuple(lexer.segments)


def strings(source: str) -> Iterator[Segment]:
    """The string literals of *source*, those inside interpolations included."""

    return (segment for segment in segments(source) if segment.kind == "string")


def code(source: str) -> str:
    """*source* with every comment, string literal, and regex literal taken out."""

    return "".join(segment.text for segment in segments(source) if segment.kind == "code")
