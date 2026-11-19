"""The macOS app's contract with ``metab``, as ``apps/macos/metab-contract.toml`` declares it.

The declaration lists what the app in ``apps/macos`` depends on in ``metab``. This module
reads it, and holds the two operations that the golden's driver
(``tests/test_app_contract_golden.py``) and the check (``devtools/check_app_contract.py``)
must agree on:

- **Projection.** The golden records what the app reads of an answer and nothing else:
  the declared keys of a JSON object (:func:`project`) and the declared lines of a stream
  (:func:`kept_lines`). So a field the app does not read can come and go without touching
  the golden, and a change to the golden is a change to something the app reads. A
  declared key that an answer no longer has is an error, not an omission.
- **Reading the golden back.** A block is one command, written by
  ``tests/golden_harness.py`` ``block`` with a ``contract`` section that names its
  scenario (:func:`read_blocks`), and its command line is held to the declared argument
  list (:func:`matches_argv`).

``docs/project/architecture/arch-app-contract.md`` describes the contract and its checks.
"""

from __future__ import annotations

import json
import re
import shlex
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, cast

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
APP_ROOT: Final = REPO_ROOT / "apps" / "macos"
DECLARATION: Final = APP_ROOT / "metab-contract.toml"
GOLDEN_DIR: Final = REPO_ROOT / "tests" / "golden"
GOLDEN_NAME: Final = "app-contract.txt"
GOLDEN: Final = GOLDEN_DIR / GOLDEN_NAME

# The section of a block that names its scenario: ``<id>`` or ``<id>/<scenario>``.
SCENARIO_SECTION: Final = "contract"
# What stands in a block for output the app shows a person and reads nothing of.
SHOWN_OUTPUT: Final = "<shown as written, not read>"
OWN_PREFIX: Final = "own:"

_PLACEHOLDER: Final = re.compile(r"\{[a-z_]+\}")
_BLOCK_HEADER: Final = re.compile(r"^# (.+)\nexit: (\S+)\n--- stdout ---$", re.MULTILINE)
_SECTION: Final = re.compile(r"^--- ([a-z]+) ---$", re.MULTILINE)
_ASSIGNMENT: Final = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.DOTALL)


class ContractError(Exception):
    """The declaration, or an answer held to it, is not what the contract says."""


@dataclass(frozen=True, slots=True)
class Surface:
    """A command the app runs, or a route it asks: what it sends and what it reads back."""

    id: str
    # "command" or "route".
    kind: str
    # What follows ``metab``, with ``{name}`` for a value that varies.
    argv: tuple[str, ...]
    source: str
    json: tuple[str, ...] = ()
    values: Mapping[str, tuple[str, ...]] = field(default_factory=dict[str, tuple[str, ...]])
    # The golden that shows the values, when the contract's own cannot.
    values_in: str = ""
    stdout: tuple[str, ...] = ()
    stderr: tuple[str, ...] = ()
    shown: bool = False
    app_runs: bool = True
    because: str = ""
    note: str = ""
    # A route's path, and the spelling of it in the Swift source.
    route: str = ""
    literal: str = ""

    @property
    def flags(self) -> frozenset[str]:
        return frozenset(word for word in self.argv if word.startswith("--"))


@dataclass(frozen=True, slots=True)
class Line:
    id: str
    pattern: re.Pattern[str]
    source: str
    golden: str = ""
    pinned_by: str = ""
    note: str = ""


@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    source: str
    metab: str
    golden: str = ""
    note: str = ""


@dataclass(frozen=True, slots=True)
class Pinned:
    """A behavior, a copied value, or something ``metab`` reads of the app: what it is,
    and the test that holds the two sides together."""

    # "behavior", "copy", or "app_side".
    kind: str
    id: str
    what: str
    pinned_by: str
    source: str = ""
    golden: str = ""


@dataclass(frozen=True, slots=True)
class FileUse:
    """One Swift file that starts a process, decodes JSON, sends a request, or scripts a
    page: what it runs or reads, and for a launch how many places build a command."""

    uses: tuple[str, ...]
    sites: int = 0

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(use for use in self.uses if not use.startswith(OWN_PREFIX))


