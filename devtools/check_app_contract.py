"""Fail the build when the macOS app and ``metab`` disagree about what the app depends on.

``apps/macos/metab-contract.toml`` declares that contract, and
``tests/golden/app-contract.txt`` records it as ``metab`` answers it. The app updates
apart from the ``metab`` a user has installed, so a change on either side that the other
does not follow breaks a release that is already on someone's Mac. A declaration nobody
checks would only describe the contract on the day it was written, so this holds it to
both sides:

- **The app's sources.** Every flag, route, and variable the Swift sources name is
  declared, and every file that starts a process, decodes JSON, sends a request, or
  scripts a page is listed with what it runs or reads. So a new dependency fails here
  until it is declared, and a declared one the sources no longer name fails as stale.
  The sources are read as text (``devtools/swift_text.py``), because this runs in every
  CI job and the app's own tests run only on macOS.
- **The goldens.** Every declared command and route has a block whose command line is
  the declared argument list, and a block holds exactly the declared keys and lines,
  with text the app only shows recorded as present and not word for word. Every value
  of ``metab``'s that the app copies is a line of the copies golden.
- **The changelog.** A branch that changes what is declared, a golden, or a copied value
  names the change in a changelog fragment, and no patch release's section holds one
  that is not a fix.

Whether the app's code builds the declared argument lists and reads the recorded answers
is not this check's: ``AppContractTests.swift`` runs the app's own builders and readers
against the golden.

**What no search here finds,** so review declares it, as it declares a new functional
aspect in the parity registry:

- a new reader of a line of output, which is ordinary string handling;
- a key a listed JSON file comes to read through an Optional property of a ``Decodable``
  type: a subscript and a coding key's raw value are searched, a bare property is not,
  and a missing Optional reads as nil, so the app's tests pass without it;
- a command built as ``.init(…)`` where the type is inferred, which is not spelled
  ``LaunchSpec(``; and a request made as ``webView.load(.init(url:))`` or
  ``Data(contentsOf:)``, which names neither ``URLRequest`` nor ``URLSession``;
- a short flag, and a flag or a route assembled from parts;
- a route not spelled ``api/…``, such as a page's address;
- anything the app comes to rely on in a page except through its own script, which is
  listed under ``[files.script]``.

    python -m devtools.check_app_contract check --against origin/main
    python -m devtools.check_app_contract report
    python -m devtools.check_app_contract accepts /path/to/metab

``docs/project/architecture/arch-app-contract.md`` describes the contract.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final, cast

from devtools import app_contract, changelog, check_ci, swift_text
from devtools.app_contract import Block, Contract, ContractError, Surface

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
APP: Final = "apps/macos"
DECLARATION: Final = f"{APP}/metab-contract.toml"
GOLDEN_DIR: Final = "tests/golden"
GOLDEN: Final = f"{GOLDEN_DIR}/{app_contract.GOLDEN_NAME}"
COPIES: Final = f"{GOLDEN_DIR}/{app_contract.COPIES_NAME}"
# What `metab` answers and defines: a change to either is a change to the contract.
GOLDENS: Final = (GOLDEN, COPIES)
# The workflow that runs the app's tests, on a change to a path its filters name.
APP_WORKFLOW: Final = ".github/workflows/macos-app.yml"
# The app's live tests run the real `metab`, so what they pass it is searched too.
LIVE_TESTS: Final = "Tests/ShellCoreTests/LiveMetabTests.swift"
# The one place a child is spawned; every command reaches it through a `LaunchSpec`.
SPAWN_FILE: Final = "Sources/ShellCore/Supervision/ServerProcess.swift"
# Where `MetabRequirement.requiredFlags`, the flags setup probes a `metab` with, is set.
REQUIREMENT_FILE: Final = "Sources/ShellCore/Setup/MetabVersion.swift"
PROBE_ID: Final = "version-probe"

# A changelog entry that names a change to the contract, and one that names a fix: metab
# answered the same surface wrongly. The first ships in a minor or major release; the
# second may ship in a patch (docs/publishing.md, "Choosing a Version").
CHANGE_MARK: Final = "- **App contract:**"
FIX_MARK: Final = "- **App contract fix:**"

_FLAG: Final = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")
# A variable of metab's, or of the interpreter that runs it.
_VARIABLE: Final = re.compile(r"\b(?:METAB(?:ROWSER)?_[A-Z0-9_]+|PYTHON[A-Z]+)\b")
# A key a Swift file reads of a JSON object: a subscript, or a coding key's raw value.
_SUBSCRIPT_KEY: Final = re.compile(r'\[\s*"([a-z][a-z0-9_]*)"\s*\]')
_CODING_KEYS: Final = re.compile(r"\benum\s+CodingKeys\b[^{]*\{([^}]*)\}")
_RAW_VALUE: Final = re.compile(r'\bcase\s+\w+\s*=\s*"([a-z][a-z0-9_]*)"')
_ROUTE: Final = re.compile(r"/?\bapi/[a-z0-9_-]+(?:/[a-z0-9_-]+)*")
_FILE_USE: Final = {
    "launch": re.compile(r"\bLaunchSpec\("),
    "json": re.compile(r"\b(?:JSONDecoder|JSONSerialization)\b"),
    "http": re.compile(r"\b(?:URLSession|URLRequest)\b"),
    "script": re.compile(
        r"\b(?:WKUserScript|WKScriptMessageHandler|evaluateJavaScript|callAsyncJavaScript)\b"
    ),
}
_FILE_USE_SAYS: Final = {
    "launch": "builds a command to run (`LaunchSpec(`)",
    "json": "decodes JSON",
    "http": "sends a request",
    "script": "scripts a page",
}
# What a file's line in `[files.*]` says when what it uses is the app's own.
_FILE_USE_OWN: Final = {
    "launch": "what it runs",
    "json": "whose JSON it is",
    "http": "what it requests",
    "script": "what it scripts",
}
_SPAWN: Final = re.compile(r"\bposix_spawnp?\(|\bProcess\(\)|\bNSTask\b")
_REQUIRED_FLAGS: Final = re.compile(r"static\s+let\s+requiredFlags\s*=\s*\[([^\]]*)\]")
_RELEASE_HEADING: Final = re.compile(r"^## (\d+)\.(\d+)\.(\d+)\b.*$", re.MULTILINE)
_SECTION_END: Final = re.compile(r"^#{1,2} ", re.MULTILINE)
# A short `metab` command that starts no server answers in under a second.
ACCEPTS_TIMEOUT_SECONDS: Final = 60
# What each placeholder is filled with when a `metab` is asked whether it takes a
# command's flags; `--version` answers before any of them is read.
_PROBE_VALUES: Final = {
    "root": ".",
    "folder": ".",
    "port": "8411",
    "link": "https://github.com/octo/demo",
    "url": "https://github.com/octo/demo",
    "target": "https://github.com/octo/demo",
    "limit": "100",
    "after": "",
    "path": "README.md",
}


# ── Reading the tree ────────────────────────────────────────────────


def _read(root: Path, relative: str) -> str | None:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except OSError:
        return None


def app_sources(root: Path) -> dict[str, str]:
    """The app's Swift sources and its live tests, by path under ``apps/macos``."""

    app = root / APP
    found = {
        path.relative_to(app).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted((app / "Sources").rglob("*.swift"))
    }
    live = _read(root, f"{APP}/{LIVE_TESTS}")
    if live is not None:
        found[LIVE_TESTS] = live
    return found


