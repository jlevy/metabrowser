"""The commands the agent skill teaches, held to the ``metab`` they run.

``skills/metabrowser/SKILL.md`` is copied into agents' environments and followed as
written, so a renamed flag, a moved route, or a recipe whose output stops parsing fails
there, for someone else, while every check here stays green. A review of the skill on
2026-11-17 found all three. These checks read the skill the way an agent does, every
command in its code blocks and code spans, and hold it to the ``metab`` of the same
commit, the build the skill is written for:

1. **Flags.** Every ``--flag`` of a ``metab`` command, or of a span of flags alone such
   as ``--plugins --json`` or ``<path> --walk``, is an option of the command Typer builds
   from ``metabrowser.cli.main``. Every whole command also passes the checks the CLI
   makes before it does anything, so a flag its mode refuses, as ``--no-serve --format
   json`` is refused, fails here and not with exit status 2 in an agent's shell.
   :func:`mode_refusal` runs the command itself up to its dispatch, so a mode or option
   the CLI gains needs no change here.
2. **Routes.** Every ``/api/`` route the skill names is one ``metab --api /api/routes``
   lists, with the method its command uses: POST for an ``--api`` with ``--data`` or a
   route the text calls ``POST``, and GET for any other ``--api``.
3. **Parseable output.** A ``metab`` command whose output another program reads, piped,
   captured with ``$(…)``, or written to a file, and every ``--api`` command, asks for
   ``--format json`` or ``yaml``, or ``--json`` in a plugin mode, so standard output is
   one document.
4. **Recipes run.** Each recipe under "From a Pull-Request URL", "Publish and Confirm
   It", and "Refresh It After a Push" that reads JSON with ``jq`` is a run of
   consecutive commands of ``tests/golden/cli-skill-recipes.tryscript.md`` joined with
   ``&&``, with the placeholders that transcript names filled in, so the golden runs the
   skill's own text. The refresh beside a checkout cannot run offline there:
   ``tests/test_cli_github_checkout_golden.py`` posts its body, :func:`refresh_body`, and
   :func:`refresh_findings` holds every field its filter reads to the answer that test
   pins.
5. **Names.** A code span of prose that is a field path, such as
   ``.last_refresh.outcome``, or a name with an underscore, such as
   ``not_found_or_private``, names only words of the source under ``src/``: a key, a
   field, or a value the code spells. A word the code also uses elsewhere passes, so
   this catches a misspelling and not a name moved to another meaning.
6. **Presenting.** Each ``--present`` recipe under "Present It in the App" and "When a
   Sandbox Blocks It" is a command of ``tests/golden/cli-present-delivery.txt``, with the
   placeholders
   :data:`PRESENT_SPELLING` names filled in. That transcript runs the production CLI
   with a stand-in LaunchServices and ``open``, never a real app, and runs the skill's
   shape of command for each status the skill tells apart; every field path the
   section's prose names is a key of each report it prints. The section's table lists,
   for each status a delivery code ends with, exactly the codes ``DELIVERY_EXIT_CODES``
   in ``cli/present.py`` maps to it, so a new code fails here until the skill says what
   to do about it, and every other status it restates is the constant behind its row:
   a refusal's, a usage error's, and an ``Error:`` line's. Each rerun outside the
   sandbox carries ``--open-in app``: without it, the default ``auto`` falls back to a
   browser when no app takes the target, and starts a server outside the sandbox.
7. **Guide values.** A one-word code span under "Write a Guided Review" and its
   subsections, such as ``ready`` or ``side``, is a string ``guided_review.py`` spells, a
   state its route answers or a value it compares, or a field of the block's models, so
   a state renamed in prose fails here though check 5 leaves one-word values alone.
8. **The block skeletons.** Each block under "Write the Block", its commit IDs filled
   in, is a guide ``parse_guide`` reads, with a quoted title holding ``: `` and a note
   whose list keeps its lines, the two YAML rules the section states. The first is flat,
   as a short guide is, and the second puts its steps in groups, as a longer one does.

``docs/working-with-agents.md`` repeats the skill's commands for a person, so checks 1,
2, 3, and 5 read it too. Outside every check: the names of query parameters, page
addresses such as ``/pull/<n>/files``, package names, and one-word values such as
``stale`` outside the guided-review sections.

Each check is proven by a mutation of the skill it must fail.
"""

from __future__ import annotations

import ast
import json
import re
import shlex
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

import pytest
import typer
import typer.main

from devtools import tryscript_blocks
from metabrowser.builtin_plugins.github import guided_review
from metabrowser.builtin_plugins.github.guided_review import GuideError, parse_guide
from metabrowser.cli import main as cli_main
from metabrowser.cli.exit_codes import PRESENT_REFUSED_EXIT_CODE
from metabrowser.cli.present import DELIVERY_EXIT_CODES
from metabrowser.errors import CLIError
from tests.golden_harness import run_metab

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
SKILL: Final = REPO_ROOT / "skills" / "metabrowser" / "SKILL.md"
GUIDE: Final = REPO_ROOT / "docs" / "working-with-agents.md"
GOLDEN: Final = REPO_ROOT / "tests" / "golden" / "cli-skill-recipes.tryscript.md"
# What `tests/test_cli_github_checkout_golden.py` pins for the checkout's refresh: the
# transcript of the bodies it posts, and the answer to the one that asks for a comparison.
CHECKOUT_GOLDEN: Final = REPO_ROOT / "tests" / "golden" / "cli-github-checkout.txt"
CHECKOUT_ANSWERS: Final = (
    REPO_ROOT / "tests" / "fixtures" / "github-checkout-comparison-responses.json"
)
# The pull request that test refreshes with a comparison.
CHECKOUT_PULL: Final = 10

# The words that run ``metab`` in the skill; ``<invocation>`` is the local command or
# ``uvx metabrowser@latest``, and a ``uvx`` line runs it after the package.
PROGRAMS: Final = frozenset({"metab", "metabrowser", "<invocation>"})
# Words a shell reads before the program of a command.
_KEYWORDS: Final = frozenset({"if", "then", "else", "elif", "do", "while", "until", "!", "time"})
_ASSIGNMENT: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_SEPARATORS: Final = frozenset({"|", "||", "&&", ";", ";;", "&", "(", ")"})
# A redirection, and not a placeholder such as `<path>` or `<file>.patch`.
_REDIRECT: Final = re.compile(r"^\d*(?:>>?|<)(?![^<>]*>)")
# A redirection of standard output to a file, which the next command then reads.
_TO_FILE: Final = re.compile(r"^1?>>?(?![^<>]*>)")
_FLAG: Final = re.compile(r"^--[A-Za-z]")
_ROUTE: Final = re.compile(r"/api/[^\s`'\"?),]+")
_POSTED: Final = re.compile(r"\bPOST (/api/[^\s`'\"?),]+)")
_SPAN: Final = re.compile(r"`([^`]+)`")
_HEADING: Final = re.compile(r"^#{2,6} (.+)$")
# A fence opens a block at any indentation, under a list item too, with backticks or
# tildes; the block ends at a line of the same character at least as long.
_FENCE: Final = re.compile(r"^\s*(`{3,}|~{3,})")
# A line that the next one continues: a backslash, or an operator that needs more.
_CONTINUED: Final = re.compile(r"(?:\\|\||&&)\s*$")
_FORMATS: Final = frozenset({"json", "yaml"})
_PLUGIN_MODES: Final = frozenset({"--plugins", "--plugin", "--doctor"})
# A field path such as `.last_refresh.outcome`, or a name such as `not_cached`.
_NAME: Final = re.compile(r"\.?[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*")

