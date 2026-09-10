"""Fail the build when CLI goldens drift from registered routes and declared behavior.

Every data surface the browser consumes should be reachable from ``metab`` and
pinned by a golden transcript. A table nobody checks is worse than no table, so
this reads the parity table in the views/models/routes map and compares it to
what the code actually registers. Kind coverage is read from executable console
blocks, so mentioning a kind in surrounding prose cannot satisfy the gate.

Gap rows were permitted while the debt was paid down, and are not any more:
every registered surface is either covered by a transcript or exempt with a
reason. A new route or kind arrives with its golden or the build fails.

User-visible functional aspects are an explicit architecture registry because source
scanning cannot infer product semantics. The checker validates every declared owner,
tier, command, and evidence file; review remains responsible for declaring a new aspect.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_DOC = REPO_ROOT / "docs/project/architecture/arch-views-models-routes.md"
BUILTIN_PLUGINS = REPO_ROOT / "src/metabrowser/builtin_plugins"
SOURCE_ROOT = REPO_ROOT / "src/metabrowser"
GOLDEN_DIR = REPO_ROOT / "tests/golden"

_STATUSES = frozenset({"covered", "exempt"})
_FUNCTIONAL_TIERS = frozenset({"data", "interaction", "paint-exempt"})
# Modes that issue a route without naming it on the command line, mapped to the
# routes each one can actually issue. The mapping matters: crediting a mode for
# a surface it never touches is the same false evidence as crediting prose.
# `--api` is absent because it always names its route, so a row claiming it must
# show the route in a command. `--walk` and `--diff` are absent for the opposite
# reason: they reach their models through the library and issue no request at
# all, which is the model-versus-wire gap this check exists to close.
_INDIRECT_MODES: dict[str, tuple[str, ...]] = {
    "--check-api": ("/api/tree", "/api/recent", "/api/index/progress"),
}


@dataclass(frozen=True, slots=True)
class ParityRow:
    surface: str
    status: str
    cli: str
    evidence: str


@dataclass(frozen=True, slots=True)
class FunctionalParityRow:
    aspect: str
    tier: str
    owner: str
    command: str
    evidence: str


@dataclass(frozen=True, slots=True)
class InteractionSessionContract:
    executed_owners: frozenset[str]
    problem: str | None = None


@dataclass(frozen=True, slots=True)
class GoldenCommand:
    command: str
    output: tuple[str, ...]
    status: int


def _console_commands(golden: str) -> list[GoldenCommand]:
    """Parse executable tryscript commands with their output and exit status."""

    commands: list[GoldenCommand] = []
    in_console = False
    command_parts: list[str] = []
    output: list[str] = []
    status: int | None = None

    def finish() -> None:
        nonlocal command_parts, output, status
        if command_parts:
            command = " ".join(part.removesuffix("\\").rstrip() for part in command_parts)
            commands.append(
                GoldenCommand(
                    command=command,
                    output=tuple(output),
                    # Tryscript only prints ``? N`` for an expected nonzero
                    # exit. An omitted marker is the ordinary success form.
                    status=0 if status is None else status,
                )
            )
        command_parts = []
        output = []
        status = None

    for line in golden.splitlines():
        stripped = line.strip()
        if stripped == "```console":
            finish()
            in_console = True
            continue
        if stripped == "```" and in_console:
            finish()
            in_console = False
            continue
        if not in_console:
            continue
        if stripped.startswith("$ "):
            finish()
            command_parts = [stripped[2:]]
            continue
        if command_parts and command_parts[-1].endswith("\\") and stripped.startswith("> "):
            command_parts.append(stripped[2:])
            continue
        match = re.fullmatch(r"\? (-?\d+)", stripped)
        if command_parts and match is not None:
            status = int(match.group(1))
            continue
        if command_parts:
            output.append(stripped)
    finish()
    return commands


def _command_parts(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return []


def _route_token_matches(token: str, surface: str) -> bool:
    if token == surface:
        return True
    return token.startswith(surface) and len(token) > len(surface) and token[len(surface)] in "/?"


def _option_value(parts: list[str], option: str) -> str | None:
    """Return the value attached to one CLI option, if it has one."""

    try:
        index = parts.index(option)
    except ValueError:
        return None
    return parts[index + 1] if index + 1 < len(parts) else None


def _command_exercises(command: str, surface: str, cli: str) -> bool:
    """Whether one metab command reaches exactly the declared route shape."""

    parts = _command_parts(command)
    if not parts or parts[0] != "metab":
        return False
    api_value = _option_value(parts, "--api")
    if "--api" in cli and api_value is not None and _route_token_matches(api_value, surface):
        return True
    show_value = _option_value(parts, "--show")
    if "--show" in cli and show_value is not None:
        if surface == "/api/file" and not _route_token_matches(show_value, "/commit"):
            return True
        if surface == "/api/plugin/diff/comparison" and _route_token_matches(show_value, "/commit"):
            return True
        if surface in {"/view", "/commit"} and _route_token_matches(show_value, surface):
            return True
    for mode, surfaces in _INDIRECT_MODES.items():
        if mode in parts and mode in cli and surface in surfaces:
            return True
    return False


def _exercises(golden: str, surface: str, cli: str, *, successful_only: bool) -> bool:
    """Whether a transcript attempts, or successfully runs, a route surface."""

    return any(
        (not successful_only or command.status == 0)
        and _command_exercises(command.command, surface, cli)
        for command in _console_commands(golden)
    )


def registered_surfaces() -> set[str]:
    """Every ``/api/`` route registered anywhere in the package, plus plugin hooks."""

    surfaces: set[str] = set()
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        # The path may sit on the line after `Route(` when the registration is
        # wrapped, which a pattern anchored to `Route("` misses entirely.
        for route in re.findall(r'Route\(\s*"([^"]+)"', path.read_text(encoding="utf-8")):
            # Browser routes are surfaces too: `/view/<path>` and `/commit/<rev>`
            # are the addresses a reader lands on, and the four-layer model this
            # check enforces starts at the route. Enumerating only `/api/` left
            # them ungoverned even after --show learned to resolve them.
            if route.startswith(("/api/", "/view", "/commit", "/raw", "/_debug")):
                # Route patterns carry placeholders; the table documents the shape.
                surfaces.add(route.split("{", 1)[0].rstrip("/"))
    for manifest_path in sorted(BUILTIN_PLUGINS.glob("*/manifest.toml")):
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        name = manifest["plugin"]["name"]
        for hook in manifest.get("data_hook", []):
            surfaces.add(f"/api/plugin/{name}/{hook['route']}")
    return surfaces


def registered_kinds() -> set[str]:
    """Every built-in kind declared or consumed by a manifest view."""

    kinds: set[str] = set()
    for manifest_path in sorted(BUILTIN_PLUGINS.glob("*/manifest.toml")):
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        for rule in manifest.get("kind", []):
            kinds.add(rule["id"])
        # Core fallbacks such as text, binary, folder, and unknown-jsonl are
        # assigned imperatively, then consumed by manifest-declared views.
        # Reading both tables keeps those registered kinds in the same gate.
        for view in manifest.get("view", []):
            kinds.add(view["kind"])
    return kinds


def golden_kinds() -> set[str]:
    """Kind ids emitted by a successful ``metab --show`` transcript command."""

    kinds: set[str] = set()
    for path in sorted(GOLDEN_DIR.glob("*.tryscript.md")):
        for command in _console_commands(path.read_text(encoding="utf-8")):
            parts = _command_parts(command.command)
            if command.status != 0 or not parts or parts[0] != "metab" or "--show" not in parts:
                continue
            for line in command.output:
                match = re.fullmatch(r"kind: ([a-z0-9][a-z0-9-]*)", line)
                if match is not None:
                    kinds.add(match.group(1))
    return kinds


def parity_rows(doc: str) -> list[ParityRow]:
    """Rows of the parity table, which is the one whose header names Surface."""

    rows: list[ParityRow] = []
    in_table = False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("| Surface | Status |"):
            in_table = True
            continue
        if in_table:
            if not stripped.startswith("|"):
                break
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) != 4 or set(cells[0]) <= {"-", " "}:
                continue
            rows.append(
                ParityRow(
                    surface=cells[0].strip("`"),
                    status=cells[1],
                    cli=cells[2],
                    evidence=cells[3],
                )
            )
    return rows


def functional_parity_rows(doc: str) -> list[FunctionalParityRow]:
    """Rows of the checked user-visible functional-aspect table."""

    rows: list[FunctionalParityRow] = []
    in_table = False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("| Aspect | Tier |"):
            in_table = True
            continue
        if in_table:
            if not stripped.startswith("|"):
                break
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) != 5 or set(cells[0]) <= {"-", " "}:
                continue
            rows.append(
                FunctionalParityRow(
                    aspect=cells[0].strip("`"),
                    tier=cells[1],
                    owner=cells[2],
                    command=cells[3].strip("`"),
                    evidence=cells[4],
                )
            )
    return rows


def _canonical_source_owner(owner: str) -> tuple[str | None, str | None]:
    """Resolve one declared owner and require its canonical path under source."""

    source_root = SOURCE_ROOT.resolve()
    candidate = (source_root / owner).resolve()
    try:
        relative = candidate.relative_to(source_root).as_posix()
    except ValueError:
        return None, "escapes the production source root"
    if relative != owner:
        return None, f"must use canonical path {relative!r}"
    if not candidate.is_file():
        return None, "does not exist"
    return relative, None


def _coverage_owner(url: str) -> str | None:
    """Map one executed V8 script URL to a canonical production owner."""

    if url.startswith("file:"):
        parsed = urlsplit(url)
        candidate = Path(url2pathname(unquote(parsed.path)))
    elif ":" in url.split("/", 1)[0]:
        return None
    else:
        candidate = Path(url)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    source_root = SOURCE_ROOT.resolve()
    try:
        owner = resolved.relative_to(source_root).as_posix()
    except ValueError:
        return None
    return owner if resolved.is_file() else None


def _read_coverage_owners(coverage_dir: Path) -> InteractionSessionContract:
    """Read V8's checker-controlled coverage files after a session exits."""

    owners: set[str] = set()
    coverage_files = sorted(coverage_dir.glob("coverage-*.json"))
    if not coverage_files:
        return InteractionSessionContract(frozenset(), "Node emitted no V8 coverage")
    try:
        for path in coverage_files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for script in payload.get("result", []):
                owner = _coverage_owner(script.get("url", ""))
                if owner is None:
                    continue
                source = (SOURCE_ROOT / owner).read_text(encoding="utf-8")
                source_length = len(source.encode("utf-16-le")) // 2
                # V8 offsets are UTF-16 code units. Requiring the executed
                # top-level range to span the source file prevents a session
                # from crediting arbitrary VM source merely by assigning it a
                # production filename.
                exact_top_level_execution = any(
                    scope.get("startOffset") == 0
                    and scope.get("endOffset") == source_length
                    and scope.get("count", 0) > 0
                    for function in script.get("functions", [])
                    for scope in function.get("ranges", [])
                )
                if not exact_top_level_execution:
                    continue
                owners.add(owner)
    except (AttributeError, json.JSONDecodeError, OSError, TypeError) as exc:
        return InteractionSessionContract(frozenset(), f"could not read V8 coverage: {exc}")
    return InteractionSessionContract(frozenset(owners))