def _literals(source: str) -> list[str]:
    return [segment.text for segment in swift_text.strings(source)]


def _named(sources: Mapping[str, str], pattern: re.Pattern[str]) -> dict[str, list[str]]:
    """What *pattern* finds in the string literals of *sources*, with the files it is in."""

    found: dict[str, list[str]] = {}
    for path, source in sources.items():
        for literal in _literals(source):
            for name in pattern.findall(literal):
                files = found.setdefault(name, [])
                if path not in files:
                    files.append(path)
    return found


def _mentions(source: str, word: str) -> bool:
    """Whether *source* holds *word* as a whole string literal or as an identifier."""

    if any(literal == word for literal in _literals(source)):
        return True
    return re.search(rf"(?<![\w.]){re.escape(word)}\b", swift_text.code(source)) is not None


# ── The declaration against the app's sources ───────────────────────


def _declared_routes(contract: Contract) -> dict[str, Surface]:
    """Every route the contract names: a route's own, and one a command passes ``--api``."""

    routes: dict[str, Surface] = {}
    for surface in contract.surfaces:
        if surface.kind == "route":
            routes[surface.route] = surface
        elif "--api" in surface.argv:
            route = surface.argv[surface.argv.index("--api") + 1]
            routes[route.partition("?")[0]] = surface
    return routes


