from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, cast

from metabrowser import server
from metabrowser.repository_context import discover_repository_context

_OVERSIZED_GIT_CONFIG_BYTES = 1024 * 1024 + 1


def _write_repository(root: Path, *, remote: str, head: str, revision: str) -> None:
    git_dir = root / ".git"
    (git_dir / "refs" / "heads").mkdir(parents=True)
    (git_dir / "config").write_text(
        f'[remote "origin"]\n\turl = {remote}\n',
    )
    (git_dir / "HEAD").write_text(f"ref: refs/heads/{head}\n")
    ref = git_dir / "refs" / "heads" / head
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(f"{revision}\n")


def test_discovers_bounded_github_identity_for_served_subdirectory(tmp_path: Path) -> None:
    revision = "a" * 40
    _write_repository(
        tmp_path,
        remote="git@github.com:example/docs.git",
        head="feature/navigation",
        revision=revision,
    )
    served = tmp_path / "packages" / "handbook"
    served.mkdir(parents=True)

    assert discover_repository_context(served) == {
        "branch": "feature/navigation",
        "host": "github.com",
        "name": "docs",
        "owner": "example",
        "revision": revision,
        "served_prefix": "packages/handbook",
    }


def test_rejects_non_github_remote_and_invalid_revision(tmp_path: Path) -> None:
    _write_repository(
        tmp_path,
        remote="https://example.com/example/docs.git",
        head="main",
        revision="not-a-commit",
    )

    assert discover_repository_context(tmp_path) is None


def test_rejects_oversized_git_configuration(tmp_path: Path) -> None:
    revision = "d" * 40
    _write_repository(
        tmp_path,
        remote="https://github.com/example/docs.git",
        head="main",
        revision=revision,
    )
    (tmp_path / ".git" / "config").write_bytes(b"x" * _OVERSIZED_GIT_CONFIG_BYTES)

    assert discover_repository_context(tmp_path) is None


def test_reads_packed_branch_revision(tmp_path: Path) -> None:
    revision = "b" * 40
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text(
        '[remote "origin"]\n\turl = https://github.com/example/docs.git\n'
    )
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    (git_dir / "packed-refs").write_text(f"{revision} refs/heads/main\n")

    assert discover_repository_context(tmp_path) == {
        "branch": "main",
        "host": "github.com",
        "name": "docs",
        "owner": "example",
        "revision": revision,
        "served_prefix": "",
    }


def test_index_exposes_only_public_repository_identity(tmp_path: Path) -> None:
    revision = "c" * 40
    _write_repository(
        tmp_path,
        remote="https://github.com/example/docs.git",
        head="main",
        revision=revision,
    )
    served = tmp_path / "docs"
    served.mkdir()
    previous_root = server._resolved_root_dir()
    try:
        server._set_root_dir(served)
        response = asyncio.run(server.index(cast(Any, object())))
    finally:
        server._set_root_dir(previous_root)

    html = bytes(response.body).decode("utf-8")
    match = re.search(r"window\.METABROWSER_REPOSITORY_CONTEXT=([^;]+);", html)
    assert match is not None
    assert json.loads(match.group(1)) == {
        "branch": "main",
        "host": "github.com",
        "name": "docs",
        "owner": "example",
        "revision": revision,
        "served_prefix": "docs",
    }
    assert str(tmp_path) not in match.group(1)