# The sections whose recipes the golden runs, and how it spells their placeholders.
GOLDEN_SECTION: Final = "From a Pull-Request URL"
GUIDE_CONFIRM_SECTION: Final = "Publish and Confirm It"
GUIDE_REFRESH_SECTION: Final = "Refresh It After a Push"
GOLDEN_SECTIONS: Final = (GOLDEN_SECTION, GUIDE_CONFIRM_SECTION, GUIDE_REFRESH_SECTION)
GOLDEN_SPELLING: Final = {
    "<invocation>": (
        "METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab"
    ),
    "<url>": "https://github.com/octo/demo/pull/7",
    "<n>": "7",
    "<k>": "1",
    "<path>": "src/app.txt",
    "<tmp>": "tmp",
}

# The section on writing a guided review and its subsections, whose one-word code spans
# check 7 holds to the guided-review module, and the subsection with the block skeletons.
GUIDE_SECTIONS: Final = frozenset(
    {"Write a Guided Review", "Write the Block", GUIDE_CONFIRM_SECTION, GUIDE_REFRESH_SECTION}
)
SKELETON_SECTION: Final = "Write the Block"
# A skeleton is the guide's own Markdown inside a four-backtick `markdown` fence, as the
# format reference shows it, so the `guided-review` fence is part of what an agent copies.
# The section has two, a flat guide and one in groups, in that order.
_SKELETON: Final = re.compile(r"^````markdown\n(.*?)^````$", re.MULTILINE | re.DOTALL)
# Full commit IDs for a skeleton's placeholders, which a pin must be.
SKELETON_SPELLING: Final = {
    "<full merge-base commit ID>": "1" * 40,
    "<full head commit ID>": "2" * 40,
}
_WORD: Final = re.compile(r"[a-z][a-z0-9_]*")
# The section of the refresh a checkout's folder server needs before it reads a pull
# request; its `"comparison": true` acquires a store from GitHub, so the golden cannot
# run it, and `tests/test_cli_github_checkout_golden.py` posts its body instead.
REFRESH_SECTION: Final = "Beside a Checkout"
REFRESH_ROUTE: Final = "/api/plugin/github/pull-refresh"

# The section of the `--present` recipes, the transcript that runs them against a
# stand-in app, and how that transcript spells their placeholders.
PRESENT_SECTION: Final = "Present It in the App"
# The section of the rerun outside the sandbox, whose recipes the transcript runs too.
RERUN_SECTION: Final = "When a Sandbox Blocks It"
PRESENT_GOLDEN: Final = REPO_ROOT / "tests" / "golden" / "cli-present-delivery.txt"
PRESENT_SPELLING: Final = {
    "<invocation>": "metab",
    "<target>": "notes",
    "<root>": "notes",
    "<relative-path>": "docs/guide.md",
}
# The shape of every recipe: `--present` first, and the report as JSON.
PRESENT_PREFIX: Final = "metab --present "
PRESENT_SUFFIX: Final = " --format json"
# A block of an in-process transcript (`tests/golden_harness.block`): its command line,
# its status, and its standard output.
_TRANSCRIPT_BLOCK: Final = re.compile(
    r"^# ([^\n]+)\nexit: (\d+)\n--- stdout ---\n(.*?)--- stderr ---\n", re.MULTILINE | re.DOTALL
)
# A row of the section's table: its status, and the cell of codes after it.
_STATUS_ROW: Final = re.compile(r"^\| (\d+) \| ([^|]*) \|")
_CODE: Final = re.compile(r"`([a-z_]+)`")
# What the code cell of a row without a delivery code says it is, and the status the code
# ends such a command with.
_MARKED_STATUSES: Final = {
    "a refusal": PRESENT_REFUSED_EXIT_CODE,
    "a usage error": typer.BadParameter("").exit_code,
    "an `error:` line": CLIError("").exit_code,
}


@dataclass(frozen=True, slots=True)
class Code:
    """One piece of code in the skill: a logical line of a block, or a span of prose."""

    line: int
    text: str
    block: bool
    section: str


@dataclass(frozen=True, slots=True)
class Command:
    """The arguments of one ``metab`` invocation the skill writes."""

    where: str
    args: tuple[str, ...]
    # A whole command line, as opposed to a span of flags alone such as `--plugins --json`.
    whole: bool
    # Its standard output is piped to another command, captured with `$(…)`, or written
    # to a file.
    read: bool


# ── Reading the skill ───────────────────────────────────────────────


def _body(text: str) -> tuple[list[str], int]:
    """The lines after the frontmatter, and how many lines the frontmatter took."""

    lines = text.split("\n")
    if lines and lines[0] == "---":
        end = lines.index("---", 1)
        return lines[end + 1 :], end + 1
    return lines, 0


def _depth(text: str) -> int:
    """How many parentheses *text* leaves open; 1 while a quote is still open."""

    try:
        tokens = _tokens(text)
    except ValueError:
        return 1
    return tokens.count("(") - tokens.count(")")


def _closes(line: str, fence: str) -> bool:
    """Whether *line* ends the block that *fence* opened."""

    closing = line.strip()
    return len(closing) >= len(fence) and set(closing) == {fence[0]}


def code_pieces(text: str) -> list[Code]:
    """Every logical line of a fenced block, and every code span of the prose."""

    lines, offset = _body(text)
    pieces: list[Code] = []
    section = ""
    fence: str | None = None
    pending: list[str] = []
    pending_line = 0
    paragraph: list[tuple[int, str]] = []

    def spans() -> None:
        joined = "\n".join(line for _number, line in paragraph)
        for match in _SPAN.finditer(joined):
            number = paragraph[0][0] + joined.count("\n", 0, match.start())
            pieces.append(Code(number, " ".join(match.group(1).split()), False, section))
        paragraph.clear()

    for index, line in enumerate(lines):
        number = index + 1 + offset
        if fence is not None:
            if _closes(line, fence):
                fence = None
                continue
            if not pending:
                pending_line = number
            pending.append(line)
            logical = " ".join(part.strip().removesuffix("\\") for part in pending)
            if not _CONTINUED.search(line) and _depth(logical) <= 0:
                pieces.append(Code(pending_line, " ".join(logical.split()), True, section))
                pending.clear()
            continue
        opened = _FENCE.match(line)
        if opened is not None:
            spans()
            fence = opened.group(1)
            continue
        heading = _HEADING.match(line)
        if heading is not None:
            spans()
            section = heading.group(1).strip()
            continue
        if not line.strip():
            spans()
        else:
            paragraph.append((number, line))
    spans()
    return pieces