def source_problems(contract: Contract, sources: Mapping[str, str]) -> list[str]:
    """Where the declaration and the app's Swift sources disagree."""

    problems: list[str] = []
    for where, path in _source_references(contract):
        if path not in sources:
            problems.append(f"{where}: its source {path} is not one of the app's Swift files")

    # Flags.
    declared_flags = {flag for surface in contract.surfaces for flag in surface.flags}
    used_flags = _named(sources, _FLAG)
    for flag, files in sorted(used_flags.items()):
        if flag not in declared_flags | contract.other_flags:
            problems.append(
                f"{', '.join(files)}: passes or shows `{flag}`, which the contract does not "
                f"declare. If metab takes it, add it to the `argv` of its [[command]] in "
                f'{DECLARATION}; if another tool does, add "{flag}" to `flags` under [other]'
            )
    needed = {
        flag
        for surface in contract.surfaces
        if surface.app_runs or surface.shown
        for flag in surface.flags
    }
    for flag in sorted((needed | contract.other_flags) - set(used_flags)):
        problems.append(f"the contract declares `{flag}`, which no Swift source names any more")

    # Variables.
    declared_variables = {variable.name for variable in contract.variables}
    used_variables = _named(sources, _VARIABLE)
    for name, files in sorted(used_variables.items()):
        if name not in declared_variables | contract.other_env:
            problems.append(
                f"{', '.join(files)}: names `{name}`, which the contract does not declare. "
                f"If metab reads it, add to {DECLARATION}:\n"
                f'    [[env]]\n    name = "{name}"\n    source = "{files[0]}"\n'
                '    metab = "src/metabrowser/<the module that reads it>"\n'
                f"  If it is the app's own or the interpreter's, add \"{name}\" to `env` "
                "under [other]"
            )
    for name in sorted((declared_variables | contract.other_env) - set(used_variables)):
        problems.append(f"the contract declares `{name}`, which no Swift source names any more")

    # Routes.
    declared_routes = _declared_routes(contract)
    for spelled, files in sorted(_named(sources, _ROUTE).items()):
        route = "/" + spelled.lstrip("/")
        if route not in declared_routes:
            problems.append(
                f"{', '.join(files)}: asks for `{route}`, which the contract does not "
                f"declare. Add to {DECLARATION}:\n"
                f'    [[route]]\n    id = "<a name>"\n    route = "{route}"\n'
                f'    literal = "{spelled}"\n    source = "{files[0]}"\n'
                '    json = ["<each key the app reads>"]'
            )
    for surface in contract.surfaces:
        source = sources.get(surface.source, "")
        if surface.kind == "route" and surface.literal not in _literals(source):
            problems.append(
                f'[[route]] {surface.id}: {surface.source} no longer spells it "{surface.literal}"'
            )

    # Files that start a process, decode JSON, send a request, or script a page.
    for kind, pattern in _FILE_USE.items():
        declared = contract.files[kind]
        for path, source in sources.items():
            if not path.startswith("Sources/"):
                continue
            count = len(pattern.findall(swift_text.code(source)))
            if count and path not in declared:
                problems.append(
                    f"{path}: {_FILE_USE_SAYS[kind]}, and [files.{kind}] does not list it. "
                    f"{_file_line(kind, path, count)}"
                )
            elif kind == "launch" and path in declared and count != declared[path].sites:
                problems.append(
                    f"{path}: builds a command in {count} places, and [files.launch] says "
                    f"{declared[path].sites}. Set `sites = {count}` on its line in "
                    f"[files.launch] of {DECLARATION}, and add to its `runs` the id of the "
                    "[[command]] the new one runs"
                )
        for path in declared:
            source = sources.get(path)
            if source is None or not pattern.search(swift_text.code(source)):
                problems.append(f"[files.{kind}] {path}: no longer {_FILE_USE_SAYS[kind]}")
    launched = {identifier for use in contract.files["launch"].values() for identifier in use.ids}
    for surface in contract.surfaces:
        if surface.kind == "command" and surface.app_runs and surface.id not in launched:
            problems.append(f"[[command]] {surface.id}: no file in [files.launch] runs it")
    for path, source in sources.items():
        spawns = path != SPAWN_FILE and path.startswith("Sources/")
        if spawns and _SPAWN.search(swift_text.code(source)):
            problems.append(
                f"{path}: starts a process by itself. Every command goes through a "
                f"`LaunchSpec`, which {SPAWN_FILE} alone spawns, so that this check sees it"
            )

    # The keys and values a reader is declared to read are still in its source.
    for surface in contract.surfaces:
        source = sources.get(surface.source, "")
        for path in surface.json:
            for segment in path.split("."):
                key = segment.removesuffix("[]")
                if not _mentions(source, key):
                    problems.append(
                        f"{surface.id}: declares the key `{path}`, and {surface.source} no "
                        f"longer names `{key}`"
                    )
        for key, values in surface.values.items():
            for value in values:
                if not _mentions(source, value):
                    problems.append(
                        f"{surface.id}: declares the value `{value}` of `{key}`, and "
                        f"{surface.source} no longer names it"
                    )

    problems += _read_key_problems(contract, sources)
    problems += _probe_problems(contract, sources)
    return problems


def _file_line(kind: str, path: str, count: int) -> str:
    """The line to add for a file `[files.<kind>]` does not list, ready to paste."""

    own = f'"own: <{_FILE_USE_OWN[kind]}>"'
    value = f"{{ sites = {count}, runs = [{own}] }}" if kind == "launch" else f"[{own}]"
    return (
        f'Add to [files.{kind}] in {DECLARATION}:\n    "{path}" = {value}\n'
        "  If what it uses is metab's, declare that as a [[command]], [[route]], or "
        "[[behavior]], and write its id in place of the `own:` text"
    )


