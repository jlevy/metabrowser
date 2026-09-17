"""Owner-only storage for the Metabrowser application home.

Repository stores, source bindings, and provider mirrors may hold private content, so
everything Metabrowser keeps under the application home must be readable only by the
user running it. This module is the enforcement point cache and provider code call
before they create or open anything there. It does not decide where the home is or what
goes in it; resolving ``METABROWSER_HOME`` and the ``f01`` layout belong to their own
modules.

Each rule answers a specific threat:

- **Nothing another principal can redirect.** Every directory the kernel traverses to
  reach the home must be owned by root or the current user and must not be writable by
  anyone else unless its sticky bit is set, because whoever can write to an ancestor can
  rename the home away and substitute their own. A symbolic link above the home is
  followed only when root or the current user owns it — ``/home`` pointing into
  ``/var/home`` is layout, not an attack — and each directory it leads through is held
  to the same rule. The home itself and everything below it are never links.
- **Nothing another principal can read.** The home is owned by the current user and
  grants no group or other access. Directories below it are exactly ``0700`` and files
  exactly ``0600``, whatever the umask.
- **No window.** New directories and files are created with the restrictive mode, which
  a umask can only narrow, and then set exactly. Entries below the home are reached by
  directory descriptor with ``O_NOFOLLOW`` and re-identified by device and inode after
  opening, so a swap between inspection and use is refused rather than followed.
- **Repair only what is ours.** An entry below the home that the current user owns is
  tightened, and the repair is logged. The home is never repaired: a permissive home was
  chosen by someone, so an explicit ``METABROWSER_HOME`` receives a refusal with a
  remedy rather than a quiet change. Nothing above the home is ever modified, so a
  user's workspace or checkout keeps its modes.
- **Fail closed.** A platform without descriptor-relative, no-follow operations —
  Windows today — and a file system that does not keep modes are both refused as
  ``unverifiable``.

Only POSIX ownership and mode bits are verified.
On Linux a POSIX ACL cannot grant more than the group-class mask, which ``0700`` and
``0600`` clear. macOS extended ACLs and NFSv4 ACLs are not inspected.
One narrow fallback follows a link on Linux: an owned entry whose own mode shuts its
owner out is restored by path, because Linux cannot ``chmod`` without following.
Only the owner or root can replace an entry inside a directory that is private to its
owner, and the identity check after opening still refuses the swap.

A refusal is a :class:`PrivateStorageError`.
Its message names a logical location and a remedy but never a path, because it may reach
a job status or an API envelope and a cache path can name a private repository.
The path stays on the exception for local logs and CLI rendering.
"""

from __future__ import annotations

import errno
import logging
import os
import stat
from enum import StrEnum
from pathlib import Path
from typing import Final

from metabrowser.inventory_engine.contract import require_canonical_inventory_path

log = logging.getLogger(__name__)

PRIVATE_DIRECTORY_MODE: Final = 0o700
PRIVATE_FILE_MODE: Final = 0o600

# Any permission granted to group or other.
_SHARED_ACCESS_BITS: Final = 0o077
# Above the home only write access matters: the home itself refuses traversal, but
# whoever can write to an ancestor can replace everything below it.
_SHARED_WRITE_BITS: Final = 0o022
_ROOT_UID: Final = 0
# The number of symbolic links Linux follows while resolving one path (MAXSYMLINKS).
_MAX_SYMLINK_HOPS: Final = 40
# A final symbolic link under O_NOFOLLOW is ELOOP on Linux and macOS and EMLINK on
# FreeBSD; with O_DIRECTORY Linux reports ENOTDIR first.
_UNOPENABLE_LINK_ERRNOS: Final = frozenset({errno.ELOOP, errno.EMLINK, errno.ENOTDIR})

_OWNER_ONLY_CHECKS_SUPPORTED: Final = (
    os.name == "posix"
    and hasattr(os, "O_NOFOLLOW")
    and hasattr(os, "O_DIRECTORY")
    and os.open in os.supports_dir_fd
    and os.mkdir in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.stat in os.supports_follow_symlinks
    and os.chmod in os.supports_dir_fd
)
_LINK_SAFE_CHMOD: Final = os.chmod in os.supports_follow_symlinks


class PrivateStorageLocation(StrEnum):
    """Where owner-only storage was refused, as a logical place rather than a path."""

    HOME_ANCESTOR = "home_ancestor"
    HOME = "home"
    ENTRY = "entry"


