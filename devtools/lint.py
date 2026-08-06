import argparse
import subprocess
from pathlib import Path

from funlog import log_calls
from rich import get_console, reconfigure
from rich import print as rprint

# Update as needed.
SRC_PATHS = ["src", "tests", "devtools"]
DOC_PATHS = [
    str(path)
    for path in sorted(Path(".").rglob("*.md"))
    if not any(
        part
        in {
            ".agents",
            ".claude",
            ".git",
            ".pytest_cache",
            ".tbd",
            ".venv",
            "attic",
            "dist",
            "node_modules",
        }
        for part in path.parts
    )
]
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
