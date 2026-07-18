"""Spike: build a synthetic dirty Git repository resembling an aggressive agent session.

Creates, under --dir: 600 committed source files plus one 30k-line generated lockfile,
then perturbs the working tree with 500 small edits, a full lockfile rewrite, untracked
files, renames, deletions, a binary change, and partial staging.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

BASE_FILES = 600
BASE_LINES = 80
LOCK_LINES = 30_000
MODIFIED = 500
UNTRACKED = 12
RENAMED = 3
DELETED = 2


def git(repo: Path, *args: str) -> None:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(repo),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Spike",
        "GIT_AUTHOR_EMAIL": "spike@example.invalid",
        "GIT_COMMITTER_NAME": "Spike",
        "GIT_COMMITTER_EMAIL": "spike@example.invalid",
    }
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def source_lines(index: int, count: int) -> list[str]:
    return [
        f"    value_{index}_{n} = compute_{index}(alpha, beta) + {n}  # marker line {n}"
        for n in range(count)
    ]


def lock_lines(count: int, generation: int) -> list[str]:
    return [
        f'  "package-{n:05d}": {{"version": "{generation}.{n % 9}.{n % 17}", "integrity": "sha512-{n:064d}"}},'
        for n in range(count)
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, type=Path)
    ns = ap.parse_args()
    repo: Path = ns.dir
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q", "-b", "main")

    for i in range(BASE_FILES):
        sub = repo / f"src/pkg_{i % 20:02d}"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / f"mod_{i:04d}.py").write_text("\n".join(source_lines(i, BASE_LINES)) + "\n")
    (repo / "package-lock.json").write_text(
        "{\n" + "\n".join(lock_lines(LOCK_LINES, 1)) + "\n}\n"
    )
    (repo / "logo.bin").write_bytes(bytes(range(256)) * 64)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")

    # Working-tree perturbations (unstaged unless noted).
    for i in range(MODIFIED):
        path = repo / f"src/pkg_{i % 20:02d}/mod_{i:04d}.py"
        lines = path.read_text().splitlines()
        lines[10] = lines[10] + "  # touched"
        lines.insert(40, f"    inserted_{i} = refactor({i})")
        del lines[60]
        path.write_text("\n".join(lines) + "\n")
    (repo / "package-lock.json").write_text(
        "{\n" + "\n".join(lock_lines(LOCK_LINES + 1500, 2)) + "\n}\n"
    )
    for i in range(UNTRACKED):
        (repo / f"src/new_module_{i:02d}.py").write_text(
            "\n".join(source_lines(1000 + i, 60)) + "\n"
        )
    for i in range(RENAMED):
        old_path = repo / f"src/pkg_{(599 - i) % 20:02d}/mod_{599 - i:04d}.py"
        new_path = old_path.with_name(old_path.stem + "_moved.py")
        git(repo, "mv", str(old_path.relative_to(repo)), str(new_path.relative_to(repo)))
    for i in range(DELETED):
        (repo / f"src/pkg_{(550 + i) % 20:02d}/mod_{550 + i:04d}.py").unlink()
    (repo / "logo.bin").write_bytes(bytes(reversed(range(256))) * 64)

    # Partial staging: stage one edit, then edit the same file again.
    staged = repo / "src/pkg_00/mod_0000.py"
    staged.write_text(staged.read_text() + "# staged tail\n")
    git(repo, "add", str(staged.relative_to(repo)))
    staged.write_text(staged.read_text() + "# unstaged tail\n")

    print(repo.resolve())


if __name__ == "__main__":
    main()