class PrivateStorageViolation(StrEnum):
    """Why a location cannot hold owner-only content."""

    SYMLINK = "symlink"
    FOREIGN_OWNER = "foreign_owner"
    PERMISSIVE = "permissive"
    NOT_DIRECTORY = "not_directory"
    NOT_REGULAR_FILE = "not_regular_file"
    UNVERIFIABLE = "unverifiable"


_UNSUPPORTED_PLATFORM: Final = (
    "this platform does not provide the ownership and no-follow checks owner-only storage "
    "relies on, and current-user-only ACL verification for Windows is not implemented "
    "yet. Remote repository and provider content cannot be stored on this platform"
)
_MODES_NOT_KEPT: Final = (
    "its file system did not keep owner-only permissions. Set METABROWSER_HOME to a "
    "directory on a file system with Unix permissions"
)
_CHECK_DENIED: Final = (
    "permission was denied while checking it. Make sure it belongs to the current user, "
    "or set METABROWSER_HOME to a private directory you own"
)
_CHANGED_DURING_CHECK: Final = (
    "it was replaced while it was being checked. Make sure nothing else is modifying the "
    "application home, then retry"
)
_TOO_MANY_LINKS: Final = (
    "too many symbolic links lead through it. Set METABROWSER_HOME to the real location "
    "of the application home"
)

_SUBJECTS: Final = {
    PrivateStorageLocation.HOME_ANCESTOR: (
        "A path component above the Metabrowser application home"
    ),
    PrivateStorageLocation.HOME: "The Metabrowser application home",
    PrivateStorageLocation.ENTRY: "An entry in the Metabrowser application home",
}
_MOVE_HOME: Final = "or set METABROWSER_HOME to a private directory you own"


def _describe(
    violation: PrivateStorageViolation,
    location: PrivateStorageLocation,
    mode: int | None,
    detail: str | None,
) -> str:
    """Return a path-free, actionable sentence for one refusal."""

    subject = _SUBJECTS[location]
    mode_text = "" if mode is None else f" (mode {mode:04o})"
    above = location is PrivateStorageLocation.HOME_ANCESTOR
    match violation:
        case PrivateStorageViolation.SYMLINK if above:
            return (
                f"{subject} is a symbolic link owned by another user, which could redirect "
                "private content. Set METABROWSER_HOME to a path that does not pass through it."
            )
        case PrivateStorageViolation.SYMLINK if location is PrivateStorageLocation.HOME:
            return (
                f"{subject} is a symbolic link. Set METABROWSER_HOME to the directory it "
                "points to instead."
            )
        case PrivateStorageViolation.SYMLINK:
            return (
                f"{subject} is a symbolic link, and Metabrowser never writes private content "
                f"through one. Move the link aside, {_MOVE_HOME}."
            )
        case PrivateStorageViolation.FOREIGN_OWNER if above:
            return (
                f"{subject} is owned by another user, who could replace the home. Set "
                "METABROWSER_HOME to a path whose directories belong to you or to root."
            )
        case PrivateStorageViolation.FOREIGN_OWNER:
            return (
                f"{subject} is owned by another user, as happens after running Metabrowser "
                f"with sudo. Restore its ownership to the current user, {_MOVE_HOME}."
            )
        case PrivateStorageViolation.PERMISSIVE if above:
            return (
                f"{subject} is writable by other users{mode_text}, who could replace the "
                "home. Remove group and other write access, or set METABROWSER_HOME to a "
                "path outside it."
            )
        case PrivateStorageViolation.PERMISSIVE:
            return (
                f"{subject} is accessible to other users{mode_text}. Run chmod 700 on it, "
                f"{_MOVE_HOME}."
            )
        case PrivateStorageViolation.NOT_DIRECTORY if above:
            return (
                f"{subject} is not a directory. Set METABROWSER_HOME to a path whose "
                "components are directories."
            )
        case PrivateStorageViolation.NOT_DIRECTORY:
            return f"{subject} is not a directory. Move it aside, {_MOVE_HOME}."
        case PrivateStorageViolation.NOT_REGULAR_FILE:
            return f"{subject} is not a regular file. Move it aside, {_MOVE_HOME}."
        case PrivateStorageViolation.UNVERIFIABLE:
            return f"{subject} cannot be verified as private to the current user: {detail}."


