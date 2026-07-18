"""Spike: deterministic renderer fixtures shared by every renderer under test.

Writes to fixtures/out/: FilePatch JSON (for the custom and server-HTML renderers),
old/new file contents (for libraries that diff contents themselves), and a scenario
index. All content is formulaic so runs are reproducible without committing megabytes.
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from spike_git_adapter import parse_unified_patch  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "out"


def code_lines(seed: int, count: int) -> list[str]:
    return [
        f"    value_{seed}_{n} = compute_{seed}(alpha, beta) + {n}  # marker line {n}"
        for n in range(count)
    ]


def lock_lines(count: int, generation: int) -> list[str]:
    return [
        f'  "package-{n:05d}": {{"version": "{generation}.{n % 9}.{n % 17}", "integrity": "sha512-{n:064d}"}},'
        for n in range(count)
    ]


def edit_blocks(lines: list[str], blocks: int, seed: int) -> list[str]:
    new = list(lines)
    step = max(1, len(new) // (blocks + 1))
    for b in range(blocks):
        at = min(len(new) - 12, (b + 1) * step)
        for k in range(4):
            new[at + k] = new[at + k].replace("compute", f"refactor{seed}")
        new[at + 6 : at + 6] = [f"    added_{seed}_{b}_{k} = migrate({b}, {k})" for k in range(3)]
        del new[at + 10]
    return new


def unified_text(old: list[str], new: list[str], path: str) -> str:
    body = "\n".join(
        difflib.unified_diff(old, new, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="", n=3)
    )
    return f"diff --git a/{path} b/{path}\n{body}\n"


def patch_from(old: list[str], new: list[str], path: str) -> dict:
    return parse_unified_patch(unified_text(old, new, path), path, "modified")


def write_pair(stem: str, old: list[str], new: list[str], path: str) -> dict:
    (OUT / f"contents_{stem}_old.txt").write_text("\n".join(old) + "\n")
    (OUT / f"contents_{stem}_new.txt").write_text("\n".join(new) + "\n")
    (OUT / f"unified_{stem}.diff").write_text(unified_text(old, new, path))
    patch = patch_from(old, new, path)
    (OUT / f"fp_{stem}.json").write_text(json.dumps(patch))
    return {
        "id": stem,
        "patch": f"fp_{stem}.json",
        "old": f"contents_{stem}_old.txt",
        "new": f"contents_{stem}_new.txt",
        "path": path,
        "lang": "python" if path.endswith(".py") else "json",
        "patchLines": sum(
            len(g["lines"]) for h in patch["hunks"] for g in h["groups"]
        ),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    scenarios = []

    old = code_lines(7, 200)
    scenarios.append(write_pair("small", old, edit_blocks(old, 3, 7), "src/service.py"))

    old = code_lines(11, 2400)
    scenarios.append(write_pair("medium", old, edit_blocks(old, 60, 11), "src/big_refactor.py"))

    old = ["{"] + lock_lines(18_000, 1) + ["}"]
    new = ["{"] + lock_lines(19_500, 2) + ["}"]
    scenarios.append(write_pair("huge", old, new, "package-lock.json"))

    files = []
    for i in range(50):
        base = code_lines(100 + i, 160)
        patch = patch_from(base, edit_blocks(base, 2, 100 + i), f"src/pkg_{i % 8}/mod_{i:03d}.py")
        files.append(patch)
    (OUT / "set50.json").write_text(json.dumps({"files": files}))
    scenarios.append({"id": "set50", "set": "set50.json", "files": len(files)})

    (OUT / "scenarios.json").write_text(json.dumps({"scenarios": scenarios}, indent=1))
    print(json.dumps(scenarios, indent=1))


if __name__ == "__main__":
    main()
