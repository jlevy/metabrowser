"""The GitHub architecture document's route table is checked against the plugin manifest.

``docs/project/architecture/arch-github-pull-requests.md`` lists every data route the
``github`` plugin registers, with its methods. A row for a route the manifest no longer
declares, or a declared route with no row, fails here rather than drifting.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "docs/project/architecture/arch-github-pull-requests.md"
MANIFEST = REPO_ROOT / "src/metabrowser/builtin_plugins/github/manifest.toml"
HEADER = ("Route", "Methods", "Answers or starts")


def _cells(line: str) -> tuple[str, ...]:
    return tuple(cell.strip() for cell in line.strip().strip("|").split("|"))


def _unquoted(cell: str) -> str:
    return cell.strip().strip("`")


def _documented_routes() -> dict[str, frozenset[str]]:
    lines = DOC.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if _cells(line) == HEADER)
    routes: dict[str, frozenset[str]] = {}
    for line in lines[start + 2 :]:
        if not line.strip().startswith("|"):
            break
        route, methods, _ = _cells(line)
        name = _unquoted(route)
        assert name not in routes, f"{name} has two rows"
        routes[name] = frozenset(_unquoted(method) for method in methods.split(","))
    return routes


def _declared_routes() -> dict[str, frozenset[str]]:
    manifest = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
    return {hook["route"]: frozenset(hook["methods"]) for hook in manifest["data_hook"]}


def test_every_declared_route_has_one_row_with_its_methods() -> None:
    assert _documented_routes() == _declared_routes()
