import argparse
import subprocess
from pathlib import Path

from funlog import log_calls
from rich import get_console, reconfigure
from rich import print as rprint

# Update as needed.
SRC_PATHS = ["src", "tests", "devtools"]

# Tracked agent scaffolding: real files in the repository, but not prose this
# project authors or spell-checks. Everything else that should stay out of the
# doc lint (build output, caches, .venv, node_modules, read-only third-party
# checkouts under attic/) is already in .gitignore, and git enumerates the
# doc set below, so those trees never have to be named twice.
DOC_SKIP_PARTS = frozenset({".agents", ".claude", ".tbd"})

# Only consulted when git cannot enumerate the tree; git applies .gitignore
# itself, so these names are duplicated nowhere in the normal path.
FALLBACK_SKIP_PARTS = DOC_SKIP_PARTS | {
    ".git",
    ".pytest_cache",
    ".venv",
    "attic",
    "dist",
    "node_modules",
}


def _repository_markdown() -> list[str]:
    """Markdown git considers part of the repository, ignored trees excluded.

    `--cached --others --exclude-standard` is tracked files plus untracked ones
    git would offer to add, so a brand-new document is linted immediately while
    an ignored tree is never walked at all. Outside a work tree (an unpacked
    sdist, say) this falls back to a filesystem walk that has to name the
    ignored directories itself.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "*.md"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        paths = sorted(Path(".").rglob("*.md"))
        skip = FALLBACK_SKIP_PARTS
    else:
        paths = sorted({Path(name) for name in result.stdout.split("\0") if name})
        skip = DOC_SKIP_PARTS
    return [str(path) for path in paths if not skip.intersection(path.parts) and path.is_file()]


DOC_PATHS = _repository_markdown()
BIOME_PATHS = [
    "src/metabrowser/static",
    "src/metabrowser/builtin_plugins",
    "tests/dom",
    "biome.json",
    "package.json",
    "tsconfig.json",
    "tsconfig.legacy.json",
]
TSC_CONFIGS = ["tsconfig.json", "tsconfig.legacy.json"]


reconfigure(emoji=not get_console().options.legacy_windows)  # No emojis on legacy windows.


def main() -> int:
    parser = argparse.ArgumentParser(description="Run linting and formatting.")
    # CI should not modify files: check-only mode fails on any issue instead of
    # silently fixing it, so unformatted code can't slip through.
    parser.add_argument("--check", action="store_true", help="Check only, without modifying files.")
    args = parser.parse_args()

    rprint()

    errcount = 0
    if args.check:
        errcount += run(["codespell", *SRC_PATHS, *DOC_PATHS])
        errcount += run(["ruff", "check", *SRC_PATHS])
        errcount += run(["ruff", "format", "--check", *SRC_PATHS])
    else:
        errcount += run(["codespell", "--write-changes", *SRC_PATHS, *DOC_PATHS])
        errcount += run(["ruff", "check", "--fix", *SRC_PATHS])
        errcount += run(["ruff", "format", *SRC_PATHS])
    errcount += run(["basedpyright", "--stats", *SRC_PATHS])
    biome_args = ["npx", "--no-install", "biome"]
    if args.check:
        biome_args.append("ci")
    else:
        biome_args.extend(["check", "--write", "--unsafe"])
    biome_args.extend(BIOME_PATHS)
    errcount += run(biome_args)
    for config in TSC_CONFIGS:
        errcount += run(["npx", "--no-install", "tsc", "--noEmit", "-p", config])

    rprint()

    if errcount != 0:
        rprint(f"[bold red]:x: Lint failed with {errcount} errors.[/bold red]")
    else:
        rprint("[bold green]:white_check_mark: Lint passed![/bold green]")
    rprint()

    return errcount


@log_calls(level="warning", show_timing_only=True)
def run(cmd: list[str]) -> int:
    rprint()
    rprint(f"[bold green]>> {' '.join(cmd)}[/bold green]")
    errcount = 0
    try:
        subprocess.run(cmd, text=True, check=True)
    except KeyboardInterrupt:
        rprint("[yellow]Keyboard interrupt - Cancelled[/yellow]")
        errcount = 1
    except subprocess.CalledProcessError as e:
        rprint(f"[bold red]Error: {e}[/bold red]")
        errcount = 1

    return errcount


if __name__ == "__main__":
    raise SystemExit(main())
