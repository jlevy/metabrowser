"""A bare fast-import store and a pinned ASGI client for Git revision tests."""

from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path

from httpx2 import ASGITransport, AsyncClient

from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import GitRevisionSubject, git_revision_subject
from metabrowser.server import app
from metabrowser.source import attach_subject, reset_source_session


def git_env(root: Path) -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    return env


def fast_import_store(
    tmp_path: Path,
    files: Mapping[bytes, bytes],
    *,
    symlinks: Mapping[bytes, bytes] | None = None,
) -> tuple[Path, str]:
    """A bare store with one commit. Names are plain ASCII, so no quoting.

    *symlinks* maps a link's name to its target, stored as a mode 120000 blob.
    """

    store = tmp_path / "store.git"
    env = git_env(tmp_path)
    subprocess.run(
        ["git", "init", "-q", "--bare", "--template=", "-b", "main", str(store)],
        check=True,
        capture_output=True,
        env=env,
    )
    stream = bytearray(
        b"commit refs/heads/main\n"
        b"committer Pin <pin@example.invalid> 1767225600 +0000\n"
        b"data 4\npin\n\n"
    )
    for name, body in files.items():
        stream += b"M 100644 inline " + name + b"\ndata " + str(len(body)).encode() + b"\n"
        stream += body + b"\n"
    for name, target in (symlinks or {}).items():
        stream += b"M 120000 inline " + name + b"\ndata " + str(len(target)).encode() + b"\n"
        stream += target + b"\n"
    stream += b"\ndone\n"
    subprocess.run(
        ["git", "--git-dir", str(store), "fast-import", "--quiet", "--done"],
        check=True,
        capture_output=True,
        input=bytes(stream),
        env=env,
    )
    commit = subprocess.run(
        ["git", "--git-dir", str(store), "rev-parse", "refs/heads/main"],
        check=True,
        capture_output=True,
        env=env,
    ).stdout
    return store, commit.decode().strip()


@asynccontextmanager
async def pinned_client(
    store: Path, commit: str, *, raise_app_exceptions: bool = True, ref: str | None = None
) -> AsyncGenerator[tuple[AsyncClient, GitRevisionSubject], None]:
    subject = await git_revision_subject(
        target=repository_store_target(git_dir=store),
        commit_oid=commit,
        store_identity="pin-fixture",
        ref=ref,
    )
    attach_subject(subject)
    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                yield client, subject
    finally:
        await subject.aclose()
        reset_source_session()