def _read_key_problems(contract: Contract, sources: Mapping[str, str]) -> list[str]:
    """A key a listed file reads of a JSON answer, which that answer's entry lacks.

    In a file `[files.json]` lists with a contract id, every key in a subscript
    (``page["sources"]``) or a coding key's raw value (``case openedAt = "opened_at"``)
    is a segment of a path that one of its entries declares.
    """

    problems: list[str] = []
    for path, use in contract.files["json"].items():
        surfaces = [found for name in use.ids if (found := contract.surface(name))]
        source = sources.get(path)
        if not surfaces or source is None:
            continue
        declared = {
            segment.removesuffix("[]")
            for surface in surfaces
            for declared_path in surface.json
            for segment in declared_path.split(".")
        }
        # Comments are prose, and a key in one reads nothing.
        text = "".join(
            f'"{segment.text}"' if segment.kind == "string" else segment.text
            for segment in swift_text.segments(source)
            if segment.kind in ("code", "string")
        )
        read = set(_SUBSCRIPT_KEY.findall(text))
        for body in _CODING_KEYS.findall(text):
            read |= set(_RAW_VALUE.findall(body))
        for key in sorted(read - declared):
            ids = ", ".join(surface.id for surface in surfaces)
            problems.append(
                f"{path}: reads the key `{key}`, which {ids} does not declare. Add its path "
                f"to that entry's `json` in {DECLARATION}"
            )
    return problems


def _source_references(contract: Contract) -> list[tuple[str, str]]:
    references = [(f"{surface.kind} {surface.id}", surface.source) for surface in contract.surfaces]
    references += [(f"line {line.id}", line.source) for line in contract.lines]
    references += [(f"env {variable.name}", variable.source) for variable in contract.variables]
    references += [
        (f"{item.kind} {item.id}", item.source) for item in contract.pinned if item.source
    ]
    return references


def required_flags(sources: Mapping[str, str]) -> list[str]:
    """``MetabRequirement.requiredFlags`` as the flags its members are set to.

    The list names constants, ``CLIServeLaunch.exitOnEOF`` among them, each set once to a
    string in the file that declares its type.
    """

    requirement = sources.get(REQUIREMENT_FILE, "")
    found = _REQUIRED_FLAGS.search(swift_text.code(requirement))
    if found is None:
        raise ContractError(f"{REQUIREMENT_FILE} no longer sets `requiredFlags` to a list")
    flags: list[str] = []
    for member in (word.strip() for word in found[1].split(",") if word.strip()):
        owner, _, name = member.rpartition(".")
        declares = re.compile(rf"\b(?:enum|struct|class)\s+{re.escape(owner)}\b")
        value = re.compile(rf'static\s+let\s+{re.escape(name)}(?:\s*:\s*String)?\s*=\s*"([^"]+)"')
        values = [
            match[1]
            for source in sources.values()
            if declares.search(swift_text.code(source))
            for match in value.finditer(source)
        ]
        if len(values) != 1:
            raise ContractError(
                f"`{member}` in requiredFlags is not a constant set once to a string, so "
                "this check cannot read the flag it names"
            )
        flags.append(values[0])
    return flags


def _probe_problems(contract: Contract, sources: Mapping[str, str]) -> list[str]:
    """The declared probe is the flags setup probes a ``metab`` with, then ``--version``."""

    probe = contract.surface(PROBE_ID)
    if probe is None:
        return [f"the contract declares no [[command]] {PROBE_ID}, setup's check of a metab"]
    try:
        expected = [*required_flags(sources), "--version"]
    except ContractError as error:
        return [str(error)]
    if list(probe.argv) != expected:
        return [
            f"[[command]] {PROBE_ID}: declares `{' '.join(probe.argv)}`, and the app probes "
            f"with `{' '.join(expected)}` (MetabRequirement.requiredFlags, then --version)"
        ]
    return []


# ── The declaration against the goldens ─────────────────────────────


def _pin_problem(root: Path, reference: str, holds: str) -> str | None:
    """Why *reference* pins nothing, or None.

    ``path::name`` names a test function of a Python module or of one of the app's Swift
    suites. A path alone names a browserless session or a golden, which must contain
    *holds*: the selector, the message, or the line that the entry depends on.
    """

    path, _, name = reference.partition("::")
    text = _read(root, path)
    if text is None:
        return f"`{path}` is missing"
    if not name:
        return None if holds in text else f"`{path}` does not contain `{holds}`"
    if path.endswith(".swift"):
        declares = rf"@Test\b[^\n]*\bfunc {re.escape(name)}\("
        found = re.search(declares, swift_text.code(text))
    else:
        found = re.search(rf"^(?:async )?def {re.escape(name)}\(", text, re.MULTILINE)
    return None if found else f"`{reference}` names no test"