class PrivateStorageError(Exception):
    """Owner-only storage was refused.

    ``str()`` is path-free and actionable, so it is safe for a job status or response
    body. ``path`` names the offending location for local logs and CLI rendering only.
    ``mode`` is set for a permissive refusal.
    """

    def __init__(
        self,
        violation: PrivateStorageViolation,
        location: PrivateStorageLocation,
        path: Path,
        *,
        mode: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(_describe(violation, location, mode, detail))
        self.violation: PrivateStorageViolation = violation
        self.location: PrivateStorageLocation = location
        self.path: Path = path
        self.mode: int | None = mode


# ── Public API ─────────────────────────────────────────────────────


def validate_private_home(home: Path) -> None:
    """Refuse *home* unless only the current user can read, redirect, or replace it.

    Changes nothing. A missing home raises :class:`FileNotFoundError`, because whether
    that is an error belongs to the caller.
    """

    _require_home_argument(home)
    _verify_home_ancestors(home)
    os.close(_open_home(home))


def ensure_private_directory(home: Path, relative_path: str = "") -> Path:
    """Create or verify the owner-only directory *relative_path* below *home*.

    *relative_path* is a POSIX-relative path such as ``"cache/staging"``; the empty
    string names the home. A missing home is created ``0700`` inside an existing parent,
    but an existing home is never repaired. Missing directories below it are created
    ``0700``, and existing ones the current user owns are tightened to exactly ``0700``.
    Returns the directory's path.
    """

    _require_home_argument(home)
    require_canonical_inventory_path(relative_path, "application-home path", allow_root=True)
    _verify_home_ancestors(home)
    _create_home_if_missing(home)
    path = home
    fd = _open_home(home)
    try:
        for name in relative_path.split("/") if relative_path else ():
            path = path / name
            child = _open_directory_entry(fd, name, path, create=True)
            os.close(fd)
            fd = child
    finally:
        os.close(fd)
    return path


def open_private_file(home: Path, relative_path: str, flags: int) -> int:
    """Open the owner-only file *relative_path* below *home* with ``os.open`` *flags*.

    Returns a descriptor the caller must close. ``O_NOFOLLOW`` and ``O_CLOEXEC`` are
    always added. With ``O_CREAT`` a new file is created ``0600``; with ``O_EXCL`` an
    existing file raises :class:`FileExistsError`, so no-replace publication keeps its
    meaning. An existing file the current user owns is tightened to exactly ``0600``.
    Parent directories are verified and tightened as in :func:`ensure_private_directory`
    but never created, so a missing one raises :class:`FileNotFoundError`.
    """

    _require_home_argument(home)
    require_canonical_inventory_path(relative_path, "application-home path", allow_root=False)
    if flags & os.O_DIRECTORY:
        raise ValueError("open_private_file opens files; use ensure_private_directory")
    _verify_home_ancestors(home)
    *parents, name = relative_path.split("/")
    path = home
    fd = _open_home(home)
    try:
        for parent in parents:
            path = path / parent
            child = _open_directory_entry(fd, parent, path, create=False)
            os.close(fd)
            fd = child
        return _open_file_entry(fd, name, flags, path / name)
    finally:
        os.close(fd)


# ── The home and what lies above it ────────────────────────────────


def _owner_only_checks_supported() -> bool:
    """Whether this platform provides every primitive the checks rely on."""

    return _OWNER_ONLY_CHECKS_SUPPORTED


def _require_home_argument(home: Path) -> None:
    if not _owner_only_checks_supported():
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE,
            PrivateStorageLocation.HOME,
            home,
            detail=_UNSUPPORTED_PLATFORM,
        )
    if not home.is_absolute() or ".." in home.parts:
        raise ValueError("application home must be an absolute path without '..' components")


def _verify_home_ancestors(home: Path) -> None:
    """Verify every directory the kernel traverses to reach *home*, following trusted links."""

    uid = os.geteuid()
    current = Path(home.anchor)
    _require_trusted_ancestor(current, _lstat_ancestor(current), uid)
    pending = list(reversed(home.parent.parts[1:]))
    hops = 0
    while pending:
        name = pending.pop()
        if name == "..":
            current = current.parent
            continue
        candidate = current / name
        status = _lstat_ancestor(candidate)
        if not stat.S_ISLNK(status.st_mode):
            _require_trusted_ancestor(candidate, status, uid)
            current = candidate
            continue
        if status.st_uid not in (_ROOT_UID, uid):
            raise PrivateStorageError(
                PrivateStorageViolation.SYMLINK, PrivateStorageLocation.HOME_ANCESTOR, candidate
            )
        hops += 1
        if hops > _MAX_SYMLINK_HOPS:
            raise PrivateStorageError(
                PrivateStorageViolation.UNVERIFIABLE,
                PrivateStorageLocation.HOME_ANCESTOR,
                candidate,
                detail=_TOO_MANY_LINKS,
            )
        # A relative target resolves from the directory holding the link; an absolute one
        # restarts at the (already verified) root.
        target = Path(os.readlink(candidate))
        if target.is_absolute():
            current = Path(target.anchor)
            pending.extend(reversed(target.parts[1:]))
        else:
            pending.extend(reversed(target.parts))


