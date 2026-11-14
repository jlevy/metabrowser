"""Owner-only storage for the application home.

Repository cache content may be private, so every directory Metabrowser
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
import json
import logging
import os
import stat
import subprocess
import sys
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from metabrowser import home as home_module
from metabrowser.cache.listing import list_private_directory
from metabrowser.home import (
    PRIVATE_DIRECTORY_MODE,
    PRIVATE_FILE_MODE,
    PrivateStorageError,
    PrivateStorageLocation,
    PrivateStorageViolation,
    SharedEntryPolicy,
    ensure_private_directory,
    open_private_file,
    private_directory,
    private_directory_is_writable,
    validate_private_home,
)
from tests.required_tools import needs_git

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
_skip_off_darwin = pytest.mark.skipif(
    sys.platform != "darwin",
    reason=(
        "extended ACLs are inspected only on macOS; a Linux POSIX ACL cannot exceed the "
        "group-class mask that 0700 and 0600 clear, as metabrowser/home.py records"
    ),
)


def darwin_only[Test: Callable[..., object]](test: Test) -> Test:
    """Mark a test for the macOS tier, which CI does not run; see docs/e2e-testing.md."""

    return pytest.mark.macos_tier(_skip_off_darwin(test))


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


# ── Refusals ───────────────────────────────────────────────────────
#
# One tree holds every state another principal could have left: homes that are shared,
# linked, foreign, or not directories; ancestors that are writable, foreign, or loops;
# and, inside a good home, entries that are foreign, linked, of the wrong type, hard
# linked, or shared. Each row below is one call into that tree, and the same is required
# of all of them: a typed refusal that names what is wrong and where, and a tree left
# exactly as it was. The tree is compared whole, so nothing was repaired, created,
# written through a link, or removed. Races, FIFOs, ACLs, and what is accepted have
# their own tests below.

_SHARED_HOME_MODES = (0o750, 0o705, 0o755, 0o777, 0o710)
_SHARED_FILE_MODES = (0o644, 0o604, 0o640, 0o044)


def _hostile_tree(root: Path) -> list[Path]:
    """Build the tree and return the entries that are to report another user as owner."""

    foreign_owned: list[Path] = []

    def foreign(path: Path) -> Path:
        foreign_owned.append(path)
        return path

    def shared(path: Path, mode: int) -> Path:
        path.mkdir()
        path.chmod(mode)
        return path

    def public_file(path: Path, data: bytes) -> Path:
        path.write_bytes(data)
        path.chmod(0o644)
        return path

    homes = _private_dir(root / "homes")
    for mode in _SHARED_HOME_MODES:
        shared(homes / f"mode-{mode:04o}", mode)
    (homes / "linked").symlink_to(_private_dir(homes / "real"), target_is_directory=True)
    foreign(_private_dir(homes / "foreign"))
    (homes / "file").write_bytes(b"not a directory\n")

    _private_dir(shared(root / "shared", 0o777) / "mine")
    shared(root / "group-writable", 0o775)
    shared(root / "other-writable", 0o757)
    foreign(_private_dir(root / "someone-elses"))
    # The sticky bit protects entries from other users, not from the directory's owner.
    foreign(shared(root / "sticky-foreign", 0o1777))
    (root / "planted").symlink_to(_private_dir(root / "real-above"), target_is_directory=True)
    foreign(root / "planted")
    (root / "loop-a").symlink_to(root / "loop-b")
    (root / "loop-b").symlink_to(root / "loop-a")

    outside = shared(root / "outside", 0o755)
    victim = public_file(root / "victim.txt", b"keep me\n")
    published = public_file(root / "public_index.html", b"precious shared content\n")
    home = ensure_private_directory(root / "home")
    foreign(shared(home / "foreign-dir", 0o755))
    foreign(public_file(home / "foreign.yml", b"root wrote this\n"))
    (home / "linked-dir").symlink_to(outside, target_is_directory=True)
    (home / "linked.yml").symlink_to(victim)
    (home / "dangling.yml").symlink_to(root / "never-created.txt")
    (home / "a-file").write_bytes(b"not a directory\n")
    (home / "a-file").chmod(PRIVATE_FILE_MODE)
    _private_dir(home / "a-directory")
    os.link(published, home / "hard-linked.yml")
    for mode in _SHARED_FILE_MODES:
        (home / f"shared-{mode:04o}.yml").write_bytes(b"old\n")
        (home / f"shared-{mode:04o}.yml").chmod(mode)
    (shared(home / "shared-dir", 0o750) / "inner.yml").write_bytes(b"inside\n")
    (home / "shared-dir" / "inner.yml").chmod(PRIVATE_FILE_MODE)
    return foreign_owned


def _tree(root: Path) -> dict[str, tuple[int, int, int, int, bytes]]:
    """Every entry below *root*: mode, link count, size, write time, and content or target.

    A file its owner cannot read, such as the mode 0044 one in the hostile tree, is
    compared by mode, link count, size, and write time. Its content is not: reading it
    would take a ``chmod``, which is the change this snapshot exists to catch.
    """

    entries: dict[str, tuple[int, int, int, int, bytes]] = {}
    for directory, names, files in os.walk(root):
        for name in [*names, *files]:
            path = Path(directory) / name
            status = os.lstat(path)
            content = b""
            if stat.S_ISLNK(status.st_mode):
                content = os.readlink(path).encode()
            elif stat.S_ISREG(status.st_mode) and status.st_mode & stat.S_IRUSR:
                content = path.read_bytes()
            regular = stat.S_ISREG(status.st_mode)
            entries[str(path.relative_to(root))] = (
                status.st_mode,
                status.st_nlink if regular else 0,
                status.st_size if regular else 0,
                status.st_mtime_ns if regular else 0,
                content,
            )
    return entries


@dataclass(frozen=True, slots=True)
class _Call:
    """One call into the storage layer, named by its arguments."""

    name: str
    run: Callable[[Path], object]


def _validate(home: str) -> _Call:
    return _Call(f"validate {home}", lambda root: validate_private_home(root / home))


def _ensure(home: str, relative: str) -> _Call:
    return _Call(
        f"ensure {home} {relative}", lambda root: ensure_private_directory(root / home, relative)
    )


_FLAG_NAMES = (
    ("wrongly", os.O_WRONLY),
    ("rdwr", os.O_RDWR),
    ("creat", os.O_CREAT),
    ("trunc", os.O_TRUNC),
    ("append", os.O_APPEND),
)


def _open(home: str, relative: str, flags: int, shared: SharedEntryPolicy = "repair") -> _Call:
    """An open named by its flags' names, which are the same on every platform."""

    access = "+".join(name for name, bit in _FLAG_NAMES if flags & bit) or "rdonly"
    policy = "" if shared == "repair" else f" shared={shared}"
    return _Call(
        f"open {home} {relative} {access}{policy}",
        lambda root: open_private_file(root / home, relative, flags, shared=shared),
    )


