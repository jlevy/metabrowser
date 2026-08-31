"""Fail the build when the CLI parity table drifts from the registered routes.

Every data surface the browser consumes should be reachable from ``metab`` and
pinned by a golden transcript. A table nobody checks is worse than no table, so
this reads the parity table in the views/models/routes map and compares it to
what the code actually registers.

Gap rows were permitted while the debt was paid down, and are not any more:
every registered surface is either covered by a transcript or exempt with a
reason. A new route arrives with its golden or the build fails.
"""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_DOC = REPO_ROOT / "docs/project/architecture/arch-views-models-routes.md"
BUILTIN_PLUGINS = REPO_ROOT / "src/metabrowser/builtin_plugins"
SOURCE_ROOT = REPO_ROOT / "src/metabrowser"
GOLDEN_DIR = REPO_ROOT / "tests/golden"

_STATUSES = frozenset({"covered", "exempt"})
# Modes that issue a route without naming it on the command line, mapped to the
# routes each one can actually issue. The mapping matters: crediting a mode for
# a surface it never touches is the same false evidence as crediting prose.
# `--api` is absent because it always names its route, so a row claiming it must
# show the route in a command. `--walk` and `--diff` are absent for the opposite
# reason: they reach their models through the library and issue no request at
# all, which is the model-versus-wire gap this check exists to close.
_INDIRECT_MODES: dict[str, tuple[str, ...]] = {
    "--show": ("/api/file", "/api/plugin/diff/comparison", "/view", "/commit"),
    "--check-api": ("/api/tree", "/api/recent", "/api/index/progress"),
}


def _command_lines(golden: str) -> list[str]:
    """The `$ metab ...` lines in a transcript, which are what it actually runs."""

    return [line.strip()[2:] for line in golden.splitlines() if line.strip().startswith("$ ")]


def _exercises(golden: str, surface: str, cli: str) -> bool:
    """Whether a transcript runs the surface, rather than merely mentioning it.

    Naming the route in a command is direct evidence. A mode that resolves the
    route internally -- `--show` reaching `/api/file` without naming it -- is
    evidence only when the row says so, which is why the CLI column is read
    here and not just the route.
    """

    commands = _command_lines(golden)
    if any(surface in command for command in commands):
        return True
    for mode, issues in _INDIRECT_MODES.items():
        if mode not in cli or surface not in issues:
            continue
        if any(mode in command for command in commands):
            return True
    return False


@dataclass(frozen=True, slots=True)
class ParityRow:
    surface: str
    status: str
    cli: str
    evidence: str


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

    for row in rows:
        if row.status not in _STATUSES:
            problems.append(
                f"{row.surface}: status {row.status!r} is not one of {sorted(_STATUSES)}"
            )
            continue
        if row.status == "covered":
            goldens = [name.strip().strip("`") for name in row.evidence.split(",") if name.strip()]
            for golden in goldens:
                path = GOLDEN_DIR / golden
                if not path.exists():
                    problems.append(f"{row.surface}: golden {golden} does not exist")
                elif not _exercises(path.read_text(encoding="utf-8"), row.surface, row.cli):
                    problems.append(f"{row.surface}: golden {golden} never exercises it")
        elif not row.evidence or row.evidence == "—":
            problems.append(f"{row.surface}: an exempt row must give a reason")

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
    print(f"Parity checks passed: {covered} covered, {exempt} exempt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