@dataclass(frozen=True, slots=True)
class Contract:
    surfaces: tuple[Surface, ...]
    lines: tuple[Line, ...]
    variables: tuple[Variable, ...]
    pinned: tuple[Pinned, ...]
    # ``launch``, ``json``, ``http``, and ``script``, each a map from a file to its use.
    files: Mapping[str, Mapping[str, FileUse]]
    other_flags: frozenset[str]
    other_env: frozenset[str]

    def surface(self, identifier: str) -> Surface | None:
        return next((item for item in self.surfaces if item.id == identifier), None)

    def line(self, identifier: str) -> Line | None:
        return next((item for item in self.lines if item.id == identifier), None)

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(
            [item.id for item in self.surfaces]
            + [item.id for item in self.pinned if item.kind == "behavior"]
        )


FILE_KINDS: Final = ("launch", "json", "http", "script")
_SURFACE_KEYS: Final = {
    "command": frozenset(
        {
            "id",
            "argv",
            "source",
            "json",
            "values",
            "values_in",
            "stdout",
            "stderr",
            "output",
            "app_runs",
            "because",
            "note",
        }
    ),
    "route": frozenset({"id", "route", "literal", "source", "json", "values", "values_in", "note"}),
}
_TABLE_KEYS: Final = {
    "line": frozenset({"id", "pattern", "source", "golden", "pinned_by", "note"}),
    "env": frozenset({"name", "source", "metab", "golden", "note"}),
    "behavior": frozenset({"id", "source", "what", "pinned_by", "golden"}),
    "copy": frozenset({"swift", "source", "metab", "pinned_by"}),
    "app_side": frozenset({"id", "what", "pinned_by"}),
}
_TOP_LEVEL: Final = frozenset({"command", "route", "files", "other", *_TABLE_KEYS})


def _strings(value: object, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in cast("list[object]", value)
    ):
        raise ContractError(f"{where}: must be a list of strings")
    return tuple(cast("list[str]", value))


def _text(table: Mapping[str, object], key: str, where: str, *, required: bool = True) -> str:
    value = table.get(key, "")
    if not isinstance(value, str) or (required and not value):
        raise ContractError(f"{where}: needs a `{key}`, as text")
    return value


def _tables(document: Mapping[str, object], name: str) -> list[dict[str, object]]:
    value = document.get(name, [])
    if not isinstance(value, list) or not all(
        isinstance(item, dict) for item in cast("list[object]", value)
    ):
        raise ContractError(f"[[{name}]]: must be an array of tables")
    return cast("list[dict[str, object]]", value)