def _lstat_ancestor(path: Path) -> os.stat_result:
    try:
        return os.lstat(path)
    except PermissionError as error:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE,
            PrivateStorageLocation.HOME_ANCESTOR,
            path,
            detail=_CHECK_DENIED,
        ) from error


def _require_trusted_ancestor(path: Path, status: os.stat_result, uid: int) -> None:
    location = PrivateStorageLocation.HOME_ANCESTOR
    if not stat.S_ISDIR(status.st_mode):
        raise PrivateStorageError(PrivateStorageViolation.NOT_DIRECTORY, location, path)
    if status.st_uid not in (_ROOT_UID, uid):
        raise PrivateStorageError(PrivateStorageViolation.FOREIGN_OWNER, location, path)
    mode = stat.S_IMODE(status.st_mode)
    if mode & _SHARED_WRITE_BITS and not mode & stat.S_ISVTX:
        raise PrivateStorageError(PrivateStorageViolation.PERMISSIVE, location, path, mode=mode)


def _create_home_if_missing(home: Path) -> None:
    try:
        os.mkdir(home, PRIVATE_DIRECTORY_MODE)
    except FileExistsError:
        return
    # The umask can only have removed bits, so the new home was never wider than 0700.
    # Its parent was verified, so nobody else can have replaced it since.
    os.chmod(home, PRIVATE_DIRECTORY_MODE)
    if stat.S_IMODE(os.lstat(home).st_mode) != PRIVATE_DIRECTORY_MODE:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE,
            PrivateStorageLocation.HOME,
            home,
            detail=_MODES_NOT_KEPT,
        )


def _open_home(home: Path) -> int:
    """Open a verified descriptor on the home, which is refused rather than repaired."""

    location = PrivateStorageLocation.HOME
    status = _stat_no_follow(None, home, location, home)
    _require_owned(status, location, home, directory=True)
    mode = stat.S_IMODE(status.st_mode)
    if mode & _SHARED_ACCESS_BITS:
        raise PrivateStorageError(PrivateStorageViolation.PERMISSIVE, location, home, mode=mode)
    fd = _open_no_follow(None, home, os.O_RDONLY | os.O_DIRECTORY, location, home, None)
    try:
        _require_same_object(fd, status, location, home)
    except BaseException:
        os.close(fd)
        raise
    return fd


# ── Entries below the home ─────────────────────────────────────────


def _open_directory_entry(parent_fd: int, name: str, path: Path, *, create: bool) -> int:
    """Open a verified ``0700`` descriptor on the directory *name* inside *parent_fd*."""

    created = False
    if create:
        try:
            os.mkdir(name, PRIVATE_DIRECTORY_MODE, dir_fd=parent_fd)
            created = True
        except FileExistsError:
            pass
    location = PrivateStorageLocation.ENTRY
    status = _stat_no_follow(parent_fd, name, location, path)
    _require_owned(status, location, path, directory=True)
    fd = _open_no_follow(
        parent_fd, name, os.O_RDONLY | os.O_DIRECTORY, location, path, PRIVATE_DIRECTORY_MODE
    )
    try:
        _require_same_object(fd, status, location, path)
        _settle_mode(fd, PRIVATE_DIRECTORY_MODE, path)
    except BaseException:
        os.close(fd)
        raise
    if not created:
        _log_repair(path, status, PRIVATE_DIRECTORY_MODE)
    return fd


def _open_file_entry(parent_fd: int, name: str, flags: int, path: Path) -> int:
    """Open a verified ``0600`` descriptor on the file *name* inside *parent_fd*."""

    location = PrivateStorageLocation.ENTRY
    try:
        before: os.stat_result | None = _stat_no_follow(parent_fd, name, location, path)
    except FileNotFoundError:
        if not flags & os.O_CREAT:
            raise
        before = None
    if before is not None:
        _require_owned(before, location, path, directory=False)
    restore = None if before is None else PRIVATE_FILE_MODE
    fd = _open_no_follow(parent_fd, name, flags, location, path, restore)
    try:
        if before is None:
            # Created here: judge what was actually opened.
            _require_owned(os.fstat(fd), location, path, directory=False)
        else:
            _require_same_object(fd, before, location, path)
        _settle_mode(fd, PRIVATE_FILE_MODE, path)
    except BaseException:
        os.close(fd)
        raise
    if before is not None:
        _log_repair(path, before, PRIVATE_FILE_MODE)
    return fd


