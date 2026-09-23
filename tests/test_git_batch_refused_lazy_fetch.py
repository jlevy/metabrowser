"""The batch reader treats an older Git's refused lazy fetch as a missing object.

With ``GIT_NO_LAZY_FETCH`` set, Git 2.43.7 dies with ``could not fetch <oid> from
promisor remote`` for a promised object the store lacks, where newer releases answer
``missing``. The admitted-git CI lane runs the real 2.43.7; this stand-in ``git``
reproduces that exact death on any host so the reader's handling is always tested.
"""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

import pytest

from metabrowser.git import process as git_process
from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import (
    GitBatchProtocolError,
    GitObjectUnavailableError,
    _BatchObjectReader,  # pyright: ignore[reportPrivateUsage]
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the stand-in git is a shell script")

PRESENT = "1" * 40
OTHER = "2" * 40
MISSING = "3" * 40
MISSING_TOO = "4" * 40

# Answers ``info``/``contents`` for PRESENT and OTHER, and dies on MISSING the way
# Git 2.43.7 does. It counts spawns so a test can see the actor restart.
_STAND_IN = f"""#!/bin/sh
echo spawn >> "$STAND_IN_LOG"
while IFS= read -r line; do
  cmd=${{line%% *}}
  oid=${{line#* }}
  case "$cmd" in
    flush) ;;
    info|contents)
      if [ "$oid" = "{MISSING}" ] || [ "$oid" = "{MISSING_TOO}" ]; then
        echo "fatal: could not fetch $oid from promisor remote" >&2
        exit 128
      fi
      if [ "$oid" = "$STAND_IN_CORRUPT" ]; then
        echo "fatal: loose object $oid is corrupt" >&2
        exit 128
      fi
      echo "$oid blob 5"
      if [ "$cmd" = contents ]; then printf 'hello\\n'; fi
      ;;
  esac
done
"""


@pytest.fixture
def stand_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    script = tmp_path / "git"
    script.write_text(_STAND_IN)
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "spawns.log"
    monkeypatch.setenv("STAND_IN_LOG", str(log))
    monkeypatch.setenv("STAND_IN_CORRUPT", "none")
    monkeypatch.setattr(git_process, "git_executable", lambda: str(script))
    (tmp_path / "store.git").mkdir()
    return log


def _reader(tmp_path: Path) -> _BatchObjectReader:
    return _BatchObjectReader(repository_store_target(git_dir=tmp_path / "store.git"))


def test_info_many_reports_the_refused_object_missing_and_the_rest_unknown(
    tmp_path: Path, stand_in: Path
) -> None:
    """One death per chunk at most: the unanswered objects are left out, not re-asked.

    Re-asking cost a new actor per missing object, which timed a converging store's
    listing out on Git 2.43. After the chunk, a fresh actor still answers.
    """

    async def run() -> tuple[dict[str, object], bytes]:
        reader = _reader(tmp_path)
        try:
            found: dict[str, object] = dict(
                await reader.info_many((PRESENT, MISSING, OTHER, MISSING_TOO))
            )
            return found, await reader.read_blob(OTHER, max_blob_bytes=1024)
        finally:
            await reader.aclose()

    found, body = asyncio.run(run())
    assert found[PRESENT] is not None
    assert found[MISSING] is None
    assert OTHER not in found and MISSING_TOO not in found
    assert body == b"hello"
    assert len(stand_in.read_text().splitlines()) == 2


def test_a_single_read_of_the_refused_object_is_unavailable_and_the_actor_recovers(
    tmp_path: Path, stand_in: Path
) -> None:
    async def run() -> bytes:
        reader = _reader(tmp_path)
        try:
            with pytest.raises(GitObjectUnavailableError) as caught:
                await reader.read_blob(MISSING, max_blob_bytes=1024)
            assert caught.value.oid == MISSING
            return await reader.read_blob(PRESENT, max_blob_bytes=1024)
        finally:
            await reader.aclose()

    assert asyncio.run(run()) == b"hello"


def test_another_fatal_death_is_still_a_framing_failure(
    tmp_path: Path, stand_in: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a refused lazy fetch naming a requested object is read as missing."""

    monkeypatch.setenv("STAND_IN_CORRUPT", OTHER)

    async def run() -> None:
        reader = _reader(tmp_path)
        try:
            with pytest.raises(GitBatchProtocolError):
                await reader.info_many((PRESENT, OTHER))
        finally:
            await reader.aclose()

    asyncio.run(run())


def test_the_batch_actor_runs_untranslated() -> None:
    assert git_process.BATCH_OBJECT_POLICY.extra_env == {"LC_ALL": "C"}
