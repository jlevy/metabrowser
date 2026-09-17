"""Owner-only storage for the application home.

Repository and provider cache content may be private, so every directory Metabrowser
creates under the application home is ``0700`` and every file ``0600`` whatever the
process umask, and a home that another principal could read, redirect, or replace is
refused rather than written through. These tests build every case in a temporary
directory. Foreign ownership cannot be created without privileges, so it is simulated by
rewriting the owner that ``stat`` reports for one inode; nothing on disk is changed to
fake it.
"""

from __future__ import annotations

import errno
import logging
import os
import stat
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from metabrowser import home as home_module
from metabrowser.cli.api_cli import run_api
from metabrowser.home import (
    PRIVATE_DIRECTORY_MODE,
    PRIVATE_FILE_MODE,
    PrivateStorageError,
    PrivateStorageLocation,
    PrivateStorageViolation,
    ensure_private_directory,
    open_private_file,
    validate_private_home,
)

pytestmark = pytest.mark.skipif(
    os.name != "posix",
    reason=(
        "owner-only enforcement is defined by POSIX ownership and modes; a platform "
        "without them fails closed, which test_unsupported_platform_fails_closed "
        "simulates on POSIX"
    ),
)

PRIVATE_SLUG = "github-com--acme--private-roadmap--0123abcd4567"


# ── Helpers ────────────────────────────────────────────────────────


@contextmanager
def _umask(value: int) -> Generator[None]:
    previous = os.umask(value)
    try:
        yield
    finally:
        os.umask(previous)


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


def _refusal(call: Callable[[], object]) -> PrivateStorageError:
    with pytest.raises(PrivateStorageError) as caught:
        call()
    return caught.value


def _private_dir(path: Path) -> Path:
    path.mkdir()
    path.chmod(PRIVATE_DIRECTORY_MODE)
    return path


