"""Nondestructive access to other applications' SQLite databases, with real owners.

Each scenario in ``tests/sqlite_guest_scenarios.py`` runs in a process of its own with a
real owner in another, and checks what Metabrowser's read answered and what it left
beside the database. They run as an unprivileged user, since a superuser ignores the
folder and file permissions the read-only cases depend on: as the test's own user when
that is not root (as in CI), and as ``nobody`` through ``su`` when it is (as in a
container), from a folder ``nobody`` owns. The access table they check is
``metabrowser.sqlite_access.choose``; the measurements behind it are
``explorations/sqlite-guest-reads/README.md``.
"""

from __future__ import annotations

import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests import sqlite_guest_scenarios

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path(sqlite_guest_scenarios.__file__)
# The slowest scenario, the contention run, takes about four seconds alone: three paces
# of one second each and their staging. Under a full parallel suite it takes several
# times that.
SCENARIO_TIMEOUT_S = 90

pytestmark = pytest.mark.timeout(SCENARIO_TIMEOUT_S + 15)


def _unprivileged() -> tuple[list[str], int | None]:
    """The command prefix that runs a scenario unprivileged, and the uid it runs as."""
    if os.geteuid() != 0:
        return [], None
    try:
        nobody = pwd.getpwnam("nobody")
    except KeyError:
        pytest.skip("running as root with no nobody user to drop to")
    return ["su", "nobody", "-s", "/bin/sh", "-c"], nobody.pw_uid


@pytest.fixture
def guest_folder() -> Iterator[tuple[Path, list[str]]]:
    prefix, uid = _unprivileged()
    folder = Path(tempfile.mkdtemp(prefix="mb-sqlite-guest-", dir="/tmp" if uid else None))
    if uid is not None:
        folder.chmod(0o755)
        os.chown(folder, uid, pwd.getpwuid(uid).pw_gid)
    try:
        yield folder, prefix
    finally:
        for path in [folder, *folder.rglob("*")]:
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)
        shutil.rmtree(folder, ignore_errors=True)


def _run(name: str, folder: Path, prefix: list[str]) -> dict[str, object]:
    command = [sys.executable, str(SCRIPT), name, str(folder)]
    environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    if prefix:
        inner = " ".join(_quote(part) for part in command)
        command = [*prefix, f"cd / && PYTHONPATH={_quote(str(REPO_ROOT))} exec {inner}"]
    done = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=SCENARIO_TIMEOUT_S,
        env=environment,
        cwd="/",
        check=False,
    )
    assert done.returncode == 0, f"{name} failed:\n{done.stdout}\n{done.stderr}"
    lines = done.stdout.strip().splitlines()
    assert lines[-2] == f"ok {name}"
    return json.loads(lines[-1])


def _quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


@pytest.mark.parametrize("name", sorted(sqlite_guest_scenarios.SCENARIOS))
def test_scenario(name: str, guest_folder: tuple[Path, list[str]]) -> None:
    folder, prefix = guest_folder
    _run(name, folder, prefix)