def _tokens(text: str) -> list[str]:
    """Shell words and operators, with a redirection such as ``2>&1`` as one word."""

    lexer = shlex.shlex(
        re.sub(r"\d*>&\d+", " __redirect__ ", text), posix=True, punctuation_chars="|&;()"
    )
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _segments(tokens: list[str]) -> Iterator[tuple[list[str], bool]]:
    """Each simple command of *tokens*, and whether another command reads its output."""

    words: list[str] = []
    captured = False
    for index, token in enumerate(tokens):
        if token in _SEPARATORS:
            if words:
                yield words, captured or token == "|"
            words = []
            captured = token == "(" and index > 0 and tokens[index - 1].endswith("$")
            continue
        words.append(token)
    if words:
        yield words, captured


def _metab_args(words: list[str]) -> list[str] | None:
    """The arguments *words* pass to ``metab``, or ``None`` when they run something else."""

    rest = list(words)
    while rest and (_ASSIGNMENT.match(rest[0]) or rest[0] in _KEYWORDS):
        rest = rest[1:]
    if not rest:
        return None
    if rest[0] == "uvx":
        package = next((i for i, word in enumerate(rest) if word.startswith("metabrowser")), None)
        return None if package is None else rest[package + 1 :]
    return rest[1:] if rest[0] in PROGRAMS else None


def _without_redirects(args: list[str]) -> tuple[str, ...]:
    kept: list[str] = []
    skip = False
    for word in args:
        if skip:
            skip = False
        elif word == "__redirect__":
            pass
        elif _REDIRECT.match(word):
            skip = _REDIRECT.sub("", word) == ""
        else:
            kept.append(word)
    return tuple(kept)


def commands(text: str, name: str = "SKILL.md") -> list[Command]:
    """Every ``metab`` invocation in *text*, whole or as a span of flags."""

    found: list[Command] = []
    for piece in code_pieces(text):
        where = f"{name}:{piece.line}"
        try:
            tokens = _tokens(piece.text)
        except ValueError:
            continue
        # A span that starts with a flag or a placeholder, such as `--plugins --json` or
        # `<path> --walk`, names flags of a command the prose describes.
        first = tokens[0] if tokens else ""
        names_flags = _FLAG.match(first) is not None or first.startswith("<")
        if not piece.block and names_flags and first not in PROGRAMS:
            found.append(Command(where, tuple(tokens), whole=False, read=False))
            continue
        for words, read in _segments(tokens):
            args = _metab_args(words)
            if args is not None:
                written = any(_TO_FILE.match(word) for word in args)
                found.append(
                    Command(where, _without_redirects(args), whole=True, read=read or written)
                )
    return found


def _value(args: tuple[str, ...], option: str) -> str | None:
    if option not in args:
        return None
    index = args.index(option)
    return args[index + 1] if index + 1 < len(args) else None


def _recipes(text: str) -> list[Code]:
    """The recipes of :data:`GOLDEN_SECTIONS` that read JSON with ``jq``."""

    return [
        piece
        for piece in code_pieces(text)
        if piece.block and piece.section in GOLDEN_SECTIONS and "jq" in _tokens(piece.text)
    ]


def refresh_recipe(text: str) -> tuple[str, str]:
    """The body the checkout's refresh recipe posts, ``<n>`` and all, and its ``jq`` filter."""

    recipes = [
        piece
        for piece in code_pieces(text)
        if piece.block and piece.section == REFRESH_SECTION and REFRESH_ROUTE in piece.text
    ]
    assert len(recipes) == 1, f"SKILL.md has {len(recipes)} recipes of {REFRESH_ROUTE}"
    tokens = _tokens(recipes[0].text)
    assert "echo" in tokens and "jq" in tokens, f"the recipe has no body or filter: {tokens}"
    body = tokens[tokens.index("echo") + 1]
    query = next(word for word in tokens[tokens.index("jq") + 1 :] if not word.startswith("-"))
    return body, query


def refresh_body(number: int, text: str | None = None) -> dict[str, Any]:
    """The body the skill's refresh recipe posts for pull request *number*."""

    body, _query = refresh_recipe(SKILL.read_text(encoding="utf-8") if text is None else text)
    return json.loads(body.replace("<n>", str(number)))


def present_recipes(text: str) -> list[Code]:
    """The commands of :data:`PRESENT_SECTION`'s and :data:`RERUN_SECTION`'s blocks that
    present a target."""

    return [
        piece
        for piece in code_pieces(text)
        if piece.block
        and piece.section in (PRESENT_SECTION, RERUN_SECTION)
        and "--present" in _tokens(piece.text)
    ]


def rerun_findings(text: str) -> list[str]:
    """Reruns outside the sandbox that lack ``--open-in app``, which keeps them to the app."""

    reruns = [piece for piece in present_recipes(text) if piece.section == RERUN_SECTION]
    if not reruns:
        return [f"SKILL.md has no --present rerun under {RERUN_SECTION!r}"]
    found: list[str] = []
    for piece in reruns:
        tokens = _tokens(piece.text)
        if ("--open-in", "app") not in pairwise(tokens):
            found.append(
                f"SKILL.md:{piece.line}: {piece.text!r} reruns outside the sandbox without "
                "--open-in app, so under auto it can start a server there"
            )
    return found


def _section(text: str, heading: str) -> str:
    """The lines of the section *heading* names, up to the next heading."""

    lines, _offset = _body(text)
    start = next(
        i for i, line in enumerate(lines) if _HEADING.match(line) and line.endswith(heading)
    )
    end = next((i for i in range(start + 1, len(lines)) if _HEADING.match(lines[i])), len(lines))
    return "\n".join(lines[start + 1 : end])


def transcript_blocks(transcript: str) -> list[tuple[str, int, str]]:
    """Each block of an in-process transcript: its command, status, and standard output.

    The command drops the environment assignments a block's line starts with, which the
    harness sets for the run, such as the stand-in ``open``'s failure switch.
    """

    found: list[tuple[str, int, str]] = []
    for match in _TRANSCRIPT_BLOCK.finditer(transcript):
        words = match.group(1).split()
        while words and _ASSIGNMENT.match(words[0]):
            words = words[1:]
        found.append((" ".join(words), int(match.group(2)), match.group(3)))
    return found


# ── What the build offers ───────────────────────────────────────────


def option_names() -> frozenset[str]:
    """Every long option of the ``metab`` command, ``--help`` included."""

    command = typer.main.get_command(cli_main._app)
    context = command.make_context("metab", [], resilient_parsing=True)
    return frozenset(
        name
        for parameter in command.get_params(context)
        for name in (*parameter.opts, *parameter.secondary_opts)
        if name.startswith("--")
    )