def _every_entry_point(home: str) -> tuple[_Call, ...]:
    return (
        _validate(home),
        _ensure(home, "cache"),
        _open(home, "config.yml", os.O_WRONLY | os.O_CREAT),
    )


@dataclass(frozen=True, slots=True)
class _Refused:
    """How one call into the hostile tree must be refused."""

    call: _Call
    violation: PrivateStorageViolation
    location: PrivateStorageLocation
    says: tuple[str, ...] = ()
    mode: int | None = None
    at: str | None = None


_V, _L = PrivateStorageViolation, PrivateStorageLocation
_W = os.O_WRONLY
_REFUSED: tuple[_Refused, ...] = (
    # An explicit permissive METABROWSER_CACHE_DIR gets an actionable refusal, not a private write.
    *(
        _Refused(call, _V.PERMISSIVE, _L.HOME, ("chmod 700", "METABROWSER_CACHE_DIR"), mode)
        for mode in _SHARED_HOME_MODES
        for call in _every_entry_point(f"homes/mode-{mode:04o}")
    ),
    *(
        _Refused(call, _V.SYMLINK, _L.HOME, ("METABROWSER_CACHE_DIR",))
        for call in _every_entry_point("homes/linked")
    ),
    _Refused(_ensure("homes/foreign", "cache"), _V.FOREIGN_OWNER, _L.HOME, ("sudo",)),
    _Refused(_ensure("homes/file", "cache"), _V.NOT_DIRECTORY, _L.HOME),
    _Refused(_ensure("shared/home", "cache"), _V.PERMISSIVE, _L.HOME_ANCESTOR, mode=0o777),
    _Refused(
        _open("shared/home", "config.yml", os.O_RDONLY),
        _V.PERMISSIVE,
        _L.HOME_ANCESTOR,
        mode=0o777,
    ),
    _Refused(_ensure("shared/mine/home", "cache"), _V.PERMISSIVE, _L.HOME_ANCESTOR, at="shared"),
    # Write access for the group alone, or for others alone, is enough to replace the home.
    _Refused(_ensure("group-writable/home", "cache"), _V.PERMISSIVE, _L.HOME_ANCESTOR, mode=0o775),
    _Refused(_ensure("other-writable/home", "cache"), _V.PERMISSIVE, _L.HOME_ANCESTOR, mode=0o757),
    _Refused(_ensure("someone-elses/home", "cache"), _V.FOREIGN_OWNER, _L.HOME_ANCESTOR),
    _Refused(_ensure("sticky-foreign/home", "cache"), _V.FOREIGN_OWNER, _L.HOME_ANCESTOR),
    _Refused(_ensure("planted/home", "cache"), _V.SYMLINK, _L.HOME_ANCESTOR),
    _Refused(_validate("loop-a/home"), _V.UNVERIFIABLE, _L.HOME_ANCESTOR),
    _Refused(_ensure("home", "foreign-dir/staging"), _V.FOREIGN_OWNER, _L.ENTRY),
    _Refused(_open("home", "foreign.yml", os.O_RDONLY), _V.FOREIGN_OWNER, _L.ENTRY),
    _Refused(_ensure("home", "linked-dir/staging"), _V.SYMLINK, _L.ENTRY),
    _Refused(_open("home", "linked-dir/layout.yml", _W | os.O_CREAT), _V.SYMLINK, _L.ENTRY),
    _Refused(_open("home", "linked.yml", _W | os.O_CREAT | os.O_TRUNC), _V.SYMLINK, _L.ENTRY),
    _Refused(_open("home", "linked.yml", os.O_RDONLY), _V.SYMLINK, _L.ENTRY),
    _Refused(_open("home", "dangling.yml", _W | os.O_CREAT), _V.SYMLINK, _L.ENTRY),
    _Refused(_ensure("home", "a-file/job"), _V.NOT_DIRECTORY, _L.ENTRY),
    _Refused(_open("home", "a-directory", os.O_RDONLY), _V.NOT_REGULAR_FILE, _L.ENTRY),
    *(
        _Refused(_open("home", "hard-linked.yml", flags), _V.HARD_LINK, _L.ENTRY, ("hard link",))
        for flags in (os.O_RDONLY, os.O_RDWR, _W | os.O_CREAT | os.O_TRUNC)
    ),
    # Tightening a mode does not revoke a descriptor opened while the file was shared, so
    # a write in place is refused where a read would repair.
    *(
        _Refused(
            _open("home", f"shared-{mode:04o}.yml", flags),
            _V.PERMISSIVE,
            _L.ENTRY,
            ("replace it atomically",),
        )
        for mode in _SHARED_FILE_MODES
        for flags in (_W, os.O_RDWR, _W | os.O_TRUNC, _W | os.O_APPEND, os.O_RDWR | os.O_CREAT)
    ),
    # shared="refuse": a read that must not touch what the user owns refuses a shared file
    # and a shared parent directory, with the remedy for each, where the default repairs.
    *(
        _Refused(
            _open("home", f"shared-{mode:04o}.yml", os.O_RDONLY, "refuse"),
            _V.PERMISSIVE,
            _L.ENTRY,
            ("chmod 600", "does not change your entries"),
            mode,
        )
        for mode in (0o644, 0o604, 0o640)
    ),
    _Refused(
        _open("home", "shared-dir/inner.yml", os.O_RDONLY, "refuse"),
        _V.PERMISSIVE,
        _L.ENTRY,
        ("chmod 700", "does not change your entries"),
        0o750,
    ),
    # shared="keep" lets sharing stand for a read and nothing else: a write in place is
    # still refused, and so is every entry that is wrong for another reason.
    _Refused(
        _open("home", "shared-0644.yml", _W, "keep"),
        _V.PERMISSIVE,
        _L.ENTRY,
        ("replace it atomically",),
    ),
    _Refused(_open("home", "linked.yml", os.O_RDONLY, "keep"), _V.SYMLINK, _L.ENTRY),
    _Refused(_open("home", "hard-linked.yml", os.O_RDONLY, "keep"), _V.HARD_LINK, _L.ENTRY),
    _Refused(_open("home", "foreign.yml", os.O_RDONLY, "keep"), _V.FOREIGN_OWNER, _L.ENTRY),
)


