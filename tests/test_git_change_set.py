"""The commit change-set check peels its revision before reading raw records."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from metabrowser.git.change_set import require_commit_blobs
from metabrowser.git.process import GitLocation, repository_store_target
from tests.git_pin_harness import fast_import_store, git_env

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")


def test_an_annotated_tag_header_is_not_read_as_change_records(tmp_path: Path) -> None:
    """Unpeeled, the tag header shifts ``-z`` tokens so a path is read as a record.

    The first path sorts first and is shaped like a raw record naming a blob the
    store lacks, so a desynchronized parse reports that blob unavailable.
    """

    forged = f":000000 100644 {'0' * 40} {'f' * 40} A".encode()
    store, commit = fast_import_store(tmp_path, {forged: b"x\n", b"a.txt": b"a\n"})
    message = "release\n"
    env = {**git_env(tmp_path), "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(
        ["git", "--git-dir", str(store), "tag", "-a", "v1", "-m", message, commit],
        check=True,
        capture_output=True,
        env=env,
    )
    tag = subprocess.run(
        ["git", "--git-dir", str(store), "rev-parse", "refs/tags/v1"],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    ).stdout.strip()
    assert tag != commit
    location = GitLocation.revision(repository_store_target(git_dir=store), commit)
    asyncio.run(require_commit_blobs(location, tag))