def _usage_error() -> type[Exception]:
    """Click's ``UsageError``, which every refusal before ``_metab``'s dispatch raises.

    Typer vendors Click and exports ``BadParameter``, one of its subclasses, and not the
    class itself, so it is reached through that public name.
    """

    base = next(cls for cls in typer.BadParameter.__mro__ if cls.__name__ == "UsageError")
    assert issubclass(base, Exception)
    return base


_USAGE_ERROR: Final = _usage_error()


class _Dispatched(Exception):
    """Raised in place of ``_metab``'s dispatch, once every check before it has passed."""


def mode_refusal(args: tuple[str, ...]) -> str | None:
    """Why the CLI refuses *args* before running anything, or ``None`` when it accepts them.

    This runs the ``metab`` command itself: Click parses *args*, and ``_metab`` runs as far
    as its dispatch on the mode. ``_check_format_applicability`` is the last check it makes
    before the dispatch, so a stand-in calls it and then raises, and nothing the command
    would do runs. A command that returns without that check is reported, not accepted.
    """

    if "--help" in args or "--version" in args:
        return None
    command = typer.main.get_command(cli_main._app)
    last_check = cli_main._check_format_applicability

    def check_then_stop(*arguments: Any) -> None:
        last_check(*arguments)
        raise _Dispatched

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cli_main, "_check_format_applicability", check_then_stop)
        try:
            with command.make_context("metab", list(args)) as context:
                command.invoke(context)
        except _Dispatched:
            return None
        except _USAGE_ERROR as refusal:
            return str(refusal)
    raise AssertionError(
        f"metab {' '.join(args)} returned without calling _check_format_applicability, "
        "where mode_refusal stops it"
    )


RouteTable = Mapping[str, tuple[str, ...]]


def _route_pattern(path: str) -> re.Pattern[str]:
    parts = re.split(r"(\{[^}]+\})", path)
    return re.compile(
        "".join(
            (".+" if part.endswith(":path}") else "[^/]+")
            if part.startswith("{")
            else re.escape(part)
            for part in parts
        )
    )


def _methods(route: str, table: RouteTable) -> tuple[str, ...] | None:
    """The methods of the registered route *route* names, or ``None`` when none matches."""

    concrete = re.sub(r"<[^>]*>", "x", route.split("?", 1)[0])
    for path, methods in table.items():
        if _route_pattern(path).fullmatch(concrete):
            return methods
    return None


def _served_routes(root: Path) -> dict[str, tuple[str, ...]]:
    result = run_metab([str(root), "--api", "/api/routes", "--format", "json"])
    assert result.exit_code == 0, result.stderr
    return {
        entry["path"]: tuple(entry["methods"] or ())
        for entry in json.loads(result.stdout)["routes"]
        if entry["path"].startswith("/api/")
    }


# ── The checks ──────────────────────────────────────────────────────


def flag_findings(text: str, options: frozenset[str], name: str = "SKILL.md") -> list[str]:
    return [
        f"{command.where}: {word.split('=', 1)[0]} is not an option of metab"
        for command in commands(text, name)
        for word in command.args
        if _FLAG.match(word) and word.split("=", 1)[0] not in options
    ]


def mode_findings(text: str, name: str = "SKILL.md") -> list[str]:
    found: list[str] = []
    for command in commands(text, name):
        if not command.whole:
            continue
        refusal = mode_refusal(command.args)
        if refusal is not None:
            found.append(f"{command.where}: metab {' '.join(command.args)} is refused: {refusal}")
    return found


def route_findings(text: str, table: RouteTable, name: str = "SKILL.md") -> list[str]:
    """Routes *text* names that *table* lacks, or that its commands use another way."""

    found: list[str] = []
    for piece in code_pieces(text):
        where = f"{name}:{piece.line}"
        for route in _ROUTE.findall(piece.text):
            if _methods(route, table) is None:
                found.append(f"{where}: {route} is not a registered route")
        for route in _POSTED.findall(piece.text):
            methods = _methods(route, table)
            if methods is not None and "POST" not in methods:
                found.append(f"{where}: {route} does not take POST")
    for command in commands(text, name):
        route = _value(command.args, "--api")
        if not command.whole or route is None or not route.startswith("/api/"):
            continue
        methods = _methods(route, table)
        method = "POST" if "--data" in command.args else "GET"
        if methods is not None and method not in methods:
            found.append(f"{command.where}: {route} does not take {method}")
    return found


def format_findings(text: str, name: str = "SKILL.md") -> list[str]:
    found: list[str] = []
    for command in commands(text, name):
        if not command.whole or not (command.read or "--api" in command.args):
            continue
        plugin_mode = any(mode in command.args for mode in _PLUGIN_MODES)
        if plugin_mode and "--json" in command.args:
            continue
        if _value(command.args, "--format") in _FORMATS:
            continue
        why = "its output is read" if command.read else "it issues --api"
        asked = "--json" if plugin_mode else "--format json"
        found.append(f"{command.where}: metab {' '.join(command.args)} lacks {asked}, and {why}")
    return found


def _normalized(command: str) -> str:
    return " ".join(command.split())


def _runs(golden: str) -> set[str]:
    """Each run of consecutive commands of *golden*, chained as a recipe chains them."""

    ran = [_normalized(block.command) for block in tryscript_blocks.blocks(golden)]
    return {
        " && ".join(ran[start:end])
        for start in range(len(ran))
        for end in range(start + 1, len(ran) + 1)
    }


def recipe_findings(text: str, golden: str) -> list[str]:
    """Recipes of :data:`GOLDEN_SECTIONS` that read JSON and the golden does not run."""

    recipes = _recipes(text)
    found: list[str] = [
        f"SKILL.md has no recipe that reads JSON under {section!r}"
        for section in GOLDEN_SECTIONS
        if not any(piece.section == section for piece in recipes)
    ]
    runs = _runs(golden)
    for piece in recipes:
        spelled = piece.text
        for placeholder, value in GOLDEN_SPELLING.items():
            spelled = spelled.replace(placeholder, value)
        if _normalized(spelled) not in runs:
            found.append(
                f"SKILL.md:{piece.line}: no run of consecutive commands of {GOLDEN.name} "
                f"is {spelled!r}"
            )
    return found


def refresh_findings(text: str, answer: Mapping[str, Any]) -> list[str]:
    """Fields the refresh recipe's filter reads that *answer*, a refresh's, lacks."""

    _body, query = refresh_recipe(text)
    found: list[str] = []
    for path in (part.strip() for part in query.split(",")):
        if _NAME.fullmatch(path) is None or not path.startswith("."):
            found.append(f"the refresh recipe's filter reads {path!r}, which is not a field path")
            continue
        node: Any = answer
        for key in path.removeprefix(".").split("."):
            if not isinstance(node, Mapping) or key not in node:
                found.append(f"the refresh recipe reads {path}, which the answer lacks")
                break
            node = node[key]
    return found


