"""Atomic record I/O and lock-verified publication in a temporary application home.

Interrupted writes and publications are real: a child interpreter is killed with SIGKILL
at the rename that would have committed, and the parent checks what a later process
finds on disk.
"""

from __future__ import annotations

import ctypes
import errno
import fcntl
import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from metabrowser import home as home_module
from metabrowser.cache.atomic import (
    MAX_RECORD_BYTES,
    RecordError,
    publish_entry,
    read_bytes_bounded,
    read_record,
    serialize_record,
    write_record_atomic,
)
from metabrowser.cache.locks import LockOrderError, repository_store_lock, staging_entry_lock
from metabrowser.cache.records import (
    CACHE_LAYOUT_CONTRACT_ID,
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    CacheLayout,
)
from metabrowser.home import (
    ensure_home,
    ensure_private_directory,
    rename_without_replacing,
    write_private_file_atomic,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="owner-only storage is POSIX-only")

STORE_KEY = "c" * 64
CHILD_TIMEOUT = 60


@pytest.fixture
def home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    ensure_home(home)
    return home


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


def _temporaries(directory: Path) -> list[str]:
    return sorted(name for name in os.listdir(directory) if name.endswith(".tmp"))


def _run_killed_at_rename(home: Path, body: str) -> subprocess.CompletedProcess[str]:
    """Run *body* in a child whose first rename that commits kills the child."""

    script = textwrap.dedent(
        """
        import os, signal, sys
        from pathlib import Path
        from metabrowser import home as home_module
        home = Path(sys.argv[1])

        def die(*_args, **_kwargs):
            os.kill(os.getpid(), signal.SIGKILL)

        os.replace = die
        os.rename = die
        home_module.rename_without_replacing = die
        """
    ) + textwrap.dedent(body)
    return subprocess.run(
        [sys.executable, "-c", script, str(home)],
        capture_output=True,
        text=True,
        timeout=CHILD_TIMEOUT,
        check=False,
    )


# ── Atomic files ───────────────────────────────────────────────────


def test_an_atomic_write_replaces_the_whole_file_with_a_private_one(home: Path) -> None:
    write_private_file_atomic(home, "cache/example.yml", b"first\n")
    first_inode = os.lstat(home / "cache/example.yml").st_ino
    write_private_file_atomic(home, "cache/example.yml", b"second\n")

    assert (home / "cache/example.yml").read_bytes() == b"second\n"
    assert os.lstat(home / "cache/example.yml").st_ino != first_inode
    assert _mode(home / "cache/example.yml") == 0o600
    assert _temporaries(home / "cache") == []


def test_a_no_replace_write_refuses_an_existing_file_and_leaves_no_temporary(home: Path) -> None:
    write_private_file_atomic(home, "cache/example.yml", b"first\n", replace=False)

    with pytest.raises(FileExistsError):
        write_private_file_atomic(home, "cache/example.yml", b"second\n", replace=False)

    assert (home / "cache/example.yml").read_bytes() == b"first\n"
    assert _temporaries(home / "cache") == []


def test_an_atomic_write_needs_an_existing_private_parent(home: Path) -> None:
    with pytest.raises(FileNotFoundError):
        write_private_file_atomic(home, "cache/missing/example.yml", b"x")
    assert not (home / "cache/missing").exists()


def test_a_write_killed_before_its_rename_leaves_the_previous_record(home: Path) -> None:
    write_private_file_atomic(home, "cache/example.yml", b"old\n")

    result = _run_killed_at_rename(
        home,
        """
        home_module.write_private_file_atomic(home, "cache/example.yml", b"new\\n")
        print("rename did not run")
        """,
    )

    assert result.returncode == -9, result.stderr
    assert (home / "cache/example.yml").read_bytes() == b"old\n"
    (leftover,) = _temporaries(home / "cache")
    assert leftover.startswith(".example.yml.")
    assert (home / "cache" / leftover).read_bytes() == b"new\n"

    write_private_file_atomic(home, "cache/example.yml", b"newer\n")

    assert (home / "cache/example.yml").read_bytes() == b"newer\n"
    assert _temporaries(home / "cache") == []


def test_a_live_writers_temporary_is_never_removed(home: Path) -> None:
    live = home / "cache/.example.yml.0123456789abcdef.tmp"
    fd = home_module.open_private_file(
        home, "cache/.example.yml.0123456789abcdef.tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL
    )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        write_private_file_atomic(home, "cache/example.yml", b"content\n")
        assert live.exists()
    finally:
        os.close(fd)
    write_private_file_atomic(home, "cache/example.yml", b"content\n")
    assert not live.exists()


def test_the_no_replace_rename_refuses_an_empty_directory_os_rename_would_replace(
    tmp_path: Path,
) -> None:
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "payload").write_text("staged")
    (tmp_path / "target").mkdir()

    with pytest.raises(FileExistsError):
        rename_without_replacing(tmp_path / "source", tmp_path / "target")

    assert (tmp_path / "source" / "payload").read_text() == "staged"
    assert list((tmp_path / "target").iterdir()) == []


def test_without_a_platform_no_replace_rename_the_absence_check_still_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(home_module, "_no_replace_rename", lambda: (None, 0, False))
    (tmp_path / "source").mkdir()
    (tmp_path / "target").mkdir()

    with pytest.raises(FileExistsError):
        rename_without_replacing(tmp_path / "source", tmp_path / "target")
    assert rename_without_replacing(tmp_path / "source", tmp_path / "published") is False
    assert (tmp_path / "published").is_dir()


