"""The macOS app's contract with ``metab``, as ``apps/macos/metab-contract.toml`` declares it.

The declaration lists what the app in ``apps/macos`` depends on in ``metab``. This module
reads it, and holds the operations that the golden's driver
(``tests/test_app_contract_golden.py``) and the check (``devtools/check_app_contract.py``)
must agree on:

- **Projection.** The golden records what the app reads of an answer and nothing else:
  the declared keys of a JSON object (:func:`project`) and the part of each declared line
  that the app parses (:func:`read_lines`). So a field the app does not read can come and
  go without touching the golden, and a change to the golden is a change to something
  the app reads. A declared key that an answer no longer has is an error, not an
  omission.
- **Presence, not wording.** Text the app shows a person, and a value it keeps or hands
  back unread, is recorded as :data:`TEXT` or :data:`OPAQUE`: that it is there, and a
  string. A reworded message is no change to what the app reads.
- **Framing.** The app finds a command's JSON answer by the lines of its output, so the
  golden records the projection as ``metab`` framed the whole answer
  (:func:`framing_of`, :func:`dump`), and the lines of stderr that a reader of those
  lines would take (:func:`framing_lines`).
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
# What ``metab`` defines for each value the app holds a copy of, a line for each.
COPIES_NAME: Final = "app-contract-copies.txt"

# The section of a block that names its scenario: ``<id>`` or ``<id>/<scenario>``.
SCENARIO_SECTION: Final = "contract"
# What stands in a block for output the app shows a person and reads nothing of.
SHOWN_OUTPUT: Final = "<shown as written, not read>"
# What stands for text the app shows and never reads, and for a value it keeps or hands
# back unread.
TEXT: Final = "<text>"
OPAQUE: Final = "<opaque>"
OWN_PREFIX: Final = "own:"
# Where a `pinned_by` that is a file, not a test function, may be: a browserless session
# or a golden. Such a pin says in `holds` what the file must contain.
PIN_FILE_ROOTS: Final = ("tests/dom/", "tests/golden/")

_PLACEHOLDER: Final = re.compile(r"\{[a-z_]+\}")
_BLOCK_HEADER: Final = re.compile(r"^# (.+)\nexit: (\S+)\n--- stdout ---$", re.MULTILINE)
_SECTION: Final = re.compile(r"^--- ([a-z]+) ---$", re.MULTILINE)
_ASSIGNMENT: Final = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.DOTALL)
_VALUE_REFERENCE: Final = re.compile(
    r"(?:[a-z_][a-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*|pyproject\.toml:[a-z.]+)"
)


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
    # Keys whose text the app shows and never reads, and keys it keeps or hands back unread.
    shown_keys: tuple[str, ...] = ()
    opaque: tuple[str, ...] = ()
    stdout: tuple[str, ...] = ()
    stderr: tuple[str, ...] = ()
    # The whole output is shown as written.
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

    @property
    def masks(self) -> dict[str, str]:
        """Each key recorded by its presence, with what stands for its value."""

        return {**dict.fromkeys(self.shown_keys, TEXT), **dict.fromkeys(self.opaque, OPAQUE)}


@dataclass(frozen=True, slots=True)
class Line:
    id: str
    pattern: re.Pattern[str]
    source: str
    golden: str = ""
    pinned_by: str = ""
    holds: str = ""
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
    what holds the two sides together, and the definitions of ``metab``'s it rests on."""

    # "behavior", "copy", or "app_side".
    kind: str
    id: str
    what: str
    pinned_by: str
    source: str = ""
    golden: str = ""
    # What a `pinned_by` that names a file must contain.
    holds: str = ""
    # ``module:NAME`` or ``pyproject.toml:dotted.key``, each a line of the copies golden.
    values: tuple[str, ...] = ()


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

    @property
    def value_references(self) -> tuple[str, ...]:
        """Every definition of ``metab``'s an entry names, in the order declared, once."""

        return tuple(dict.fromkeys(name for item in self.pinned for name in item.values))