def _has_field(node: Any, path: str) -> bool:
    for key in path.removeprefix(".").split("."):
        if not isinstance(node, Mapping) or key not in node:
            return False
        node = node[key]
    return True


def present_findings(text: str, transcript: str) -> list[str]:
    """Present recipes the delivery transcript does not run, and fields its reports lack."""

    recipes = present_recipes(text)
    if not recipes:
        return [f"SKILL.md has no --present recipe under {PRESENT_SECTION!r}"]
    blocks = transcript_blocks(transcript)
    ran = {command for command, _status, _stdout in blocks}
    found: list[str] = []
    for piece in recipes:
        spelled = piece.text
        for placeholder, value in PRESENT_SPELLING.items():
            spelled = spelled.replace(placeholder, value)
        spelled = _normalized(spelled)
        if spelled not in ran:
            found.append(f"SKILL.md:{piece.line}: {PRESENT_GOLDEN.name} does not run {spelled!r}")
        elif not (spelled.startswith(PRESENT_PREFIX) and spelled.endswith(PRESENT_SUFFIX)):
            found.append(
                f"SKILL.md:{piece.line}: {spelled!r} does not start with {PRESENT_PREFIX.strip()!r} "
                f"and end with {PRESENT_SUFFIX.strip()!r}, which a sandbox rule and jq need"
            )
    # Every report of the skill's shape of command, whatever its target and status.
    reports = [
        (status, json.loads(stdout))
        for command, status, stdout in blocks
        if command.startswith(PRESENT_PREFIX) and command.endswith(PRESENT_SUFFIX)
    ]
    wanted = {PRESENT_REFUSED_EXIT_CODE, *DELIVERY_EXIT_CODES.values()}
    missing = sorted(wanted - {status for status, _report in reports})
    if missing:
        found.append(f"{PRESENT_GOLDEN.name} runs the skill's command with no status {missing}")
    fields = [
        piece.text
        for piece in code_pieces(text)
        if not piece.block
        and piece.section == PRESENT_SECTION
        and piece.text.startswith(".")
        and _NAME.fullmatch(piece.text)
    ]
    if not fields:
        found.append(f"SKILL.md names no report field under {PRESENT_SECTION!r}")
    for path in dict.fromkeys(fields):
        lacking = sorted({status for status, report in reports if not _has_field(report, path)})
        if lacking:
            found.append(f"the report of status {lacking} has no {path}, which SKILL.md reads")
    return found


def status_code_findings(text: str) -> list[str]:
    """Rows of the recipes' table whose status is not the one the code ends with.

    A row that lists delivery codes gives the status ``DELIVERY_EXIT_CODES`` maps them
    to, and the rows of one status list exactly the codes mapped to it. Each row without
    a delivery code says what it is in its code cell: a refusal, whose status is
    ``PRESENT_REFUSED_EXIT_CODE``; a usage error, Click's; or an ``Error:`` line,
    ``CLIError``'s. So every status the table restates is held to its constant.
    """

    listed: dict[int, set[str]] = {}
    marked: dict[str, list[int]] = {marker: [] for marker in _MARKED_STATUSES}
    found: list[str] = []
    for line in _section(text, PRESENT_SECTION).splitlines():
        row = _STATUS_ROW.match(line)
        if row is None:
            continue
        status, cell = int(row.group(1)), row.group(2)
        codes = set(_CODE.findall(cell))
        markers = [marker for marker in _MARKED_STATUSES if marker in cell.lower()]
        if codes:
            listed.setdefault(status, set()).update(codes)
        elif len(markers) == 1:
            marked[markers[0]].append(status)
        else:
            found.append(
                f"the row for status {status} names no delivery code and is not one of {list(_MARKED_STATUSES)}"
            )
    for marker, expected in _MARKED_STATUSES.items():
        if not marked[marker]:
            found.append(f"the table has no row for {marker}")
        found += [
            f"the table gives {marker} status {status}, where the code ends with {expected}"
            for status in marked[marker]
            if status != expected
        ]
    for status in sorted(set(DELIVERY_EXIT_CODES.values()) | set(listed)):
        expected_codes = {code for code, mapped in DELIVERY_EXIT_CODES.items() if mapped == status}
        if listed.get(status, set()) != expected_codes:
            found.append(
                f"the table lists {sorted(listed.get(status, set()))} for status {status}, where "
                f"DELIVERY_EXIT_CODES maps {sorted(expected_codes)} to it"
            )
    return found


def name_findings(text: str, words: frozenset[str], name: str = "SKILL.md") -> list[str]:
    """Field paths and underscored names in *text*'s prose that are not among *words*."""

    found: list[str] = []
    for piece in code_pieces(text):
        if piece.block or _NAME.fullmatch(piece.text) is None:
            continue
        if not piece.text.startswith(".") and "_" not in piece.text:
            continue
        found += [
            f"{name}:{piece.line}: `{piece.text}` names {part!r}, which no source under src/ uses"
            for part in piece.text.removeprefix(".").split(".")
            if part not in words
        ]
    return found


def guide_values() -> frozenset[str]:
    """Every string ``guided_review.py`` spells, and every field of the block's models.

    The strings are the states its route answers, the reasons a reference is not ready,
    and the values it compares, such as a reference's ``side``; the fields are the keys a
    block holds below ``collection``.
    """

    tree = ast.parse(Path(guided_review.__file__).read_text(encoding="utf-8"))
    strings = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    models = (
        guided_review.Collection,
        guided_review.CollectionComparison,
        guided_review.CollectionGroup,
        guided_review.CollectionItem,
        guided_review.CollectionReference,
    )
    return frozenset(strings | {name for model in models for name in model.model_fields})


def guide_value_findings(text: str, values: frozenset[str]) -> list[str]:
    """One-word code spans of :data:`GUIDE_SECTIONS` that are not among *values*."""

    return [
        f"SKILL.md:{piece.line}: `{piece.text}` is not a value or field of guided_review.py"
        for piece in code_pieces(text)
        if not piece.block
        and piece.section in GUIDE_SECTIONS
        and _WORD.fullmatch(piece.text)
        and piece.text not in values
    ]


# What each skeleton under SKELETON_SECTION shows, in order: whether its steps are grouped.
SKELETONS: Final = {"flat": False, "grouped": True}


def skeletons(text: str) -> list[str]:
    """The descriptions the block skeletons of :data:`SKELETON_SECTION` make, IDs filled in."""

    found = _SKELETON.findall(_section(text, SKELETON_SECTION))
    assert len(found) == len(SKELETONS), (
        f"SKILL.md has {len(found)} block skeletons under {SKELETON_SECTION!r}, "
        f"not {len(SKELETONS)}"
    )
    bodies: list[str] = []
    for body in found:
        for placeholder, value in SKELETON_SPELLING.items():
            assert placeholder in body, f"a skeleton has no {placeholder}"
            body = body.replace(placeholder, value)
        bodies.append(body)
    return bodies


