"""Spike: hardened Git subprocess adapter producing a manifest and lazy per-file patches.

Validates the acquisition design in docs/project/specs/active/plan-2026-07-18-git-diff-view.md:
porcelain v2 status, numstat totals, untracked synthesis, semantic per-file patches, and
manifest-before-patch timing on repositories with pathological files.

Usage:
  python spike_git_adapter.py --repo PATH --out DIR [--emit-patches N] [--contrast]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GIT_TIMEOUT_S = 30.0
OUTPUT_CAP_BYTES = 64 * 1024 * 1024
UNTRACKED_BYTE_CAP = 500_000
UNTRACKED_LINE_CAP = 10_000
BINARY_SNIFF_BYTES = 8_192


@dataclass
class GitRunner:
    """Runs git with a sanitized environment and hardened defaults."""

    repo: Path
    home: Path

    def argv(self, *args: str) -> list[str]:
        return [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=",
            "--no-optional-locks",
            *args,
        ]

    def env(self) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }

    def run(self, *args: str) -> bytes:
        proc = subprocess.run(
            self.argv(*args),
            cwd=self.repo,
            env=self.env(),
            capture_output=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
        if proc.returncode not in (0, 1):  # git diff exits 1 when differences exist
            raise RuntimeError(f"git {args[0]} failed rc={proc.returncode}: {proc.stderr[:400]!r}")
        if len(proc.stdout) > OUTPUT_CAP_BYTES:
            raise RuntimeError(f"git {args[0]} output exceeded cap ({len(proc.stdout)} bytes)")
        return proc.stdout


@dataclass
class FileChange:
    path: str
    old_path: str | None
    status: str
    staged: bool
    unstaged: bool
    additions: int | None = None
    deletions: int | None = None
    binary: bool = False

    def file_id(self) -> str:
        return hashlib.sha1(self.path.encode("utf-8", "surrogateescape")).hexdigest()[:16]

    def to_json(self) -> dict[str, Any]:
        return {
            "fileId": self.file_id(),
            "path": self.path,
            "oldPath": self.old_path,
            "status": self.status,
            "staged": self.staged,
            "unstaged": self.unstaged,
            "additions": self.additions,
            "deletions": self.deletions,
            "binary": self.binary,
        }


def parse_porcelain_v2(raw: bytes) -> list[FileChange]:
    """Parse `git status --porcelain=v2 -z` records into FileChange entries."""
    changes: list[FileChange] = []
    fields = raw.split(b"\0")
    i = 0
    while i < len(fields):
        rec = fields[i]
        i += 1
        if not rec:
            continue
        kind = rec[:1]
        if kind == b"?":
            path = rec[2:].decode("utf-8", "surrogateescape")
            changes.append(FileChange(path, None, "untracked", False, True))
            continue
        if kind not in (b"1", b"2", b"u"):
            continue
        parts = rec.split(b" ", 8 if kind == b"1" else 9)
        xy = parts[1].decode()
        path = parts[-1].decode("utf-8", "surrogateescape")
        old_path: str | None = None
        if kind == b"2":  # rename/copy: next NUL field is the original path
            old_path = fields[i].decode("utf-8", "surrogateescape")
            i += 1
        staged = xy[0] != "."
        unstaged = xy[1] != "."
        code = (xy[1] if unstaged else xy[0]).upper()
        status = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "T": "typechange",
        }.get(code, "modified")
        if kind == b"u":
            status = "unmerged"
        changes.append(FileChange(path, old_path, status, staged, unstaged))
    return changes


def parse_numstat(raw: bytes) -> dict[str, tuple[int | None, int | None]]:
    """Parse `git diff --numstat -z -M` into {path: (adds, dels)}; None means binary."""
    out: dict[str, tuple[int | None, int | None]] = {}
    fields = raw.split(b"\0")
    i = 0
    while i < len(fields):
        rec = fields[i]
        i += 1
        if not rec:
            continue
        adds_b, dels_b, rest = rec.split(b"\t", 2)
        adds = None if adds_b == b"-" else int(adds_b)
        dels = None if dels_b == b"-" else int(dels_b)
        if rest == b"":  # rename: two following NUL fields are old and new path
            i += 1  # old path (unused here)
            path = fields[i].decode("utf-8", "surrogateescape")
            i += 1
        else:
            path = rest.decode("utf-8", "surrogateescape")
        out[path] = (adds, dels)
    return out


def parse_unified_patch(text: str, path: str, status: str) -> dict[str, Any]:
    """Parse one file's unified diff into semantic hunks with grouped line runs."""
    hunks: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    adds = dels = 0
    binary = False
    for line in text.splitlines():
        if line.startswith("@@"):
            # Format: @@ -oldStart,oldLines +newStart,newLines @@ optional section
            body = line.split("@@")
            ranges = body[1].strip().split(" ")
            old_start, old_lines = _parse_range(ranges[0])
            new_start, new_lines = _parse_range(ranges[1])
            groups = []
            current = None
            hunks.append(
                {
                    "oldStart": old_start,
                    "oldLines": old_lines,
                    "newStart": new_start,
                    "newLines": new_lines,
                    "section": body[2].strip() if len(body) > 2 else "",
                    "groups": groups,
                }
            )
            continue
        if not hunks:
            if line.startswith("Binary files"):
                binary = True
            continue
        tag = line[:1]
        kind = {"+": "add", "-": "del", " ": "context"}.get(tag)
        if kind is None:
            if line.startswith("\\ No newline"):
                if current is not None:
                    current["noNewline"] = True
            continue
        if kind == "add":
            adds += 1
        elif kind == "del":
            dels += 1
        if current is None or current["type"] != kind:
            current = {"type": kind, "lines": []}
            groups.append(current)
        current["lines"].append(line[1:])
    return {
        "schema": "spike-filepatch/1",
        "path": path,
        "status": status,
        "binary": binary,
        "additions": adds,
        "deletions": dels,
        "hunks": hunks,
        "truncated": False,
    }