def test_a_file_system_that_ignores_the_no_replace_flag_falls_back_to_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unsupported(*_arguments: object) -> int:

        ctypes.set_errno(errno.EINVAL)
        return -1

    monkeypatch.setattr(home_module, "_no_replace_rename", lambda: (unsupported, 1, False))
    (tmp_path / "source").mkdir()
    (tmp_path / "target").mkdir()

    with pytest.raises(FileExistsError):
        rename_without_replacing(tmp_path / "source", tmp_path / "target")
    assert rename_without_replacing(tmp_path / "source", tmp_path / "published") is False


# ── Publication ────────────────────────────────────────────────────


def test_publication_moves_a_staged_entry_under_its_owning_lock(home: Path) -> None:
    ensure_private_directory(home, "cache/staging/acquire-1/store")
    (home / "cache/staging/acquire-1/store/marker").write_text("complete")

    with staging_entry_lock(home, "acquire-1"), repository_store_lock(home, STORE_KEY) as owner:
        publish_entry(
            home,
            "cache/staging/acquire-1/store",
            f"cache/repository-stores/{STORE_KEY}",
            owner=owner,
        )

    assert (home / f"cache/repository-stores/{STORE_KEY}/marker").read_text() == "complete"
    assert not (home / "cache/staging/acquire-1/store").exists()


def test_publication_refuses_an_existing_target_even_an_empty_one(home: Path) -> None:
    ensure_private_directory(home, "cache/staging/acquire-1/store")
    ensure_private_directory(home, f"cache/repository-stores/{STORE_KEY}")

    with repository_store_lock(home, STORE_KEY) as owner, pytest.raises(FileExistsError):
        publish_entry(
            home,
            "cache/staging/acquire-1/store",
            f"cache/repository-stores/{STORE_KEY}",
            owner=owner,
        )

    assert (home / "cache/staging/acquire-1/store").is_dir()


def test_publication_requires_its_owning_lock_to_be_held(home: Path) -> None:
    ensure_private_directory(home, "cache/staging/acquire-1/store")
    owner = repository_store_lock(home, STORE_KEY)
    owner.release()

    with pytest.raises(LockOrderError, match="owning lock"):
        publish_entry(
            home,
            "cache/staging/acquire-1/store",
            f"cache/repository-stores/{STORE_KEY}",
            owner=owner,
        )


def test_a_publication_killed_at_its_rename_leaves_only_reclaimable_staging(home: Path) -> None:
    ensure_private_directory(home, "cache/staging/acquire-1/store")

    result = _run_killed_at_rename(
        home,
        f"""
        from metabrowser.cache import atomic, locks
        atomic.rename_without_replacing = die
        staging = locks.staging_entry_lock(home, "acquire-1")
        owner = locks.repository_store_lock(home, {STORE_KEY!r})
        atomic.publish_entry(
            home, "cache/staging/acquire-1/store", "cache/repository-stores/{STORE_KEY}", owner=owner
        )
        print("rename did not run")
        """,
    )

    assert result.returncode == -9, result.stderr
    assert not (home / f"cache/repository-stores/{STORE_KEY}").exists()
    assert (home / "cache/staging/acquire-1/store").is_dir()
    # The operating system released the killed owner's locks.
    staging_entry_lock(home, "acquire-1").release()
    repository_store_lock(home, STORE_KEY, blocking=False).release()


# ── Records ────────────────────────────────────────────────────────


def test_records_round_trip_without_a_schema_path(home: Path) -> None:
    layout = CacheLayout(format="f01", created_by="0.11.0")

    write_record_atomic(home, "cache/layout.yml", layout, CACHE_LAYOUT_CONTRACT_ID)

    assert read_record(home, "cache/layout.yml", CACHE_LAYOUT_CONTRACT_ID) == layout
    text = (home / "cache/layout.yml").read_text()
    assert text.startswith("layout:\n") or text.startswith("softschema:\n")
    assert "\n  schema:" not in text
    assert (
        serialize_record(layout, CACHE_LAYOUT_CONTRACT_ID)
        == (home / "cache/layout.yml").read_bytes()
    )


def test_a_record_read_in_the_wrong_slot_is_refused_without_naming_its_path(home: Path) -> None:
    write_record_atomic(
        home,
        "cache/layout.yml",
        CacheLayout(format="f01", created_by="0.11.0"),
        CACHE_LAYOUT_CONTRACT_ID,
    )

    with pytest.raises(RecordError) as refused:
        read_record(home, "cache/layout.yml", REPOSITORY_STORE_STATE_CONTRACT_ID)

    assert str(home) not in str(refused.value)
    assert refused.value.path == home / "cache/layout.yml"


def test_an_oversized_record_is_refused_before_it_is_parsed(home: Path) -> None:
    write_private_file_atomic(home, "cache/layout.yml", b"#" * (MAX_RECORD_BYTES + 1))

    with pytest.raises(RecordError, match="larger"):
        read_bytes_bounded(home, "cache/layout.yml")


@pytest.mark.parametrize(
    "payload",
    [
        b"softschema: [unclosed\n",
        b"!!python/object:os.system {}\n",
        b"softschema:\n  contract: com.github.jlevy.metabrowser.cache:CacheLayout/v1\n"
        b"  envelope: layout\n  status: enforced\nlayout: &a\n  format: f01\n"
        b"  created_by: 0.11.0\nother: *a\n",
    ],
    ids=["malformed", "custom-tag", "extra-top-level-key"],
)
def test_malformed_records_are_refused(home: Path, payload: bytes) -> None:
    write_private_file_atomic(home, "cache/layout.yml", payload)

    with pytest.raises(RecordError):
        read_record(home, "cache/layout.yml", CACHE_LAYOUT_CONTRACT_ID)