def skeleton_findings(text: str) -> list[str]:
    """Why a skeleton is not a guide the page reads, or does not show the rules it states."""

    found: list[str] = []
    for (name, grouped), body in zip(SKELETONS.items(), skeletons(text), strict=True):
        try:
            guide = parse_guide(body)
        except GuideError as refusal:
            found.append(f"the page refuses the {name} skeleton: {refusal}")
            continue
        if guide is None:
            found.append(f"the {name} skeleton has no guided-review block the page reads")
            continue
        pins = (guide.comparison.merge_base, guide.comparison.head)
        if pins != tuple(SKELETON_SPELLING.values()):
            found.append(f"the {name} skeleton's pins read as {pins}, not its placeholders")
        steps = guide.flat_items()
        if not any(": " in step.title for step in steps):
            found.append(
                f"no title of the {name} skeleton holds ': ', so it hides the quoting rule"
            )
        if not any("\n- " in step.note for step in steps):
            found.append(f"no note of the {name} skeleton keeps a list's lines")
        if (steps != guide.items) != grouped:
            found.append(f"the {name} skeleton {'has no' if grouped else 'has a'} group")
    return found


# ── The skill as it is ──────────────────────────────────────────────


@pytest.fixture
def skill() -> str:
    return SKILL.read_text(encoding="utf-8")


@pytest.fixture
def guide() -> str:
    return GUIDE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def routes(tmp_path_factory: pytest.TempPathFactory) -> RouteTable:
    return _served_routes(tmp_path_factory.mktemp("routes"))


@pytest.fixture(scope="module")
def source() -> frozenset[str]:
    """Every identifier and word of the Python under ``src/``."""

    return frozenset(
        word
        for path in sorted((REPO_ROOT / "src").rglob("*.py"))
        for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", path.read_text(encoding="utf-8"))
    )


# The routes the recipes read with `jq`, and the others the skill names in prose, which
# the reader must find for the checks to mean anything.
RECIPE_ROUTES: Final = frozenset(
    {
        "/api/plugin/github/pull?number=<n>",
        "$ROUTE",
        "/api/source/status",
        REFRESH_ROUTE,
        "/api/plugin/github/guided-review?number=<n>&step=<k>",
        "/api/plugin/github/guided-review?number=<n>",
    }
)
PROSE_ROUTES: Final = frozenset({"/api/routes", "/api/file?path=<log>", "/api/git/log?limit=<n>"})


def test_the_skill_is_read_as_commands(skill: str, guide: str) -> None:
    """The reader finds the recipes, so the checks below are not passing on nothing."""

    found = commands(skill)
    flagged = [c for c in found if c.whole and any(_FLAG.match(word) for word in c.args)]
    # 21 when this was written. The floor sits well below it, so an edit of the skill
    # does not trip it, and a reader that stops seeing blocks or spans still does; the
    # named routes below are the specific check.
    assert len(flagged) >= 12, [command.where for command in flagged]
    read = {_value(command.args, "--api") for command in found if command.read}
    named = {_value(command.args, "--api") for command in found if command.whole}
    assert read >= RECIPE_ROUTES and named >= PROSE_ROUTES, (read, named)
    assert any(not command.whole for command in found)
    assert len(_recipes(skill)) == 5
    assert len(present_recipes(skill)) == 4
    assert len([c for c in commands(guide, GUIDE.name) if c.whole]) >= 8


def test_every_flag_is_an_option_of_metab(skill: str, guide: str) -> None:
    assert flag_findings(skill, option_names()) == []
    assert flag_findings(guide, option_names(), GUIDE.name) == []


def test_every_command_passes_its_mode_check(skill: str, guide: str) -> None:
    assert mode_findings(skill) == []
    assert mode_findings(guide, GUIDE.name) == []


def test_every_route_is_registered(skill: str, guide: str, routes: RouteTable) -> None:
    assert route_findings(skill, routes) == []
    assert route_findings(guide, routes, GUIDE.name) == []


def test_every_read_command_prints_one_document(skill: str, guide: str) -> None:
    assert format_findings(skill) == []
    assert format_findings(guide, GUIDE.name) == []


def test_the_golden_runs_the_recipes(skill: str) -> None:
    assert recipe_findings(skill, GOLDEN.read_text(encoding="utf-8")) == []


def test_the_checkout_golden_posts_the_refresh_and_pins_what_it_reads(skill: str) -> None:
    posted = json.dumps(refresh_body(CHECKOUT_PULL, skill))
    assert f"--- body ---\n{posted}\n" in CHECKOUT_GOLDEN.read_text(encoding="utf-8")
    answers = json.loads(CHECKOUT_ANSWERS.read_text(encoding="utf-8"))
    assert refresh_findings(skill, answers["ready"]["body"]) == []


def test_every_name_in_prose_is_one_the_source_uses(
    skill: str, guide: str, source: frozenset[str]
) -> None:
    assert name_findings(skill, source) == []
    assert name_findings(guide, source, GUIDE.name) == []


def test_the_delivery_golden_runs_the_present_recipes(skill: str) -> None:
    assert present_findings(skill, PRESENT_GOLDEN.read_text(encoding="utf-8")) == []


def test_the_present_table_gives_each_status_its_codes(skill: str) -> None:
    assert status_code_findings(skill) == []


def test_every_rerun_outside_the_sandbox_is_kept_to_the_app(skill: str) -> None:
    assert rerun_findings(skill) == []


def test_every_guide_value_is_one_the_module_spells(skill: str) -> None:
    assert guide_value_findings(skill, guide_values()) == []


def test_the_block_skeletons_are_guides_the_page_reads(skill: str) -> None:
    assert skeleton_findings(skill) == []


# ── Each check fails its mutation ───────────────────────────────────


def _mutated(skill: str, old: str, new: str) -> str:
    assert old in skill, f"the mutation no longer applies: {old!r} is not in the text"
    return skill.replace(old, new, 1)


DETECT: Final = "--api '/api/plugin/github/pull?number=<n>' --format json > <tmp>/pull.json"


def test_a_rerun_without_open_in_app_fails(skill: str) -> None:
    rerun = "<invocation> --present <target> --open-in app --format json"
    mutated = _mutated(skill, rerun, rerun.replace(" --open-in app", ""))
    findings = rerun_findings(mutated)
    assert len(findings) == 1 and "without --open-in app" in findings[0]


def test_a_recipe_without_format_json_fails(skill: str) -> None:
    mutated = _mutated(skill, DETECT, DETECT.replace(" --format json", ""))
    findings = format_findings(mutated)
    assert len(findings) == 1 and "lacks --format json, and its output is read" in findings[0]
    assert recipe_findings(mutated, GOLDEN.read_text(encoding="utf-8"))