def _block_problems(contract: Contract, block: Block) -> list[str]:
    """Why one block of the golden is not what its surface declares."""

    where = f"{app_contract.GOLDEN_NAME}: `{block.scenario}`"
    surface = contract.surface(block.surface_id)
    if surface is None:
        return [f"{where}: runs something the contract does not declare"]
    problems: list[str] = []
    if not app_contract.matches_argv(block.argv, surface.argv):
        problems.append(
            f"{where}: runs `{block.command}`, which is not the declared "
            f"`metab {' '.join(surface.argv)}`"
        )
    declared = {variable.name for variable in contract.variables}
    for name in block.environment:
        if _VARIABLE.fullmatch(name) and name not in declared:
            problems.append(f"{where}: sets `{name}`, which the contract does not declare")
    if surface.shown:
        if block.stdout not in ("", f"{app_contract.SHOWN_OUTPUT}\n") or block.stderr:
            problems.append(f"{where}: records output the app shows as written and never reads")
        return problems
    if surface.json:
        answer = block.payload()
        if answer is None:
            return [*problems, f"{where}: records no JSON answer"]
        try:
            read = app_contract.project(answer, surface.json)
        except ContractError as error:
            return [*problems, f"{where}: {error}"]
        if read != answer:
            problems.append(f"{where}: records keys the contract does not declare the app reads")
        for path, mask in surface.masks.items():
            for value in app_contract.values_at(answer, path):
                if value is not None and value != mask:
                    problems.append(
                        f"{where}: records what `{path}` says, and the app only shows it or "
                        f"keeps it unread; the golden holds `{mask}` there"
                    )
        for line in block.stderr.splitlines():
            if line != app_contract.TEXT and not line.strip().startswith(("{", "}")):
                problems.append(
                    f"{where}: records the stderr line `{line}`, which no reader of a JSON "
                    f"answer takes; the golden holds `{app_contract.TEXT}` for it"
                )
        return problems
    for stream, names, text in (
        ("stdout", surface.stdout, block.stdout),
        ("stderr", surface.stderr, block.stderr),
    ):
        patterns = [line.pattern for name in names if (line := contract.line(name))]
        for line in text.splitlines():
            if not app_contract.is_read_line(line, patterns):
                problems.append(
                    f"{where}: records the {stream} line `{line}`, which is not the part of "
                    "a declared line that the app parses"
                )
    return problems


def copies_problems(contract: Contract, root: Path) -> list[str]:
    """The copies golden holds a line for each definition an entry names, and no other."""

    text = _read(root, COPIES)
    if text is None:
        return [f"{COPIES} is missing; `make golden-update` writes it"]
    recorded = set(app_contract.read_copies(text))
    named = set(contract.value_references)
    problems = [
        f"{COPIES}: has no line for `{name}`, which an entry's `values` names; "
        "`make golden-update` writes it"
        for name in sorted(named - recorded)
    ]
    problems += [
        f"{COPIES}: records `{name}`, which no entry's `values` names"
        for name in sorted(recorded - named)
    ]
    return problems


def golden_problems(contract: Contract, root: Path) -> list[str]:
    """Where the declaration and the goldens disagree."""

    golden = _read(root, GOLDEN)
    if golden is None:
        return [f"{GOLDEN} is missing; `make golden-update` writes it"]
    try:
        blocks = app_contract.read_blocks(golden)
    except ContractError as error:
        return [f"{GOLDEN}: {error}"]
    problems: list[str] = []
    for block in blocks:
        try:
            problems += _block_problems(contract, block)
        except ContractError as error:
            problems.append(f"{GOLDEN}: {error}")
    if problems:
        return problems

    scenarios = [block.scenario for block in blocks]
    for scenario in sorted({name for name in scenarios if scenarios.count(name) > 1}):
        problems.append(f"{GOLDEN}: `{scenario}` names more than one block")
    by_surface: dict[str, list[Block]] = {}
    for block in blocks:
        by_surface.setdefault(block.surface_id, []).append(block)
    for surface in contract.surfaces:
        own = by_surface.get(surface.id, [])
        if not own:
            problems.append(
                f"{surface.kind} {surface.id}: {GOLDEN} has no block for it; add a scenario "
                "to tests/test_app_contract_golden.py and run `make golden-update`"
            )
            continue
        # Each value the app tells apart is shown by a block, or by the golden named.
        evidence = _read(root, f"{GOLDEN_DIR}/{surface.values_in}") if surface.values_in else None
        if surface.values_in and evidence is None:
            problems.append(f"{surface.id}: its `values_in` golden {surface.values_in} is missing")
        for path, values in surface.values.items():
            shown = {
                value
                for block in own
                for value in app_contract.values_at(block.payload(), path)
                if isinstance(value, str)
            }
            key = path.rpartition(".")[2].removesuffix("[]")
            for value in values:
                elsewhere = evidence is not None and f'"{key}": "{value}"' in evidence
                if value not in shown and not elsewhere:
                    problems.append(
                        f"{surface.id}: no golden shows `{key}` as `{value}`, a value the "
                        "contract declares the app tells apart"
                    )

    # Each line is shown by a golden, or held by a test where no transcript can show it.
    for line in contract.lines:
        readers = [
            (surface, stream)
            for surface in contract.surfaces
            for stream, names in (("stdout", surface.stdout), ("stderr", surface.stderr))
            if line.id in names
        ]
        if line.golden:
            text = _read(root, f"{GOLDEN_DIR}/{line.golden}")
            if text is None:
                problems.append(f"[[line]] {line.id}: its golden {line.golden} is missing")
            elif not any(line.pattern.search(found) for found in text.splitlines()):
                problems.append(f"[[line]] {line.id}: no line of {line.golden} matches its pattern")
        elif readers:
            recorded = [
                found
                for surface, stream in readers
                for block in by_surface.get(surface.id, [])
                for found in getattr(block, stream).splitlines()
            ]
            if not any(line.pattern.search(found) for found in recorded):
                problems.append(f"[[line]] {line.id}: no block of {GOLDEN} records it")
        elif not line.pinned_by:
            problems.append(
                f"[[line]] {line.id}: nothing shows it. Name the command that prints it, a "
                "`golden` that records it, or the test that holds it in `pinned_by`"
            )

    for variable in contract.variables:
        where = f"[[env]] {variable.name}"
        metab = _read(root, variable.metab)
        if metab is None or variable.name not in metab:
            problems.append(f"{where}: {variable.metab} does not name it")
        if variable.golden:
            text = _read(root, f"{GOLDEN_DIR}/{variable.golden}")
            if text is None or variable.name not in text:
                problems.append(f"{where}: its golden {variable.golden} does not set it")
        elif not any(variable.name in block.environment for block in blocks):
            problems.append(f"{where}: no block of {GOLDEN} sets it")

    references = [(f"[[line]] {line.id}", line.pinned_by, line.holds) for line in contract.lines]
    references += [
        (f"[[{item.kind}]] {item.id}", item.pinned_by, item.holds) for item in contract.pinned
    ]
    for where, reference, holds in references:
        if reference and (problem := _pin_problem(root, reference, holds)):
            problems.append(f"{where}: {problem}")
    for item in contract.pinned:
        if item.golden and _read(root, f"{GOLDEN_DIR}/{item.golden}") is None:
            problems.append(f"[[{item.kind}]] {item.id}: its golden {item.golden} is missing")
    return problems


