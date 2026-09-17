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

import contextlib
import errno
import logging
import os
import shutil
import stat
import subprocess
import sys
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from metabrowser import home as home_module
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


skip_as_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root is never denied by modes, so a denial cannot be staged"
)
darwin_only = pytest.mark.skipif(
    sys.platform != "darwin",
    reason=(
        "extended ACLs are inspected only on macOS; a Linux POSIX ACL cannot exceed the "
        "group-class mask that 0700 and 0600 clear, as metabrowser/home.py records"
    ),
)


_PATHS_GIVEN_ACLS: list[Path] = []


def _add_acl(path: Path, entry: str) -> None:
    subprocess.run(["/bin/chmod", "+a", entry, str(path)], check=True, capture_output=True)
    _PATHS_GIVEN_ACLS.append(path)


@pytest.fixture(autouse=True)
def remove_test_acls() -> Generator[None]:
    """Strip ACLs a test added; a ``deny delete`` entry would stop temp-directory cleanup."""

    yield
    while _PATHS_GIVEN_ACLS:
        path = _PATHS_GIVEN_ACLS.pop()
        if os.path.lexists(path):
            subprocess.run(["/bin/chmod", "-N", str(path)], check=False, capture_output=True)


def _current_user_name() -> str:
    return subprocess.run(
        ["/usr/bin/id", "-un"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _acl_lines(path: Path) -> list[str]:
    listing = subprocess.run(
        ["/bin/ls", "-led", str(path)], check=True, capture_output=True, text=True
    ).stdout
    return [line.strip() for line in listing.splitlines()[1:]]


def _outcome_within_deadline(call: Callable[[], object], fifo: Path) -> BaseException | None:
    """Run *call* in a thread and fail if it blocks opening *fifo*."""

    outcome: list[BaseException | None] = []

    def run() -> None:
        try:
            call()
        except BaseException as error:
            outcome.append(error)
        else:
            outcome.append(None)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(5.0)
    if thread.is_alive():
        # Open the other end so the blocked open returns and the thread can finish.
        released: list[int] = []
        for flags in (os.O_RDONLY | os.O_NONBLOCK, os.O_WRONLY | os.O_NONBLOCK):
            with contextlib.suppress(OSError):
                released.append(os.open(fifo, flags))
        thread.join(5.0)
        for fd in released:
            os.close(fd)
        pytest.fail("opening a private file blocked on a FIFO")
    return outcome[0]


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


def test_repair_removes_only_group_and_other_access(
    home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A Metabrowser entry the current user owns is repairable, without widening the owner."""

    _private_dir(home)
    (home / "cache").mkdir()
    (home / "cache").chmod(0o755)
    (home / "cache" / "objects").mkdir()
    (home / "cache" / "objects" / "pack.idx").write_bytes(b"pack\n")
    (home / "cache" / "objects" / "pack.idx").chmod(0o444)
    (home / "cache" / "objects").chmod(0o551)
    (home / "config.yml").write_bytes(b"config\n")
    (home / "config.yml").chmod(0o640)

    try:
        with caplog.at_level(logging.WARNING, logger="metabrowser.home"):
            ensure_private_directory(home, "cache/objects")
            os.close(open_private_file(home, "cache/objects/pack.idx", os.O_RDONLY))
            os.close(open_private_file(home, "config.yml", os.O_RDONLY))

        assert _mode(home / "cache") == 0o700
        assert _mode(home / "cache" / "objects") == 0o500
        assert _mode(home / "cache" / "objects" / "pack.idx") == 0o400
        assert _mode(home / "config.yml") == 0o600
        assert len([r for r in caplog.records if "owner-only" in r.getMessage()]) == 4
    finally:
        (home / "cache" / "objects").chmod(PRIVATE_DIRECTORY_MODE)


@pytest.mark.parametrize(
    ("directory_mode", "file_mode"),
    [(0o700, 0o600), (0o500, 0o400), (0o700, 0o400), (0o500, 0o700)],
    ids=lambda mode: f"{mode:04o}",
)
def test_owner_only_entries_are_accepted_without_repair(
    home: Path, caplog: pytest.LogCaptureFixture, directory_mode: int, file_mode: int
) -> None:
    ensure_private_directory(home, "cache/objects")
    (home / "cache" / "objects" / "ab").write_bytes(b"object\n")
    (home / "cache" / "objects" / "ab").chmod(file_mode)
    (home / "cache" / "objects").chmod(directory_mode)

    try:
        with caplog.at_level(logging.WARNING, logger="metabrowser.home"):
            ensure_private_directory(home, "cache/objects")
            os.close(open_private_file(home, "cache/objects/ab", os.O_RDONLY))
            validate_private_home(home)
    finally:
        (home / "cache" / "objects").chmod(PRIVATE_DIRECTORY_MODE)

    assert _mode(home / "cache" / "objects" / "ab") == file_mode
    assert caplog.records == []


@skip_as_root
def test_owner_permissions_are_never_widened(home: Path) -> None:
    """An owner-only entry its owner cannot use is refused, not given more owner access."""

    ensure_private_directory(home)
    (home / "cache").mkdir()
    (home / "cache").chmod(0o000)
    (home / "config.yml").write_bytes(b"config\n")
    (home / "config.yml").chmod(0o400)
    try:
        error = _refusal(lambda: ensure_private_directory(home, "cache/staging"))
        assert error.violation is PrivateStorageViolation.UNVERIFIABLE
        assert "never widens" in str(error)
        assert _mode(home / "cache") == 0o000

        error = _refusal(lambda: open_private_file(home, "config.yml", os.O_RDWR))
        assert error.violation is PrivateStorageViolation.UNVERIFIABLE
        assert "never widens" in str(error)
        assert _mode(home / "config.yml") == 0o400
    finally:
        (home / "cache").chmod(PRIVATE_DIRECTORY_MODE)


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_a_git_store_written_under_umask_077_validates_without_repair(
    home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Git child processes run with umask 077, which yields 0700 directories and 0400 objects."""

    ensure_private_directory(home, "cache/repository-stores/store")
    store = home / "cache" / "repository-stores" / "store"
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    } | {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(
        ["git", "init", "--quiet", "--bare", "repository.git"],
        cwd=store,
        check=True,
        env=environment,
        umask=0o077,
    )
    (store / "blob.txt").write_bytes(b"private content\n")
    subprocess.run(
        ["git", "--git-dir", "repository.git", "hash-object", "-w", "blob.txt"],
        cwd=store,
        check=True,
        env=environment,
        umask=0o077,
        capture_output=True,
    )
    (store / "blob.txt").unlink()
    before = {path: os.lstat(path).st_mode for path in store.rglob("*")}
    modes = {stat.S_IMODE(mode) for mode in before.values()}
    assert 0o400 in modes, "Git wrote its object owner-read-only"

    with caplog.at_level(logging.WARNING, logger="metabrowser.home"):
        for path in sorted(before):
            relative = path.relative_to(home).as_posix()
            if stat.S_ISDIR(before[path]):
                ensure_private_directory(home, relative)
            else:
                os.close(open_private_file(home, relative, os.O_RDONLY))
        validate_private_home(home)

    assert caplog.records == []
    assert {path: os.lstat(path).st_mode for path in store.rglob("*")} == before


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


@pytest.mark.parametrize(
    "flags",
    [os.O_RDONLY, os.O_WRONLY, os.O_WRONLY | os.O_CREAT],
    ids=["read", "write", "write-create"],
)
def test_a_fifo_is_refused_without_blocking(home: Path, flags: int) -> None:
    """O_RDONLY and O_WRONLY opens of a FIFO block until the other end opens."""

    ensure_private_directory(home, "cache/locks")
    fifo = home / "cache" / "locks" / "home.lock"
    os.mkfifo(fifo, 0o600)

    error = _outcome_within_deadline(
        lambda: open_private_file(home, "cache/locks/home.lock", flags), fifo
    )

    assert isinstance(error, PrivateStorageError)
    assert error.violation is PrivateStorageViolation.NOT_REGULAR_FILE
    assert stat.S_ISFIFO(os.lstat(fifo).st_mode)


# ── TOCTOU ─────────────────────────────────────────────────────────


def _swap_after_nofollow_stat(
    monkeypatch: pytest.MonkeyPatch, name: str | Path, replace: Callable[[], None]
) -> None:
    """Run *replace* right after *name* is inspected without following links.

    A string names an entry inspected relative to its parent's descriptor; a path names
    the home. The swap happens whether or not the inspection found anything.
    """

    real_stat = os.stat
    swapped: list[bool] = []

    def racing_stat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        relative = isinstance(name, str)
        matches = (
            path == name
            and kwargs.get("follow_symlinks") is False
            and (kwargs.get("dir_fd") is not None) == relative
        )
        try:
            return real_stat(path, *args, **kwargs)
        finally:
            if matches and not swapped:
                swapped.append(True)
                replace()

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
        # Renamed, not removed: the original stays allocated, so the new directory cannot
        # reuse its inode number, which Linux would otherwise do at once.
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

    linked = home / "cache" / "sources" / f"{PRIVATE_SLUG}.yml"
    linked.write_bytes(b"")
    os.link(linked, tmp_path / "elsewhere.yml")
    errors.append(
        _refusal(lambda: open_private_file(home, f"cache/sources/{PRIVATE_SLUG}.yml", os.O_RDONLY))
    )
    (tmp_path / "elsewhere.yml").unlink()
    linked.chmod(0o644)
    errors.append(
        _refusal(lambda: open_private_file(home, f"cache/sources/{PRIVATE_SLUG}.yml", os.O_WRONLY))
    )

    assert {error.violation for error in errors} == {
        PrivateStorageViolation.SYMLINK,
        PrivateStorageViolation.NOT_DIRECTORY,
        PrivateStorageViolation.FOREIGN_OWNER,
        PrivateStorageViolation.PERMISSIVE,
        PrivateStorageViolation.HARD_LINK,
    }
    for error in errors:
        message = str(error)
        assert "Metabrowser application home" in message
        assert str(tmp_path) not in message
        assert PRIVATE_SLUG not in message
        assert "ghp_" not in message
        assert error.path.is_absolute()
    assert errors[0].path == source


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


# ── Ancestor and home evidence (review mutants m2, m3, m5, m8) ─────


def test_a_writable_ancestor_two_levels_above_the_home_is_refused(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o777)
    mine = _private_dir(shared / "mine")

    error = _refusal(lambda: ensure_private_directory(mine / "home", "cache"))

    assert error.violation is PrivateStorageViolation.PERMISSIVE
    assert error.location is PrivateStorageLocation.HOME_ANCESTOR
    assert error.path == shared
    assert not (mine / "home").exists()


def test_a_sticky_ancestor_owned_by_another_user_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sticky bit protects entries from other users, not from the directory's owner."""

    shared = tmp_path / "sticky-foreign"
    shared.mkdir()
    shared.chmod(0o1777)
    _disguise_owner(monkeypatch, shared, _another_uid())

    error = _refusal(lambda: ensure_private_directory(shared / "home", "cache"))

    assert error.violation is PrivateStorageViolation.FOREIGN_OWNER
    assert error.location is PrivateStorageLocation.HOME_ANCESTOR
    monkeypatch.undo()
    assert not (shared / "home").exists()


def test_the_root_directory_is_verified(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _disguise_owner(monkeypatch, Path("/"), _another_uid())

    error = _refusal(lambda: ensure_private_directory(home, "cache"))

    assert error.violation is PrivateStorageViolation.FOREIGN_OWNER
    assert error.location is PrivateStorageLocation.HOME_ANCESTOR
    assert error.path == Path("/")


def test_the_home_replaced_mid_check_is_unverifiable(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _private_dir(home)
    aside = home.parent / "home-aside"

    def replace() -> None:
        # Renamed, not removed, so the new home cannot reuse the original's inode number.
        home.rename(aside)
        _private_dir(home)

    _swap_after_nofollow_stat(monkeypatch, home, replace)
    error = _refusal(lambda: ensure_private_directory(home, "cache"))
    monkeypatch.undo()

    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert error.location is PrivateStorageLocation.HOME
    assert list(home.iterdir()) == []
    assert list(aside.iterdir()) == []


# ── Files: identity, hard links, and open side effects (m4, m6, m7) ─


@pytest.mark.parametrize("replacement", ["new-file", "hard-link"])
@pytest.mark.parametrize(
    "flags", [os.O_RDONLY, os.O_WRONLY | os.O_TRUNC], ids=["read", "write-truncate"]
)
def test_a_file_replaced_by_another_file_mid_check_is_refused_untouched(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str, flags: int
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside data that must survive\n")
    outside.chmod(0o644)
    ensure_private_directory(home, "cache")
    _write_file(home, "cache/layout.yml", b"ours\n")
    layout = home / "cache" / "layout.yml"

    def replace() -> None:
        layout.unlink()
        if replacement == "hard-link":
            os.link(outside, layout)
        else:
            layout.write_bytes(b"someone else's\n")
            layout.chmod(PRIVATE_FILE_MODE)

    # Linux file systems reuse a freed inode number at once, so a replacement created right
    # after the unlink could carry the original's number and pass the identity check. An
    # open descriptor keeps the original inode allocated until the call returns.
    original = os.open(layout, os.O_RDONLY)
    try:
        _swap_after_nofollow_stat(monkeypatch, "layout.yml", replace)
        error = _refusal(lambda: open_private_file(home, "cache/layout.yml", flags))
        monkeypatch.undo()
    finally:
        os.close(original)

    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert outside.read_bytes() == b"outside data that must survive\n"
    assert _mode(outside) == 0o644


@pytest.mark.parametrize("replacement", ["shared-mode", "hard-link", "foreign-owner"])
def test_a_replacement_that_reuses_the_inode_number_is_still_judged_on_its_descriptor(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str
) -> None:
    """(device, inode) cannot prove identity alone, so every privacy fact is judged on the fd.

    The replacement is made to report the original's device and inode, as an immediately
    reused inode number would, and must still be refused for what it actually is.
    """

    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside data that must survive\n")
    outside.chmod(0o644)
    ensure_private_directory(home, "cache")
    _write_file(home, "cache/layout.yml", b"ours\n")
    layout = home / "cache" / "layout.yml"
    original = os.lstat(layout)
    real_fstat = os.fstat

    def replace() -> None:
        layout.unlink()
        if replacement == "hard-link":
            os.link(outside, layout)
        else:
            layout.write_bytes(b"replacement\n")
            layout.chmod(0o644 if replacement == "shared-mode" else PRIVATE_FILE_MODE)
        swapped = os.lstat(layout)
        owner = _another_uid() if replacement == "foreign-owner" else swapped.st_uid

        def reused_identity(fd: int) -> os.stat_result:
            result = real_fstat(fd)
            if (result.st_dev, result.st_ino) != (swapped.st_dev, swapped.st_ino):
                return result
            fields = list(result[:10])
            fields[1], fields[2], fields[4] = original.st_ino, original.st_dev, owner
            return os.stat_result(fields)

        monkeypatch.setattr(os, "fstat", reused_identity)

    _swap_after_nofollow_stat(monkeypatch, "layout.yml", replace)
    error = _refusal(lambda: open_private_file(home, "cache/layout.yml", os.O_WRONLY | os.O_TRUNC))
    monkeypatch.undo()

    assert (
        error.violation
        is {
            "shared-mode": PrivateStorageViolation.PERMISSIVE,
            "hard-link": PrivateStorageViolation.HARD_LINK,
            "foreign-owner": PrivateStorageViolation.FOREIGN_OWNER,
        }[replacement]
    )
    assert outside.read_bytes() == b"outside data that must survive\n"
    assert _mode(outside) == 0o644
    if replacement != "hard-link":
        assert layout.read_bytes() == b"replacement\n"


@pytest.mark.parametrize(
    "flags",
    [os.O_RDONLY, os.O_RDWR, os.O_WRONLY | os.O_CREAT | os.O_TRUNC],
    ids=["read", "read-write", "write-create-truncate"],
)
def test_a_hard_linked_file_is_refused_and_never_repaired(
    home: Path, tmp_path: Path, flags: int
) -> None:
    outside = tmp_path / "public_index.html"
    outside.write_bytes(b"precious shared content\n")
    outside.chmod(0o644)
    ensure_private_directory(home, "cache")
    os.link(outside, home / "cache" / "layout.yml")

    error = _refusal(lambda: open_private_file(home, "cache/layout.yml", flags))

    assert error.violation is PrivateStorageViolation.HARD_LINK
    assert error.location is PrivateStorageLocation.ENTRY
    assert "hard link" in str(error)
    assert outside.read_bytes() == b"precious shared content\n"
    assert _mode(outside) == 0o644


def test_a_hard_link_made_after_opening_is_refused(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Link count is judged on the descriptor too, and a refused new file is removed."""

    ensure_private_directory(home, "cache")
    escape = tmp_path / "escape.yml"
    real_open = os.open

    def linking_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        fd = real_open(path, flags, *args, **kwargs)
        if path == "layout.yml" and flags & os.O_CREAT:
            os.link(home / "cache" / "layout.yml", escape)
        return fd

    monkeypatch.setattr(os, "open", linking_open)
    error = _refusal(
        lambda: open_private_file(home, "cache/layout.yml", os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    )
    monkeypatch.undo()

    assert error.violation is PrivateStorageViolation.HARD_LINK
    assert not (home / "cache" / "layout.yml").exists()
    assert escape.read_bytes() == b""


def test_a_hard_link_appearing_during_creation_is_refused_untouched(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside data that must survive\n")
    outside.chmod(0o644)
    ensure_private_directory(home, "cache")

    _swap_after_nofollow_stat(
        monkeypatch, "layout.yml", lambda: os.link(outside, home / "cache" / "layout.yml")
    )
    error = _refusal(
        lambda: open_private_file(home, "cache/layout.yml", os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    )
    monkeypatch.undo()

    assert error.violation is PrivateStorageViolation.HARD_LINK
    assert outside.read_bytes() == b"outside data that must survive\n"
    assert _mode(outside) == 0o644


@pytest.mark.parametrize("flags", [os.O_RDONLY, os.O_WRONLY], ids=["read", "write"])
def test_a_file_swapped_for_a_fifo_mid_check_does_not_block(
    home: Path, monkeypatch: pytest.MonkeyPatch, flags: int
) -> None:
    ensure_private_directory(home, "cache")
    _write_file(home, "cache/layout.yml", b"ours\n")
    layout = home / "cache" / "layout.yml"

    def replace() -> None:
        layout.unlink()
        os.mkfifo(layout, PRIVATE_FILE_MODE)

    _swap_after_nofollow_stat(monkeypatch, "layout.yml", replace)
    error = _outcome_within_deadline(
        lambda: open_private_file(home, "cache/layout.yml", flags), layout
    )
    monkeypatch.undo()

    assert isinstance(error, PrivateStorageError)
    assert error.violation is PrivateStorageViolation.NOT_REGULAR_FILE


@pytest.mark.parametrize(
    "flags", [os.O_RDONLY | os.O_CREAT, os.O_WRONLY | os.O_CREAT], ids=["read", "write"]
)
def test_a_fifo_appearing_during_creation_is_refused_without_blocking(
    home: Path, monkeypatch: pytest.MonkeyPatch, flags: int
) -> None:
    ensure_private_directory(home, "cache")
    layout = home / "cache" / "layout.yml"

    _swap_after_nofollow_stat(
        monkeypatch, "layout.yml", lambda: os.mkfifo(layout, PRIVATE_FILE_MODE)
    )
    error = _outcome_within_deadline(
        lambda: open_private_file(home, "cache/layout.yml", flags), layout
    )
    monkeypatch.undo()

    assert isinstance(error, PrivateStorageError)
    assert error.violation is PrivateStorageViolation.NOT_REGULAR_FILE
    assert stat.S_ISFIFO(os.lstat(layout).st_mode), "a FIFO this call did not create is kept"


@skip_as_root
def test_restoring_owner_access_never_follows_a_swapped_link(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under umask 0777 a new directory starts without owner access and must be finished."""

    outside = tmp_path / "outside"
    outside.mkdir()
    outside.chmod(0o755)
    ensure_private_directory(home)
    cache = home / "cache"
    real_open = os.open
    swapped: list[bool] = []

    def racing_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        try:
            return real_open(path, flags, *args, **kwargs)
        except PermissionError:
            if path == "cache" and not swapped:
                swapped.append(True)
                cache.chmod(PRIVATE_DIRECTORY_MODE)
                cache.rmdir()
                cache.symlink_to(outside, target_is_directory=True)
            raise

    monkeypatch.setattr(os, "open", racing_open)
    with _umask(0o777):
        error = _refusal(lambda: ensure_private_directory(home, "cache/staging"))
    monkeypatch.undo()

    assert swapped
    assert error.violation is PrivateStorageViolation.SYMLINK
    assert _mode(outside) == 0o755
    assert list(outside.iterdir()) == []


def test_truncation_happens_only_after_verification(home: Path) -> None:
    ensure_private_directory(home, "cache")
    _write_file(home, "cache/layout.yml", b"old content\n")

    fd = open_private_file(home, "cache/layout.yml", os.O_WRONLY | os.O_TRUNC)
    with os.fdopen(fd, "wb") as handle:
        handle.write(b"new\n")

    assert (home / "cache" / "layout.yml").read_bytes() == b"new\n"


def test_returned_descriptors_block_unless_the_caller_asked_otherwise(home: Path) -> None:
    ensure_private_directory(home, "cache")
    _write_file(home, "cache/layout.yml", b"x\n")

    fd = open_private_file(home, "cache/layout.yml", os.O_RDONLY)
    try:
        assert os.get_blocking(fd)
    finally:
        os.close(fd)
    fd = open_private_file(home, "cache/layout.yml", os.O_RDONLY | os.O_NONBLOCK)
    try:
        assert not os.get_blocking(fd)
    finally:
        os.close(fd)


def test_a_refused_new_file_is_removed(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ensure_private_directory(home, "cache")

    def ignore_mode(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(os, "fchmod", ignore_mode)
    with _umask(0o277):
        error = _refusal(
            lambda: open_private_file(home, "cache/layout.yml", os.O_WRONLY | os.O_CREAT)
        )
    monkeypatch.undo()

    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert list((home / "cache").iterdir()) == []


def test_truncate_requires_write_access(home: Path) -> None:
    ensure_private_directory(home)

    with pytest.raises(ValueError):
        open_private_file(home, "config.yml", os.O_RDONLY | os.O_TRUNC)


# ── Repair is not revocation ───────────────────────────────────────


@pytest.mark.parametrize(
    "flags",
    [
        os.O_WRONLY,
        os.O_RDWR,
        os.O_WRONLY | os.O_TRUNC,
        os.O_WRONLY | os.O_APPEND,
        os.O_RDWR | os.O_CREAT,
    ],
    ids=["write", "read-write", "truncate", "append", "create"],
)
@pytest.mark.parametrize("shared_mode", [0o644, 0o604, 0o640, 0o044], ids=lambda m: f"mode-{m:04o}")
def test_writing_a_shared_file_in_place_is_refused_not_repaired(
    home: Path, flags: int, shared_mode: int
) -> None:
    ensure_private_directory(home, "cache")
    state = home / "cache" / "state.yml"
    state.write_bytes(b"old\n")
    state.chmod(shared_mode)

    error = _refusal(lambda: open_private_file(home, "cache/state.yml", flags))

    assert error.violation is PrivateStorageViolation.PERMISSIVE
    assert error.location is PrivateStorageLocation.ENTRY
    assert "replace it atomically" in str(error)
    assert _mode(state) == shared_mode
    state.chmod(PRIVATE_FILE_MODE)
    assert state.read_bytes() == b"old\n"


def test_a_descriptor_opened_while_shared_never_sees_private_writes(home: Path) -> None:
    """Tightening a mode does not revoke a descriptor, so the write is refused instead."""

    ensure_private_directory(home)
    (home / "cache").mkdir()
    (home / "cache").chmod(0o755)
    state = home / "cache" / "state.yml"
    state.write_bytes(b"old\n")
    state.chmod(0o644)
    earlier = os.open(state, os.O_RDONLY)
    try:
        with pytest.raises(PrivateStorageError):
            open_private_file(home, "cache/state.yml", os.O_WRONLY | os.O_TRUNC)
        assert os.pread(earlier, 100, 0) == b"old\n"
    finally:
        os.close(earlier)


# ── Escaping errors carry no names (finding 6) ─────────────────────


@skip_as_root
def test_escaping_errors_never_name_the_entry(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ensure_private_directory(home, "cache")
    _write_file(home, f"cache/{PRIVATE_SLUG}.yml", b"x\n")
    locked = _private_dir(tmp_path / "locked-home")
    locked.chmod(0o500)
    cases: list[tuple[type[BaseException], Callable[[], object]]] = [
        (PrivateStorageError, lambda: ensure_private_directory(locked, PRIVATE_SLUG)),
        (
            PrivateStorageError,
            lambda: open_private_file(locked, f"{PRIVATE_SLUG}.yml", os.O_WRONLY | os.O_CREAT),
        ),
        (
            FileNotFoundError,
            lambda: open_private_file(home, f"cache/{PRIVATE_SLUG}/store.yml", os.O_RDONLY),
        ),
        (FileNotFoundError, lambda: open_private_file(home, f"{PRIVATE_SLUG}.yml", os.O_RDONLY)),
        (
            FileExistsError,
            lambda: open_private_file(
                home, f"cache/{PRIVATE_SLUG}.yml", os.O_WRONLY | os.O_CREAT | os.O_EXCL
            ),
        ),
        (OSError, lambda: ensure_private_directory(home, PRIVATE_SLUG * 8)),
        (
            FileNotFoundError,
            lambda: ensure_private_directory(tmp_path / f"missing-{PRIVATE_SLUG}" / "home"),
        ),
        (FileNotFoundError, lambda: validate_private_home(tmp_path / f"absent-{PRIVATE_SLUG}")),
    ]
    try:
        for expected, call in cases:
            with pytest.raises(expected) as caught:
                call()
            message = str(caught.value)
            assert PRIVATE_SLUG not in message, message
            assert str(tmp_path) not in message, message
            assert "cache/" not in message, message
            assert caught.value.__cause__ is not None
    finally:
        locked.chmod(PRIVATE_DIRECTORY_MODE)


# ── ACLs (finding 1) ───────────────────────────────────────────────


@darwin_only
def test_an_inheritable_acl_above_the_home_is_cleared_from_created_entries(
    tmp_path: Path,
) -> None:
    parent = _private_dir(tmp_path / "parent")
    _add_acl(parent, "group:everyone allow read,list,search,file_inherit,directory_inherit")
    home = parent / "home"

    store = ensure_private_directory(home, f"cache/repository-stores/{PRIVATE_SLUG}")
    _write_file(home, f"cache/repository-stores/{PRIVATE_SLUG}/store.yml", b"store\n")

    assert _acl_lines(parent) != []
    for path in (home, home / "cache", store, store / "store.yml"):
        assert _acl_lines(path) == [], path
    validate_private_home(home)


@darwin_only
def test_a_home_with_an_allow_acl_for_others_is_refused_not_repaired(home: Path) -> None:
    _private_dir(home)
    _add_acl(home, "group:everyone allow list,search")

    for call in (
        lambda: validate_private_home(home),
        lambda: ensure_private_directory(home, "cache"),
    ):
        error = _refusal(call)
        assert error.violation is PrivateStorageViolation.PERMISSIVE
        assert error.location is PrivateStorageLocation.HOME
        assert "access control list" in str(error)

    assert _acl_lines(home) != []
    assert list(home.iterdir()) == []


@darwin_only
def test_deny_only_acls_on_ancestors_and_the_home_are_accepted(tmp_path: Path) -> None:
    """An ordinary macOS home directory carries ``group:everyone deny delete``."""

    parent = _private_dir(tmp_path / "parent")
    _add_acl(parent, "group:everyone deny delete")
    home = _private_dir(parent / "home")
    _add_acl(home, "group:everyone deny delete")
    _add_acl(home, f"user:{_current_user_name()} allow list,search,add_file")

    ensure_private_directory(home, "cache")
    validate_private_home(home)

    assert len(_acl_lines(home)) == 2


@darwin_only
@pytest.mark.parametrize(
    "rights",
    [
        "add_file",
        "add_subdirectory",
        "delete",
        "delete_child",
        "writeattr",
        "writeextattr",
        "writesecurity",
        "chown",
    ],
)
def test_an_ancestor_acl_granting_others_write_access_is_refused(
    tmp_path: Path, rights: str
) -> None:
    parent = _private_dir(tmp_path / "parent")
    _add_acl(parent, f"group:everyone allow {rights}")

    error = _refusal(lambda: ensure_private_directory(parent / "home", "cache"))

    assert error.violation is PrivateStorageViolation.PERMISSIVE
    assert error.location is PrivateStorageLocation.HOME_ANCESTOR
    assert "access control list" in str(error)
    assert not (parent / "home").exists()


@darwin_only
def test_ancestor_acls_granting_only_reads_or_the_current_user_are_accepted(
    tmp_path: Path,
) -> None:
    parent = _private_dir(tmp_path / "parent")
    _add_acl(parent, "group:everyone allow list,search,readattr,readextattr,readsecurity")
    _add_acl(parent, f"user:{_current_user_name()} allow add_file,delete_child,writesecurity")

    ensure_private_directory(parent / "home", "cache")

    assert len(_acl_lines(parent)) == 2


@darwin_only
def test_existing_entries_shared_by_acl_are_cleared_with_a_warning(
    home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ensure_private_directory(home, "cache")
    _add_acl(home / "cache", "group:everyone allow list,search")
    _write_file(home, "cache/layout.yml", b"layout\n")
    _add_acl(home / "cache" / "layout.yml", "group:everyone allow read")

    with caplog.at_level(logging.WARNING, logger="metabrowser.home"):
        ensure_private_directory(home, "cache")
        os.close(open_private_file(home, "cache/layout.yml", os.O_RDONLY))

    assert _acl_lines(home / "cache") == []
    assert _acl_lines(home / "cache" / "layout.yml") == []
    assert len([r for r in caplog.records if "access control list" in r.getMessage()]) == 2


@darwin_only
def test_writing_an_acl_shared_file_in_place_is_refused_not_repaired(home: Path) -> None:
    ensure_private_directory(home, "cache")
    _write_file(home, "cache/layout.yml", b"layout\n")
    _add_acl(home / "cache" / "layout.yml", "group:everyone allow read")

    error = _refusal(lambda: open_private_file(home, "cache/layout.yml", os.O_WRONLY))

    assert error.violation is PrivateStorageViolation.PERMISSIVE
    assert "access control list" in str(error)
    assert "replace it atomically" in str(error)
    assert _acl_lines(home / "cache" / "layout.yml") != []


def _with_acl_entries(
    monkeypatch: pytest.MonkeyPatch, entries: Callable[..., tuple[Any, ...]]
) -> None:
    monkeypatch.setattr(home_module, "_EXTENDED_ACLS", True)
    monkeypatch.setattr(home_module, "_read_acl", entries)


def test_an_unreadable_acl_fails_closed(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unreadable(*_args: Any) -> tuple[Any, ...]:
        raise home_module._AclUnverifiable("simulated libSystem failure")

    _with_acl_entries(monkeypatch, unreadable)

    error = _refusal(lambda: ensure_private_directory(home, "cache"))

    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert "access control list" in str(error)
    assert not home.exists() or list(home.iterdir()) == []


@pytest.mark.parametrize(
    ("kind", "rights"),
    [(3, 1 << 1), (1, 1 << 30)],  # kinds: 1 is KAUTH_ACE_PERMIT, 3 is AUDIT
    ids=["unknown-entry-kind", "unknown-right"],
)
def test_an_uninterpretable_acl_entry_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: int, rights: int
) -> None:
    stranger = bytes(range(16))
    entry = home_module._AclEntry(kind=kind, principal=stranger, rights=rights)
    _with_acl_entries(monkeypatch, lambda *_args: (entry,))

    error = _refusal(lambda: validate_private_home(tmp_path))

    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert error.location is PrivateStorageLocation.HOME_ANCESTOR


@skip_as_root
def test_restoring_owner_access_without_a_link_safe_primitive_is_refused(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With neither a no-follow chmod nor O_PATH, a new directory the umask shut is removed."""

    ensure_private_directory(home)
    monkeypatch.setattr(home_module, "_LINK_SAFE_CHMOD", False)
    monkeypatch.setattr(home_module, "_O_PATH", None)

    with _umask(0o777):
        error = _refusal(lambda: ensure_private_directory(home, "cache"))

    assert error.violation is PrivateStorageViolation.UNVERIFIABLE
    assert "umask" in str(error)
    assert not (home / "cache").exists()


@darwin_only
def test_created_entries_carry_no_acl_even_one_their_parent_passes_down(home: Path) -> None:
    """A verified parent may keep inheritable deny entries; what Metabrowser creates has none."""

    ensure_private_directory(home, "cache")
    _add_acl(home / "cache", "group:everyone deny delete,file_inherit,directory_inherit")

    staging = ensure_private_directory(home, "cache/staging")
    _write_file(home, "cache/layout.yml", b"layout\n")

    assert len(_acl_lines(home / "cache")) == 1
    assert _acl_lines(staging) == []
    assert _acl_lines(home / "cache" / "layout.yml") == []
