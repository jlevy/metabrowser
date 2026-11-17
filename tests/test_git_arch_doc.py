"""The Git and diff architecture documents are checked against the code they describe.

``docs/project/architecture/arch-git.md`` tabulates the ``/api/git/`` routes and the
history-session failures, and says which modules start a ``git`` process;
``arch-diff-pipeline.md`` names the modules of the diff port. A table that no longer
matches the code is worse than no table, so these fail the build instead of letting the
documents drift.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCH_DIR = REPO_ROOT / "docs/project/architecture"
GIT_DOC = ARCH_DIR / "arch-git.md"
DIFF_DOC = ARCH_DIR / "arch-diff-pipeline.md"
SRC = REPO_ROOT / "src/metabrowser"
GIT_ROUTES_SRC = SRC / "git/routes.py"
HISTORY_SRC = SRC / "git/history.py"

# The modules that may start a `git` process, as arch-git.md states them. The process
# boundary is git/process.py; build_version.py annotates a source checkout's version line.
GIT_STARTERS = frozenset({"git/process.py", "build_version.py"})

# Starting a process, by any of the standard library's spellings.
_SPAWN = re.compile(
    r"create_subprocess_(?:exec|shell)\b"
    r"|subprocess\.(?:run|Popen|call|check_call|check_output)\b"
    r"|os\.(?:exec\w*|spawn\w*|posix_spawn\w*)\b"
)
# Naming Git as the program: a literal "git" argument or the executable lookup.
_NAMES_GIT = re.compile(r"""["']git["']|\bgit_executable\(|which\(\s*["']git["']""")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _registered_routes() -> set[str]:
    """The route paths in ``GIT_ROUTES``, as written in the route table."""
    src = _text(GIT_ROUTES_SRC)
    block = src.split("GIT_ROUTES: list[Route] = [", 1)[1].split("]", 1)[0]
    return set(re.findall(r'Route\("([^"]+)"', block))


def _first_cells(doc: str, prefix: str) -> set[str]:
    """First-column cells of the table rows in *doc* that start with *prefix*."""
    cells: set[str] = set()
    for line in doc.splitlines():
        if line.startswith(prefix):
            cells.add(line.strip("|").split("|", 1)[0].strip().strip("`"))
    return cells


def test_documented_git_routes_match_the_route_table() -> None:
    registered = _registered_routes()
    assert registered, "GIT_ROUTES parsed as empty; the parser needs updating"
    assert _first_cells(_text(GIT_DOC), "| `/api/git/") == registered, (
        "arch-git.md's route table no longer matches GIT_ROUTES"
    )


def test_documented_history_failures_match_the_error_classes() -> None:
    """Each typed failure a history session raises has a row, and every row is real."""
    defined = set(
        re.findall(
            r"^class (\w+Error)\((?:HistorySessionError|GitError)\):",
            _text(HISTORY_SRC),
            re.MULTILINE,
        )
    )
    assert defined, "no history errors parsed from git/history.py; the parser needs updating"
    documented = {
        cell
        for cell in _first_cells(_text(GIT_DOC), "| `")
        if re.fullmatch(r"\w*History\w*Error", cell)
    }
    assert documented == defined, (
        "arch-git.md's history failure table no longer matches the classes in git/history.py"
    )


def test_named_modules_exist() -> None:
    """Each document points readers at specific modules; they must be real and named."""
    named = {
        GIT_DOC: (
            "git/process.py",
            "git/repo.py",
            "git/routes.py",
            "git/wire.py",
            "git/history.py",
            "git/detail.py",
            "git/ref_state.py",
            "git/route_memo.py",
            "build_version.py",
        ),
        DIFF_DOC: (
            "diff/adapters/base.py",
            "diff/adapters/git.py",
            "diff/adapters/patch_file.py",
            "diff/apply.py",
            "diff/markdown_projection.py",
            "diff/markdown_projection_worker.py",
            "builtin_plugins/diff/comparison_cache.py",
            "builtin_plugins/diff/sidekick.py",
        ),
    }
    for doc, modules in named.items():
        text = _text(doc)
        for module in modules:
            assert module in text, f"{doc.name} no longer names {module}"
            assert (SRC / module).exists(), f"{module} named in {doc.name} is gone"


def test_only_the_named_modules_start_git() -> None:
    """The process boundary in arch-git.md: two modules start git, and no others.

    A text scan: a module is counted when it both starts a process and names git as
    the program. It finds a new spawn site, not a process started through an
    indirection the text does not show.
    """
    starters = set()
    for path in SRC.rglob("*.py"):
        text = _text(path)
        if _SPAWN.search(text) and _NAMES_GIT.search(text):
            starters.add(path.relative_to(SRC).as_posix())
    assert starters == GIT_STARTERS, (
        f"modules that start git: {sorted(starters)}; arch-git.md names {sorted(GIT_STARTERS)}"
    )
    doc = _text(GIT_DOC)
    for module in GIT_STARTERS:
        assert f"`{module}`" in doc, f"arch-git.md no longer names {module} as a git starter"
