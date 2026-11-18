"""The commands the agent skill teaches, held to the ``metab`` they run.

``skills/metabrowser/SKILL.md`` is copied into agents' environments and followed as
written, so a renamed flag, a moved route, or a recipe whose output stops parsing fails
there, for someone else, while every check here stays green. A review of the skill on
2026-11-17 found all three. These checks read the skill the way an agent does, every
command in its code blocks and code spans, and hold it to the build:

1. **Flags.** Every ``--flag`` of a ``metab`` command, or of a span of flags alone, is an
   option of the command Typer builds from ``metabrowser.cli.main``. Every whole command
   also passes the mode check the CLI makes before it does anything, so a flag its mode
   refuses, as ``--no-serve --format json`` is refused, fails here and not with exit
   status 2 in an agent's shell.
2. **Routes.** Every ``/api/`` route the skill names is one ``metab --api /api/routes``
   lists, with the method its command uses: POST for an ``--api`` with ``--data`` or a
   route the text calls ``POST``, and GET for any other ``--api``.
3. **Parseable output.** A ``metab`` command whose output another program reads, piped or
   captured with ``$(…)``, and every ``--api`` command, asks for ``--format json`` or
   ``yaml``, or ``--json`` in a plugin mode, so standard output is one document.
4. **Recipes run.** Each recipe under "From a Pull-Request URL" that pipes to ``jq`` is a
   command of ``tests/golden/cli-skill-recipes.tryscript.md``, with the placeholders
   that transcript names filled in, so the golden runs the skill's own text.
5. **The release floor.** The skill says which release its commands run on, and every
   flag and route it names is in that release's surface, recorded in
   ``tests/fixtures/metab-0.12.0-surface.json``: the long options of ``metab`` 0.12.0,
   built from the ``v0.12.0`` tag, and the ``/api/`` routes its ``--api /api/routes
   --format json`` listed for an empty folder, each with its methods. A release does not
   change, so the recording cannot go stale; raising the floor means recording the new
   release the same way. Names are not behavior, so the recording also lists the option
   values that release refuses: it reads ``--data -`` as a file named ``-``.

Each check is proven by a mutation of the skill it must fail.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final, cast

import pytest
import typer.main
from typer._click.exceptions import ClickException

from devtools import tryscript_blocks
from metabrowser.cli.main import (
    _app,
    _check_format_applicability,
    _check_option_applicability,
    _explicit_params,
    _resolve_mode,
)
from tests.golden_harness import run_metab

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
SKILL: Final = REPO_ROOT / "skills" / "metabrowser" / "SKILL.md"
GOLDEN: Final = REPO_ROOT / "tests" / "golden" / "cli-skill-recipes.tryscript.md"
SURFACE: Final = REPO_ROOT / "tests" / "fixtures" / "metab-0.12.0-surface.json"

# The words that run ``metab`` in the skill; ``<invocation>`` is the local command or
# ``uvx metabrowser@latest``, and a ``uvx`` line runs it after the package.
PROGRAMS: Final = frozenset({"metab", "metabrowser", "<invocation>"})
# Words a shell reads before the program of a command.
_KEYWORDS: Final = frozenset({"if", "then", "else", "elif", "do", "while", "until", "!", "time"})
_ASSIGNMENT: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_SEPARATORS: Final = frozenset({"|", "||", "&&", ";", ";;", "&", "(", ")"})
# A redirection, and not a placeholder such as `<path>` or `<file>.patch`.
_REDIRECT: Final = re.compile(r"^\d*(?:>>?|<)(?![^<>]*>)")
_FLAG: Final = re.compile(r"^--[A-Za-z]")
_ROUTE: Final = re.compile(r"/api/[^\s`'\"?),]+")
_POSTED: Final = re.compile(r"\bPOST (/api/[^\s`'\"?),]+)")
_SPAN: Final = re.compile(r"`([^`]+)`")
_HEADING: Final = re.compile(r"^#{2,6} (.+)$")
_FENCE: Final = re.compile(r"^(`{3,})(.*)$")
_FLOOR: Final = re.compile(r"Every\s+command\s+here\s+runs\s+on\s+`metab`\s+(\S+)\s+and\s+later")
# A line that the next one continues: a backslash, or an operator that needs more.
_CONTINUED: Final = re.compile(r"(?:\\|\||&&)\s*$")
_FORMATS: Final = frozenset({"json", "yaml"})
_PLUGIN_MODES: Final = frozenset({"--plugins", "--plugin", "--doctor"})

# The section whose recipes the golden runs, and how it spells their placeholders. The
# checkout's refresh is not run there: its ``"comparison": true`` acquires a store from
# GitHub, so ``tests/test_cli_github_checkout_golden.py`` runs it in process instead.
GOLDEN_SECTION: Final = "From a Pull-Request URL"
GOLDEN_SPELLING: Final = {
    "<invocation>": (
        "METABROWSER_CONFIG_DIR=$PWD/url/config METABROWSER_CACHE_DIR=$PWD/url/home metab"
    ),
    "<url>": "https://github.com/octo/demo/pull/7",
    "<n>": "7",
    "<path>": "src/app.txt",
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
    # Its standard output is piped to another command or captured with `$(…)`.
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
        opened = _FENCE.match(line)
        if fence is not None:
            if opened is not None and line.strip() == fence:
                fence = None
                continue
            if not pending:
                pending_line = number
            pending.append(line)
            logical = " ".join(part.removesuffix("\\") for part in pending)
            if not _CONTINUED.search(line) and _depth(logical) <= 0:
                pieces.append(Code(pending_line, " ".join(logical.split()), True, section))
                pending.clear()
            continue
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


def commands(text: str) -> list[Command]:
    """Every ``metab`` invocation in the skill, whole or as a span of flags."""

    found: list[Command] = []
    for piece in code_pieces(text):
        where = f"SKILL.md:{piece.line}"
        try:
            tokens = _tokens(piece.text)
        except ValueError:
            continue
        if not piece.block and tokens and _FLAG.match(tokens[0]):
            found.append(Command(where, tuple(tokens), whole=False, read=False))
            continue
        for words, read in _segments(tokens):
            args = _metab_args(words)
            if args is not None:
                found.append(Command(where, _without_redirects(args), whole=True, read=read))
    return found


def _value(args: tuple[str, ...], option: str) -> str | None:
    if option not in args:
        return None
    index = args.index(option)
    return args[index + 1] if index + 1 < len(args) else None


# ── What the build offers ───────────────────────────────────────────


def option_names() -> frozenset[str]:
    """Every long option of the ``metab`` command, ``--help`` included."""

    command = typer.main.get_command(_app)
    context = command.make_context("metab", [], resilient_parsing=True)
    return frozenset(
        name
        for parameter in command.get_params(context)
        for name in (*parameter.opts, *parameter.secondary_opts)
        if name.startswith("--")
    )


def mode_refusal(args: tuple[str, ...]) -> str | None:
    """Why the CLI refuses *args* before running anything, or ``None`` when it accepts them.

    The same calls, in the same order, as ``metabrowser.cli.main._metab`` makes before it
    dispatches on the mode.
    """

    if "--help" in args or "--version" in args:
        return None
    command = typer.main.get_command(_app)
    try:
        # The context `_metab` itself receives: Typer annotates it as `typer.Context`, and
        # at run time it is the vendored Click context this makes.
        context = cast(typer.Context, command.make_context("metab", list(args)))
        params = context.params
        mode = _resolve_mode(
            context,
            walk=params["walk"],
            diff=params["diff"],
            api=params["api"],
            show=params["show"],
            check_api=params["check_api"],
            no_serve=params["no_serve"],
            remote=params["remote"],
            plugins=params["plugins"],
            plugin=params["plugin"],
            doctor=params["doctor"],
        )
        explicit = _explicit_params(context)
        _check_option_applicability(context, mode, explicit)
        _check_format_applicability(context, mode, params["fmt"], explicit)
    except ClickException as refusal:
        return refusal.format_message()
    return None


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


@cache
def _served_routes(root: str) -> dict[str, tuple[str, ...]]:
    result = run_metab([root, "--api", "/api/routes", "--format", "json"])
    assert result.exit_code == 0, result.stderr
    return {
        entry["path"]: tuple(entry["methods"] or ())
        for entry in json.loads(result.stdout)["routes"]
        if entry["path"].startswith("/api/")
    }


def surface() -> dict[str, Any]:
    return json.loads(SURFACE.read_text(encoding="utf-8"))


# ── The checks ──────────────────────────────────────────────────────


def flag_findings(text: str, options: frozenset[str]) -> list[str]:
    return [
        f"{command.where}: {word.split('=', 1)[0]} is not an option of metab"
        for command in commands(text)
        for word in command.args
        if _FLAG.match(word) and word.split("=", 1)[0] not in options
    ]


def mode_findings(text: str) -> list[str]:
    found: list[str] = []
    for command in commands(text):
        if not command.whole:
            continue
        refusal = mode_refusal(command.args)
        if refusal is not None:
            found.append(f"{command.where}: metab {' '.join(command.args)} is refused: {refusal}")
    return found


def route_findings(text: str, table: RouteTable) -> list[str]:
    """Routes the skill names that *table* lacks, or that its commands use another way."""

    found: list[str] = []
    for piece in code_pieces(text):
        where = f"SKILL.md:{piece.line}"
        for route in _ROUTE.findall(piece.text):
            if _methods(route, table) is None:
                found.append(f"{where}: {route} is not a registered route")
        for route in _POSTED.findall(piece.text):
            methods = _methods(route, table)
            if methods is not None and "POST" not in methods:
                found.append(f"{where}: {route} does not take POST")
    for command in commands(text):
        route = _value(command.args, "--api")
        if not command.whole or route is None or not route.startswith("/api/"):
            continue
        methods = _methods(route, table)
        method = "POST" if "--data" in command.args else "GET"
        if methods is not None and method not in methods:
            found.append(f"{command.where}: {route} does not take {method}")
    return found


def format_findings(text: str) -> list[str]:
    found: list[str] = []
    for command in commands(text):
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


def recipe_findings(text: str, golden: str) -> list[str]:
    """Recipes of :data:`GOLDEN_SECTION` piped to ``jq`` that the golden does not run."""

    ran = {_normalized(block.command) for block in tryscript_blocks.blocks(golden)}
    recipes = [
        piece
        for piece in code_pieces(text)
        if piece.block and piece.section == GOLDEN_SECTION and "jq" in _tokens(piece.text)
    ]
    if not recipes:
        return [f"SKILL.md has no recipe piped to jq under {GOLDEN_SECTION!r} for the golden"]
    found: list[str] = []
    for piece in recipes:
        spelled = piece.text
        for placeholder, value in GOLDEN_SPELLING.items():
            spelled = spelled.replace(placeholder, value)
        if _normalized(spelled) not in ran:
            found.append(f"SKILL.md:{piece.line}: no command of {GOLDEN.name} runs {spelled!r}")
    return found


def floor_findings(text: str, recorded: Mapping[str, Any]) -> list[str]:
    """What the skill names that the release it says it runs on lacks."""

    stated = _FLOOR.findall(text)
    if stated != [recorded["version"]]:
        return [
            f"SKILL.md states {stated or 'no'} release floor; its commands are checked "
            f"against {SURFACE.name}, release {recorded['version']}"
        ]
    options = frozenset(recorded["options"])
    table = {path: tuple(methods) for path, methods in recorded["api_routes"].items()}
    found = [
        finding.replace("is not an option of metab", f"is not an option of {recorded['version']}")
        for finding in flag_findings(text, options)
    ]
    found += [finding + f" in {recorded['version']}" for finding in route_findings(text, table)]
    for command in commands(text):
        if not command.whole:
            continue
        for option, values in recorded["unsupported"].items():
            if _value(command.args, option) in values:
                found.append(
                    f"{command.where}: {recorded['version']} does not take "
                    f"{option} {_value(command.args, option)}"
                )
    return found


# ── The skill as it is ──────────────────────────────────────────────


@pytest.fixture
def skill() -> str:
    return SKILL.read_text(encoding="utf-8")


@pytest.fixture
def routes(tmp_path: Path) -> RouteTable:
    return _served_routes(str(tmp_path))


def test_the_skill_is_read_as_commands(skill: str) -> None:
    """The reader finds the recipes, so the checks below are not passing on nothing."""

    found = commands(skill)
    assert sum(command.whole for command in found) > 30
    assert sum(command.read for command in found) >= 6
    assert any(not command.whole for command in found)


def test_every_flag_is_an_option_of_metab(skill: str) -> None:
    assert flag_findings(skill, option_names()) == []


def test_every_command_passes_its_mode_check(skill: str) -> None:
    assert mode_findings(skill) == []


def test_every_route_is_registered(skill: str, routes: RouteTable) -> None:
    assert route_findings(skill, routes) == []


def test_every_read_command_prints_one_document(skill: str) -> None:
    assert format_findings(skill) == []


def test_the_golden_runs_the_recipes(skill: str) -> None:
    assert recipe_findings(skill, GOLDEN.read_text(encoding="utf-8")) == []


def test_the_release_floor_has_every_flag_and_route(skill: str) -> None:
    assert floor_findings(skill, surface()) == []


# ── Each check fails its mutation ───────────────────────────────────


def _mutated(skill: str, old: str, new: str) -> str:
    assert old in skill, f"the mutation no longer applies: {old!r} is not in SKILL.md"
    return skill.replace(old, new, 1)


DETECT: Final = "--api '/api/plugin/github/pull?number=<n>' --format json |\n  jq -r '.state"


def test_a_recipe_without_format_json_fails(skill: str) -> None:
    mutated = _mutated(
        skill, DETECT, "--api '/api/plugin/github/pull?number=<n>' |\n  jq -r '.state"
    )
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
    mutated = _mutated(skill, ' --data "$BODY"', "")
    assert [
        finding.endswith("/api/plugin/github/pull-refresh does not take GET")
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


def test_a_recipe_the_golden_does_not_run_fails(skill: str) -> None:
    mutated = _mutated(skill, "jq -r .comparison_route)", "jq -r '.comparison_route')")
    findings = recipe_findings(mutated, GOLDEN.read_text(encoding="utf-8"))
    assert len(findings) == 1 and "comparison_route" in findings[0]


def test_a_route_newer_than_the_floor_fails(skill: str) -> None:
    mutated = _mutated(
        skill, "--api /api/routes --format json`", "--api /api/identity --format json`"
    )
    assert [
        finding.endswith("/api/identity is not a registered route in 0.12.0")
        for finding in floor_findings(mutated, surface())
    ] == [True]


def test_a_value_the_floor_refuses_fails(skill: str) -> None:
    mutated = _mutated(skill, '--data "$BODY"', "--data -")
    assert [
        finding.endswith("0.12.0 does not take --data -")
        for finding in floor_findings(mutated, surface())
    ] == [True]


def test_a_floor_the_skill_does_not_state_fails(skill: str) -> None:
    mutated = _mutated(
        skill, "runs on `metab` 0.12.0 and later", "runs on `metab` 0.11.0 and later"
    )
    assert floor_findings(mutated, surface())[0].startswith(
        "SKILL.md states ['0.11.0'] release floor"
    )


def _line(text: str, needle: str) -> int:
    return text[: text.index(needle)].count("\n") + 1