def _write_file(home: Path, relative: str, data: bytes) -> None:
    fd = open_private_file(home, relative, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def _disguise_owner(monkeypatch: pytest.MonkeyPatch, target: Path, uid: int) -> None:
    """Make every ``stat`` of *target*'s inode report *uid* as its owner."""

    identity = os.lstat(target)
    key = (identity.st_dev, identity.st_ino)
    real_stat, real_lstat, real_fstat = os.stat, os.lstat, os.fstat

    def rewrite(result: os.stat_result) -> os.stat_result:
        if (result.st_dev, result.st_ino) != key:
            return result
        fields = list(result[:10])
        fields[4] = uid
        return os.stat_result(fields)

    def fake_stat(*args: Any, **kwargs: Any) -> os.stat_result:
        return rewrite(real_stat(*args, **kwargs))

    def fake_lstat(*args: Any, **kwargs: Any) -> os.stat_result:
        return rewrite(real_lstat(*args, **kwargs))

    def fake_fstat(fd: int) -> os.stat_result:
        return rewrite(real_fstat(fd))

    monkeypatch.setattr(os, "stat", fake_stat)
    monkeypatch.setattr(os, "lstat", fake_lstat)
    monkeypatch.setattr(os, "fstat", fake_fstat)


def _another_uid() -> int:
    return os.geteuid() + 1


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """An application-home path whose parent is private; the home itself is not created."""

    return tmp_path / "home"


# ── Creation under any umask ───────────────────────────────────────


@pytest.mark.parametrize(
    "umask", [0o000, 0o002, 0o022, 0o077, 0o277, 0o777], ids=lambda value: f"umask-{value:03o}"
)
def test_created_home_entries_and_files_are_owner_only_under_any_umask(
    home: Path, umask: int
) -> None:
    with _umask(umask):
        store = ensure_private_directory(home, f"cache/repository-stores/{PRIVATE_SLUG}")
        _write_file(home, f"cache/repository-stores/{PRIVATE_SLUG}/store.yml", b"store: {}\n")

    assert store == home / "cache" / "repository-stores" / PRIVATE_SLUG
    for directory in (home, home / "cache", home / "cache" / "repository-stores", store):
        assert _mode(directory) == PRIVATE_DIRECTORY_MODE, directory
    assert _mode(store / "store.yml") == PRIVATE_FILE_MODE
    assert (store / "store.yml").read_bytes() == b"store: {}\n"


def test_creation_is_never_more_permissive_than_the_final_mode(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new directory or file is created restrictive, not created open and then narrowed."""

    observed: list[tuple[str, int, int]] = []
    real_mkdir, real_open = os.mkdir, os.open

    def spy_mkdir(path: Any, mode: int = 0o777, *, dir_fd: int | None = None) -> None:
        real_mkdir(path, mode, dir_fd=dir_fd)
        created = os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
        observed.append((str(path), mode, stat.S_IMODE(created.st_mode)))

    def spy_open(path: Any, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if flags & os.O_CREAT:
            observed.append((str(path), mode, stat.S_IMODE(os.fstat(fd).st_mode)))
        return fd

    monkeypatch.setattr(os, "mkdir", spy_mkdir)
    monkeypatch.setattr(os, "open", spy_open)
    with _umask(0o000):
        ensure_private_directory(home, "cache/staging")
        _write_file(home, "cache/staging/record.yml", b"x\n")
    monkeypatch.undo()

    assert [Path(name).name for name, _, _ in observed] == [
        "home",
        "cache",
        "staging",
        "record.yml",
    ]
    for name, requested, at_creation in observed:
        assert requested in (PRIVATE_DIRECTORY_MODE, PRIVATE_FILE_MODE), name
        assert at_creation & 0o077 == 0, name


def test_ensure_is_idempotent_and_returns_the_same_path(home: Path) -> None:
    first = ensure_private_directory(home, "cache/sources")
    second = ensure_private_directory(home, "cache/sources")

    assert first == second == home / "cache" / "sources"
    assert ensure_private_directory(home) == home


def test_exclusive_file_creation_keeps_no_replace_semantics(home: Path) -> None:
    ensure_private_directory(home, "cache")
    _write_file(home, "cache/layout.yml", b"first\n")

    with pytest.raises(FileExistsError):
        _write_file(home, "cache/layout.yml", b"second\n")
    assert (home / "cache" / "layout.yml").read_bytes() == b"first\n"


def test_reading_a_private_file_returns_a_usable_descriptor(home: Path) -> None:
    ensure_private_directory(home, "cache")
    _write_file(home, "cache/layout.yml", b"layout\n")

    fd = open_private_file(home, "cache/layout.yml", os.O_RDONLY)
    with os.fdopen(fd, "rb") as handle:
        assert handle.read() == b"layout\n"


def test_missing_paths_are_ordinary_not_found_errors(home: Path, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        validate_private_home(home)
    with pytest.raises(FileNotFoundError):
        open_private_file(home, "config.yml", os.O_RDONLY)

    ensure_private_directory(home)
    with pytest.raises(FileNotFoundError):
        open_private_file(home, "cache/layout.yml", os.O_RDONLY)
    assert not (home / "cache").exists()

    with pytest.raises(FileNotFoundError):
        ensure_private_directory(tmp_path / "absent-parent" / "home", "cache")
    assert not (tmp_path / "absent-parent").exists()


# ── Refusal of the home itself ─────────────────────────────────────


def test_a_private_home_validates_without_changes(home: Path) -> None:
    _private_dir(home)
    before = os.lstat(home)

    validate_private_home(home)

    after = os.lstat(home)
    assert (after.st_mode, after.st_mtime_ns) == (before.st_mode, before.st_mtime_ns)


@pytest.mark.parametrize("permissive_mode", [0o750, 0o705, 0o755, 0o777, 0o710])
def test_a_permissive_home_is_refused_rather_than_repaired(
    home: Path, permissive_mode: int
) -> None:
    """An explicit permissive METABROWSER_HOME gets an actionable refusal, not a private write."""

    home.mkdir()
    home.chmod(permissive_mode)

    for call in (
        lambda: validate_private_home(home),
        lambda: ensure_private_directory(home, "cache"),
        lambda: open_private_file(home, "config.yml", os.O_WRONLY | os.O_CREAT),
    ):
        error = _refusal(call)
        assert error.violation is PrivateStorageViolation.PERMISSIVE
        assert error.location is PrivateStorageLocation.HOME
        assert error.mode == permissive_mode
        assert "chmod 700" in str(error)
        assert "METABROWSER_HOME" in str(error)

    assert _mode(home) == permissive_mode
    assert list(home.iterdir()) == []


def test_a_symlinked_home_is_refused_without_touching_its_target(
    home: Path, tmp_path: Path
) -> None:
    target = _private_dir(tmp_path / "real-home")
    home.symlink_to(target, target_is_directory=True)

    for call in (
        lambda: validate_private_home(home),
        lambda: ensure_private_directory(home, "cache"),
        lambda: open_private_file(home, "config.yml", os.O_WRONLY | os.O_CREAT),
    ):
        error = _refusal(call)
        assert error.violation is PrivateStorageViolation.SYMLINK
        assert error.location is PrivateStorageLocation.HOME
        assert "METABROWSER_HOME" in str(error)

    assert list(target.iterdir()) == []


def test_a_foreign_owned_home_is_refused(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _private_dir(home)
    _disguise_owner(monkeypatch, home, _another_uid())

    error = _refusal(lambda: ensure_private_directory(home, "cache"))

    assert error.violation is PrivateStorageViolation.FOREIGN_OWNER
    assert error.location is PrivateStorageLocation.HOME
    assert "sudo" in str(error)
    monkeypatch.undo()
    assert list(home.iterdir()) == []


def test_a_home_that_is_not_a_directory_is_refused(home: Path) -> None:
    home.write_bytes(b"not a directory\n")

    error = _refusal(lambda: ensure_private_directory(home, "cache"))

    assert error.violation is PrivateStorageViolation.NOT_DIRECTORY
    assert error.location is PrivateStorageLocation.HOME
    assert home.read_bytes() == b"not a directory\n"


# ── Refusal above the home ─────────────────────────────────────────


def test_an_ancestor_writable_by_others_is_refused_and_left_alone(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o777)
    home = shared / "home"

    for call in (
        lambda: ensure_private_directory(home, "cache"),
        lambda: open_private_file(home, "config.yml", os.O_RDONLY),
    ):
        error = _refusal(call)
        assert error.violation is PrivateStorageViolation.PERMISSIVE
        assert error.location is PrivateStorageLocation.HOME_ANCESTOR
        assert error.mode == 0o777

    assert _mode(shared) == 0o777
    assert not home.exists()


def test_a_sticky_world_writable_ancestor_is_accepted(tmp_path: Path) -> None:
    """A shared temporary directory cannot rename an entry it does not own."""

    shared = tmp_path / "shared-tmp"
    shared.mkdir()
    shared.chmod(0o1777)

    created = ensure_private_directory(shared / "home", "cache")

    assert _mode(created) == PRIVATE_DIRECTORY_MODE
    assert stat.S_IMODE(os.lstat(shared).st_mode) == 0o1777


@pytest.mark.parametrize("readable_mode", [0o755, 0o750, 0o711, 0o700])
def test_readable_but_not_writable_ancestors_are_accepted_unchanged(
    tmp_path: Path, readable_mode: int
) -> None:
    """The user's own directories above the home are never tightened."""

    parent = tmp_path / "workspace"
    parent.mkdir()
    parent.chmod(readable_mode)

    ensure_private_directory(parent / "home", "cache")

    assert _mode(parent) == readable_mode


def test_a_foreign_owned_ancestor_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = _private_dir(tmp_path / "someone-elses")
    _disguise_owner(monkeypatch, parent, _another_uid())

    error = _refusal(lambda: ensure_private_directory(parent / "home", "cache"))

    assert error.violation is PrivateStorageViolation.FOREIGN_OWNER
    assert error.location is PrivateStorageLocation.HOME_ANCESTOR
    monkeypatch.undo()
    assert not (parent / "home").exists()


def test_an_owned_symlink_above_the_home_is_followed_and_its_target_verified(
    tmp_path: Path,
) -> None:
    """A link the user or root owns is layout, as with /home pointing into /var/home."""

    real = _private_dir(tmp_path / "real")
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    ensure_private_directory(link / "home", "cache")
    assert _mode(real / "home" / "cache") == PRIVATE_DIRECTORY_MODE

    real.chmod(0o777)
    error = _refusal(lambda: validate_private_home(link / "home"))
    assert error.violation is PrivateStorageViolation.PERMISSIVE
    assert error.location is PrivateStorageLocation.HOME_ANCESTOR
    assert _mode(real) == 0o777


def test_a_relative_symlink_above_the_home_is_resolved_from_its_directory(
    tmp_path: Path,
) -> None:
    nested = _private_dir(tmp_path / "nested")
    _private_dir(nested / "real")
    (nested / "link").symlink_to(Path("..") / "nested" / "real", target_is_directory=True)

    created = ensure_private_directory(nested / "link" / "home", "cache")

    assert created == nested / "link" / "home" / "cache"
    assert _mode(nested / "real" / "home" / "cache") == PRIVATE_DIRECTORY_MODE


def test_a_foreign_owned_symlink_above_the_home_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = _private_dir(tmp_path / "real")
    link = tmp_path / "planted"
    link.symlink_to(real, target_is_directory=True)
    _disguise_owner(monkeypatch, link, _another_uid())

    error = _refusal(lambda: ensure_private_directory(link / "home", "cache"))

    assert error.violation is PrivateStorageViolation.SYMLINK
    assert error.location is PrivateStorageLocation.HOME_ANCESTOR
    monkeypatch.undo()
    assert list(real.iterdir()) == []


def test_a_symlink_loop_above_the_home_is_unverifiable(tmp_path: Path) -> None:
    (tmp_path / "loop-a").symlink_to(tmp_path / "loop-b")
    (tmp_path / "loop-b").symlink_to(tmp_path / "loop-a")

    error = _refusal(lambda: validate_private_home(tmp_path / "loop-a" / "home"))

    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert error.location is PrivateStorageLocation.HOME_ANCESTOR


# ── Entries below the home: repair or refuse ───────────────────────


def test_owned_permissive_entries_are_tightened(
    home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A Metabrowser entry the current user owns is safely repairable."""

    _private_dir(home)
    (home / "cache").mkdir()
    (home / "cache").chmod(0o755)
    (home / "cache" / "sources").mkdir()
    (home / "cache" / "sources").chmod(0o777)
    (home / "cache" / "sources" / "state.yml").write_bytes(b"state\n")
    (home / "cache" / "sources" / "state.yml").chmod(0o644)
    (home / "config.yml").write_bytes(b"config\n")
    (home / "config.yml").chmod(0o400)

    with caplog.at_level(logging.WARNING, logger="metabrowser.home"):
        ensure_private_directory(home, "cache/sources")
        os.close(open_private_file(home, "cache/sources/state.yml", os.O_RDONLY))
        os.close(open_private_file(home, "config.yml", os.O_RDWR))

    assert _mode(home / "cache") == PRIVATE_DIRECTORY_MODE
    assert _mode(home / "cache" / "sources") == PRIVATE_DIRECTORY_MODE
    assert _mode(home / "cache" / "sources" / "state.yml") == PRIVATE_FILE_MODE
    assert _mode(home / "config.yml") == PRIVATE_FILE_MODE
    assert len([r for r in caplog.records if "owner-only" in r.getMessage()]) == 4


def test_an_owned_entry_its_owner_cannot_read_is_restored(home: Path) -> None:
    _private_dir(home)
    (home / "cache").mkdir()
    (home / "cache").chmod(0o000)
    try:
        created = ensure_private_directory(home, "cache/staging")
    finally:
        if (home / "cache").exists():
            (home / "cache").chmod(PRIVATE_DIRECTORY_MODE)

    assert _mode(home / "cache") == PRIVATE_DIRECTORY_MODE
    assert _mode(created) == PRIVATE_DIRECTORY_MODE


def test_a_foreign_owned_entry_is_refused_and_not_repaired(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home)
    (home / "cache").mkdir()
    (home / "cache").chmod(0o755)
    _disguise_owner(monkeypatch, home / "cache", _another_uid())

    error = _refusal(lambda: ensure_private_directory(home, "cache/staging"))

    assert error.violation is PrivateStorageViolation.FOREIGN_OWNER
    assert error.location is PrivateStorageLocation.ENTRY
    monkeypatch.undo()
    assert _mode(home / "cache") == 0o755
    assert not (home / "cache" / "staging").exists()


def test_a_foreign_owned_file_is_refused_and_not_repaired(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home)
    (home / "config.yml").write_bytes(b"root wrote this\n")
    (home / "config.yml").chmod(0o644)
    _disguise_owner(monkeypatch, home / "config.yml", _another_uid())

    error = _refusal(lambda: open_private_file(home, "config.yml", os.O_RDONLY))

    assert error.violation is PrivateStorageViolation.FOREIGN_OWNER
    assert error.location is PrivateStorageLocation.ENTRY
    monkeypatch.undo()
    assert _mode(home / "config.yml") == 0o644


def test_a_symlinked_entry_is_refused_without_touching_its_target(
    home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    outside.chmod(0o755)
    ensure_private_directory(home)
    (home / "cache").symlink_to(outside, target_is_directory=True)

    for call in (
        lambda: ensure_private_directory(home, "cache/staging"),
        lambda: open_private_file(home, "cache/layout.yml", os.O_WRONLY | os.O_CREAT),
    ):
        error = _refusal(call)
        assert error.violation is PrivateStorageViolation.SYMLINK
        assert error.location is PrivateStorageLocation.ENTRY

    assert _mode(outside) == 0o755
    assert list(outside.iterdir()) == []


def test_a_symlinked_file_is_refused_without_writing_through_it(home: Path, tmp_path: Path) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"keep me\n")
    victim.chmod(0o644)
    dangling = tmp_path / "never-created.txt"
    ensure_private_directory(home, "cache")
    (home / "config.yml").symlink_to(victim)
    (home / "cache" / "layout.yml").symlink_to(dangling)

    for relative, flags in (
        ("config.yml", os.O_WRONLY | os.O_CREAT | os.O_TRUNC),
        ("config.yml", os.O_RDONLY),
        ("cache/layout.yml", os.O_WRONLY | os.O_CREAT),
    ):
        error = _refusal(lambda r=relative, f=flags: open_private_file(home, r, f))
        assert error.violation is PrivateStorageViolation.SYMLINK
        assert error.location is PrivateStorageLocation.ENTRY

    assert victim.read_bytes() == b"keep me\n"
    assert _mode(victim) == 0o644
    assert not dangling.exists()


def test_entries_of_the_wrong_type_are_refused(home: Path) -> None:
    ensure_private_directory(home, "cache/locks")
    (home / "cache" / "staging").write_bytes(b"not a directory\n")

    error = _refusal(lambda: ensure_private_directory(home, "cache/staging/job"))
    assert error.violation is PrivateStorageViolation.NOT_DIRECTORY
    assert error.location is PrivateStorageLocation.ENTRY

    error = _refusal(lambda: open_private_file(home, "cache/locks", os.O_RDONLY))
    assert error.violation is PrivateStorageViolation.NOT_REGULAR_FILE
    assert error.location is PrivateStorageLocation.ENTRY


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFOs are unavailable")
def test_a_fifo_is_refused_without_blocking(home: Path) -> None:
    ensure_private_directory(home, "cache/locks")
    os.mkfifo(home / "cache" / "locks" / "home.lock", 0o600)

    error = _refusal(
        lambda: open_private_file(home, "cache/locks/home.lock", os.O_RDWR | os.O_CREAT)
    )

    assert error.violation is PrivateStorageViolation.NOT_REGULAR_FILE


# ── TOCTOU ─────────────────────────────────────────────────────────


def _swap_after_nofollow_stat(
    monkeypatch: pytest.MonkeyPatch, name: str, replace: Callable[[], None]
) -> None:
    """Run *replace* right after the entry *name* is inspected, before it is opened."""

    real_stat = os.stat
    swapped: list[bool] = []

    def racing_stat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        result = real_stat(path, *args, **kwargs)
        if path == name and kwargs.get("dir_fd") is not None and not swapped:
            swapped.append(True)
            replace()
        return result

    monkeypatch.setattr(os, "stat", racing_stat)


def test_a_directory_swapped_for_a_symlink_mid_check_is_refused(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    outside.chmod(0o755)
    ensure_private_directory(home, "cache/staging")
    staging = home / "cache" / "staging"

    def replace() -> None:
        staging.rmdir()
        staging.symlink_to(outside, target_is_directory=True)

    _swap_after_nofollow_stat(monkeypatch, "staging", replace)
    error = _refusal(lambda: ensure_private_directory(home, "cache/staging/job"))
    monkeypatch.undo()

    assert error.violation is PrivateStorageViolation.SYMLINK
    assert list(outside.iterdir()) == []
    assert _mode(outside) == 0o755


def test_a_directory_replaced_mid_check_is_unverifiable(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home, "cache/staging")
    staging = home / "cache" / "staging"

    def replace() -> None:
        staging.rename(home / "cache" / "moved-aside")
        _private_dir(staging)

    _swap_after_nofollow_stat(monkeypatch, "staging", replace)
    error = _refusal(lambda: ensure_private_directory(home, "cache/staging/job"))
    monkeypatch.undo()

    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert error.location is PrivateStorageLocation.ENTRY
    assert not (staging / "job").exists()


def test_a_file_swapped_for_a_symlink_mid_check_is_refused(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"keep me\n")
    ensure_private_directory(home)
    _write_file(home, "config.yml", b"mine\n")
    config = home / "config.yml"

    def replace() -> None:
        config.unlink()
        config.symlink_to(victim)

    _swap_after_nofollow_stat(monkeypatch, "config.yml", replace)
    error = _refusal(lambda: open_private_file(home, "config.yml", os.O_WRONLY | os.O_TRUNC))
    monkeypatch.undo()

    assert error.violation is PrivateStorageViolation.SYMLINK
    assert victim.read_bytes() == b"keep me\n"


# ── Unverifiable storage fails closed ──────────────────────────────


def test_unsupported_platform_fails_closed(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows has no POSIX modes here; until its ACL check exists it must refuse, not write."""

    monkeypatch.setattr(home_module, "_owner_only_checks_supported", lambda: False)

    for call in (
        lambda: validate_private_home(home),
        lambda: ensure_private_directory(home, "cache"),
        lambda: open_private_file(home, "config.yml", os.O_WRONLY | os.O_CREAT),
    ):
        error = _refusal(call)
        assert error.violation is PrivateStorageViolation.UNVERIFIABLE
        assert error.location is PrivateStorageLocation.HOME
        assert "Windows" in str(error)

    assert not home.exists()


def test_a_file_system_that_ignores_modes_is_unverifiable(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home)
    (home / "cache").mkdir()
    (home / "cache").chmod(0o755)
    (home / "config.yml").write_bytes(b"config\n")
    (home / "config.yml").chmod(0o644)

    def ignore_mode(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(os, "chmod", ignore_mode)
    monkeypatch.setattr(os, "fchmod", ignore_mode)

    error = _refusal(lambda: ensure_private_directory(home, "cache"))
    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert error.location is PrivateStorageLocation.ENTRY
    assert "file system" in str(error)

    error = _refusal(lambda: open_private_file(home, "config.yml", os.O_RDONLY))
    assert error.violation is PrivateStorageViolation.UNVERIFIABLE

    # The umask strips owner write, so only a chmod that takes effect reaches 0700.
    with _umask(0o277):
        error = _refusal(lambda: ensure_private_directory(home.parent / "fresh-home"))
    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert error.location is PrivateStorageLocation.HOME


def test_a_denied_check_is_unverifiable_with_its_cause(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home, "cache")
    real_stat = os.stat

    def denied(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        if path == "cache":
            raise PermissionError(errno.EACCES, "Permission denied")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", denied)
    error = _refusal(lambda: ensure_private_directory(home, "cache"))

    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert isinstance(error.__cause__, PermissionError)


# ── Input boundaries ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "relative",
    [
        "../escape",
        "cache/../../escape",
        "/etc",
        "cache//staging",
        "cache/./staging",
        "a\\b",
        "a\0b",
    ],
)
def test_entry_paths_must_stay_inside_the_home(home: Path, tmp_path: Path, relative: str) -> None:
    with pytest.raises(ValueError):
        ensure_private_directory(home, relative)
    with pytest.raises(ValueError):
        open_private_file(home, relative, os.O_WRONLY | os.O_CREAT)

    assert sorted(path.name for path in tmp_path.iterdir()) == []


@pytest.mark.parametrize("bad_home", [Path("relative/home"), Path("/tmp/../home")])
def test_the_home_must_be_an_absolute_normalized_path(bad_home: Path) -> None:
    with pytest.raises(ValueError):
        ensure_private_directory(bad_home, "cache")


def test_open_private_file_rejects_directory_flags_and_the_home_itself(home: Path) -> None:
    ensure_private_directory(home)

    with pytest.raises(ValueError):
        open_private_file(home, "", os.O_RDONLY)
    with pytest.raises(ValueError):
        open_private_file(home, "cache", os.O_RDONLY | os.O_DIRECTORY)


# ── Diagnostics ────────────────────────────────────────────────────


def test_refusals_name_a_remedy_but_never_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal may reach a job status or an API envelope, where a cache path is private."""

    home = tmp_path / "ghp_notARealTokenButShapedLikeOne" / "home"
    home.parent.mkdir()
    ensure_private_directory(home, "cache/sources")
    source = home / "cache" / "sources" / PRIVATE_SLUG
    errors: list[PrivateStorageError] = []

    source.symlink_to(tmp_path, target_is_directory=True)
    errors.append(_refusal(lambda: ensure_private_directory(home, f"cache/sources/{PRIVATE_SLUG}")))
    source.unlink()

    source.write_bytes(b"")
    errors.append(_refusal(lambda: ensure_private_directory(home, f"cache/sources/{PRIVATE_SLUG}")))
    source.unlink()

    source.mkdir()
    with monkeypatch.context() as patch:
        _disguise_owner(patch, source, _another_uid())
        errors.append(
            _refusal(lambda: ensure_private_directory(home, f"cache/sources/{PRIVATE_SLUG}"))
        )

    home.chmod(0o755)
    errors.append(_refusal(lambda: validate_private_home(home)))
    home.chmod(PRIVATE_DIRECTORY_MODE)

    home.parent.chmod(0o777)
    errors.append(_refusal(lambda: validate_private_home(home)))
    home.parent.chmod(PRIVATE_DIRECTORY_MODE)

    assert {error.violation for error in errors} == {
        PrivateStorageViolation.SYMLINK,
        PrivateStorageViolation.NOT_DIRECTORY,
        PrivateStorageViolation.FOREIGN_OWNER,
        PrivateStorageViolation.PERMISSIVE,
    }
    for error in errors:
        message = str(error)
        assert "Metabrowser application home" in message
        assert str(tmp_path) not in message
        assert PRIVATE_SLUG not in message
        assert "ghp_" not in message
        assert error.path.is_absolute()
    assert errors[0].path == source


# ── Local browsing and attached checkouts are untouched ────────────


def test_local_browsing_never_consults_the_application_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """``metab <local-dir>`` keeps working however permissive the home or the directory is."""

    unsafe_home = tmp_path / "shared-home"
    unsafe_home.mkdir()
    unsafe_home.chmod(0o777)
    linked_home = tmp_path / "home-link"
    linked_home.symlink_to(unsafe_home, target_is_directory=True)
    monkeypatch.setenv("METABROWSER_HOME", str(linked_home))

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "README.md").write_text("hello\n")
    checkout.chmod(0o777)
    linked_checkout = tmp_path / "checkout-link"
    linked_checkout.symlink_to(checkout, target_is_directory=True)

    run_api(linked_checkout, route="/api/tree?depth=1", fmt="json")

    assert "status: 200" in capsys.readouterr().out
    assert _mode(checkout) == 0o777
    assert _mode(unsafe_home) == 0o777
    assert list(unsafe_home.iterdir()) == []


def test_provider_storage_beside_a_user_checkout_leaves_the_checkout_unchanged(
    tmp_path: Path,
) -> None:
    """Attaching a checkout writes only below the home, never into or around the checkout."""

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace.chmod(0o755)
    checkout = workspace / "project"
    checkout.mkdir()
    checkout.chmod(0o775)
    (checkout / "README.md").write_bytes(b"project\n")
    (checkout / "README.md").chmod(0o664)
    before = {path: os.lstat(path) for path in (workspace, checkout, checkout / "README.md")}
    home = workspace / "home"

    ensure_private_directory(home, "cache/provider-repositories/github/instance/repository")
    ensure_private_directory(home, "cache/provider-bindings")
    _write_file(home, "cache/provider-bindings/source-key.yml", b"binding\n")
    with pytest.raises(ValueError):
        ensure_private_directory(home, "../project")

    for path, original in before.items():
        current = os.lstat(path)
        assert (current.st_mode, current.st_uid) == (original.st_mode, original.st_uid), path
    assert (checkout / "README.md").read_bytes() == b"project\n"
    assert sorted(p.name for p in checkout.iterdir()) == ["README.md"]