@pytest.mark.parametrize("refused", _REFUSED, ids=lambda refused: refused.call.name)
def test_a_call_into_a_hostile_tree_is_refused_and_changes_nothing(
    refused: _Refused, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    foreign_owned = _hostile_tree(tmp_path)
    before = _tree(tmp_path)
    for path in foreign_owned:
        _disguise_owner(monkeypatch, path, _another_uid())

    error = _refusal(lambda: refused.call.run(tmp_path))

    monkeypatch.undo()
    assert error.violation is refused.violation
    assert error.location is refused.location
    if refused.mode is not None:
        assert error.mode == refused.mode
    if refused.at is not None:
        assert error.path == tmp_path / refused.at
    for text in refused.says:
        assert text in str(error)
    assert _tree(tmp_path) == before


@pytest.mark.parametrize("policy", ["keep", "refuse"])
def test_a_read_that_keeps_or_refuses_opens_a_private_file_and_changes_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, policy: SharedEntryPolicy
) -> None:
    """Neither policy tightens anything, so a private entry opens exactly as it is."""

    _hostile_tree(tmp_path)
    before = _tree(tmp_path)

    with caplog.at_level(logging.WARNING, logger="metabrowser.home"):
        fd = open_private_file(tmp_path / "home", "a-file", os.O_RDONLY, shared=policy)
        with os.fdopen(fd, "rb") as handle:
            assert handle.read() == b"not a directory\n"

    assert _tree(tmp_path) == before
    assert caplog.records == []