FILE_KINDS: Final = ("launch", "json", "http", "script")
_READ_KEYS: Final = frozenset({"json", "values", "values_in", "shown", "opaque"})
_SURFACE_KEYS: Final = {
    "command": _READ_KEYS
    | {"id", "argv", "source", "stdout", "stderr", "output", "app_runs", "because", "note"},
    "route": _READ_KEYS | {"id", "route", "literal", "source", "note"},
}
_TABLE_KEYS: Final = {
    "line": frozenset({"id", "pattern", "source", "golden", "pinned_by", "holds", "note"}),
    "env": frozenset({"name", "source", "metab", "golden", "note"}),
    "behavior": frozenset({"id", "source", "what", "pinned_by", "holds", "golden", "values"}),
    "copy": frozenset({"swift", "source", "metab", "pinned_by", "holds", "values"}),
    "app_side": frozenset({"id", "what", "pinned_by", "holds", "values"}),
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


def is_pin_file(reference: str) -> bool:
    """Whether a ``pinned_by`` names a session or a golden, not a test function."""

    return "::" not in reference and reference.startswith(PIN_FILE_ROOTS)


def _pin(table: Mapping[str, object], where: str, *, required: bool) -> tuple[str, str]:
    """A table's ``pinned_by`` and ``holds``, held to the two forms a pin takes."""

    reference = _text(table, "pinned_by", where, required=required)
    holds = _text(table, "holds", where, required=False)
    if not reference:
        if holds:
            raise ContractError(f"{where}: `holds` says what a `pinned_by` file must contain")
        return "", ""
    path, _, name = reference.partition("::")
    if name:
        if not path.endswith((".py", ".swift")) or holds:
            raise ContractError(
                f"{where}: `{reference}` names a test function, which is a Python or Swift "
                "file, `::`, and its name, with no `holds`"
            )
    elif not is_pin_file(reference) or not holds:
        raise ContractError(
            f"{where}: `pinned_by` is a test function, as `path::name`, or a file under "
            f"{' or '.join(PIN_FILE_ROOTS)} with what it must contain in `holds`"
        )
    return reference, holds


def _surface(kind: str, table: dict[str, object]) -> Surface:
    where = f"[[{kind}]] {table.get('id', '(no id)')}"
    _known(table, _SURFACE_KEYS[kind], where)
    identifier = _text(table, "id", where)
    json_paths = _strings(table.get("json", []), f"{where}: json")
    values = _values(table, where)
    shown_keys = _strings(table.get("shown", []), f"{where}: shown")
    opaque = _strings(table.get("opaque", []), f"{where}: opaque")
    for name, keys in (("values", values), ("shown", shown_keys), ("opaque", opaque)):
        for key in keys:
            if key not in json_paths:
                raise ContractError(f"{where}: {name} names `{key}`, which `json` does not list")
    told_apart = set(values)
    for key in (*shown_keys, *opaque):
        if key in told_apart or (key in shown_keys and key in opaque):
            raise ContractError(
                f"{where}: `{key}` is one of a value the app tells apart, text it shows, "
                "or a value it keeps unread, and not two"
            )
    values_in = _text(table, "values_in", where, required=False)
    note = _text(table, "note", where, required=False)
    if kind == "route":
        route = _text(table, "route", where)
        return Surface(
            id=identifier,
            kind=kind,
            argv=("{root}", "--api", route),
            source=_text(table, "source", where),
            json=json_paths,
            values=values,
            values_in=values_in,
            shown_keys=shown_keys,
            opaque=opaque,
            note=note,
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
        values_in=values_in,
        shown_keys=shown_keys,
        opaque=opaque,
        stdout=_strings(table.get("stdout", []), f"{where}: stdout"),
        stderr=_strings(table.get("stderr", []), f"{where}: stderr"),
        shown=output == "shown",
        app_runs=app_runs,
        because=because,
        note=note,
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


def _value_references(table: Mapping[str, object], where: str) -> tuple[str, ...]:
    names = _strings(table.get("values", []), f"{where}: values")
    for name in names:
        if not _VALUE_REFERENCE.fullmatch(name):
            raise ContractError(
                f"{where}: `{name}` names no definition; write `module:NAME`, or "
                "`pyproject.toml:dotted.key`"
            )
    return names


def _pinned(kind: str, table: dict[str, object]) -> Pinned:
    name = table.get("id", table.get("swift", "(unnamed)"))
    where = f"[[{kind}]] {name}"
    _known(table, _TABLE_KEYS[kind], where)
    reference, holds = _pin(table, where, required=True)
    names = _value_references(table, where)
    if kind == "copy":
        swift = _text(table, "swift", where)
        return Pinned(
            kind,
            swift,
            f"{swift}: {_text(table, 'metab', where)}",
            reference,
            _text(table, "source", where),
            holds=holds,
            values=names,
        )
    return Pinned(
        kind,
        _text(table, "id", where),
        _text(table, "what", where),
        reference,
        _text(table, "source", where, required=kind == "behavior"),
        _text(table, "golden", where, required=False),
        holds,
        names,
    )


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
        reference, holds = _pin(table, where, required=False)
        lines.append(
            Line(
                id=_text(table, "id", where),
                pattern=pattern,
                source=_text(table, "source", where),
                golden=_text(table, "golden", where, required=False),
                pinned_by=reference,
                holds=holds,
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
    pinned = [
        _pinned(kind, table)
        for kind in ("behavior", "copy", "app_side")
        for table in _tables(document, kind)
    ]
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
        item.id for item in contract.pinned if item.kind != "copy"
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


def _masked(value: object, mask: str | None, where: str) -> object:
    """*value* as the golden records it: itself, or *mask* for a string that is there."""

    if mask is None or value is None:
        return value
    if not isinstance(value, str) or not value:
        raise ContractError(
            f"{where}: is declared as text the app shows or keeps unread, and the answer "
            f"holds {value!r}"
        )
    return mask


def _project(
    value: object, tree: Mapping[str, Any], where: str, path: str, masks: Mapping[str, str]
) -> object:
    if not tree:
        return _masked(value, masks.get(path), where)
    if value is None:
        return value
    if not isinstance(value, dict):
        raise ContractError(f"{where}: the app reads keys of it, and it is not an object")
    found = cast("dict[str, object]", value)
    kept: dict[str, object] = {}
    for segment, below in tree.items():
        key = segment.removesuffix("[]")
        here = f"{where}.{key}" if where else key
        declared = f"{path}.{segment}" if path else segment
        if key not in found:
            raise ContractError(f"{here}: the app reads this key, and the answer does not have it")
        inner = found[key]
        if segment.endswith("[]") and inner is not None:
            if not isinstance(inner, list):
                raise ContractError(f"{here}: the app reads it as a list, and it is not one")
            kept[key] = [
                _project(item, below, f"{here}[{index}]", declared, masks)
                for index, item in enumerate(cast("list[object]", inner))
            ]
        else:
            kept[key] = _project(inner, below, here, declared, masks)
    return kept


def project(answer: object, paths: Sequence[str], masks: Mapping[str, str] | None = None) -> object:
    """*answer* with only the keys *paths* name, in the order they are declared.

    A key the declaration names and the answer lacks is a :class:`ContractError`: the app
    would read nothing where it expects a value. A null where an object or a list is
    declared stays null, as ``refusal`` is for a plan. A key in *masks* is recorded as its
    mask when the answer holds a string there, and is an error when it holds anything
    else but null.
    """

    return _project(answer, _path_tree(paths), "", "", masks or {})


def read_lines(text: str, patterns: Sequence[re.Pattern[str]]) -> str:
    """What the app reads of the lines of *text*: for each line one of *patterns* finds,
    the part the pattern matches, with :data:`TEXT` for anything before or after it."""

    read: list[str] = []
    for line in text.splitlines():
        found = next((match for pattern in patterns if (match := pattern.search(line))), None)
        if found is not None:
            before = TEXT if line[: found.start()] else ""
            after = TEXT if line[found.end() :] else ""
            read.append(f"{before}{found[0]}{after}\n")
    return "".join(read)


def is_read_line(line: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    """Whether *line*, as a golden records one, is the part a pattern matches and at most
    :data:`TEXT` on either side."""

    for pattern in patterns:
        found = pattern.search(line)
        if found and line[: found.start()] in ("", TEXT) and line[found.end() :] in ("", TEXT):
            return True
    return False


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


# ── Framing ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Framing:
    """How a command wrote its JSON answer: the two choices that change its lines."""

    indent: int | None
    ensure_ascii: bool


# What `json.dumps` is asked for across metab's modes, the indented forms first.
_FRAMINGS: Final = tuple(
    Framing(indent, ensure_ascii) for indent in (2, None, 4) for ensure_ascii in (False, True)
)


def dump(value: object, framing: Framing) -> str:
    return json.dumps(value, indent=framing.indent, ensure_ascii=framing.ensure_ascii)


def split_json(stdout: str) -> tuple[str, object, str, str]:
    """What precedes the JSON object in *stdout*, the object, its text, and what follows."""

    start = stdout.find("{")
    if start < 0:
        raise ContractError(f"printed no JSON object: {stdout!r}")
    try:
        answer, end = json.JSONDecoder().raw_decode(stdout, start)
    except ValueError as error:
        raise ContractError(f"printed JSON that does not parse: {error}") from error
    return stdout[:start], answer, stdout[start:end], stdout[end:]


def framing_of(raw: str, answer: object) -> Framing:
    """The framing that writes *answer* as *raw*, which is how the command wrote it.

    The golden then records the projection in the same framing, so a command that began
    to print its answer on one line, or to escape what it printed raw, changes the golden
    as it changes what the app's line reader finds.
    """

    for framing in _FRAMINGS:
        if dump(answer, framing) == raw:
            return framing
    raise ContractError(
        "printed its JSON answer in a framing this driver does not know, so the golden "
        "cannot record what the app's reader would find"
    )


def framing_lines(text: str) -> str:
    """The lines of *text* as a reader that looks for a JSON answer sees them: a line it
    would take as part of one as written, and :data:`TEXT` for each it passes over."""

    return "".join(
        f"{line if line.strip().startswith(('{', '}')) else TEXT}\n" for line in text.splitlines()
    )


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

        try:
            return split_json(self.stdout)[1]
        except ContractError:
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


def copies_text(defined: Mapping[str, str]) -> str:
    """The copies golden for *defined*, each definition's name and its value as text."""

    return "".join(f"{name} = {value}\n" for name, value in defined.items())


def read_copies(text: str) -> dict[str, str]:
    """The definitions a copies golden records, by name."""

    return dict(line.split(" = ", 1) for line in text.splitlines() if " = " in line)
