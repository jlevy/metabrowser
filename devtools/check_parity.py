"""Fail the build when the CLI parity table drifts from the registered routes.

Every data surface the browser consumes should be reachable from ``metab`` and
pinned by a golden transcript. A table nobody checks is worse than no table, so
this reads the parity table in the views/models/routes map and compares it to
what the code actually registers.

Gap rows are permitted and counted. They make the remaining debt visible and
machine-countable rather than implicit; ``mb-4uy2`` removes that allowance once
the gaps are closed.
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

_STATUSES = frozenset({"covered", "gap", "exempt"})
_BEAD = re.compile(r"^mb-[0-9a-z]{4,}$")


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
        for route in re.findall(r'Route\("([^"]+)"', path.read_text(encoding="utf-8")):
            if route.startswith("/api/"):
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
                elif row.surface not in path.read_text(encoding="utf-8"):
                    problems.append(f"{row.surface}: golden {golden} never exercises it")
        elif row.status == "gap":
            if not _BEAD.match(row.evidence.strip("`")):
                problems.append(f"{row.surface}: a gap row must name the bead that closes it")
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
    gaps = sum(1 for row in rows if row.status == "gap")
    exempt = sum(1 for row in rows if row.status == "exempt")
    covered = sum(1 for row in rows if row.status == "covered")
    print(f"Parity checks passed: {covered} covered, {gaps} gap, {exempt} exempt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