def test_a_keep_read_opens_a_shared_file_in_a_shared_directory_as_they_are(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """``keep`` changes neither the file nor its parents and refuses neither.

    The lock replacement and the pre-read of the layout rely on it: they must see an
    entry exactly as it is, where the default would tighten both and log each repair.
    """

    _hostile_tree(tmp_path)
    home = tmp_path / "home"
    (home / "shared-dir" / "inner.yml").chmod(0o640)
    before = _tree(tmp_path)

    with caplog.at_level(logging.WARNING, logger="metabrowser.home"):
        for relative, content in (
            ("shared-0644.yml", b"old\n"),
            ("shared-dir/inner.yml", b"inside\n"),
        ):
            fd = open_private_file(home, relative, os.O_RDONLY, shared="keep")
            with os.fdopen(fd, "rb") as handle:
                assert handle.read() == content

    assert _tree(tmp_path) == before
    assert caplog.records == []
    # The default read of the same entries repairs them, which is what keep withheld.
    os.close(open_private_file(home, "shared-dir/inner.yml", os.O_RDONLY))
    assert (_mode(home / "shared-dir"), _mode(home / "shared-dir" / "inner.yml")) == (0o700, 0o600)


def test_the_root_directory_is_verified(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _disguise_owner(monkeypatch, Path("/"), _another_uid())

    error = _refusal(lambda: ensure_private_directory(home, "cache"))

    assert error.violation is PrivateStorageViolation.FOREIGN_OWNER
    assert error.location is PrivateStorageLocation.HOME_ANCESTOR
    assert error.path == Path("/")


# ── What is accepted, at the home and above it ─────────────────────


def test_a_private_home_validates_without_changes(home: Path) -> None:
    _private_dir(home)
    before = os.lstat(home)

    validate_private_home(home)

    after = os.lstat(home)
    assert (after.st_mode, after.st_mtime_ns) == (before.st_mode, before.st_mtime_ns)


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


@needs_git
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
#
# These races are staged against the full walk, which opens each directory by name and
# compares the opened descriptor with the stat before it. A directory already held from
# an earlier call is not opened by name again, so each test that races a directory starts
# with nothing held; the held walk has its own race tests below.


def _forget_held_directories() -> None:
    """Close every held directory, so the next call opens and verifies each one."""

    home_module._HELD_DIRECTORIES.clear()  # pyright: ignore[reportPrivateUsage]


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

    _forget_held_directories()
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

    _forget_held_directories()
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
        assert "Metabrowser storage directory" in message
        assert str(tmp_path) not in message
        assert PRIVATE_SLUG not in message
        assert "ghp_" not in message
        assert error.path.is_absolute()
    assert errors[0].path == source


def test_cache_storage_beside_a_user_checkout_leaves_the_checkout_unchanged(
    tmp_path: Path,
) -> None:
    """Writing the cache touches only the home, never a checkout beside it."""

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

    ensure_private_directory(home, "cache/repository-stores/store-key/repository.git")
    ensure_private_directory(home, "cache/sources/source-slug")
    _write_file(home, "cache/sources/source-slug/source.yml", b"source\n")
    with pytest.raises(ValueError):
        ensure_private_directory(home, "../project")

    for path, original in before.items():
        current = os.lstat(path)
        assert (current.st_mode, current.st_uid) == (original.st_mode, original.st_uid), path
    assert (checkout / "README.md").read_bytes() == b"project\n"
    assert sorted(p.name for p in checkout.iterdir()) == ["README.md"]


# ── The home replaced mid-check (review mutant m8) ─────────────────


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


def test_private_directory_write_admission_preserves_modes_and_refuses_links(home: Path) -> None:
    directory = ensure_private_directory(home, "bank")
    assert home_module.private_directory_is_writable(home, "bank")
    directory.chmod(0o500)
    try:
        assert not home_module.private_directory_is_writable(home, "bank")
        assert _mode(directory) == 0o500
    finally:
        directory.chmod(0o700)
    (home / "bank-link").symlink_to(directory, target_is_directory=True)
    with pytest.raises(PrivateStorageError):
        home_module.private_directory_is_writable(home, "bank-link")
    directory.chmod(0o755)
    try:
        with pytest.raises(PrivateStorageError):
            home_module.private_directory_is_writable(home, "bank")
        assert _mode(directory) == 0o755
    finally:
        directory.chmod(0o700)


def test_private_directory_write_admission_checks_readonly_mount(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home, "bank")
    real = os.fstatvfs

    def read_only(fd: int) -> os.statvfs_result:
        info = real(fd)
        return os.statvfs_result((*info[:8], info.f_flag | os.ST_RDONLY, info.f_namemax))

    monkeypatch.setattr(home_module.os, "fstatvfs", read_only)
    assert not home_module.private_directory_is_writable(home, "bank")


@darwin_only
def test_private_directory_write_admission_observes_owner_deny_acl(home: Path) -> None:
    directory = ensure_private_directory(home, "bank")
    _add_acl(directory, f"user:{_current_user_name()} deny add_file,delete_child")
    before = _acl_lines(directory)
    with pytest.raises(PermissionError):
        (directory / "write-witness").write_bytes(b"must fail")
    assert not home_module.private_directory_is_writable(home, "bank")
    assert _mode(directory) == 0o700
    assert _acl_lines(directory) == before


# ── Held directories ───────────────────────────────────────────────
#
# A directory verified once stays open, and a later call reuses its descriptor only when
# a no-follow stat of its name, taken on that call, shows the same directory still
# plainly private. Each change below is made to a tree whose directories a call has just
# left held, and the next call must answer exactly as a call with nothing held does, which
# is the walk every directory gets the first time: the same refusal or result, the same
# repairs logged, and the same tree afterwards. Two identical trees are built for each
# case, one answered warm and one cold, and both are compared whole.

_STAGING = "cache/staging"
_HELD_RECORD = f"{_STAGING}/record.json"


def _held_tree(root: Path) -> Path:
    """Build ``root/link/home`` through a relative link the user owns; return the home."""

    above = root / "above"
    above.mkdir()
    above.chmod(0o755)
    (root / "link").symlink_to("above", target_is_directory=True)
    home = root / "link" / "home"
    ensure_private_directory(home, "cache/staging")
    _write_file(home, _HELD_RECORD, b"record\n")
    return home


def _decoy_home(root: Path, mode: int) -> None:
    """Point the link above the home at a directory holding another private home."""

    decoy = root / "decoy"
    decoy.mkdir()
    ensure_private_directory(decoy / "home", "cache/staging")
    _write_file(decoy / "home", _HELD_RECORD, b"decoy\n")
    decoy.chmod(mode)
    (root / "link").unlink()
    (root / "link").symlink_to("decoy", target_is_directory=True)


def _replace(path: Path, mode: int | None = None, *, link: bool = False) -> None:
    """Rename *path* aside and put a new directory, or a link to the old one, in its place."""

    path.rename(path.with_name(f"{path.name}-old"))
    if link:
        path.symlink_to(f"{path.name}-old", target_is_directory=True)
    elif mode is not None:
        path.mkdir()
        path.chmod(mode)


@dataclass(frozen=True, slots=True)
class _Change:
    """A change made after a call, and how a read that refuses must answer it."""

    name: str
    apply: Callable[[Path, Path, pytest.MonkeyPatch], object]
    expected: tuple[object, ...]
    darwin: bool = False
    needs_non_root: bool = False


_R = "refused"
_HELD_CHANGES: tuple[_Change, ...] = (
    _Change(
        "ancestor world-writable",
        lambda root, _home, _mp: (root / "above").chmod(0o777),
        (_R, _V.PERMISSIVE, _L.HOME_ANCESTOR),
    ),
    _Change(
        "ancestor group-writable",
        lambda root, _home, _mp: (root / "above").chmod(0o775),
        (_R, _V.PERMISSIVE, _L.HOME_ANCESTOR),
    ),
    _Change(
        "ancestor ACL grants others write",
        lambda root, _home, _mp: _add_acl(root / "above", "group:everyone allow add_subdirectory"),
        (_R, _V.PERMISSIVE, _L.HOME_ANCESTOR),
        darwin=True,
    ),
    _Change(
        "ancestor link swapped to a writable directory",
        lambda root, _home, _mp: _decoy_home(root, 0o777),
        (_R, _V.PERMISSIVE, _L.HOME_ANCESTOR),
    ),
    _Change(
        "ancestor link swapped to another private home",
        lambda root, _home, _mp: _decoy_home(root, 0o755),
        ("ok", b"decoy\n"),
    ),
    _Change(
        "ancestor owned by another user",
        lambda root, _home, mp: _disguise_owner(mp, root / "above", _another_uid()),
        (_R, _V.FOREIGN_OWNER, _L.HOME_ANCESTOR),
    ),
    _Change(
        "home group-readable",
        lambda _root, home, _mp: home.chmod(0o750),
        (_R, _V.PERMISSIVE, _L.HOME),
    ),
    _Change(
        "home ACL grants others",
        lambda _root, home, _mp: _add_acl(home, "group:everyone allow list"),
        (_R, _V.PERMISSIVE, _L.HOME),
        darwin=True,
    ),
    _Change(
        "home replaced by a new private directory",
        lambda _root, home, _mp: _replace(home, 0o700),
        ("error", "FileNotFoundError"),
    ),
    _Change(
        "home replaced by a link",
        lambda _root, home, _mp: _replace(home, link=True),
        (_R, _V.SYMLINK, _L.HOME),
    ),
    _Change(
        "directory group-readable",
        lambda _root, home, _mp: (home / "cache").chmod(0o750),
        (_R, _V.PERMISSIVE, _L.ENTRY),
    ),
    _Change(
        "directory world-writable",
        lambda _root, home, _mp: (home / "cache" / "staging").chmod(0o777),
        (_R, _V.PERMISSIVE, _L.ENTRY),
    ),
    _Change(
        "directory ACL grants others",
        lambda _root, home, _mp: _add_acl(home / "cache", "group:everyone allow list"),
        (_R, _V.PERMISSIVE, _L.ENTRY),
        darwin=True,
    ),
    _Change(
        "directory ACL denies its owner",
        lambda _root, home, _mp: _add_acl(
            home / "cache" / "staging", f"user:{_current_user_name()} deny list"
        ),
        (_R, _V.UNVERIFIABLE, _L.ENTRY),
        darwin=True,
    ),
    _Change(
        "directory without owner read",
        lambda _root, home, _mp: (home / "cache" / "staging").chmod(0o300),
        (_R, _V.UNVERIFIABLE, _L.ENTRY),
        needs_non_root=True,
    ),
    _Change(
        "directory owned by another user",
        lambda _root, home, mp: _disguise_owner(mp, home / "cache", _another_uid()),
        (_R, _V.FOREIGN_OWNER, _L.ENTRY),
    ),
    _Change(
        "directory replaced by a new private one",
        lambda _root, home, _mp: _replace(home / "cache" / "staging", 0o700),
        ("error", "FileNotFoundError"),
    ),
    _Change(
        "directory replaced by a shared one",
        lambda _root, home, _mp: _replace(home / "cache" / "staging", 0o755),
        (_R, _V.PERMISSIVE, _L.ENTRY),
    ),
    _Change(
        "directory swapped for a link",
        lambda _root, home, _mp: _replace(home / "cache", link=True),
        (_R, _V.SYMLINK, _L.ENTRY),
    ),
    _Change(
        "directory removed",
        lambda _root, home, _mp: _replace(home / "cache" / "staging"),
        ("error", "FileNotFoundError"),
    ),
    _Change(
        "file group-readable",
        lambda _root, home, _mp: (home / _HELD_RECORD).chmod(0o640),
        (_R, _V.PERMISSIVE, _L.ENTRY),
    ),
    _Change(
        "file hard-linked from outside",
        lambda root, home, _mp: os.link(home / _HELD_RECORD, root / "outside.json"),
        (_R, _V.HARD_LINK, _L.ENTRY),
    ),
)


def _read_and_close(fd: int) -> bytes:
    with os.fdopen(fd, "rb") as handle:
        return handle.read()


def _batch_read(home: Path) -> tuple[bytes, ...]:
    with private_directory(home, "cache/staging", shared="refuse") as directory:
        record = _read_and_close(directory.open("record.json", os.O_RDONLY))
        try:
            os.close(directory.open("record.json-journal", os.O_RDONLY))
        except FileNotFoundError:
            return (record,)
        return (record, b"journal")


_HELD_CALLS: tuple[_Call, ...] = (
    _Call(
        "read refuse",
        lambda home: _read_and_close(
            open_private_file(home, _HELD_RECORD, os.O_RDONLY, shared="refuse")
        ),
    ),
    _Call("read repair", lambda home: _read_and_close(open_private_file(home, _HELD_RECORD, 0))),
    _Call(
        "read keep",
        lambda home: _read_and_close(open_private_file(home, _HELD_RECORD, 0, shared="keep")),
    ),
    _Call("read batch", _batch_read),
    _Call(
        "write new file",
        lambda home: os.close(
            open_private_file(home, "cache/staging/new.json", os.O_WRONLY | os.O_CREAT)
        ),
    ),
    _Call("ensure", lambda home: ensure_private_directory(home, "cache/staging/job").name),
    _Call("list", lambda home: list_private_directory(home, "cache/staging", max_entries=10)),
    _Call("writable", lambda home: private_directory_is_writable(home, "cache/staging")),
    _Call("validate", validate_private_home),
)


def _held_outcome(call: _Call, home: Path, root: Path) -> tuple[object, ...]:
    try:
        result = call.run(home)
    except PrivateStorageError as error:
        where = error.path.relative_to(root) if error.path.is_relative_to(root) else error.path
        return (_R, error.violation, error.location, error.mode, str(where))
    except OSError as error:
        return ("error", type(error).__name__)
    return ("ok", result)


def _held_snapshot(root: Path) -> dict[str, tuple[int, int, bytes, int]]:
    """Every entry below *root*: mode, link count, content or link target, and ACL entries."""

    entries: dict[str, tuple[int, int, bytes, int]] = {}
    for directory, names, files in os.walk(root):
        for name in [*names, *files]:
            path = Path(directory) / name
            status = os.lstat(path)
            content = b""
            if stat.S_ISLNK(status.st_mode):
                content = os.readlink(path).encode()
            elif stat.S_ISREG(status.st_mode) and status.st_mode & stat.S_IRUSR:
                content = path.read_bytes()
            acl = 0
            if home_module._EXTENDED_ACLS:  # pyright: ignore[reportPrivateUsage]
                acl = len(home_module._read_acl(None, path))  # pyright: ignore[reportPrivateUsage]
            regular = stat.S_ISREG(status.st_mode)
            entries[str(path.relative_to(root))] = (
                status.st_mode,
                status.st_nlink if regular else 0,
                content,
                acl,
            )
    return entries


def _restore_owner_access(root: Path) -> None:
    """Give the owner back every directory a change locked them out of, for cleanup."""

    pending = [root]
    while pending:
        directory = pending.pop()
        directory.chmod(stat.S_IMODE(os.lstat(directory).st_mode) | stat.S_IRWXU)
        # An ACL that denies the owner is removed by remove_test_acls.
        with contextlib.suppress(PermissionError):
            # Path.is_dir takes follow_symlinks only from Python 3.13.
            pending += [
                entry for entry in directory.iterdir() if stat.S_ISDIR(os.lstat(entry).st_mode)
            ]


def _held_cases() -> list[Any]:
    cases: list[Any] = []
    for change in _HELD_CHANGES:
        marks: list[Any] = []
        if change.darwin:
            marks += [pytest.mark.macos_tier, _skip_off_darwin]
        if change.needs_non_root:
            marks.append(skip_as_root)
        cases += [
            pytest.param(change, call, marks=marks, id=f"{change.name} | {call.name}")
            for call in _HELD_CALLS
        ]
    return cases


@pytest.mark.parametrize(("change", "call"), _held_cases())
def test_a_change_after_a_call_is_answered_as_if_nothing_were_held(
    change: _Change,
    call: _Call,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    answers: dict[str, tuple[object, ...]] = {}
    trees: dict[str, dict[str, tuple[int, int, bytes, int]]] = {}
    logged: dict[str, list[str]] = {}
    for run in ("warm", "cold"):
        root = _private_dir(tmp_path / run)
        home = _held_tree(root)
        _forget_held_directories()
        if run == "warm":
            # Leaves the home, cache, and cache/staging held.
            _read_and_close(open_private_file(home, _HELD_RECORD, os.O_RDONLY, shared="refuse"))
            held = home_module._HELD_DIRECTORIES._held  # pyright: ignore[reportPrivateUsage]
            assert {key[1] for key in held if key[0] == str(home)} == {"", "cache", _STAGING}
        change.apply(root, home, monkeypatch)
        if run == "cold":
            _forget_held_directories()
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="metabrowser.home"):
            answers[run] = _held_outcome(call, home, root)
        logged[run] = [
            record.getMessage().replace(str(root), "<root>") for record in caplog.records
        ]
        monkeypatch.undo()
        trees[run] = _held_snapshot(root)
        _restore_owner_access(root)

    assert answers["warm"] == answers["cold"]
    assert logged["warm"] == logged["cold"]
    assert trees["warm"] == trees["cold"]
    if call.name == "read refuse":
        # The case is not vacuous: the read that refuses answers as recorded.
        assert answers["cold"][: len(change.expected)] == change.expected


# The races of the full walk, staged against a held one. A held directory is not opened
# by name, so there is no inspection-then-open window to refuse; what must hold is that a
# swap right after its last look at the name never sends the operation through the link
# or into the replacement, and that the next call answers the changed tree as a cold one
# would. The last look at a name is its mount identity, so the swap follows that.


def _swap_after_mount_lookup(
    monkeypatch: pytest.MonkeyPatch, name: str, replace: Callable[[], None]
) -> None:
    """Run *replace* right after the held walk last looks at *name*."""

    real = home_module._mount_identity  # pyright: ignore[reportPrivateUsage]
    swapped: list[bool] = []

    def racing_lookup(dir_fd: int | None, looked_up: str | Path) -> tuple[int, int] | None:
        try:
            return real(dir_fd, looked_up)
        finally:
            if looked_up == name and dir_fd is not None and not swapped:
                swapped.append(True)
                replace()

    monkeypatch.setattr(home_module, "_mount_identity", racing_lookup)


def test_a_held_directory_swapped_for_a_symlink_after_its_check_is_never_followed(
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

    _swap_after_mount_lookup(monkeypatch, "staging", replace)
    with pytest.raises(FileNotFoundError):
        ensure_private_directory(home, "cache/staging/job")
    monkeypatch.undo()

    assert list(outside.iterdir()) == []
    assert _mode(outside) == 0o755
    error = _refusal(lambda: ensure_private_directory(home, "cache/staging/job"))
    assert error.violation is PrivateStorageViolation.SYMLINK
    assert list(outside.iterdir()) == []


def test_a_held_directory_replaced_after_its_check_keeps_the_replacement_untouched(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home, "cache/staging")
    staging = home / "cache" / "staging"

    def replace() -> None:
        staging.rename(home / "cache" / "moved-aside")
        staging.mkdir()
        staging.chmod(0o755)

    _swap_after_mount_lookup(monkeypatch, "staging", replace)
    ensure_private_directory(home, "cache/staging/job")
    monkeypatch.undo()

    # The job went into the directory that was checked, wherever it now is.
    assert (home / "cache" / "moved-aside" / "job").is_dir()
    assert list(staging.iterdir()) == []
    assert _mode(staging) == 0o755
    error = _refusal(
        lambda: open_private_file(home, "cache/staging/x", os.O_RDONLY, shared="refuse")
    )
    assert (error.violation, error.mode) == (PrivateStorageViolation.PERMISSIVE, 0o755)


# ── Held directories: mounts ───────────────────────────────────────
#
# Device and inode name a directory, not the mount it is reached through. A held
# directory is reused only while its name reaches it through the mount its descriptor
# was opened through; a platform that cannot tell holds nothing.


def _counting_opens(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    opened: list[str] = []
    real_open = os.open

    def counting_open(path: Any, *args: Any, **kwargs: Any) -> int:
        opened.append(Path(path).name if isinstance(path, Path) else str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", counting_open)
    return opened


def test_a_directory_reached_through_another_mount_is_opened_again(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home, "cache/staging")
    _write_file(home, "cache/staging/record.json", b"record\n")
    _forget_held_directories()
    _read_and_close(open_private_file(home, "cache/staging/record.json", os.O_RDONLY))
    real = home_module._mount_identity  # pyright: ignore[reportPrivateUsage]

    def another_mount(dir_fd: int | None, name: str | Path) -> tuple[int, int] | None:
        found = real(dir_fd, name)
        if found is None or name != "staging":
            return found
        return found[0], found[1] + 1

    monkeypatch.setattr(home_module, "_mount_identity", another_mount)
    opened = _counting_opens(monkeypatch)
    _read_and_close(open_private_file(home, "cache/staging/record.json", os.O_RDONLY))
    assert opened == ["staging", "record.json"]


def test_without_a_mount_identity_nothing_is_held(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home, "cache/staging")
    _write_file(home, "cache/staging/record.json", b"record\n")
    _forget_held_directories()
    monkeypatch.setattr(home_module, "_descriptor_mount_identity", lambda _fd: None)
    before = _open_descriptors()
    opened = _counting_opens(monkeypatch)
    for _ in range(2):
        _read_and_close(open_private_file(home, "cache/staging/record.json", os.O_RDONLY))
    assert opened == [home.name, "cache", "staging", "record.json"] * 2
    assert _held()._held == {}  # pyright: ignore[reportPrivateUsage]
    assert _open_descriptors() == before


# Run as root, or as root of a new user namespace, in a private mount namespace: build a
# home, leave its directories held (or not), bind-mount cache/staging over itself and
# make that mount read-only, then ask whether cache/staging is writable and create a file
# there. "unchecked" reports the held mount for the name, which is what reuse did before
# it compared mounts, and shows the bind mount is a real hazard on this kernel.
_BIND_MOUNT_SCRIPT = r"""
import errno, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from metabrowser import home as H

route = sys.argv[1]
if route == "userns":
    # Root's directories above the home show here as an unmapped owner, which the
    # ancestor walk refuses; that walk is not what this test is about, and every
    # variant skips it alike.
    H._verify_home_ancestors = lambda home: None
base = Path(tempfile.mkdtemp(prefix="mb-bind-", dir="/tmp"))
mounted = []
real_lookup = H._mount_identity

def variant(name):
    root = base / name
    root.mkdir(mode=0o700)
    home = root / "home"
    H.ensure_private_directory(home, "cache/staging")
    H._HELD_DIRECTORIES.clear()
    os.close(H.open_private_file(home, "cache/staging/before.json", os.O_WRONLY | os.O_CREAT))
    staging = str(home / "cache" / "staging")
    held = H._HELD_DIRECTORIES._held.get((str(home), "cache/staging"))
    if held is None:
        print(json.dumps({"unavailable": "this kernel reports no mount ID, so nothing is held"}))
        raise SystemExit(77)
    for command in (["mount", "--bind", staging, staging],
                    ["mount", "-o", "remount,bind,ro", staging]):
        done = subprocess.run(command, capture_output=True, text=True)
        if done.returncode:
            print(json.dumps({"unavailable": done.stderr.strip()}))
            raise SystemExit(77)
        if command[1] == "--bind":
            mounted.append(staging)
    if name == "cold":
        H._HELD_DIRECTORIES.clear()
    if name == "unchecked":
        H._mount_identity = lambda dir_fd, looked_up: (
            held.mount if looked_up == "staging" else real_lookup(dir_fd, looked_up))
    try:
        answer = {"writable": H.private_directory_is_writable(home, "cache/staging")}
        try:
            os.close(H.open_private_file(home, "cache/staging/new.json", os.O_WRONLY | os.O_CREAT))
            answer["create"] = "created"
        except OSError as error:
            answer["create"] = errno.errorcode.get(error.errno, str(error.errno))
    finally:
        H._mount_identity = real_lookup
    return answer

try:
    results = {name: variant(name) for name in ("warm", "cold", "unchecked")}
    print(json.dumps({"route": route, "results": results}))
finally:
    H._HELD_DIRECTORIES.clear()
    for staging in reversed(mounted):
        subprocess.run(["umount", staging], check=False)
    shutil.rmtree(base, ignore_errors=True)
"""


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="bind mounts are a Linux mount namespace's"
)
def test_a_read_only_bind_mount_over_a_held_directory_is_honored() -> None:
    """A cold walk reaches the read-only bind mount; a warm one must too.

    It needs a private mount namespace: as root of a new user namespace where the kernel
    allows one, or as root through ``sudo -n`` where it does not, as on GitHub's Ubuntu
    runners. With neither it skips, which the strict skip gate turns into a failure in CI.
    """

    routes = (
        ("userns", ["unshare", "--user", "--map-root-user", "--mount", "--propagation", "private"]),
        ("root", ["sudo", "-n", "unshare", "--mount", "--propagation", "private"]),
    )
    tried: list[str] = []
    for route, launcher in routes:
        done = subprocess.run(
            [*launcher, sys.executable, "-B", "-c", _BIND_MOUNT_SCRIPT, route],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
        if not lines:
            assert "Traceback" not in done.stderr, done.stderr
            tried.append(f"{route}: {done.stderr.strip()[-200:]}")
            continue
        report = json.loads(lines[-1])
        if "unavailable" in report:
            tried.append(f"{route}: {report['unavailable']}")
            continue
        results = report["results"]
        refused = {"writable": False, "create": "EROFS"}
        # Without the mount comparison the warm walk wrote through the old mount.
        assert results["unchecked"] == {"writable": True, "create": "created"}, report
        assert results["cold"] == refused, report
        assert results["warm"] == refused, report
        return
    pytest.skip(f"no private mount namespace could be made: {'; '.join(tried)}")


# ── Held directories: lifetime and cost ────────────────────────────


def _held() -> home_module._HeldDirectories:  # pyright: ignore[reportPrivateUsage]
    return home_module._HELD_DIRECTORIES  # pyright: ignore[reportPrivateUsage]


def _open_descriptors() -> int:
    return len(os.listdir("/dev/fd"))


def test_a_warm_open_opens_only_the_file(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cost this exists for: no directory is opened again, and nothing else changes."""

    ensure_private_directory(home, "cache/staging")
    _write_file(home, "cache/staging/record.json", b"record\n")
    _forget_held_directories()
    opened = _counting_opens(monkeypatch)
    _read_and_close(open_private_file(home, "cache/staging/record.json", os.O_RDONLY))
    assert opened == [home.name, "cache", "staging", "record.json"]
    opened.clear()
    _read_and_close(open_private_file(home, "cache/staging/record.json", os.O_RDONLY))
    assert opened == ["record.json"]


def test_a_directory_handle_verifies_once_for_several_files(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home, "db")
    for name in ("catalog", "catalog-journal"):
        _write_file(home, f"db/{name}", name.encode())
    walks: list[Path] = []
    real_walk = home_module._verify_home_ancestors  # pyright: ignore[reportPrivateUsage]

    def counting_walk(target: Path) -> None:
        walks.append(target)
        real_walk(target)

    monkeypatch.setattr(home_module, "_verify_home_ancestors", counting_walk)
    with private_directory(home, "db", shared="refuse") as directory:
        contents = [
            _read_and_close(directory.open(name, os.O_RDONLY))
            for name in ("catalog", "catalog-journal")
        ]
        with pytest.raises(FileNotFoundError):
            directory.open("catalog-wal", os.O_RDONLY)
    assert contents == [b"catalog", b"catalog-journal"]
    assert walks == [home]
    with pytest.raises(ValueError, match="after its block ended"):
        directory.open("catalog", os.O_RDONLY)


def test_a_directory_handle_opens_only_its_own_entries(home: Path) -> None:
    ensure_private_directory(home, "db/inner")
    _write_file(home, "db/inner/x", b"x")
    with private_directory(home, "db") as directory:
        for name in ("inner/x", "..", ".", ""):
            with pytest.raises(ValueError):
                directory.open(name, os.O_RDONLY)
        with pytest.raises(ValueError):
            directory.open("inner", os.O_RDONLY | os.O_DIRECTORY)
    with pytest.raises(FileNotFoundError) as missing, private_directory(home, "db/absent"):
        pass
    assert not (home / "db" / "absent").exists()
    assert "absent" not in str(missing.value)
    with pytest.raises(FileNotFoundError) as above, private_directory(home / "nowhere", "db"):
        pass
    assert "nowhere" not in str(above.value)


def test_held_directories_are_bounded_and_closed_when_dropped(home: Path) -> None:
    limit = home_module._HELD_DIRECTORY_LIMIT  # pyright: ignore[reportPrivateUsage]
    _forget_held_directories()
    before = _open_descriptors()
    for index in range(limit * 2):
        ensure_private_directory(home, f"d{index}")
    held = _held()._held  # pyright: ignore[reportPrivateUsage]
    assert len(held) == limit
    # The most recently used are the ones kept.
    assert (str(home), f"d{limit * 2 - 1}") in held
    assert _open_descriptors() - before == limit
    _forget_held_directories()
    assert _open_descriptors() == before


def test_a_block_borrows_only_its_own_directory_until_its_last_user_releases_it(
    home: Path,
) -> None:
    limit = home_module._HELD_DIRECTORY_LIMIT  # pyright: ignore[reportPrivateUsage]
    ensure_private_directory(home, "a/b/db")
    _write_file(home, "a/b/db/record", b"kept")
    _forget_held_directories()
    before = _open_descriptors()
    with private_directory(home, "a/b/db") as directory:
        # Every held directory is evicted and forgotten while the block still borrows its
        # own, and only its own: the home, a, and a/b were released on the way down.
        for index in range(limit + 1):
            ensure_private_directory(home, f"other{index}")
        _forget_held_directories()
        assert _open_descriptors() == before + 1
        assert _read_and_close(directory.open("record", os.O_RDONLY)) == b"kept"
    assert _open_descriptors() == before


def test_a_held_directory_that_fails_its_check_is_closed_once_reopened(home: Path) -> None:
    """A rejected held directory is released before the full check opens it again."""

    ensure_private_directory(home, "cache/staging")
    _write_file(home, "cache/staging/record.json", b"record\n")
    _forget_held_directories()
    before = _open_descriptors()
    _read_and_close(open_private_file(home, "cache/staging/record.json", os.O_RDONLY))
    (home / "cache").chmod(0o750)
    _read_and_close(open_private_file(home, "cache/staging/record.json", os.O_RDONLY))
    assert _mode(home / "cache") == PRIVATE_DIRECTORY_MODE
    assert _open_descriptors() == before + 3
    _forget_held_directories()
    assert _open_descriptors() == before


def test_held_directories_survive_concurrent_use_and_eviction(home: Path) -> None:
    """Threads open files across more directories than are held, evicting each other's."""

    limit = home_module._HELD_DIRECTORY_LIMIT  # pyright: ignore[reportPrivateUsage]
    names = [f"d{index}" for index in range(limit + 8)]
    for name in names:
        ensure_private_directory(home, f"{name}/inner")
        _write_file(home, f"{name}/inner/record", name.encode())
    _forget_held_directories()
    before = _open_descriptors()
    failures: list[BaseException] = []

    def work(offset: int) -> None:
        try:
            for step in range(150):
                name = names[(offset + step * 7) % len(names)]
                fd = open_private_file(home, f"{name}/inner/record", os.O_RDONLY, shared="refuse")
                assert _read_and_close(fd) == name.encode()
                if step % 25 == 0:
                    _forget_held_directories()
        except BaseException as error:
            failures.append(error)

    threads = [threading.Thread(target=work, args=(offset,)) for offset in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30.0)
    assert failures == []
    assert len(_held()._held) <= limit  # pyright: ignore[reportPrivateUsage]
    _forget_held_directories()
    assert _open_descriptors() == before


def _run_script(script: str, *arguments: object) -> dict[str, Any]:
    """Run *script* in a fresh interpreter and return the JSON object it prints last."""

    done = subprocess.run(
        [sys.executable, "-B", "-c", script, *map(str, arguments)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
    assert done.returncode == 0 and lines, done.stderr
    return json.loads(lines[-1])


# A walk 120 directories deep, opened cold and then warm with the descriptor limit just
# above what the process already uses plus every directory it may hold for reuse.
_DEEP_WALK_SCRIPT = r"""
import json, os, resource, sys
from pathlib import Path
from metabrowser import home as H

home, depth = Path(sys.argv[1]), int(sys.argv[2])
relative = "/".join(f"d{index}" for index in range(depth))
H.ensure_private_directory(home, relative)
os.close(H.open_private_file(home, relative + "/f", os.O_WRONLY | os.O_CREAT))
H._HELD_DIRECTORIES.clear()
highest = max(int(name) for name in os.listdir("/dev/fd"))
limit = highest + H._HELD_DIRECTORY_LIMIT + 8
soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))
answers = []
for _ in ("cold", "warm"):
    try:
        os.close(H.open_private_file(home, relative + "/f", os.O_RDONLY))
        answers.append("opened")
    except OSError as error:
        answers.append(os.strerror(error.errno))
print(json.dumps({"limit": limit, "depth": depth, "answers": answers}))
"""


def test_a_deep_walk_fits_under_a_small_descriptor_limit(home: Path) -> None:
    """A walk borrows one directory at a time, as the walk before held descriptors did."""

    report = _run_script(_DEEP_WALK_SCRIPT, home, 120)
    assert report["answers"] == ["opened", "opened"], report


# A fork inside two private_directory blocks: the outer one's directory has been evicted
# while borrowed, the inner one's is held, and another thread borrows a third, also
# evicted. The child reuses both blocks' descriptor numbers for a decoy directory and
# reports what it can reach.
_FORK_SCRIPT = r"""
import errno, json, os, sys, threading
from pathlib import Path
from metabrowser import home as H

home, decoy = Path(sys.argv[1]), Path(sys.argv[2])
for name in ("db", "outer", "evicted"):
    H.ensure_private_directory(home, name)
    fd = H.open_private_file(home, f"{name}/record", os.O_WRONLY | os.O_CREAT)
    os.write(fd, b"private")
    os.close(fd)
decoy.mkdir()
(decoy / "record").write_bytes(b"decoy")
H._HELD_DIRECTORIES.clear()

borrowing, finish = threading.Event(), threading.Event()
evicted = {}

def borrower():
    with H.private_directory(home, "evicted") as directory:
        evicted["fd"] = directory._fd
        borrowing.set()
        finish.wait(30)

def state(fd):
    try:
        os.fstat(fd)
        return "open"
    except OSError as error:
        return errno.errorcode[error.errno]

thread = threading.Thread(target=borrower)
thread.start()
borrowing.wait(30)
read, write = os.pipe()
with H.private_directory(home, "outer") as outer:
    # Evict both borrowed directories: each now closes on its last release.
    for index in range(H._HELD_DIRECTORY_LIMIT + 1):
        H.ensure_private_directory(home, f"other{index}")
    with H.private_directory(home, "db") as inner:
        numbers = {"outer": outer._fd, "inner": inner._fd}
        pid = os.fork()
        if pid == 0:
            os.close(read)
            child = {"evicted_borrow": state(evicted["fd"])}
            # Open the decoy until it gets each block's descriptor number back.
            others, reused = [], {}
            for _ in range(256):
                fd = os.open(decoy, os.O_RDONLY | os.O_DIRECTORY)
                label = next((key for key, value in numbers.items() if value == fd), None)
                if label is None:
                    others.append(fd)
                else:
                    reused[label] = fd
                if len(reused) == len(numbers):
                    break
            for fd in others:
                os.close(fd)
            child["reused"] = sorted(reused)
            for label, directory in (("outer", outer), ("inner", inner)):
                try:
                    fd = directory.open("record", os.O_RDONLY)
                    child[label] = os.read(fd, 100).decode()
                except ValueError as error:
                    child[label] = str(error)
if pid == 0:
    child["after_blocks"] = {label: state(fd) for label, fd in sorted(reused.items())}
    os.write(write, json.dumps(child).encode())
    os._exit(0)
os.close(write)
os.waitpid(pid, 0)
finish.set()
thread.join(30)
with os.fdopen(read) as pipe:
    print(json.dumps({"child": json.loads(pipe.read())}))
"""


@pytest.mark.skipif(not hasattr(os, "fork"), reason="the platform cannot fork")
def test_a_forked_child_cannot_reach_its_parents_descriptors(home: Path, tmp_path: Path) -> None:
    """A fork closes everything the parent owned and voids every lease taken before it.

    Neither block may open the decoy's file through a reused number, leaving the blocks
    must not close the child's descriptors, and the directory another thread borrowed
    after its eviction must be closed too.
    """

    child = _run_script(_FORK_SCRIPT, home, tmp_path / "decoy")["child"]
    refused = "the private directory was verified before this process forked"
    assert child == {
        "evicted_borrow": "EBADF",
        "reused": ["inner", "outer"],
        "outer": refused,
        "inner": refused,
        "after_blocks": {"inner": "open", "outer": "open"},
    }