def _parse_range(token: str) -> tuple[int, int]:
    token = token.lstrip("+-")
    if "," in token:
        a, b = token.split(",", 1)
        return int(a), int(b)
    return int(token), 1


def synthesize_untracked(repo: Path, path: str) -> dict[str, Any]:
    """Represent an untracked file as a bounded addition from an empty side."""
    full = repo / path
    size = full.stat().st_size
    with open(full, "rb") as fh:
        head = fh.read(BINARY_SNIFF_BYTES)
        if b"\0" in head:
            return {
                "schema": "spike-filepatch/1",
                "path": path,
                "status": "untracked",
                "binary": True,
                "additions": None,
                "deletions": None,
                "hunks": [],
                "truncated": False,
            }
        data = head + fh.read(UNTRACKED_BYTE_CAP - len(head))
    truncated = size > UNTRACKED_BYTE_CAP
    lines = data.decode("utf-8", "replace").splitlines()
    if len(lines) > UNTRACKED_LINE_CAP:
        lines = lines[:UNTRACKED_LINE_CAP]
        truncated = True
    return {
        "schema": "spike-filepatch/1",
        "path": path,
        "status": "untracked",
        "binary": False,
        "additions": len(lines),
        "deletions": 0,
        "hunks": [
            {
                "oldStart": 0,
                "oldLines": 0,
                "newStart": 1,
                "newLines": len(lines),
                "section": "",
                "groups": [{"type": "add", "lines": lines}],
            }
        ],
        "truncated": truncated,
    }


@dataclass
class Timings:
    ms: dict[str, float] = field(default_factory=dict)

    def timed(self, name: str):
        outer = self

        class _Ctx:
            def __enter__(self) -> None:
                self.t0 = time.perf_counter()

            def __exit__(self, *exc: object) -> None:
                outer.ms[name] = round((time.perf_counter() - self.t0) * 1000, 2)

        return _Ctx()


