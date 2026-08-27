from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_SUFFIXES = frozenset({".cjs", ".cts", ".js", ".jsx", ".mjs", ".mts", ".ts", ".tsx"})

# Dotted roles such as `types.d.ts` are conventional, but every segment must
# still be lowercase kebab-case. This keeps module URLs and imports predictable
# while allowing standard declaration and configuration suffixes.
SOURCE_NAME = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)*"
    r"\.(?:cjs|cts|js|jsx|mjs|mts|ts|tsx)$"
)

GIT_SKIP_PARTS = frozenset({".agents", ".claude", ".codex", ".tbd"})
FALLBACK_SKIP_PARTS = GIT_SKIP_PARTS | {
    ".git",
    ".venv",
    "attic",
    "dist",
    "node_modules",
}
VENDORED_ROOTS = (ROOT / "src" / "metabrowser" / "static" / "vendor",)
FINDING = "JavaScript and TypeScript filenames must use lowercase kebab-case"


def _repository_source_files() -> list[Path]:
    patterns = [f"*{suffix}" for suffix in sorted(SOURCE_SUFFIXES)]
    try:
        result = subprocess.run(
            [
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                *patterns,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        paths = sorted(
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and path.suffix in SOURCE_SUFFIXES
            and not FALLBACK_SKIP_PARTS.intersection(path.relative_to(ROOT).parts)
        )
    else:
        paths = sorted(
            ROOT / name
            for name in set(result.stdout.split("\0"))
            if name and not GIT_SKIP_PARTS.intersection(Path(name).parts)
        )
    return [path for path in paths if path.is_file() and not _is_vendored(path)]


def _is_vendored(path: Path) -> bool:
    absolute = path if path.is_absolute() else ROOT / path
    return any(absolute.is_relative_to(root) for root in VENDORED_ROOTS)


def _display_path(path: Path) -> str:
    absolute = path if path.is_absolute() else ROOT / path
    try:
        return absolute.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def find_source_naming_findings(paths: Iterable[Path] | None = None) -> list[str]:
    candidates = _repository_source_files() if paths is None else paths
    return sorted(
        f"{_display_path(path)}: {FINDING}"
        for path in candidates
        if path.suffix in SOURCE_SUFFIXES
        and not _is_vendored(path)
        and not SOURCE_NAME.fullmatch(path.name)
    )


def main() -> int:
    findings = find_source_naming_findings()
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
