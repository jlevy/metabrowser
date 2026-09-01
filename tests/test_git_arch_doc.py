"""The Git architecture document is checked against the code it describes.

``docs/project/architecture/arch-git-and-comparison-sources.md`` tabulates
the ``/api/git/`` route table and names the modules that own the Git
boundary. A table that no longer matches the code is worse than no table,
so this fails the build instead of letting the document drift.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCH_DOC = REPO_ROOT / "docs/project/architecture/arch-git-and-comparison-sources.md"
GIT_ROUTES_SRC = REPO_ROOT / "src/metabrowser/git/routes.py"


def _doc() -> str:
    return ARCH_DOC.read_text(encoding="utf-8")


def _registered_routes() -> set[str]:
    """The route paths in ``GIT_ROUTES``, as written in the route table."""
    src = GIT_ROUTES_SRC.read_text(encoding="utf-8")
    block = src.split("GIT_ROUTES: list[Route] = [", 1)[1].split("]", 1)[0]
    return set(re.findall(r'Route\("([^"]+)"', block))


def _documented_routes() -> set[str]:
    """Route cells from the document's ``| Route |`` table."""
    documented: set[str] = set()
    for line in _doc().splitlines():
        if not line.startswith("| `/api/git/"):
            continue
        first = line.strip("|").split("|", 1)[0].strip()
        documented.add(first.strip("`"))
    return documented


def test_documented_git_routes_match_the_route_table() -> None:
    registered = _registered_routes()
    assert registered, "GIT_ROUTES parsed as empty; the parser needs updating"
    assert _documented_routes() == registered, (
        "the Git architecture document's route table no longer matches GIT_ROUTES"
    )


def test_named_boundary_modules_exist() -> None:
    """The document points readers at specific modules; they must be real."""
    for module in (
        "metabrowser/git/process.py",
        "metabrowser/git/repo.py",
        "metabrowser/git/routes.py",
        "metabrowser/git/wire.py",
        "metabrowser/diff/format.py",
        "metabrowser/diff/adapters/base.py",
        "metabrowser/diff/adapters/git.py",
        "metabrowser/diff/adapters/patch_file.py",
    ):
        assert (REPO_ROOT / "src" / module).exists(), f"{module} named in the doc is gone"


def test_run_git_is_the_only_subprocess_path() -> None:
    """Invariant 1 in the document: one subprocess boundary, not two."""
    offenders = []
    for path in (REPO_ROOT / "src/metabrowser").rglob("*.py"):
        if path.name == "process.py" and path.parent.name == "git":
            continue
        text = path.read_text(encoding="utf-8")
        if "create_subprocess_exec" in text and '"git"' in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"git subprocess created outside git/process.py: {offenders}"
