"""The blocks tryscript runs in a transcript, found the way tryscript finds them.

Two checks read ``tests/golden/*.tryscript.md``: ``check_parity.py`` counts a command
as evidence for a route, and ``check_goldens.py`` looks for text that reads as evidence
and never runs. Both are only right if they agree with tryscript about what a block is,
so this module is a transcription of tryscript 0.3.0's own parser
(``findConsoleCodeBlocks``, ``parseTestFile`` and ``parseBlockContent`` in
``node_modules/tryscript/dist/src-*.mjs``), and
``tests/test_tryscript_blocks.py`` holds it to the installed tryscript on the cases
where a looser reading would differ:

- a block opens on a line that is exactly three or more backticks and then ``console``
  or ``bash``, with nothing before the backticks. An indented fence opens nothing;
- it closes on a line of at least as many backticks;
- a block has exactly one ``$`` command; following ``>`` continuations join it;
- non-executable fences are opaque, and malformed executable blocks are refused;
- ``? N`` is the expected exit status, ``! text`` is expected stderr, and every other
  line is expected output;
- a ``skip`` or ``only`` annotation, in any letter case, between the last heading and
  the block applies to it;
- the frontmatter is configuration and holds no block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

_FRONTMATTER: Final = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n")
_HEADING: Final = re.compile(r"^#+\s+(?:Test:\s*)?(.+)$", re.MULTILINE)
_OPEN: Final = re.compile(r"^(`{3,}|~{3,})(.*)$")
_ANNOTATION: Final = re.compile(r"<!--\s*(skip|only)\s*-->", re.IGNORECASE)


class ParseError(ValueError):
    """An executable transcript is malformed and cannot count as evidence."""


@dataclass(frozen=True, slots=True)
class Block:
    """One block tryscript runs."""

    # The line of the opening fence in the file, counted from 1.
    line: int
    command: str
    # Valid transcripts have exactly one `$ ` command prompt.
    dollar_lines: int
    output: tuple[str, ...]
    status: int
    # ``skip`` or ``only`` when tryscript would not run it as an ordinary test.
    annotation: str | None


def split_frontmatter(text: str) -> tuple[str, int]:
    """The transcript without its frontmatter, and how many lines the frontmatter took."""

    match = _FRONTMATTER.match(text)
    if match is None:
        return text, 0
    return text[match.end() :], text[: match.end()].count("\n")


def _annotation(body_before: str) -> str | None:
    headings = list(_HEADING.finditer(body_before))
    if not headings:
        return None
    found = _ANNOTATION.search(body_before[headings[-1].start() :])
    return None if found is None else found.group(1).lower()


def _parse(content: list[str]) -> tuple[str, int, tuple[str, ...], int]:
    command_lines: list[str] = []
    output: list[str] = []
    status = 0
    dollar_lines = 0
    in_command = False
    saw_status = False
    for line in content:
        if line.startswith("$ "):
            if dollar_lines:
                raise ParseError("2 `$` lines in one block; give each command its own block")
            in_command = True
            dollar_lines += 1
            command_lines.append(line[2:])
        elif line.startswith("> ") and in_command:
            command_lines.append(line[2:])
        elif line.startswith("? "):
            in_command = False
            if saw_status or re.fullmatch(r"[0-9]+", line[2:].strip()) is None:
                raise ParseError("expected exit status must be one non-negative integer")
            saw_status = True
            status = int(line[2:].strip())
        elif line == "!" or line.startswith("! "):
            in_command = False
        else:
            in_command = False
            output.append(line)
    if not command_lines:
        raise ParseError("executable block must contain a command prompt")
    command = ""
    for index, line in enumerate(command_lines):
        if line.endswith("\\"):
            command += line[:-1] + " "
        else:
            command += line + (" " if index < len(command_lines) - 1 else "")
    return command.strip(), dollar_lines, tuple(output), status


def _fences(text: str) -> list[tuple[int, int, list[str], str | None]]:
    """Executable fences only; other fenced examples remain opaque."""
    body, offset = split_frontmatter(text)
    lines = [line.removesuffix("\r") for line in body.split("\n")]
    found: list[tuple[int, int, list[str], str | None]] = []
    outside: list[str] = []
    index = 0
    while index < len(lines):
        opened = _OPEN.match(lines[index])
        if opened is None:
            outside.append(lines[index])
            index += 1
            continue
        fence, info = opened.groups()
        executable = fence[0] == "`" and info.strip() in {"console", "bash"}
        closing = re.compile(rf"^{re.escape(fence[0])}{{{len(fence)},}}\s*$")
        start = index
        index += 1
        while index < len(lines) and closing.match(lines[index]) is None:
            index += 1
        if index == len(lines):
            if executable:
                raise ParseError(f"unclosed executable code block at line {start + 1 + offset}")
            break
        if executable:
            found.append(
                (
                    start + 1 + offset,
                    index + 1 + offset,
                    lines[start + 1 : index],
                    _annotation("\n".join(outside)),
                )
            )
        index += 1
    return found


def blocks(text: str) -> list[Block]:
    """Every runnable block, or a refusal when the transcript is malformed."""
    found: list[Block] = []
    for line, _end, content, annotation in _fences(text):
        parsed = _parse(content)
        command, dollar_lines, output, status = parsed
        found.append(Block(line, command, dollar_lines, output, status, annotation))
    return found


def run_lines(text: str) -> set[int]:
    """The file lines, counted from 1, inside executable fences."""
    return {
        number
        for start, end, _content, _annotation in _fences(text)
        for number in range(start, end + 1)
    }