def workflow_problems(root: Path) -> list[str]:
    """The app's workflow runs when the contract changes.

    Its path filters name the app's folder, which holds the declaration, and must name the
    golden too: the golden is what ``metab`` answers, and ``AppContractTests`` is what
    holds the app's readers to it, so a pull request that changes an answer has to run
    them. Each trigger with a filter names both.
    """

    try:
        workflow = check_ci.load(root / APP_WORKFLOW)
    except RuntimeError as error:
        return [f"{error}, so nothing is known to run the app's tests"]
    # YAML 1.1 reads a bare `on` key as true.
    triggers = workflow.get("on", cast("dict[object, object]", workflow).get(True))
    if not isinstance(triggers, dict):
        return [f"{APP_WORKFLOW}: has no triggers this check can read"]
    problems: list[str] = []
    for name in ("push", "pull_request"):
        trigger = cast("dict[str, object]", triggers).get(name)
        paths = (
            cast("dict[str, object]", trigger).get("paths") if isinstance(trigger, dict) else None
        )
        if not isinstance(paths, list):
            continue  # no filter: every change runs it
        for needed in (f"{APP}/**", GOLDEN):
            if needed not in cast("list[object]", paths):
                problems.append(
                    f"{APP_WORKFLOW}: its `{name}` path filter does not name `{needed}`, so a "
                    "change to the app contract would not run the app's tests"
                )
    return problems


# ── The changelog ───────────────────────────────────────────────────


def release_problems(changelog_text: str) -> list[str]:
    """Patch releases whose changelog section names a change to the contract.

    A patch release changes nothing the app reads unless it is a fix, so its section may
    hold an entry marked as a fix and none marked as a change.
    """

    problems: list[str] = []
    for heading in _RELEASE_HEADING.finditer(changelog_text):
        if int(heading[3]) == 0:
            continue
        rest = changelog_text[heading.end() :]
        end = _SECTION_END.search(rest)
        section = rest[: end.start()] if end else rest
        marked = [line for line in section.splitlines() if line.startswith(CHANGE_MARK)]
        if marked:
            version = f"{heading[1]}.{heading[2]}.{heading[3]}"
            problems.append(
                f"CHANGELOG.md: {version} is a patch release, and its section holds "
                f"{len(marked)} `{CHANGE_MARK}` "
                f"{'entry' if len(marked) == 1 else 'entries'}. A change to what the macOS "
                f"app reads ships in a minor or major release: release this as "
                f"{heading[1]}.{int(heading[2]) + 1}.0, or mark an entry `{FIX_MARK}` if it "
                "is a bug fix"
            )
    return problems


def _git(root: Path, *args: str) -> str:
    return changelog._git(root, *args)  # pyright: ignore[reportPrivateUsage]


def _at(root: Path, revision: str, path: str) -> str | None:
    """*path* as *revision* has it, or None when it does not."""

    try:
        return _git(root, "show", f"{revision}:{path}")
    except changelog.ChangelogError:
        return None


def declared_surface(text: str | None) -> object:
    """What a declaration's *text* says the app depends on, or None for no declaration
    or one that does not parse: what it sends and reads, and each behavior, copied value,
    and thing ``metab`` reads of the app, with the definitions it names.

    Two declarations with the same surface differ only in what a release need not name:
    a note, the test that pins an entry, or which Swift file holds a reader. What a pin
    file must contain is part of it: that is the text of the page or the transcript that
    the app depends on.
    """

    if text is None:
        return None
    try:
        contract = app_contract.parse(text)
    except ContractError:
        return None
    return (
        tuple(
            (
                surface.id,
                surface.argv,
                surface.json,
                tuple(sorted(surface.values.items())),
                surface.stdout,
                surface.stderr,
                surface.shown,
                surface.app_runs,
                surface.shown_keys,
                surface.opaque,
            )
            for surface in contract.surfaces
        ),
        tuple((line.id, line.pattern.pattern) for line in contract.lines),
        tuple(variable.name for variable in contract.variables),
        tuple((item.kind, item.id, item.values, item.holds) for item in contract.pinned),
    )