def _known(table: Mapping[str, object], allowed: frozenset[str], where: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ContractError(f"{where}: has keys this check does not read: {', '.join(unknown)}")


def _values(table: Mapping[str, object], where: str) -> dict[str, tuple[str, ...]]:
    raw = table.get("values", {})
    if not isinstance(raw, dict):
        raise ContractError(f"{where}: `values` must be a table of key = [values]")
    return {
        key: _strings(found, f"{where}: values.{key}")
        for key, found in cast("dict[str, object]", raw).items()
    }


def _surface(kind: str, table: dict[str, object]) -> Surface:
    where = f"[[{kind}]] {table.get('id', '(no id)')}"
    _known(table, _SURFACE_KEYS[kind], where)
    identifier = _text(table, "id", where)
    json_paths = _strings(table.get("json", []), f"{where}: json")
    values = _values(table, where)
    for key in values:
        if key not in json_paths:
            raise ContractError(f"{where}: values.{key} names a key `json` does not list")
    if kind == "route":
        route = _text(table, "route", where)
        return Surface(
            id=identifier,
            kind=kind,
            argv=("{root}", "--api", route),
            source=_text(table, "source", where),
            json=json_paths,
            values=values,
            values_in=_text(table, "values_in", where, required=False),
            note=_text(table, "note", where, required=False),
            route=route,
            literal=_text(table, "literal", where),
        )
    output = _text(table, "output", where, required=False)
    if output not in ("", "shown"):
        raise ContractError(f'{where}: `output` is "shown" or absent')
    app_runs = table.get("app_runs", True)
    if not isinstance(app_runs, bool):
        raise ContractError(f"{where}: `app_runs` is true or false")
    because = _text(table, "because", where, required=False)
    if app_runs == bool(because):
        raise ContractError(
            f"{where}: a command the app does not run says why it is here in `because`, "
            "and one it runs has none"
        )
    if output and json_paths:
        raise ContractError(f"{where}: output the app shows as written has no `json` to read")
    return Surface(
        id=identifier,
        kind=kind,
        argv=_strings(table.get("argv"), f"{where}: argv"),
        source=_text(table, "source", where),
        json=json_paths,
        values=values,
        values_in=_text(table, "values_in", where, required=False),
        stdout=_strings(table.get("stdout", []), f"{where}: stdout"),
        stderr=_strings(table.get("stderr", []), f"{where}: stderr"),
        shown=output == "shown",
        app_runs=app_runs,
        because=because,
        note=_text(table, "note", where, required=False),
    )


def _file_uses(document: Mapping[str, object]) -> dict[str, dict[str, FileUse]]:
    raw = document.get("files", {})
    if not isinstance(raw, dict) or set(cast("dict[str, object]", raw)) != set(FILE_KINDS):
        raise ContractError(f"[files]: needs exactly the tables {', '.join(FILE_KINDS)}")
    files: dict[str, dict[str, FileUse]] = {}
    for kind, table in cast("dict[str, object]", raw).items():
        if not isinstance(table, dict):
            raise ContractError(f"[files.{kind}]: must be a table of file = use")
        uses: dict[str, FileUse] = {}
        for path, use in cast("dict[str, object]", table).items():
            where = f"[files.{kind}] {path}"
            if kind == "launch":
                if not isinstance(use, dict) or set(cast("dict[str, object]", use)) != {
                    "sites",
                    "runs",
                }:
                    raise ContractError(f"{where}: is {{ sites = N, runs = [...] }}")
                entry = cast("dict[str, object]", use)
                sites = entry["sites"]
                if not isinstance(sites, int) or isinstance(sites, bool) or sites < 1:
                    raise ContractError(f"{where}: `sites` is a count of at least 1")
                uses[path] = FileUse(_strings(entry["runs"], f"{where}: runs"), sites)
            else:
                uses[path] = FileUse(_strings(use, where))
            if not uses[path].uses:
                raise ContractError(f"{where}: names nothing it runs or reads")
        files[kind] = uses
    return files


def parse(text: str) -> Contract:
    """The contract *text* declares, or the first thing wrong with it."""

    try:
        document = cast("dict[str, object]", tomllib.loads(text))
    except tomllib.TOMLDecodeError as error:
        raise ContractError(f"not TOML: {error}") from error
    unknown = sorted(set(document) - _TOP_LEVEL)
    if unknown:
        raise ContractError(f"tables this check does not read: {', '.join(unknown)}")
    surfaces = [
        _surface(kind, table) for kind in ("command", "route") for table in _tables(document, kind)
    ]
    lines: list[Line] = []
    for table in _tables(document, "line"):
        where = f"[[line]] {table.get('id', '(no id)')}"
        _known(table, _TABLE_KEYS["line"], where)
        try:
            pattern = re.compile(_text(table, "pattern", where))
        except re.error as error:
            raise ContractError(f"{where}: its pattern does not compile: {error}") from error
        lines.append(
            Line(
                id=_text(table, "id", where),
                pattern=pattern,
                source=_text(table, "source", where),
                golden=_text(table, "golden", where, required=False),
                pinned_by=_text(table, "pinned_by", where, required=False),
                note=_text(table, "note", where, required=False),
            )
        )
    variables: list[Variable] = []
    for table in _tables(document, "env"):
        where = f"[[env]] {table.get('name', '(no name)')}"
        _known(table, _TABLE_KEYS["env"], where)
        variables.append(
            Variable(
                name=_text(table, "name", where),
                source=_text(table, "source", where),
                metab=_text(table, "metab", where),
                golden=_text(table, "golden", where, required=False),
                note=_text(table, "note", where, required=False),
            )
        )
    pinned: list[Pinned] = []
    for kind in ("behavior", "copy", "app_side"):
        for table in _tables(document, kind):
            name = table.get("id", table.get("swift", "(unnamed)"))
            where = f"[[{kind}]] {name}"
            _known(table, _TABLE_KEYS[kind], where)
            if kind == "copy":
                swift = _text(table, "swift", where)
                what = f"{swift}: {_text(table, 'metab', where)}"
                pinned.append(
                    Pinned(
                        kind,
                        swift,
                        what,
                        _text(table, "pinned_by", where),
                        _text(table, "source", where),
                    )
                )
            else:
                pinned.append(
                    Pinned(
                        kind,
                        _text(table, "id", where),
                        _text(table, "what", where),
                        _text(table, "pinned_by", where),
                        _text(table, "source", where, required=kind == "behavior"),
                        _text(table, "golden", where, required=False),
                    )
                )
    other = document.get("other", {})
    if not isinstance(other, dict) or set(cast("dict[str, object]", other)) != {"flags", "env"}:
        raise ContractError("[other]: needs exactly `flags` and `env`")
    others = cast("dict[str, object]", other)
    contract = Contract(
        surfaces=tuple(surfaces),
        lines=tuple(lines),
        variables=tuple(variables),
        pinned=tuple(pinned),
        files=_file_uses(document),
        other_flags=frozenset(_strings(others["flags"], "[other] flags")),
        other_env=frozenset(_strings(others["env"], "[other] env")),
    )
    _check_references(contract)
    return contract


def _check_references(contract: Contract) -> None:
    """Every id is declared once, and every id something names is declared."""

    seen: set[str] = set()
    for identifier in [item.id for item in contract.surfaces] + [
        item.id for item in contract.pinned if item.kind == "behavior"
    ]:
        if "/" in identifier or not identifier:
            raise ContractError(f"{identifier!r}: an id is a name without `/`")
        if identifier in seen:
            raise ContractError(f"{identifier}: declared twice")
        seen.add(identifier)
    line_ids = [line.id for line in contract.lines]
    for identifier in line_ids:
        if line_ids.count(identifier) > 1:
            raise ContractError(f"[[line]] {identifier}: declared twice")
    for surface in contract.surfaces:
        for name in (*surface.stdout, *surface.stderr):
            if contract.line(name) is None:
                raise ContractError(f"{surface.id}: reads a line `{name}` no [[line]] declares")
    for kind, files in contract.files.items():
        for path, use in files.items():
            for identifier in use.ids:
                if identifier not in contract.ids:
                    raise ContractError(
                        f"[files.{kind}] {path}: names `{identifier}`, which nothing declares; "
                        f"what is the app's own starts with `{OWN_PREFIX}`"
                    )


def load(path: Path = DECLARATION) -> Contract:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ContractError(f"{path}: cannot be read: {error}") from error
    try:
        return parse(text)
    except ContractError as error:
        raise ContractError(f"{path.name}: {error}") from error


# ── Projection ──────────────────────────────────────────────────────


def _path_tree(paths: Iterable[str]) -> dict[str, Any]:
    """*paths* as nested keys: ``a.b`` and ``a[].c`` become ``{"a": {"b": …}}`` and
    ``{"a[]": {"c": …}}``, with an empty table where a path ends."""

    tree: dict[str, Any] = {}
    for path in paths:
        node = tree
        for segment in path.split("."):
            node = node.setdefault(segment, {})
    return tree


def _project(value: object, tree: Mapping[str, Any], where: str) -> object:
    if not tree or value is None:
        return value
    if not isinstance(value, dict):
        raise ContractError(f"{where}: the app reads keys of it, and it is not an object")
    found = cast("dict[str, object]", value)
    kept: dict[str, object] = {}
    for segment, below in tree.items():
        key = segment.removesuffix("[]")
        here = f"{where}.{key}" if where else key
        if key not in found:
            raise ContractError(f"{here}: the app reads this key, and the answer does not have it")
        inner = found[key]
        if segment.endswith("[]") and inner is not None:
            if not isinstance(inner, list):
                raise ContractError(f"{here}: the app reads it as a list, and it is not one")
            kept[key] = [
                _project(item, below, f"{here}[{index}]")
                for index, item in enumerate(cast("list[object]", inner))
            ]
        else:
            kept[key] = _project(inner, below, here)
    return kept


def project(answer: object, paths: Sequence[str]) -> object:
    """*answer* with only the keys *paths* name, in the order they are declared.

    A key the declaration names and the answer lacks is a :class:`ContractError`: the app
    would read nothing where it expects a value. A null where an object or a list is
    declared stays null, as ``refusal`` is for a plan.
    """

    return _project(answer, _path_tree(paths), "")


def kept_lines(text: str, patterns: Sequence[re.Pattern[str]]) -> str:
    """The lines of *text* that one of *patterns* matches, each ending in a newline."""

    return "".join(
        f"{line}\n"
        for line in text.splitlines()
        if any(pattern.search(line) for pattern in patterns)
    )


def values_at(answer: object, path: str) -> list[object]:
    """Every value *answer* holds at *path*, through each element of a ``[]`` list."""

    found: list[object] = [answer]
    for segment in path.split("."):
        key = segment.removesuffix("[]")
        below: list[object] = []
        for value in found:
            if not isinstance(value, dict) or key not in value:
                continue
            inner = cast("dict[str, object]", value)[key]
            if segment.endswith("[]") and isinstance(inner, list):
                below.extend(cast("list[object]", inner))
            else:
                below.append(inner)
        found = below
    return found


# ── The golden ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Block:
    """One command of the golden: its line, its exit status, and what it printed."""

    command: str
    status: str
    stdout: str
    stderr: str
    scenario: str

    @property
    def surface_id(self) -> str:
        return self.scenario.partition("/")[0]

    @property
    def environment(self) -> dict[str, str]:
        """The variables assigned before ``metab`` on the command line."""

        return dict(_split_command(self.command)[0])

    @property
    def argv(self) -> list[str]:
        """What follows ``metab`` on the command line."""

        return _split_command(self.command)[1]

    def payload(self) -> object | None:
        """The JSON object in stdout, or None when there is none."""

        start = self.stdout.find("{")
        if start < 0:
            return None
        try:
            return json.loads(self.stdout[start:])
        except ValueError:
            return None


def _split_command(command: str) -> tuple[list[tuple[str, str]], list[str]]:
    try:
        words = shlex.split(command)
    except ValueError as error:
        raise ContractError(f"`{command}` is not a command line: {error}") from error
    assignments: list[tuple[str, str]] = []
    while words and (found := _ASSIGNMENT.fullmatch(words[0])) and words[0] != "metab":
        assignments.append((found[1], found[2]))
        words = words[1:]
    if not words or words[0] != "metab":
        raise ContractError(f"`{command}` does not run metab")
    return assignments, words[1:]


def read_blocks(text: str) -> list[Block]:
    """The blocks of the golden's *text*, in order."""

    headers = list(_BLOCK_HEADER.finditer(text))
    blocks: list[Block] = []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        body = text[header.end() + 1 : end]
        sections: dict[str, str] = {}
        name = "stdout"
        start = 0
        for marker in _SECTION.finditer(body):
            sections[name] = body[start : marker.start()]
            name = marker[1]
            start = min(marker.end() + 1, len(body))
        sections[name] = body[start:]
        scenario = sections.get(SCENARIO_SECTION, "").strip()
        if not scenario:
            raise ContractError(f"`{header[1]}`: its block names no scenario")
        blocks.append(
            Block(
                command=header[1],
                status=header[2],
                stdout=sections.get("stdout", ""),
                stderr=sections.get("stderr", ""),
                scenario=scenario,
            )
        )
    return blocks


def argv_pattern(argv: Sequence[str]) -> list[re.Pattern[str]]:
    """One pattern for each declared word: itself, with any text for each ``{name}``."""

    patterns: list[re.Pattern[str]] = []
    for word in argv:
        parts = _PLACEHOLDER.split(word)
        patterns.append(re.compile(".*".join(re.escape(part) for part in parts), re.DOTALL))
    return patterns


def matches_argv(found: Sequence[str], declared: Sequence[str]) -> bool:
    """Whether the words *found* are the *declared* argument list with its values filled."""

    patterns = argv_pattern(declared)
    return len(found) == len(patterns) and all(
        pattern.fullmatch(word) for pattern, word in zip(patterns, found, strict=True)
    )
