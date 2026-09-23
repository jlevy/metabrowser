"""Golden transcript of real ``metab`` subprocesses acquiring a ``file://`` origin.

The other acquisition goldens run the CLI in process with the Git floor patched,
because the ordinary CI runner's Git is below it. This one patches nothing: each
command is a separate ``metab`` process that detects the Git on ``PATH``, applies
the production floor, acquires blobless into a fresh home, and reads the result.
It skips where no admitted Git is installed and cannot skip in the CI
``admitted-git`` job, which runs it on the lowest admitted Git release and the
newest patched one (see ``tests/admitted_git.py``).

The origin allows filters, so the store is published ``converging`` with only the
default revision's blobs present. The transcript pins first open, the cache hit,
a read of a prefetched blob, and the typed ``object_unavailable`` answer for the
commit that needs a blob the prefetch skipped.

Regenerate after an intended change with:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_cli_live_acquire_golden.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from metabrowser.git.tree_source import GitPath
from tests.admitted_git import require_admitted_git
from tests.test_cli_cache_acquire_golden import _block, _file_url
from tests.test_cli_golden import check_golden

pytestmark = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

# Pinned by the identity, dates, and recipe in ``_two_commit_origin``.
FIRST_REVISION = "042f85f6d00e35e36494a3c201048675cd24abc7"
SECOND_REVISION = "cf318083ef13511a14c0532985bdb24bd59d2787"
OLD_WIRE = GitPath.from_segments(b"notes", b"old.txt").to_wire()


@dataclass(frozen=True, slots=True)
class _Result:
    """The fields ``_block`` reads from a CLI result."""

    exit_code: int
    stdout: str
    stderr: str


def _git_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_AUTHOR_DATE": "2020-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2020-01-01T00:00:00Z",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return env


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()


def _two_commit_origin(tmp_path: Path) -> Path:
    """A bare origin that allows filters; HEAD changes the file the first commit added."""

    work = tmp_path / "work"
    origin = tmp_path / "origin.git"
    work.mkdir()
    _git(work, "init", "-q", "--initial-branch=topic")
    (work / "notes").mkdir()
    (work / "notes" / "old.txt").write_text("first draft\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "-c", "commit.gpgsign=false", "commit", "-qm", "first")
    (work / "notes" / "old.txt").write_text("second draft\n", encoding="utf-8")
    _git(work, "-c", "commit.gpgsign=false", "commit", "-qam", "second")
    _git(work, "clone", "-q", "--bare", "--template=", "--", str(work), str(origin))
    _git(origin, "config", "uploadpack.allowFilter", "true")
    _git(origin, "config", "uploadpack.allowAnySHA1InWant", "true")
    assert _git(origin, "rev-parse", "HEAD~1") == FIRST_REVISION
    assert _git(origin, "rev-parse", "HEAD") == SECOND_REVISION
    return origin


def _metab() -> str:
    beside = Path(sys.executable).parent / "metab"
    found = str(beside) if beside.is_file() else shutil.which("metab")
    assert found, "the metab console script is not installed in this environment"
    return found


def _run(home: Path, *args: str) -> _Result:
    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "METABROWSER_HOME": str(home),
            "METABROWSER_LOG_LEVEL": "ERROR",
            "METABROWSER_PLUGINS_DIRS": "",
            "TERM": "dumb",
            "TZ": "UTC",
        }
    )
    completed = subprocess.run(
        [_metab(), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=120,
    )
    return _Result(completed.returncode, completed.stdout, completed.stderr)


def test_golden_live_blobless_acquire_and_unconverged_read(tmp_path: Path) -> None:
    require_admitted_git()
    home = tmp_path / "home"
    url = _file_url(_two_commit_origin(tmp_path))

    first = _run(home, url, "--no-serve")
    again = _run(home, url, "--no-serve")
    shown = _run(home, url, "--show", "notes/old.txt")
    current = _run(home, url, "--api", f"/api/file?path={OLD_WIRE}")
    unconverged = _run(home, url, "--api", f"/api/git/commit/{SECOND_REVISION}")

    assert first.exit_code == 0, first
    assert "strategy: blobless" in first.stdout
    assert first.stdout == again.stdout
    assert shown.exit_code == 0, shown
    assert '"content": "second draft\\n"' in current.stdout
    assert '"code": "object_unavailable"' in unconverged.stdout

    rendered = "".join(
        [
            _block("file://<ORIGIN> --no-serve", first, origin_url=url, api=False),
            _block("file://<ORIGIN> --no-serve", again, origin_url=url, api=False),
            _block("file://<ORIGIN> --show notes/old.txt", shown, origin_url=url, api=False),
            _block(
                f"file://<ORIGIN> --api /api/file?path={OLD_WIRE}",
                current,
                origin_url=url,
                api=False,
            ),
            _block(
                f"file://<ORIGIN> --api /api/git/commit/{SECOND_REVISION}",
                unconverged,
                origin_url=url,
                api=False,
            ),
        ]
    )
    assert str(tmp_path) not in rendered
    check_golden("cli-cache-acquire-live.txt", rendered)