# ── Shared checks ──────────────────────────────────────────────────


def _stat_no_follow(
    dir_fd: int | None, name: str | Path, location: PrivateStorageLocation, path: Path
) -> os.stat_result:
    try:
        return os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except PermissionError as error:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHECK_DENIED
        ) from error


def _require_owned(
    status: os.stat_result, location: PrivateStorageLocation, path: Path, *, directory: bool
) -> None:
    if stat.S_ISLNK(status.st_mode):
        raise PrivateStorageError(PrivateStorageViolation.SYMLINK, location, path)
    if directory and not stat.S_ISDIR(status.st_mode):
        raise PrivateStorageError(PrivateStorageViolation.NOT_DIRECTORY, location, path)
    if not directory and not stat.S_ISREG(status.st_mode):
        raise PrivateStorageError(PrivateStorageViolation.NOT_REGULAR_FILE, location, path)
    if status.st_uid != os.geteuid():
        raise PrivateStorageError(PrivateStorageViolation.FOREIGN_OWNER, location, path)


def _open_no_follow(
    dir_fd: int | None,
    name: str | Path,
    flags: int,
    location: PrivateStorageLocation,
    path: Path,
    restore_mode: int | None,
) -> int:
    """Open without following a final link.

    With *restore_mode*, an entry already verified as the current user's whose own mode
    denies its owner is restored to that mode and opened once more.
    """

    def attempt() -> int:
        try:
            return os.open(
                name, flags | os.O_NOFOLLOW | os.O_CLOEXEC, PRIVATE_FILE_MODE, dir_fd=dir_fd
            )
        except OSError as error:
            if error.errno in _UNOPENABLE_LINK_ERRNOS:
                raise _unopenable(dir_fd, name, flags, location, path) from error
            raise

    try:
        return attempt()
    except PermissionError as error:
        if restore_mode is None:
            raise PrivateStorageError(
                PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHECK_DENIED
            ) from error
        mode = restore_mode
    if _LINK_SAFE_CHMOD:
        os.chmod(name, mode, dir_fd=dir_fd, follow_symlinks=False)
    else:
        os.chmod(name, mode, dir_fd=dir_fd)
    try:
        return attempt()
    except PermissionError as error:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHECK_DENIED
        ) from error


def _unopenable(
    dir_fd: int | None,
    name: str | Path,
    flags: int,
    location: PrivateStorageLocation,
    path: Path,
) -> PrivateStorageError:
    """Classify a no-follow open that failed because of what the entry turned out to be."""

    try:
        status = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except OSError:
        status = None
    if status is not None and stat.S_ISLNK(status.st_mode):
        return PrivateStorageError(PrivateStorageViolation.SYMLINK, location, path)
    if status is not None and flags & os.O_DIRECTORY and not stat.S_ISDIR(status.st_mode):
        return PrivateStorageError(PrivateStorageViolation.NOT_DIRECTORY, location, path)
    return PrivateStorageError(
        PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHANGED_DURING_CHECK
    )


def _require_same_object(
    fd: int, expected: os.stat_result, location: PrivateStorageLocation, path: Path
) -> None:
    opened = os.fstat(fd)
    if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHANGED_DURING_CHECK
        )


def _settle_mode(fd: int, private_mode: int, path: Path) -> None:
    """Set an owned entry's mode to exactly *private_mode* through its descriptor."""

    if stat.S_IMODE(os.fstat(fd).st_mode) == private_mode:
        return
    location = PrivateStorageLocation.ENTRY
    try:
        os.fchmod(fd, private_mode)
    except PermissionError as error:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHECK_DENIED
        ) from error
    if stat.S_IMODE(os.fstat(fd).st_mode) != private_mode:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_MODES_NOT_KEPT
        )


def _log_repair(path: Path, before: os.stat_result, private_mode: int) -> None:
    previous = stat.S_IMODE(before.st_mode)
    if previous != private_mode:
        log.warning(
            "Tightened %s from mode %04o to owner-only mode %04o", path, previous, private_mode
        )