def test_an_api_command_without_format_json_fails(skill: str) -> None:
    mutated = _mutated(skill, "--api /api/routes --format json`", "--api /api/routes`")
    assert ["it issues --api" in finding for finding in format_findings(mutated)] == [True]


def test_a_missing_route_fails(skill: str, routes: RouteTable) -> None:
    mutated = _mutated(
        skill, "/api/plugin/github/pull?number=<n>", "/api/plugin/github/pul?number=<n>"
    )
    assert route_findings(mutated, routes) == [
        f"SKILL.md:{line}: /api/plugin/github/pul is not a registered route"
        for line in [_line(mutated, "/api/plugin/github/pul?")]
    ]


def test_a_route_used_with_the_wrong_method_fails(skill: str, routes: RouteTable) -> None:
    mutated = _mutated(skill, "\n  --data <tmp>/refresh.json --format json", "\n  --format json")
    assert [
        finding.endswith(f"{REFRESH_ROUTE} does not take GET")
        for finding in route_findings(mutated, routes)
    ] == [True]


def test_an_unknown_flag_fails(skill: str) -> None:
    mutated = _mutated(skill, "<invocation> <url> --no-serve\n", "<invocation> <url> --no-sreve\n")
    assert [finding.split(": ", 1)[1] for finding in flag_findings(mutated, option_names())] == [
        "--no-sreve is not an option of metab"
    ]


def test_a_flag_its_mode_refuses_fails(skill: str) -> None:
    mutated = _mutated(
        skill, "<invocation> <url> --no-serve\n", "<invocation> <url> --no-serve --format json\n"
    )
    findings = mode_findings(mutated)
    assert len(findings) == 1 and "--format not valid with --no-serve" in findings[0]


def test_the_mode_check_runs_the_cli_up_to_its_dispatch() -> None:
    """Accepted commands stop before they run, and refusals are the CLI's own words."""

    assert mode_refusal(("--plugins", "--json")) is None
    assert mode_refusal(("root", "--api", "/api/routes", "--format", "json")) is None
    refused = mode_refusal(("root", "--walk", "--no-serve"))
    assert refused is not None and "mode flags are mutually exclusive" in refused
    unknown = mode_refusal(("root", "--no-sreve"))
    assert unknown is not None and "--no-sreve" in unknown


def test_a_recipe_the_golden_does_not_run_fails(skill: str) -> None:
    mutated = _mutated(
        skill, "jq -er .comparison_route <tmp>/pull.json)", "jq -er .comparison <tmp>/pull.json)"
    )
    findings = recipe_findings(mutated, GOLDEN.read_text(encoding="utf-8"))
    assert len(findings) == 1 and ".comparison " in findings[0]


def test_a_broken_filter_fails(skill: str) -> None:
    mutated = _mutated(
        skill,
        "jq -r '.state, .reason, .last_refresh.outcome' <tmp>/pull.json",
        "jq -r '.state, .reason, .last_refresh.outcom' <tmp>/pull.json",
    )
    findings = recipe_findings(mutated, GOLDEN.read_text(encoding="utf-8"))
    assert len(findings) == 1 and ".last_refresh.outcom'" in findings[0]


def test_a_refresh_the_checkout_golden_does_not_post_fails(skill: str) -> None:
    mutated = _mutated(skill, '"comparison": true}', '"compare": true}')
    posted = json.dumps(refresh_body(CHECKOUT_PULL, mutated))
    assert f"--- body ---\n{posted}\n" not in CHECKOUT_GOLDEN.read_text(encoding="utf-8")


def test_a_refresh_field_the_answer_lacks_fails(skill: str) -> None:
    answers = json.loads(CHECKOUT_ANSWERS.read_text(encoding="utf-8"))
    mutated = _mutated(skill, "'.state, .last_refresh.outcome,", "'.state, .last_refresh.result,")
    assert refresh_findings(mutated, answers["ready"]["body"]) == [
        "the refresh recipe reads .last_refresh.result, which the answer lacks"
    ]


def test_a_span_that_starts_with_a_placeholder_is_checked(skill: str) -> None:
    mutated = _mutated(skill, "`<path> --walk`", "`<path> --wlak`")
    assert [finding.split(": ", 1)[1] for finding in flag_findings(mutated, option_names())] == [
        "--wlak is not an option of metab"
    ]


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_an_indented_or_tilde_block_is_checked(skill: str, fence: str) -> None:
    """A block under a list item, or fenced with tildes, is read as code and not as prose."""

    block = (
        f"\n  {fence}shell\n"
        "  <invocation> <url> --no-sreve\n"
        "  <invocation> <url> --no-serve --format json\n"
        "  <invocation> <url> --api /api/routes --format json > <tmp>/routes.json &&\n"
        "    jq -r '.routes[].path' <tmp>/routes.json\n"
        f"  {fence}\n"
    )
    anchor = "  `.record.unavailable.comparison` names why\n"
    mutated = _mutated(skill, anchor, anchor + block)
    assert [finding.split(": ", 1)[1] for finding in flag_findings(mutated, option_names())] == [
        "--no-sreve is not an option of metab"
    ]
    assert any("--format not valid with --no-serve" in found for found in mode_findings(mutated))
    assert any("routes.json" in found for found in recipe_findings(mutated, GOLDEN.read_text()))


def test_a_name_the_source_does_not_use_fails(skill: str, source: frozenset[str]) -> None:
    mutated = _mutated(skill, "`.pin_ref` names", "`.pinref` names")
    assert [finding.split(": ", 1)[1] for finding in name_findings(mutated, source)] == [
        "`.pinref` names 'pinref', which no source under src/ uses"
    ]


GUIDE_STEP_ROUTE: Final = "/api/plugin/github/guided-review?number=<n>&step=<k>"


def test_a_wrong_guide_route_fails(skill: str, routes: RouteTable) -> None:
    mutated = _mutated(skill, GUIDE_STEP_ROUTE, GUIDE_STEP_ROUTE.replace("review?", "reviews?"))
    line = _line(mutated, "guided-reviews?")
    assert route_findings(mutated, routes) == [
        f"SKILL.md:{line}: /api/plugin/github/guided-reviews is not a registered route"
    ]
    findings = recipe_findings(mutated, GOLDEN.read_text(encoding="utf-8"))
    assert len(findings) == 1 and findings[0].startswith(f"SKILL.md:{line}: ")


def test_a_guide_state_the_route_never_answers_fails(skill: str, source: frozenset[str]) -> None:
    """A renamed state passes check 5, which leaves one-word values alone, and fails check 7."""

    mutated = _mutated(skill, "`.state` is `ready` when", "`.state` is `done` when")
    assert name_findings(mutated, source) == []
    assert guide_value_findings(mutated, guide_values()) == [
        f"SKILL.md:{_line(mutated, '`done`')}: `done` is not a value or field of guided_review.py"
    ]
    field = _mutated(skill, "with a `side`,", "with a `sides`,")
    assert [found.split(": ", 1)[1] for found in guide_value_findings(field, guide_values())] == [
        "`sides` is not a value or field of guided_review.py"
    ]