def build_manifest(runner: GitRunner, timings: Timings) -> list[FileChange]:
    with timings.timed("status_porcelain_v2"):
        raw_status = runner.run("status", "--porcelain=v2", "-z", "--untracked-files=all")
    with timings.timed("parse_status"):
        changes = parse_porcelain_v2(raw_status)
    with timings.timed("numstat"):
        raw_numstat = runner.run(
            "diff", "HEAD", "--numstat", "-z", "-M", "--no-ext-diff", "--no-textconv"
        )
    with timings.timed("merge_numstat"):
        stats = parse_numstat(raw_numstat)
        for change in changes:
            stat = stats.get(change.path)
            if stat is not None:
                change.additions, change.deletions = stat
                change.binary = stat[0] is None
    return changes


def patch_for(runner: GitRunner, change: FileChange) -> dict[str, Any]:
    if change.status == "untracked":
        return synthesize_untracked(runner.repo, change.path)
    spec = f":(literal){change.path}"
    old_spec = f":(literal){change.old_path}" if change.old_path else None
    args = ["diff", "HEAD", "--no-color", "--no-ext-diff", "--no-textconv", "-M", "--unified=3", "--"]
    args.append(spec)
    if old_spec:
        args.append(old_spec)
    text = runner.run(*args).decode("utf-8", "replace")
    patch = parse_unified_patch(text, change.path, change.status)
    patch["fileId"] = change.file_id()
    return patch


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--emit-patches", type=int, default=10)
    ap.add_argument("--contrast", action="store_true", help="also time one-shot git diff HEAD")
    ns = ap.parse_args()

    out: Path = ns.out
    out.mkdir(parents=True, exist_ok=True)
    timings = Timings()
    with tempfile.TemporaryDirectory(prefix="spike-git-home-") as home:
        runner = GitRunner(ns.repo.resolve(), Path(home))
        with timings.timed("discovery"):
            top = runner.run("rev-parse", "--show-toplevel").decode().strip()
        t_manifest0 = time.perf_counter()
        changes = build_manifest(runner, timings)
        timings.ms["manifest_total"] = round((time.perf_counter() - t_manifest0) * 1000, 2)

        manifest = {
            "schema": "spike-manifest/1",
            "repo": top,
            "totals": {
                "files": len(changes),
                "additions": sum(c.additions or 0 for c in changes),
                "deletions": sum(c.deletions or 0 for c in changes),
                "exact": all(c.additions is not None for c in changes if not c.binary),
            },
            "files": [c.to_json() for c in changes],
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=1))

        # Lazy per-file patches: a typical small file, the largest file, then a batch.
        by_size = sorted(changes, key=lambda c: (c.additions or 0) + (c.deletions or 0))
        interesting: list[FileChange] = []
        if by_size:
            interesting.append(by_size[len(by_size) // 2])
            interesting.append(by_size[-1])
        interesting.extend(by_size[: max(0, ns.emit_patches - len(interesting))])
        seen: set[str] = set()
        patch_times: dict[str, float] = {}
        for change in interesting:
            if change.path in seen:
                continue
            seen.add(change.path)
            t0 = time.perf_counter()
            patch = patch_for(runner, change)
            patch_times[change.path] = round((time.perf_counter() - t0) * 1000, 2)
            (out / f"patch-{change.file_id()}.json").write_text(json.dumps(patch))
        timings.ms["patch_each"] = patch_times  # type: ignore[assignment]

        if ns.contrast:
            t0 = time.perf_counter()
            full = runner.run("diff", "HEAD", "--no-color", "--no-ext-diff", "--no-textconv", "-M")
            timings.ms["one_shot_git_diff_head"] = round((time.perf_counter() - t0) * 1000, 2)
            timings.ms["one_shot_bytes"] = len(full)  # type: ignore[assignment]

        (out / "timings.json").write_text(json.dumps(timings.ms, indent=1))
        print(json.dumps({"files": len(changes), "timings": timings.ms}, indent=1))


if __name__ == "__main__":
    main()
