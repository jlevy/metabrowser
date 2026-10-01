"""``devtools/tryscript_blocks.py`` finds the blocks the installed tryscript runs.

The parser is a transcription of tryscript's, and a transcription drifts. So the oracle
here is tryscript itself: ``tests/dom/tryscript-blocks.js`` asks the installed package to
parse each file, and the two must agree on every committed transcript and on the cases
where a looser reading of Markdown would differ.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools import tryscript_blocks
from tests.golden_harness import GOLDEN_DIR, run_session

CASES: dict[str, str] = {
    "console": "```console\n$ metab root\nok\n? 0\n```\n",
    "bash-fence": "```bash\n$ metab root\nok\n```\n",
    "other-fence": "```shell\n$ metab root\n```\n\n```\n$ metab root\n```\n",
    "indented-fence": "  ```console\n  $ metab root\n  ```\n",
    "fence-with-trailing-space": "```console  \n$ metab root\n```  \n",
    "four-backticks": "````console\n$ metab root\n```\nstill output\n? 2\n````\n",
    "unclosed": "```console\n$ metab root\n",
    "no-command": "```console\njust output\n```\n",
    "continuation": "```console\n$ metab root \\\n> --walk\n> --json\nout\n? 1\n```\n",
    "two-dollar-lines": "```console\n$ metab a\n$ metab b\n```\n",
    "continuation-after-output": "```console\n$ metab a\nout\n> not a continuation\n```\n",
    "stderr-line": "```console\n$ metab a\n! warning\nout\n? 3\n```\n",
    "skip": "## A test <!-- skip -->\n\n```console\n$ metab root\n```\n",
    "skip-uppercase": "## A test <!-- SKIP -->\n\n```console\n$ metab root\n```\n",
    "only-mixed-case": "## A test\n\n<!--   Only -->\n\n```console\n$ metab root\n```\n",
    "annotation-under-an-earlier-heading": (
        "## One <!-- skip -->\n\n```console\n$ metab a\n```\n\n"
        "## Two\n\n```console\n$ metab b\n```\n"
    ),
    "frontmatter": (
        "---\nsandbox: true\nbefore: >-\n  metab setup\n---\n# T\n\n```console\n$ metab a\n```\n"
    ),
    "crlf": "```console\r\n$ metab root\r\nout\r\n```\r\n",
}


def _ours(text: str) -> list[dict[str, object]]:
    return [
        {
            "command": block.command,
            "status": block.status,
            "skip": block.annotation == "skip",
            "only": block.annotation == "only",
        }
        for block in tryscript_blocks.blocks(text)
    ]


def test_the_parser_agrees_with_the_installed_tryscript(tmp_path: Path) -> None:
    files: dict[str, str] = {}
    for name, text in CASES.items():
        path = tmp_path / f"{name}.tryscript.md"
        path.write_bytes(text.encode())
        files[str(path)] = text
    for path in sorted(GOLDEN_DIR.glob("*.tryscript.md")):
        files[str(path)] = path.read_bytes().decode()
    theirs = run_session("tryscript-blocks.js", *files)
    assert len(theirs) == len(files) > len(CASES)
    for name, text in files.items():
        assert _ours(text) == theirs[name], name


@pytest.mark.parametrize(
    ("case", "commands"),
    [
        ("console", ["metab root"]),
        ("bash-fence", ["metab root"]),
        ("other-fence", []),
        ("indented-fence", []),
        ("two-dollar-lines", ["metab a metab b"]),
        ("continuation", ["metab root  --walk --json"]),
        ("unclosed", []),
    ],
)
def test_what_counts_as_a_block(case: str, commands: list[str]) -> None:
    """The cases the checks rely on, stated without Node."""

    assert [block.command for block in tryscript_blocks.blocks(CASES[case])] == commands


def test_a_block_knows_its_line_and_its_dollar_lines() -> None:
    (block,) = tryscript_blocks.blocks(CASES["frontmatter"])
    assert (block.line, block.dollar_lines, block.status) == (8, 1, 0)
    (joined,) = tryscript_blocks.blocks(CASES["two-dollar-lines"])
    assert joined.dollar_lines == 2


def test_run_lines_are_the_lines_inside_a_fence_tryscript_opens() -> None:
    text = "intro\n```console\n$ metab a\nout\n```\n\n  ```console\n  $ metab b\n  ```\n"
    assert tryscript_blocks.run_lines(text) == {2, 3, 4, 5}