def test_a_guide_recipe_the_golden_does_not_run_fails(skill: str) -> None:
    golden = GOLDEN.read_text(encoding="utf-8")
    filtered = _mutated(skill, ".stale.changed_steps, .stale", ".stale.steps, .stale")
    findings = recipe_findings(filtered, golden)
    assert len(findings) == 1 and ".stale.steps" in findings[0]
    # A renamed heading takes its recipe out of the golden's reach, which is reported.
    renamed = _mutated(skill, "### Publish and Confirm It\n", "### Publish It\n")
    assert recipe_findings(renamed, golden) == [
        f"SKILL.md has no recipe that reads JSON under {GUIDE_CONFIRM_SECTION!r}"
    ]


SKELETON_TITLE: Final = '"Keystone: the snapshot is served before the worker ends"'
# The grouped skeleton's two group heads, which a mutation takes out to leave its steps
# ungrouped.
SKELETON_DECISIONS_GROUP: Final = "    - title: Decisions\n      items:\n"
SKELETON_TESTING_GROUP: Final = "    - title: Testing\n      items:\n"
# The testing step's list note and its reference, at the flat skeleton's indent; the grouped
# skeleton's lines are these with four more spaces. Each begins at a line's start, so a
# mutation of the flat one cannot match inside the grouped one.
SKELETON_LIST_NOTE: Final = "\n      note: |-\n"
SKELETON_TESTING_REFERENCE: Final = "\n      references:\n        - {path: tests/test_cache.py}\n"


def _indented(lines: str) -> str:
    """*lines*, each that holds text four spaces deeper, as the grouped skeleton has them."""
    return "\n".join(f"    {line}" if line else line for line in lines.split("\n"))


def test_a_skeleton_the_page_refuses_fails(skill: str) -> None:
    # The flat skeleton comes first, so a mutation applied once reaches it.
    unquoted = _mutated(skill, SKELETON_TITLE, SKELETON_TITLE.strip('"'))
    assert skeleton_findings(unquoted) == [
        "the page refuses the flat skeleton: The guided-review block contains invalid YAML."
    ]
    for name, note in (("flat", SKELETON_LIST_NOTE), ("grouped", _indented(SKELETON_LIST_NOTE))):
        folded = _mutated(skill, note, note.replace("|-", ">-"))
        assert skeleton_findings(folded) == [f"no note of the {name} skeleton keeps a list's lines"]
    for name, at in (("flat", "items.1."), ("grouped", "items.1.items.0.")):
        reference = SKELETON_TESTING_REFERENCE
        bare = _mutated(skill, reference if name == "flat" else _indented(reference), "\n")
        assert skeleton_findings(bare) == [
            f"the page refuses the {name} skeleton: The guided-review block does not satisfy "
            f"the v1 SoftSchema at {at}"
        ]
    # Without their groups' heads, the steps are one list, which YAML reads at any indent.
    ungrouped = _mutated(skill, SKELETON_TESTING_GROUP, "")
    ungrouped = _mutated(ungrouped, SKELETON_DECISIONS_GROUP, "")
    assert skeleton_findings(ungrouped) == ["the grouped skeleton has no group"]
    # The grouped skeleton in the flat one's place shows no flat guide.
    flat, grouped = _SKELETON.findall(_section(skill, SKELETON_SECTION))
    assert skeleton_findings(_mutated(skill, flat, grouped)) == ["the flat skeleton has a group"]


PRESENT: Final = "<invocation> --present <target> --format json\n"


def test_a_present_recipe_the_delivery_golden_does_not_run_fails(skill: str) -> None:
    golden = PRESENT_GOLDEN.read_text(encoding="utf-8")
    dropped = _mutated(skill, PRESENT, PRESENT.replace(" --format json", ""))
    findings = present_findings(dropped, golden)
    assert len(findings) == 1 and "does not run 'metab --present notes'" in findings[0]
    # The transcript runs this order too, for the command-line guide; a sandbox rule for
    # the prefix `metab --present` would not match it.
    moved = _mutated(skill, PRESENT, "<invocation> <target> --present --format json\n")
    findings = present_findings(moved, golden)
    assert len(findings) == 1 and "does not start with 'metab --present'" in findings[0]


def test_a_report_field_the_golden_lacks_fails(skill: str) -> None:
    mutated = _mutated(skill, "`.target.page`, the address", "`.target.address`, the address")
    assert present_findings(mutated, PRESENT_GOLDEN.read_text(encoding="utf-8")) == [
        "the report of status [0, 1, 3, 4, 5] has no .target.address, which SKILL.md reads"
    ]


def test_a_delivery_code_under_another_status_fails(skill: str) -> None:
    mutated = _mutated(skill, "| `lookup_failed`, `open_failed` |", "| `lookup_failed` |")
    assert status_code_findings(mutated) == [
        "the table lists ['lookup_failed'] for status 5, where DELIVERY_EXIT_CODES maps "
        "['lookup_failed', 'open_failed'] to it"
    ]
    moved = _mutated(skill, "`app_not_marked`, ", "").replace(
        "| `lookup_failed`, `open_failed` |", "| `app_not_marked`, `lookup_failed`, `open_failed` |"
    )
    assert len(status_code_findings(moved)) == 2


@pytest.mark.parametrize(
    ("row", "marker", "expected"),
    [
        ("| 3 | A refusal’s code |", "a refusal", 3),
        ("| 2 | None: a usage error |", "a usage error", 2),
        ("| 1 | None: an `Error:` line |", "an `error:` line", 1),
    ],
)
def test_a_restated_status_the_code_does_not_end_with_fails(
    skill: str, row: str, marker: str, expected: int
) -> None:
    renumbered = _mutated(skill, row, row.replace(f"| {expected} |", "| 7 |", 1))
    assert status_code_findings(renumbered) == [
        f"the table gives {marker} status 7, where the code ends with {expected}"
    ]
    assert status_code_findings(_mutated(skill, row + " ", "| 9 | Gone | ")) == [
        f"the row for status 9 names no delivery code and is not one of {list(_MARKED_STATUSES)}",
        f"the table has no row for {marker}",
    ]


def test_the_guide_is_held_to_the_same_checks(guide: str, routes: RouteTable) -> None:
    mutated = _mutated(guide, "--api /api/routes --format json`", "--api /api/route --fromat json`")
    assert [found.split(": ", 1)[1] for found in flag_findings(mutated, option_names(), "g")] == [
        "--fromat is not an option of metab"
    ]
    assert [found.split(": ", 1)[1] for found in route_findings(mutated, routes, "g")] == [
        "/api/route is not a registered route"
    ]


def _line(text: str, needle: str) -> int:
    return text[: text.index(needle)].count("\n") + 1