def _branch_marks(root: Path, base: str) -> set[str]:
    """The marks among the entries of the fragments this branch added or edited."""

    marks: set[str] = set()
    directory = root / changelog.FRAGMENTS
    names = sorted(path.name for path in directory.glob("*.md")) if directory.is_dir() else []
    for name in names:
        relative = f"{changelog.FRAGMENTS}/{name}"
        text = _read(root, relative)
        if not changelog.is_fragment(relative) or text is None or text == _at(root, base, relative):
            continue
        try:
            entries = changelog.parse_fragment(name, text).entries
        except changelog.ChangelogError:
            continue  # `changelog check` reports a fragment it cannot read
        marks |= {
            mark for mark in (CHANGE_MARK, FIX_MARK) for entry in entries if entry.startswith(mark)
        }
    return marks


def change_problems(root: Path, against: str) -> list[str]:
    """A branch that changes the contract and does not say so in a changelog fragment.

    A file changed when it differs from the merge base of *against* and ``HEAD``, and
    from *against* itself, which a merge of it in progress brings. A change to the
    declared surface, what the app depends on, is a change to the contract, and a
    fragment the branch adds or edits must name it with :data:`CHANGE_MARK`. A change to
    a golden alone is ``metab`` answering the same surface differently, or defining a
    value the app copies differently, which is either that or a bug fix, so either mark
    names it.
    """

    try:
        base = _git(root, "merge-base", against, "HEAD").strip()
    except changelog.ChangelogError as error:
        return [f"{error}\nThe app contract check compares with the merge base of {against}."]

    def differs(path: str, read: Callable[[str | None], object]) -> bool:
        now = read(_read(root, path))
        return now != read(_at(root, base, path)) and now != read(_at(root, against, path))

    surface = differs(DECLARATION, declared_surface)
    goldens = [path for path in GOLDENS if differs(path, lambda text: text)]
    marks = _branch_marks(root, base)
    if not (surface or goldens) or CHANGE_MARK in marks or (FIX_MARK in marks and not surface):
        return []
    where = f"since the merge base with {against} ({base[:12]})"
    remedy = (
        f"Name it in a changelog fragment, {changelog.FRAGMENTS}/<bead>.md, with an entry "
        f"that starts `{CHANGE_MARK}`, which ships in a minor or major release of metab"
    )
    after = (
        "Change the app in the same commit, and raise MetabRequirement.minimumRelease if the "
        "app now needs the newer metab (docs/project/architecture/arch-app-contract.md)."
    )
    if surface:
        fix = f" An entry marked `{FIX_MARK}` does not name it: a fix keeps what the app reads."
        return [
            f"{DECLARATION} declares a different surface {where}, so this branch changes what "
            f"the macOS app depends on in metab. {remedy}."
            f"{fix if FIX_MARK in marks else ''} {after}"
        ]
    return [
        f"{' and '.join(goldens)} changed {where}, so metab answers the macOS app differently "
        f"in something the app reads, or defines a value the app copies differently. {remedy}, "
        f"or `{FIX_MARK}` when the old answer was a bug, which may ship in a patch. {after}"
    ]


# ── The whole check ─────────────────────────────────────────────────


def check(root: Path = REPO_ROOT, against: str | None = None) -> list[str]:
    """Every problem with the contract under *root*."""

    try:
        contract = app_contract.load(root / DECLARATION)
    except ContractError as error:
        return [str(error)]
    problems = source_problems(contract, app_sources(root))
    problems += golden_problems(contract, root)
    problems += copies_problems(contract, root)
    problems += workflow_problems(root)
    text = _read(root, changelog.CHANGELOG)
    if text is not None:
        problems += release_problems(text)
    if against is not None:
        problems += change_problems(root, against)
    return problems


