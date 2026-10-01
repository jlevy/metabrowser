"""The blocks tryscript runs in a transcript, found the way tryscript finds them.

Two checks read ``tests/golden/*.tryscript.md``: ``check_parity.py`` counts a command
as evidence for a route, and ``check_goldens.py`` looks for text that reads as evidence
and never runs. Both are only right if they agree with tryscript about what a block is,
so this module is a transcription of tryscript 0.1.7's own parser
(``findConsoleCodeBlocks``, ``parseTestFile`` and ``parseBlockContent`` in
``node_modules/tryscript/dist/src-*.mjs``), and
``tests/test_tryscript_blocks.py`` holds it to the installed tryscript on the cases
where a looser reading would differ:

- a block opens on a line that is exactly three or more backticks and then ``console``
  or ``bash``, with nothing before the backticks. An indented fence opens nothing;
- it closes on a line of at least as many backticks;
- a block is one command: every ``$`` line, and each ``>`` line directly after one, is
  joined to it with a space;
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
_OPEN: Final = re.compile(r"^(`{3,})(console|bash)\s*$")
_ANNOTATION: Final = re.compile(r"<!--\s*(skip|only)\s*-->", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Block:
    """One block tryscript runs."""

    # The line of the opening fence in the file, counted from 1.
    line: int
    command: str
    # How many lines began `$ `. tryscript joins them all into the one command.
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


def _parse(content: list[str]) -> tuple[str, int, tuple[str, ...], int] | None:
    command_lines: list[str] = []
    output: list[str] = []
    status = 0
    dollar_lines = 0
    in_command = False
    for line in content:
        if line.startswith("$ "):
            in_command = True
            dollar_lines += 1
            command_lines.append(line[2:])
        elif line.startswith("> ") and in_command:
            command_lines.append(line[2:])
        elif line.startswith("? "):
            in_command = False
            digits = re.match(r"\s*(-?\d+)", line[2:])
            status = int(digits.group(1)) if digits is not None else 0
        elif line.startswith("! "):
            in_command = False
        else:
            in_command = False
            output.append(line)
    if not command_lines:
        return None
    command = ""
    for index, line in enumerate(command_lines):
        if line.endswith("\\"):
            command += line[:-1] + " "
        else:
            command += line + (" " if index < len(command_lines) - 1 else "")
    return command.strip(), dollar_lines, tuple(output), status


def blocks(text: str) -> list[Block]:
    """Every block of *text* that tryscript runs, in order."""

    body, offset = split_frontmatter(text)
    lines = [line.removesuffix("\r") for line in body.split("\n")]
    found: list[Block] = []
    index = 0
    while index < len(lines):
        opened = _OPEN.match(lines[index])
        if opened is None:
            index += 1
            continue
        closing = re.compile(rf"^`{{{len(opened.group(1))},}}\s*$")
        start = index
        index += 1
        while index < len(lines):
            if closing.match(lines[index]) is not None:
                parsed = _parse(lines[start + 1 : index])
                if parsed is not None:
                    command, dollar_lines, output, status = parsed
                    found.append(
                        Block(
                            line=start + 1 + offset,
                            command=command,
                            dollar_lines=dollar_lines,
                            output=output,
                            status=status,
                            annotation=_annotation("\n".join(lines[:start])),
                        )
                    )
                index += 1
                break
            index += 1
    return found


def run_lines(text: str) -> set[int]:
    """The file lines, counted from 1, that lie inside a fence tryscript opens."""

    body, offset = split_frontmatter(text)
    lines = [line.removesuffix("\r") for line in body.split("\n")]
    inside: set[int] = set()
    index = 0
    while index < len(lines):
        opened = _OPEN.match(lines[index])
        if opened is None:
            index += 1
            continue
        closing = re.compile(rf"^`{{{len(opened.group(1))},}}\s*$")
        start = index
        index += 1
        while index < len(lines):
            if closing.match(lines[index]) is not None:
                inside.update(range(start + 1 + offset, index + 2 + offset))
                index += 1
                break
            index += 1
    return inside