def _interaction_session_contract(command_parts: list[str]) -> InteractionSessionContract:
    """Execute one exact Node session and derive owners from V8 coverage."""

    with tempfile.TemporaryDirectory(prefix="metabrowser-parity-") as directory:
        coverage_dir = Path(directory)
        environment = os.environ.copy()
        environment["NODE_V8_COVERAGE"] = str(coverage_dir)
        try:
            result = subprocess.run(
                command_parts,
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return InteractionSessionContract(frozenset(), f"could not execute session: {exc}")
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
            return InteractionSessionContract(
                frozenset(),
                f"session exited {result.returncode}: {detail}",
            )
        return _read_coverage_owners(coverage_dir)


def _check_functional_parity(doc: str) -> list[str]:
    """Validate executable evidence for user-visible functional semantics."""

    rows = functional_parity_rows(doc)
    if not rows:
        return ["the functional UI parity table is missing from the map document"]

    problems: list[str] = []
    seen: set[str] = set()
    registered = registered_surfaces()
    session_contracts: dict[str, InteractionSessionContract] = {}
    for row in rows:
        if row.aspect in seen:
            problems.append(f"functional aspect {row.aspect!r} is listed more than once")
        seen.add(row.aspect)
        if row.tier not in _FUNCTIONAL_TIERS:
            problems.append(
                f"{row.aspect}: tier {row.tier!r} is not one of {sorted(_FUNCTIONAL_TIERS)}"
            )
            continue
        owners = [part.strip().strip("`") for part in row.owner.split(",") if part.strip()]
        canonical_source_owners: list[str] = []
        if not owners or row.owner == "—":
            problems.append(f"{row.aspect}: name the production owner")
        else:
            for owner in owners:
                if owner.startswith("/"):
                    if owner not in registered:
                        problems.append(f"{row.aspect}: route owner {owner!r} is not registered")
                else:
                    canonical, problem = _canonical_source_owner(owner)
                    if problem is not None:
                        problems.append(f"{row.aspect}: source owner {owner!r} {problem}")
                    elif canonical is not None:
                        canonical_source_owners.append(canonical)
        if row.tier == "paint-exempt":
            if row.command != "—":
                problems.append(f"{row.aspect}: a paint exemption cannot claim a CLI command")
            if not row.evidence or row.evidence == "—":
                problems.append(f"{row.aspect}: a paint exemption needs a specific reason")
            test_paths = [
                value
                for value in re.findall(r"`([^`]+)`", row.evidence)
                if value.startswith("tests/")
            ]
            if not test_paths:
                problems.append(f"{row.aspect}: a paint exemption needs focused test evidence")
            for test_path in test_paths:
                if not (REPO_ROOT / test_path).is_file():
                    problems.append(f"{row.aspect}: paint evidence {test_path!r} does not exist")
            continue
        if not row.command or row.command == "—":
            problems.append(f"{row.aspect}: covered behavior needs a CLI command")
            continue
        command_parts = _command_parts(row.command)
        if row.tier == "data" and (not command_parts or command_parts[0] != "metab"):
            problems.append(f"{row.aspect}: data semantics must run through metab")
        if row.tier == "data":
            for owner in (value for value in owners if value.startswith("/")):
                api_value = _option_value(command_parts, "--api")
                if api_value is None or not _route_token_matches(api_value, owner):
                    problems.append(
                        f"{row.aspect}: data command does not name route owner {owner!r}"
                    )
        if row.tier == "interaction":
            session_name = command_parts[1] if len(command_parts) == 2 else ""
            session_root = (REPO_ROOT / "tests/dom").resolve()
            session_path = (REPO_ROOT / session_name).resolve() if session_name else None
            session_is_contained = False
            if session_path is not None:
                try:
                    session_path.relative_to(session_root)
                    session_is_contained = True
                except ValueError:
                    pass
            if (
                len(command_parts) != 2
                or command_parts[0] != "node"
                or not session_name.endswith(".js")
                or session_path is None
                or not session_is_contained
                or session_name != session_path.relative_to(REPO_ROOT.resolve()).as_posix()
            ):
                problems.append(
                    f"{row.aspect}: interaction command must be exactly "
                    "'node tests/dom/<session>.js'"
                )
            else:
                if not session_path.is_file():
                    problems.append(
                        f"{row.aspect}: interaction session {session_name!r} does not exist"
                    )
                else:
                    contract = session_contracts.get(row.command)
                    if contract is None:
                        contract = _interaction_session_contract(command_parts)
                        session_contracts[row.command] = contract
                    if contract.problem:
                        problems.append(
                            f"{row.aspect}: interaction session contract invalid: "
                            f"{contract.problem}"
                        )
                    for owner in canonical_source_owners:
                        if owner not in contract.executed_owners:
                            problems.append(
                                f"{row.aspect}: interaction session did not execute owner {owner!r}"
                            )
        goldens = [name.strip().strip("`") for name in row.evidence.split(",") if name.strip()]
        if not goldens:
            problems.append(f"{row.aspect}: covered behavior needs golden evidence")
            continue
        for golden in goldens:
            path = GOLDEN_DIR / golden
            if not path.exists():
                problems.append(f"{row.aspect}: golden {golden} does not exist")
                continue
            commands = _console_commands(path.read_text(encoding="utf-8"))
            if not any(
                command.command == row.command and command.status == 0 for command in commands
            ):
                problems.append(
                    f"{row.aspect}: golden {golden} never runs successful CLI command "
                    f"{row.command!r}"
                )
    return problems


def check() -> list[str]:
    problems: list[str] = []
    doc = MAP_DOC.read_text(encoding="utf-8")
    rows = parity_rows(doc)
    if not rows:
        return ["the parity table is missing from the map document"]

    listed = {row.surface for row in rows}
    registered = registered_surfaces()

    for surface in sorted(registered - listed):
        problems.append(f"{surface} is registered but has no parity row")
    for surface in sorted(listed - registered):
        problems.append(f"{surface} has a parity row but is not registered")

    for kind in sorted(registered_kinds() - golden_kinds()):
        problems.append(f"kind {kind!r} has no golden console output")

    for row in rows:
        if row.status not in _STATUSES:
            problems.append(
                f"{row.surface}: status {row.status!r} is not one of {sorted(_STATUSES)}"
            )
            continue
        if row.status == "covered":
            goldens = [name.strip().strip("`") for name in row.evidence.split(",") if name.strip()]
            successful_evidence = False
            for golden in goldens:
                path = GOLDEN_DIR / golden
                if not path.exists():
                    problems.append(f"{row.surface}: golden {golden} does not exist")
                    continue
                content = path.read_text(encoding="utf-8")
                if not _exercises(content, row.surface, row.cli, successful_only=False):
                    problems.append(f"{row.surface}: golden {golden} never exercises it")
                if _exercises(content, row.surface, row.cli, successful_only=True):
                    successful_evidence = True
            if goldens and not successful_evidence:
                problems.append(f"{row.surface}: evidence has no successful exact route invocation")
        elif not row.evidence or row.evidence == "—":
            problems.append(f"{row.surface}: an exempt row must give a reason")

    problems.extend(_check_functional_parity(doc))

    return problems


def main() -> int:
    problems = check()
    if problems:
        print("Parity check failed:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    rows = parity_rows(MAP_DOC.read_text(encoding="utf-8"))
    exempt = sum(1 for row in rows if row.status == "exempt")
    covered = sum(1 for row in rows if row.status == "covered")
    kinds = len(registered_kinds())
    functional_rows = functional_parity_rows(MAP_DOC.read_text(encoding="utf-8"))
    paint_exempt = sum(row.tier == "paint-exempt" for row in functional_rows)
    print(
        f"Parity checks passed: {covered} routes covered, {exempt} exempt; "
        f"{kinds} kinds covered; {len(functional_rows)} functional aspects declared "
        f"({paint_exempt} paint-exempt)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