def report(contract: Contract) -> str:
    """The inventory, a line for each thing the app depends on."""

    lines: list[str] = []
    commands = [surface for surface in contract.surfaces if surface.kind == "command"]
    routes = [surface for surface in contract.surfaces if surface.kind == "route"]
    keys = sum(len(surface.json) for surface in contract.surfaces)
    counts = {
        "commands the app runs": sum(1 for surface in commands if surface.app_runs),
        "commands shown or kept for the golden": sum(1 for s in commands if not s.app_runs),
        "routes": len(routes),
        "JSON keys read": keys,
        "lines read": len(contract.lines),
        "variables": len(contract.variables),
        "behaviors": sum(1 for item in contract.pinned if item.kind == "behavior"),
        "copied values": sum(1 for item in contract.pinned if item.kind == "copy"),
        "read by metab of the app": sum(1 for item in contract.pinned if item.kind == "app_side"),
    }
    lines += [f"{count:3} {name}" for name, count in counts.items()]
    lines.append("")
    for surface in contract.surfaces:
        what = "route  " if surface.kind == "route" else "command"
        shape = surface.route if surface.kind == "route" else "metab " + " ".join(surface.argv)
        reads = ", ".join(surface.json) or ", ".join((*surface.stdout, *surface.stderr))
        reads = reads or ("shown as written" if surface.shown else "exit status")
        runs = "" if surface.app_runs else "  (not run by the app)"
        lines.append(f"{what} {surface.id}: {shape}{runs}\n          reads: {reads}")
    for line in contract.lines:
        lines.append(f"line    {line.id}: {line.pattern.pattern}")
    for variable in contract.variables:
        lines.append(f"env     {variable.name}")
    for item in contract.pinned:
        lines.append(f"{item.kind:9}{item.id}: {item.pinned_by}")
    return "\n".join(lines) + "\n"


def probe_commands(contract: Contract) -> list[tuple[Surface, list[str]]]:
    """Each command the app runs, with ``--version`` after it: what asks a ``metab``
    whether it takes the command's flags, as the app's own probe asks about three."""

    commands: list[tuple[Surface, list[str]]] = []
    for surface in contract.surfaces:
        if surface.kind != "command" or not surface.app_runs:
            continue
        argv = [word.format(**_PROBE_VALUES) for word in surface.argv]
        commands.append((surface, argv if "--version" in argv else [*argv, "--version"]))
    return commands


def accepts(contract: Contract, executable: str) -> list[str]:
    """The commands *executable* does not take, each with what it said.

    ``--version`` is answered before any other option is read, so a ``metab`` that knows
    every flag of a command prints its version and one that does not exits 2 naming the
    first it does not know. Nothing is served, opened, or written. A route is not asked:
    that needs a server.
    """

    refused: list[str] = []
    for surface, argv in probe_commands(contract):
        try:
            result = subprocess.run(
                [executable, *argv],
                capture_output=True,
                text=True,
                check=False,
                timeout=ACCEPTS_TIMEOUT_SECONDS,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            refused.append(f"{surface.id}: could not run `{executable}`: {error}")
            continue
        if result.returncode == 0 and re.search(r"^metab \S", result.stdout, re.MULTILINE):
            continue
        said = [line.strip(" │") for line in (result.stderr or result.stdout).splitlines()]
        # The line that names one of the command's flags, as the app's own probe reads it.
        named = next(
            (line for line in said if any(flag in line for flag in surface.flags)),
            said[-1] if said else "nothing",
        )
        refused.append(
            f"{surface.id}: `metab {' '.join(argv)}` exited {result.returncode}: {named}"
        )
    return refused


def referenced_files(contract: Contract) -> list[str]:
    """Every file the check reads besides the app's sources, by path from the root."""

    files = {DECLARATION, *GOLDENS, APP_WORKFLOW, changelog.CHANGELOG, f"{APP}/{LIVE_TESTS}"}
    goldens: Iterable[str] = [
        *(surface.values_in for surface in contract.surfaces),
        *(line.golden for line in contract.lines),
        *(variable.golden for variable in contract.variables),
        *(item.golden for item in contract.pinned),
    ]
    files |= {f"{GOLDEN_DIR}/{name}" for name in goldens if name}
    tests: Iterable[str] = [
        *(line.pinned_by for line in contract.lines),
        *(item.pinned_by for item in contract.pinned),
    ]
    files |= {reference.partition("::")[0] for reference in tests if reference}
    files |= {variable.metab for variable in contract.variables}
    return sorted(files)


def main(argv: Sequence[str] | None = None, root: Path = REPO_ROOT) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m devtools.check_app_contract",
        description="Check the macOS app's contract with metab (apps/macos/metab-contract.toml).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check_parser = commands.add_parser("check", help="compare the contract with both sides")
    check_parser.add_argument(
        "--against",
        metavar="REF",
        help="also fail when the contract changed since the merge base with REF and no "
        "changelog fragment names the change",
    )
    commands.add_parser("report", help="print the inventory")
    accepts_parser = commands.add_parser(
        "accepts", help="ask a metab executable whether it takes every command the app runs"
    )
    accepts_parser.add_argument("metab", help="the path of a metab executable")
    args = parser.parse_args(argv)

    if args.command == "check":
        problems = check(root, args.against)
        if problems:
            print("App contract check failed:")
            print("\n".join(f"- {problem}" for problem in problems))
            return 1
        print("App contract check passed.")
        return 0
    try:
        contract = app_contract.load(root / DECLARATION)
    except ContractError as error:
        print(error, file=sys.stderr)
        return 1
    if args.command == "report":
        print(report(contract), end="")
        return 0
    refused = accepts(contract, args.metab)
    if refused:
        print(f"{args.metab} does not take every command the macOS app runs:")
        print("\n".join(f"- {line}" for line in refused))
        return 1
    print(f"{args.metab} takes every command the macOS app runs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
