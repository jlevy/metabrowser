"""Owner-only storage for the Metabrowser application home.

Repository stores, source bindings, and provider mirrors may hold private content, so
everything Metabrowser keeps under the application home must be reachable only by the
user running it. This module is the enforcement point cache and provider code call
before they create or open anything there. It also resolves where the home is
(``METABROWSER_HOME``, else ``~/.metabrowser``), creates the owner-only ``f01`` directory
skeleton with its ``CACHEDIR.TAG``, and publishes files atomically; what the records in
that skeleton mean belongs to :mod:`metabrowser.cache`. Whichever directory resolution
chooses is Metabrowser-owned by definition, so every entry below it that the current
user owns is Metabrowser's to repair. Nothing here runs unless a caller asks for the
application home: browsing an ordinary local path never resolves, validates, or creates
it.

Each rule answers a specific threat:

- **Nothing another principal can redirect.** Every directory the kernel traverses to
  reach the home must be owned by root or the current user and must not give anyone
  else write access, whether through its mode (unless the sticky bit is set) or, on
  macOS, through an ACL allow entry, because whoever can write to an ancestor can rename
  the home away and substitute their own. Read access above the home is harmless and
  accepted. A symbolic link above the home is followed only when root or the current
  user owns it — ``/home`` pointing into ``/var/home`` is layout, not an attack — and
  each directory it leads through is held to the same rule.
- **Nothing another principal can read.** The home is owned by the current user, has no
  group or other mode bits, and on macOS has no ACL allow entry for anyone else. An
  entry below it is private under the same test: no group or other permission bits and
  no allow entry for another principal. Any owner-only mode passes, so the ``0400``
  objects and owner-only directories that Git writes under umask ``077`` need no repair.
  A regular file has exactly one link, since a second link reaches the same content from
  outside.
- **No window and no side effect before verification.** The home is created by path
  under its verified parent, then set to ``0700`` and stripped of inherited ACL entries
  while it is still empty. Entries this module creates are exactly ``0700`` directories
  and ``0600`` files without ACL entries, whatever the umask and whatever a parent would
  have them inherit; they start with the restrictive mode, which a umask can only
  narrow, and are removed again if they are refused. Entries are reached by directory
  descriptor with ``O_NOFOLLOW`` and re-identified by device and inode after opening.
  That identity is only a hint, because an unlinked entry's inode number can be reused
  at once, as Linux file systems do; safety never rests on it alone, since owner, type,
  mode, link count, and ACL are all judged again on the opened descriptor. A file is
  opened with ``O_NONBLOCK`` and without ``O_TRUNC``, and all of that is judged before
  it is truncated or handed back.
- **Repair only what is ours, and never mistake repair for revocation.** Repairing an
  entry the current user owns removes its group and other permission bits and clears a
  sharing ACL, with a logged warning; it never adds owner permissions, so an existing
  entry whose own mode denies its owner the access requested is refused instead.
  Tightening affects later opens only: a descriptor or directory handle opened while the
  entry was shared stays usable. Directories and read-only opens are therefore repaired,
  but an in-place write to a file that was shared is refused. Record writes create a
  temporary file with ``O_CREAT | O_EXCL`` and rename it into place. A lock file that was
  ever shared is replaced the same way only after its old file's lock is acquired without
  blocking, and that lock is released after the rename; if it cannot be acquired the file
  is refused, because another holder may still have it locked and a replacement would let
  a second holder take the same lock. The home is never repaired, and nothing above it is
  modified.
- **Fail closed.** A platform without descriptor-relative, no-follow operations —
  Windows today — a file system that does not keep modes, and an ACL that cannot be read
  or interpreted are all refused as ``unverifiable``.

On Linux only mode bits are inspected, and that suffices for POSIX ACLs. Once an object
has an ACL, its group-class mode bits are the ACL mask, which bounds every named user
and group entry and the owning group, and its other-class bits are the ``other`` entry;
a mode without group or other bits clears both, so no entry grants access. A parent's
default ACL reaches a new entry through the create mode, and the exact mode set
afterwards clears the mask again. NFSv4 ACLs are not inspected.

Only a directory this module has just created is ever given owner access it lacks,
which a umask such as ``0777`` leaves it without. That never follows a link: macOS
changes the mode without following, Linux changes it through an ``O_PATH`` descriptor,
and a platform with neither refuses and removes the directory.

A refusal is a :class:`PrivateStorageError`. Its message names a logical location and a
remedy but never a path, because it may reach a job status or an API envelope and a
cache path can name a private repository; the path stays on the exception for local
logs and CLI rendering. Any other ``OSError`` leaves the public functions without file
names, chained to the original.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import functools
import logging
import os
import re
import secrets
import stat
import struct
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from metabrowser.inventory_engine.contract import require_canonical_inventory_path

try:
    import fcntl
except ImportError:  # Windows: every public call below refuses as unverifiable first.
    fcntl = None

log = logging.getLogger(__name__)

PRIVATE_DIRECTORY_MODE: Final = 0o700
PRIVATE_FILE_MODE: Final = 0o600

METABROWSER_HOME_ENV: Final = "METABROWSER_HOME"
DEFAULT_HOME_NAME: Final = ".metabrowser"
CACHE_DIRECTORY: Final = "cache"
CACHEDIR_TAG_PATH: Final = "cache/CACHEDIR.TAG"
# https://bford.info/cachedir/: backup and cleanup tools skip a directory holding a file
# with this name that begins with this signature.
CACHEDIR_TAG_SIGNATURE: Final = b"Signature: 8a477f597d28d172789f06886806bc55"
CACHEDIR_TAG_CONTENT: Final = (
    CACHEDIR_TAG_SIGNATURE + b"\n"
    b"# This file is a cache directory tag created by Metabrowser.\n"
    b"# For information about cache directory tags, see https://bford.info/cachedir/\n"
)
# The owner-only directories of the f01 layout, parents first. Lock files live under
# cache/locks/ so no publication, purge, quarantine, or reclamation ever renames one.
F01_DIRECTORIES: Final = (
    "cache",
    "cache/locks",
    "cache/locks/sources",
    "cache/locks/stores",
    "cache/locks/staging",
    "cache/locks/trash",
    "cache/locks/jobs",
    "cache/locks/providers",
    "cache/staging",
    "cache/trash",
    "cache/quarantine",
    "cache/sources",
    "cache/repository-stores",
)

# Any permission granted to group or other.
_SHARED_ACCESS_BITS: Final = 0o077
# Above the home only write access matters: the home itself refuses traversal, but
# whoever can write to an ancestor can replace everything below it.
_SHARED_WRITE_BITS: Final = 0o022
_WRITE_ACCESS_FLAGS: Final = os.O_WRONLY | os.O_RDWR
_ROOT_UID: Final = 0
# The number of symbolic links Linux follows while resolving one path (MAXSYMLINKS).
_MAX_SYMLINK_HOPS: Final = 40
# How a no-follow, non-blocking open says the entry is not what was inspected: a final
# link is ELOOP on Linux and macOS and EMLINK on FreeBSD, O_DIRECTORY on a link or file
# is ENOTDIR, and a FIFO without a reader, a socket, or a device is ENXIO, ENODEV, or
# EOPNOTSUPP.
_UNOPENABLE_ERRNOS: Final = frozenset(
    {
        errno.ELOOP,
        errno.EMLINK,
        errno.ENOTDIR,
        errno.ENXIO,
        errno.ENODEV,
        errno.EOPNOTSUPP,
        errno.ENOTSUP,
    }
)

_OWNER_ONLY_CHECKS_SUPPORTED: Final = (
    os.name == "posix"
    and hasattr(os, "O_NOFOLLOW")
    and hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NONBLOCK")
    and os.open in os.supports_dir_fd
    and os.mkdir in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.stat in os.supports_follow_symlinks
    and os.chmod in os.supports_dir_fd
)
_LINK_SAFE_CHMOD: Final = os.chmod in os.supports_follow_symlinks
_O_PATH: Final[int | None] = getattr(os, "O_PATH", None)
_PROC_SELF_FD: Final = Path("/proc/self/fd")

# Atomic publication. A temporary file is `.<target>.<16 hex>.tmp` beside its target and
# holds an exclusive flock for its whole life, so a later writer of the same target can
# tell a crashed writer's leftover from a live one without guessing from its age.
_TEMPORARY_SUFFIX_RE: Final = r"\.[0-9a-f]{16}\.tmp"
_TEMPORARY_ATTEMPTS: Final = 4
# No-replace renames: renameat2(RENAME_NOREPLACE) on Linux, renamex_np(RENAME_EXCL) on
# macOS. A file system that does not implement the flag answers with one of these, and
# publication then relies on its verify-absent check under the owning lock alone.
_AT_FDCWD: Final = -100
_RENAME_NOREPLACE: Final = 0x1
_RENAME_EXCL: Final = 0x4
_NO_REPLACE_UNSUPPORTED_ERRNOS: Final = frozenset(
    {errno.EINVAL, errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}
)

# macOS extended ACLs, read through libSystem. ``acl_copy_ext_native`` exports an ACL
# as a ``struct kauth_filesec`` from <sys/kauth.h>: a header of magic, owner and group
# GUIDs, entry count, and flags, followed by one ``struct kauth_ace`` per entry.
_EXTENDED_ACLS = sys.platform == "darwin"
_LIBSYSTEM: Final = "/usr/lib/libSystem.B.dylib"
_ACL_TYPE_EXTENDED: Final = 0x00000100
_KAUTH_FILESEC_MAGIC: Final = 0x012CC16D
_KAUTH_FILESEC_NOACL: Final = 0xFFFFFFFF
_FILESEC_HEADER: Final = struct.Struct("=I16s16sII")
_FILESEC_ACE: Final = struct.Struct("=16sII")
_ACL_KIND_MASK: Final = 0xF
_ACL_PERMIT: Final = 1
_ACL_DENY: Final = 2
_GUID_SIZE: Final = 16
_ID_TYPE_UID: Final = 0
_ACL_READ_CLASS_RIGHTS: Final = (
    (1 << 1)  # read data, list directory
    | (1 << 3)  # execute, search
    | (1 << 7)  # read attributes
    | (1 << 9)  # read extended attributes
    | (1 << 11)  # read security
    | (1 << 20)  # synchronize
    | (1 << 22)  # generic execute
    | (1 << 24)  # generic read
)
_ACL_WRITE_CLASS_RIGHTS: Final = (
    (1 << 2)  # write data, add file
    | (1 << 4)  # delete
    | (1 << 5)  # append data, add subdirectory
    | (1 << 6)  # delete child
    | (1 << 8)  # write attributes
    | (1 << 10)  # write extended attributes
    | (1 << 12)  # write security
    | (1 << 13)  # change owner
    | (1 << 21)  # generic all
    | (1 << 23)  # generic write
)
_ACL_KNOWN_RIGHTS: Final = _ACL_READ_CLASS_RIGHTS | _ACL_WRITE_CLASS_RIGHTS


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
    HARD_LINK = "hard_link"
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
_CREATE_DENIED: Final = (
    "permission was denied while creating it. Make sure the current user can write to the "
    "directory that holds it, or set METABROWSER_HOME to a private directory you own"
)
_CANNOT_RESTORE: Final = (
    "the umask left the new directory without owner access, and this platform cannot "
    "restore it without following a link. Run Metabrowser with a umask that keeps owner "
    "permissions, such as 077"
)
_OWNER_DENIED: Final = (
    "its own permissions deny the current user this access, and Metabrowser never widens "
    "the owner permissions of an existing entry. Replace it, or restore owner access with "
    "chmod u+rw (u+rwx for a directory)"
)
_CHANGED_DURING_CHECK: Final = (
    "it was replaced while it was being checked. Make sure nothing else is modifying the "
    "application home, then retry"
)
_TOO_MANY_LINKS: Final = (
    "too many symbolic links lead through it. Set METABROWSER_HOME to the real location "
    "of the application home"
)
_ACL_UNVERIFIABLE: Final = (
    "its access control list could not be read or interpreted. Remove the list with "
    "chmod -N, or set METABROWSER_HOME to a directory on a local APFS volume"
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
    through_acl: bool,
) -> str:
    """Return a path-free, actionable sentence for one refusal."""

    subject = _SUBJECTS[location]
    if through_acl:
        access = " through an access control list"
    else:
        access = "" if mode is None else f" (mode {mode:04o})"
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
                f"{subject} gives other users write access{access}, so they could replace "
                "the home. Remove that access, or set METABROWSER_HOME to a path outside it."
            )
        case PrivateStorageViolation.PERMISSIVE if location is PrivateStorageLocation.HOME:
            remedy = "Remove those entries with chmod -N" if through_acl else "Run chmod 700 on it"
            return f"{subject} is accessible to other users{access}. {remedy}, {_MOVE_HOME}."
        case PrivateStorageViolation.PERMISSIVE:
            return (
                f"{subject} is accessible to other users{access}, and tightening it would not "
                "revoke a descriptor opened while it was shared. Remove it, or replace it "
                "atomically with a new private file instead of writing it in place."
            )
        case PrivateStorageViolation.HARD_LINK:
            return (
                f"{subject} has more than one hard link, so its content can be reached from "
                "outside the application home. Remove it, or replace it atomically with a "
                "new private file."
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
    ``mode`` is set when a permission mode caused a permissive refusal.
    """

    def __init__(
        self,
        violation: PrivateStorageViolation,
        location: PrivateStorageLocation,
        path: Path,
        *,
        mode: int | None = None,
        detail: str | None = None,
        through_acl: bool = False,
    ) -> None:
        super().__init__(_describe(violation, location, mode, detail, through_acl))
        self.violation: PrivateStorageViolation = violation
        self.location: PrivateStorageLocation = location
        self.path: Path = path
        self.mode: int | None = mode


class ApplicationHomeError(ValueError):
    """``METABROWSER_HOME`` does not name a usable application home."""


def _without_file_names[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Re-raise an ``OSError`` leaving *function* without its file names.

    Python puts the name it passed to the system call into the message, and below the
    home that name can be a private repository's slug.
    """

    @functools.wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except OSError as error:
            if error.errno is None:
                raise OSError("file system operation failed") from error
            raise OSError(error.errno, os.strerror(error.errno)) from error

    return wrapper


# ── Public API ─────────────────────────────────────────────────────


@_without_file_names
def validate_private_home(home: Path) -> None:
    """Refuse *home* unless only the current user can read, redirect, or replace it.

    Changes nothing. A missing home raises :class:`FileNotFoundError`, because whether
    that is an error belongs to the caller.
    """

    _require_home_argument(home)
    _verify_home_ancestors(home)
    os.close(_open_home(home))


@_without_file_names
def ensure_private_directory(home: Path, relative_path: str = "") -> Path:
    """Create or verify the owner-only directory *relative_path* below *home*.

    *relative_path* is a POSIX-relative path such as ``"cache/staging"``; the empty
    string names the home. A missing home is created ``0700`` inside an existing parent,
    but an existing home is never repaired. Missing directories below it are created
    exactly ``0700`` without ACL entries. An existing one the current user owns keeps its
    owner permissions and loses only group and other access and any ACL that shares it,
    which does not revoke a directory handle someone opened while it was shared. Returns
    the directory's path.
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


@_without_file_names
def open_private_file(
    home: Path, relative_path: str, flags: int, *, repair_shared: bool = True
) -> int:
    """Open the owner-only file *relative_path* below *home* with ``os.open`` *flags*.

    Returns a blocking descriptor the caller must close, unless *flags* ask for
    ``O_NONBLOCK``. With ``O_CREAT`` a missing file is created exactly ``0600`` without
    ACL entries; with ``O_EXCL`` an existing file raises :class:`FileExistsError`. An
    existing file must be a regular file with one link that the current user owns, and
    any owner-only mode, such as the ``0400`` Git gives objects, is accepted as it is.
    Opened read-only, a file that was shared loses only its group and other access and
    its sharing ACL. Opened for writing, a file that was shared is refused instead,
    because tightening would not revoke a descriptor opened while it was shared: write
    records by creating a temporary file with ``O_CREAT | O_EXCL`` and renaming it into
    place, and replace a lock file the same way. Owner permissions are never widened, so
    a write to a ``0400`` file is refused. ``O_TRUNC`` is applied only after
    verification. Parent directories are verified and repaired as in
    :func:`ensure_private_directory` but never created, so a missing one raises
    :class:`FileNotFoundError`.

    With *repair_shared* false, a read-only open of a shared file returns a descriptor
    without tightening it. That is for a caller about to replace the file: it locks the
    old file first, and a tightened file would look private to every later open while
    whoever opened it when it was shared might still hold its lock.
    """

    _require_home_argument(home)
    require_canonical_inventory_path(relative_path, "application-home path", allow_root=False)
    if flags & os.O_DIRECTORY:
        raise ValueError("open_private_file opens files; use ensure_private_directory")
    if flags & os.O_TRUNC and not flags & _WRITE_ACCESS_FLAGS:
        raise ValueError("O_TRUNC needs O_WRONLY or O_RDWR")
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
        return _open_file_entry(fd, name, flags, path / name, repair_shared=repair_shared)
    finally:
        os.close(fd)


def application_home(environ: Mapping[str, str] | None = None) -> Path:
    """Return the application home without touching the file system.

    ``METABROWSER_HOME`` names it when set; otherwise it is ``~/.metabrowser``. An empty,
    relative, or ``..``-containing ``METABROWSER_HOME`` raises
    :class:`ApplicationHomeError` rather than falling back, so a harness that meant to
    isolate the home can never write to the real one.
    """

    variables = os.environ if environ is None else environ
    value = variables.get(METABROWSER_HOME_ENV)
    if value is None:
        return Path.home() / DEFAULT_HOME_NAME
    if not value:
        raise ApplicationHomeError(
            "METABROWSER_HOME is set but empty. Unset it to use ~/.metabrowser, or set it "
            "to the absolute path of a private directory."
        )
    home = Path(value)
    if not home.is_absolute() or ".." in home.parts:
        raise ApplicationHomeError(
            "METABROWSER_HOME must be an absolute path without '..' components."
        )
    return home


@_without_file_names
def ensure_home(home: Path) -> Path:
    """Create or verify the home and its owner-only ``f01`` skeleton; return the cache root.

    Every directory in :data:`F01_DIRECTORIES` is created ``0700`` or verified, and
    ``cache/CACHEDIR.TAG`` is written atomically unless a file beginning with the cache
    directory signature is already there. Records inside the skeleton are the cache
    layout's business, not this function's.
    """

    for directory in F01_DIRECTORIES:
        ensure_private_directory(home, directory)
    try:
        fd = open_private_file(home, CACHEDIR_TAG_PATH, os.O_RDONLY)
    except FileNotFoundError:
        existing = b""
    else:
        try:
            existing = os.read(fd, len(CACHEDIR_TAG_SIGNATURE))
        finally:
            os.close(fd)
    if existing != CACHEDIR_TAG_SIGNATURE:
        write_private_file_atomic(home, CACHEDIR_TAG_PATH, CACHEDIR_TAG_CONTENT)
    return home / CACHE_DIRECTORY


@_without_file_names
def write_private_file_atomic(
    home: Path, relative_path: str, data: bytes, *, replace: bool = True
) -> None:
    """Publish *data* at *relative_path* below *home* by atomic rename.

    The bytes go to an exclusive ``0600`` temporary file beside the target, which holds
    an exclusive ``flock`` while it lives, and are flushed with ``fsync``; the file is
    renamed into place and the directory is synced. A reader sees the old content or
    the new, never a partial write. With *replace* false an existing target raises
    :class:`FileExistsError`, through the platform's no-replace rename where it has one.
    Before writing, leftovers of this target from a writer that crashed are removed:
    their locks are free, while a live writer's is held. The parent directory must
    already exist.
    """

    require_canonical_inventory_path(relative_path, "application-home path", allow_root=False)
    directory, _, name = relative_path.rpartition("/")
    for _ in range(_TEMPORARY_ATTEMPTS):
        temporary = f"{directory}/" if directory else ""
        temporary += f".{name}.{secrets.token_hex(8)}.tmp"
        try:
            # Verifies every parent directory, so the listing below reads a private one.
            fd = open_private_file(home, temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            continue
        try:
            if not _hold_temporary(fd, home / temporary):
                continue
            _remove_stale_temporaries(home, directory, name)
            _write_all(fd, data)
            os.fsync(fd)
            try:
                if replace:
                    os.replace(home / temporary, home / relative_path)
                else:
                    rename_without_replacing(home / temporary, home / relative_path)
            except BaseException:
                with contextlib.suppress(OSError):
                    os.unlink(home / temporary)
                raise
            _sync_directory(home / directory if directory else home)
            return
        finally:
            os.close(fd)
    raise PrivateStorageError(
        PrivateStorageViolation.UNVERIFIABLE,
        PrivateStorageLocation.ENTRY,
        home / relative_path,
        detail=_CHANGED_DURING_CHECK,
    )


def rename_without_replacing(source: Path, target: Path) -> bool:
    """Rename *source* to *target*, raising :class:`FileExistsError` if *target* exists.

    Uses ``renameat2(RENAME_NOREPLACE)`` on Linux or ``renamex_np(RENAME_EXCL)`` on
    macOS, which refuse even an empty target directory that ``os.rename`` would replace.
    Returns whether that atomic check was used. Where the platform or file system lacks
    it, the target is checked with ``lstat`` first, which is safe only because every
    Metabrowser writer of a published path holds the lock that owns it; callers must
    hold that lock either way.
    """

    function, flag, dirfd_arguments = _no_replace_rename()
    if function is not None:
        ctypes.set_errno(0)
        arguments: tuple[object, ...]
        if dirfd_arguments:
            arguments = (_AT_FDCWD, os.fsencode(source), _AT_FDCWD, os.fsencode(target), flag)
        else:
            arguments = (os.fsencode(source), os.fsencode(target), flag)
        if function(*arguments) == 0:
            return True
        failure = ctypes.get_errno()
        if failure == errno.EEXIST:
            raise FileExistsError(failure, os.strerror(failure))
        if failure not in _NO_REPLACE_UNSUPPORTED_ERRNOS:
            raise OSError(failure, os.strerror(failure))
    try:
        os.lstat(target)
    except FileNotFoundError:
        os.rename(source, target)
        return False
    raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST))


def no_replace_rename_available() -> bool:
    """Whether this platform exposes an atomic no-replace rename."""

    return _no_replace_rename()[0] is not None


# ── Atomic publication ─────────────────────────────────────────────


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def _sync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _same_inode(fd: int, path: Path) -> bool:
    """Whether *path* still names the file open as *fd*."""

    opened = os.fstat(fd)
    try:
        current = os.lstat(path)
    except FileNotFoundError:
        return False
    return (opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino)


def _hold_temporary(fd: int, path: Path) -> bool:
    """Take a new temporary file's liveness lock; ``False`` if a cleaner took it first."""

    if fcntl is None:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE,
            PrivateStorageLocation.ENTRY,
            path,
            detail=_UNSUPPORTED_PLATFORM,
        )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return _same_inode(fd, path)


def _remove_stale_temporaries(home: Path, directory: str, name: str) -> None:
    """Remove temporaries of *name* in *directory* whose writers are gone."""

    pattern = re.compile(rf"\.{re.escape(name)}{_TEMPORARY_SUFFIX_RE}")
    for entry in os.listdir(home / directory if directory else home):
        if pattern.fullmatch(entry) is None:
            continue
        relative = f"{directory}/{entry}" if directory else entry
        try:
            fd = open_private_file(home, relative, os.O_RDONLY | os.O_NONBLOCK)
        except (FileNotFoundError, PrivateStorageError):
            continue
        try:
            if fcntl is None:
                return
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            if _same_inode(fd, home / relative):
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(home / relative)
                log.info("Removed a temporary file left by an interrupted write")
        finally:
            os.close(fd)


@functools.cache
def _no_replace_rename() -> tuple[Callable[..., int] | None, int, bool]:
    """Return the platform no-replace rename, its flag, and whether it takes dirfds."""

    try:
        if sys.platform == "darwin":
            function = ctypes.CDLL(_LIBSYSTEM, use_errno=True).renamex_np
            function.restype = ctypes.c_int
            function.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
            return function, _RENAME_EXCL, False
        if sys.platform.startswith("linux"):
            function = ctypes.CDLL(None, use_errno=True).renameat2
            function.restype = ctypes.c_int
            function.argtypes = (
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            )
            return function, _RENAME_NOREPLACE, True
    except (OSError, AttributeError):
        pass
    return None, 0, False


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
    if any(
        entry.rights & _ACL_WRITE_CLASS_RIGHTS for entry in _foreign_grants(None, location, path)
    ):
        raise PrivateStorageError(
            PrivateStorageViolation.PERMISSIVE, location, path, through_acl=True
        )


def _create_home_if_missing(home: Path) -> None:
    location = PrivateStorageLocation.HOME
    try:
        os.mkdir(home, PRIVATE_DIRECTORY_MODE)
    except FileExistsError:
        return
    except PermissionError as error:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, home, detail=_CREATE_DENIED
        ) from error
    # The umask can only have removed bits, and the verified parent lets nobody else
    # replace the new home, so it is finished by path while it is still empty.
    os.chmod(home, PRIVATE_DIRECTORY_MODE)
    fd = _open_no_follow(None, home, os.O_RDONLY | os.O_DIRECTORY, location, home)
    try:
        if stat.S_IMODE(os.fstat(fd).st_mode) != PRIVATE_DIRECTORY_MODE:
            raise PrivateStorageError(
                PrivateStorageViolation.UNVERIFIABLE, location, home, detail=_MODES_NOT_KEPT
            )
        _clear_acl(fd, location, home)
    finally:
        os.close(fd)


def _open_home(home: Path) -> int:
    """Open a verified descriptor on the home, which is refused rather than repaired."""

    location = PrivateStorageLocation.HOME
    status = _stat_no_follow(None, home, location, home)
    _require_directory(status, location, home)
    _refuse_shared_home_mode(status, home)
    fd = _open_no_follow(None, home, os.O_RDONLY | os.O_DIRECTORY, location, home)
    try:
        opened = _require_same_object(fd, status, location, home)
        _require_directory(opened, location, home)
        _refuse_shared_home_mode(opened, home)
        if _foreign_grants(fd, location, home):
            raise PrivateStorageError(
                PrivateStorageViolation.PERMISSIVE, location, home, through_acl=True
            )
    except BaseException:
        os.close(fd)
        raise
    return fd


def _refuse_shared_home_mode(status: os.stat_result, home: Path) -> None:
    mode = stat.S_IMODE(status.st_mode)
    if mode & _SHARED_ACCESS_BITS:
        raise PrivateStorageError(
            PrivateStorageViolation.PERMISSIVE, PrivateStorageLocation.HOME, home, mode=mode
        )


# ── Entries below the home ─────────────────────────────────────────


def _open_directory_entry(parent_fd: int, name: str, path: Path, *, create: bool) -> int:
    """Open a verified owner-only descriptor on the directory *name* inside *parent_fd*.

    A directory this call creates is finished at exactly ``0700`` and removed again if it
    is refused. An existing one keeps its owner permissions and loses only group and
    other access and a sharing ACL.
    """

    location = PrivateStorageLocation.ENTRY
    created = False
    if create:
        try:
            os.mkdir(name, PRIVATE_DIRECTORY_MODE, dir_fd=parent_fd)
            created = True
        except FileExistsError:
            pass
        except PermissionError as error:
            raise PrivateStorageError(
                PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CREATE_DENIED
            ) from error
    status = _stat_no_follow(parent_fd, name, location, path)
    repair = _Repair()
    try:
        _require_directory(status, location, path)
        # Only a directory this call created may be given owner access it lacks, which a
        # umask such as 0777 leaves it without.
        fd = _open_no_follow(
            parent_fd,
            name,
            os.O_RDONLY | os.O_DIRECTORY,
            location,
            path,
            restore_mode=PRIVATE_DIRECTORY_MODE if created else None,
            denied=_OWNER_DENIED,
        )
        try:
            opened = _require_same_object(fd, status, location, path)
            _require_directory(opened, location, path)
            if created:
                _clear_acl(fd, location, path)
                _set_exact_mode(fd, PRIVATE_DIRECTORY_MODE, location, path)
            else:
                if _foreign_grants(fd, location, path):
                    repair.cleared_acl = _clear_acl(fd, location, path)
                repair.previous_mode = _remove_shared_access(fd, opened, location, path)
        except BaseException:
            os.close(fd)
            raise
    except BaseException:
        if created:
            _remove_created_directory(parent_fd, name, status)
        raise
    repair.log(path)
    return fd


def _open_file_entry(
    parent_fd: int, name: str, flags: int, path: Path, *, repair_shared: bool = True
) -> int:
    """Open a verified owner-only descriptor on the file *name* inside *parent_fd*."""

    location = PrivateStorageLocation.ENTRY
    creating = bool(flags & os.O_CREAT)
    exclusive = creating and bool(flags & os.O_EXCL)
    before: os.stat_result | None
    # Two passes: a file that appears between inspection and exclusive creation is judged
    # once more as an existing file.
    for _ in range(2):
        try:
            before = _stat_no_follow(parent_fd, name, location, path)
        except FileNotFoundError:
            if not creating:
                raise
            before = None
        if before is not None:
            _require_regular_file(before, location, path)
        if before is None or exclusive:
            create_flags = (flags & ~os.O_TRUNC) | os.O_CREAT | os.O_EXCL
            try:
                fd = _open_no_follow(parent_fd, name, create_flags, location, path)
            except FileExistsError:
                if exclusive:
                    raise
                continue
            return _finish_created_file(parent_fd, name, fd, flags, path)
        return _open_existing_file(
            parent_fd, name, flags, before, path, repair_shared=repair_shared
        )
    raise PrivateStorageError(
        PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHANGED_DURING_CHECK
    )


def _finish_created_file(parent_fd: int, name: str, fd: int, flags: int, path: Path) -> int:
    """Verify a file this call created, removing it again if it is refused."""

    location = PrivateStorageLocation.ENTRY
    try:
        _require_regular_file(os.fstat(fd), location, path)
        _clear_acl(fd, location, path)
        _set_exact_mode(fd, PRIVATE_FILE_MODE, location, path)
        _restore_blocking(fd, flags)
    except BaseException:
        _remove_created_file(parent_fd, name, fd)
        os.close(fd)
        raise
    return fd


def _open_existing_file(
    parent_fd: int,
    name: str,
    flags: int,
    before: os.stat_result,
    path: Path,
    *,
    repair_shared: bool = True,
) -> int:
    location = PrivateStorageLocation.ENTRY
    writes = bool(flags & _WRITE_ACCESS_FLAGS)
    if writes and stat.S_IMODE(before.st_mode) & _SHARED_ACCESS_BITS:
        raise PrivateStorageError(
            PrivateStorageViolation.PERMISSIVE,
            location,
            path,
            mode=stat.S_IMODE(before.st_mode),
        )
    open_flags = flags & ~(os.O_CREAT | os.O_EXCL | os.O_TRUNC)
    fd = _open_no_follow(parent_fd, name, open_flags, location, path, denied=_OWNER_DENIED)
    repair = _Repair()
    try:
        opened = os.fstat(fd)
        _require_regular_file(opened, location, path, same_as=before)
        mode = stat.S_IMODE(opened.st_mode)
        if writes and mode & _SHARED_ACCESS_BITS:
            raise PrivateStorageError(PrivateStorageViolation.PERMISSIVE, location, path, mode=mode)
        foreign_grants = _foreign_grants(fd, location, path)
        if foreign_grants and writes:
            raise PrivateStorageError(
                PrivateStorageViolation.PERMISSIVE, location, path, through_acl=True
            )
        if repair_shared:
            if foreign_grants:
                repair.cleared_acl = _clear_acl(fd, location, path)
            repair.previous_mode = _remove_shared_access(fd, opened, location, path)
        if flags & os.O_TRUNC:
            os.ftruncate(fd, 0)
        _restore_blocking(fd, flags)
    except BaseException:
        os.close(fd)
        raise
    repair.log(path)
    return fd


def _remove_created_file(parent_fd: int, name: str, fd: int) -> None:
    """Unlink *name* only while it still names the file this call created as *fd*."""

    with contextlib.suppress(OSError):
        created = os.fstat(fd)
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
            os.unlink(name, dir_fd=parent_fd)


def _remove_created_directory(parent_fd: int, name: str, created: os.stat_result) -> None:
    """Remove *name* only while it is still the empty directory this call created.

    No descriptor is held here, so a reused inode number could make another directory
    match; only the owner or root can place one inside the verified private parent, and
    ``rmdir`` removes nothing but an empty directory. The file cleanup holds its
    descriptor, so its inode cannot be reused while it compares.
    """

    with contextlib.suppress(OSError):
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) == (
            created.st_dev,
            created.st_ino,
        ):
            os.rmdir(name, dir_fd=parent_fd)


@dataclass(slots=True)
class _Repair:
    """What repairing one existing entry changed, reported once it has been verified."""

    previous_mode: int | None = None
    cleared_acl: bool = False

    def log(self, path: Path) -> None:
        if self.previous_mode is not None:
            log.warning(
                "Tightened %s to owner-only access: mode %04o is now %04o",
                path,
                self.previous_mode,
                self.previous_mode & ~_SHARED_ACCESS_BITS,
            )
        if self.cleared_acl:
            log.warning("Removed the access control list that shared %s with other users", path)


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


def _require_directory(
    status: os.stat_result, location: PrivateStorageLocation, path: Path
) -> None:
    if stat.S_ISLNK(status.st_mode):
        raise PrivateStorageError(PrivateStorageViolation.SYMLINK, location, path)
    if not stat.S_ISDIR(status.st_mode):
        raise PrivateStorageError(PrivateStorageViolation.NOT_DIRECTORY, location, path)
    if status.st_uid != os.geteuid():
        raise PrivateStorageError(PrivateStorageViolation.FOREIGN_OWNER, location, path)


def _require_regular_file(
    status: os.stat_result,
    location: PrivateStorageLocation,
    path: Path,
    *,
    same_as: os.stat_result | None = None,
) -> None:
    if stat.S_ISLNK(status.st_mode):
        raise PrivateStorageError(PrivateStorageViolation.SYMLINK, location, path)
    if not stat.S_ISREG(status.st_mode):
        raise PrivateStorageError(PrivateStorageViolation.NOT_REGULAR_FILE, location, path)
    if same_as is not None and (status.st_dev, status.st_ino) != (
        same_as.st_dev,
        same_as.st_ino,
    ):
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHANGED_DURING_CHECK
        )
    if status.st_uid != os.geteuid():
        raise PrivateStorageError(PrivateStorageViolation.FOREIGN_OWNER, location, path)
    if status.st_nlink == 0:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHANGED_DURING_CHECK
        )
    if status.st_nlink != 1:
        raise PrivateStorageError(PrivateStorageViolation.HARD_LINK, location, path)


def _open_no_follow(
    dir_fd: int | None,
    name: str | Path,
    flags: int,
    location: PrivateStorageLocation,
    path: Path,
    *,
    restore_mode: int | None = None,
    denied: str | None = None,
) -> int:
    """Open without following a final link and without blocking on a FIFO.

    With *restore_mode* and a parent descriptor, a directory this call created whose mode
    the umask left without owner access is set to that mode, without following a link,
    and opened once more. Otherwise a permission failure is refused with *denied* as its
    explanation.
    """

    def attempt() -> int:
        try:
            return os.open(
                name,
                flags | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                PRIVATE_FILE_MODE,
                dir_fd=dir_fd,
            )
        except OSError as error:
            if error.errno in _UNOPENABLE_ERRNOS:
                raise _unopenable(dir_fd, name, flags, location, path) from error
            raise

    if denied is None:
        denied = _CREATE_DENIED if flags & os.O_CREAT else _CHECK_DENIED
    try:
        return attempt()
    except PermissionError as error:
        if restore_mode is None or dir_fd is None:
            raise PrivateStorageError(
                PrivateStorageViolation.UNVERIFIABLE, location, path, detail=denied
            ) from error
        parent_fd, mode = dir_fd, restore_mode
    _restore_owner_access(parent_fd, str(name), mode, location, path)
    try:
        return attempt()
    except PermissionError as error:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHECK_DENIED
        ) from error


def _restore_owner_access(
    parent_fd: int, name: str, mode: int, location: PrivateStorageLocation, path: Path
) -> None:
    """Set *name*'s mode without following a link, or refuse where that is impossible."""

    try:
        if _LINK_SAFE_CHMOD:
            os.chmod(name, mode, dir_fd=parent_fd, follow_symlinks=False)
            return
        if _O_PATH is None or not _PROC_SELF_FD.is_dir():
            raise PrivateStorageError(
                PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CANNOT_RESTORE
            )
        # An O_PATH descriptor names the inode itself without needing read access, and
        # its /proc link changes exactly that inode.
        handle = os.open(name, _O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent_fd)
        try:
            if stat.S_ISLNK(os.fstat(handle).st_mode):
                raise PrivateStorageError(PrivateStorageViolation.SYMLINK, location, path)
            os.chmod(_PROC_SELF_FD / str(handle), mode)
        finally:
            os.close(handle)
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
    if status is not None and not flags & os.O_DIRECTORY and not stat.S_ISREG(status.st_mode):
        return PrivateStorageError(PrivateStorageViolation.NOT_REGULAR_FILE, location, path)
    return PrivateStorageError(
        PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHANGED_DURING_CHECK
    )


def _require_same_object(
    fd: int, expected: os.stat_result, location: PrivateStorageLocation, path: Path
) -> os.stat_result:
    """Refuse a descriptor whose (device, inode) differs from the entry inspected earlier.

    A match does not prove identity: once the inspected entry is unlinked, its inode
    number may be reused immediately (Linux does), so a replacement can match. Callers
    therefore judge owner, type, mode, link count, and ACL again on the returned status
    and descriptor, and this check only turns an observable swap into a clear refusal.
    """

    opened = os.fstat(fd)
    if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHANGED_DURING_CHECK
        )
    return opened


def _set_exact_mode(fd: int, mode: int, location: PrivateStorageLocation, path: Path) -> None:
    """Finish an entry this call created at exactly *mode*, through its descriptor."""

    if stat.S_IMODE(os.fstat(fd).st_mode) != mode:
        _change_mode(fd, mode, location, path)


def _remove_shared_access(
    fd: int, opened: os.stat_result, location: PrivateStorageLocation, path: Path
) -> int | None:
    """Remove group and other permission bits, leaving the owner's untouched.

    Returns the mode before the change, or ``None`` when the entry was already owner-only.
    """

    previous = stat.S_IMODE(opened.st_mode)
    if not previous & _SHARED_ACCESS_BITS:
        return None
    _change_mode(fd, previous & ~_SHARED_ACCESS_BITS, location, path)
    return previous


def _change_mode(fd: int, mode: int, location: PrivateStorageLocation, path: Path) -> None:
    try:
        os.fchmod(fd, mode)
    except PermissionError as error:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_CHECK_DENIED
        ) from error
    if stat.S_IMODE(os.fstat(fd).st_mode) != mode:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_MODES_NOT_KEPT
        )


def _restore_blocking(fd: int, flags: int) -> None:
    if not flags & os.O_NONBLOCK:
        os.set_blocking(fd, True)


# ── macOS extended ACLs ────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _AclEntry:
    """One extended ACL entry: its kind, the principal's GUID, and its rights bits."""

    kind: int
    principal: bytes
    rights: int


class _AclUnverifiable(Exception):
    """An extended ACL could not be read, cleared, or interpreted."""


def _foreign_grants(
    fd: int | None, location: PrivateStorageLocation, path: Path
) -> tuple[_AclEntry, ...]:
    """Return the ACL allow entries that name a principal other than the current user.

    Reads through *fd*, or through *path* without following a final link when *fd* is
    ``None``. Deny entries never grant access and are ignored; an entry of any other
    kind, or an allow entry with a right this module does not know, is refused.
    """

    if not _EXTENDED_ACLS:
        return ()
    try:
        grants: list[_AclEntry] = []
        for entry in _read_acl(fd, path):
            if entry.kind == _ACL_DENY:
                continue
            if entry.kind != _ACL_PERMIT or entry.rights & ~_ACL_KNOWN_RIGHTS:
                raise _AclUnverifiable(f"kind {entry.kind} with rights {entry.rights:#x}")
            if not _is_current_user(entry.principal):
                grants.append(entry)
        return tuple(grants)
    except _AclUnverifiable as error:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_ACL_UNVERIFIABLE
        ) from error


def _clear_acl(fd: int, location: PrivateStorageLocation, path: Path) -> bool:
    """Remove every extended ACL entry through *fd*; return whether there were any."""

    if not _EXTENDED_ACLS:
        return False
    try:
        if not _read_acl(fd, path):
            return False
        library = _libsystem()
        empty = library.acl_init(0)
        if not empty:
            raise _AclUnverifiable("acl_init failed")
        try:
            ctypes.set_errno(0)
            if library.acl_set_fd_np(fd, empty, _ACL_TYPE_EXTENDED) != 0:
                raise _AclUnverifiable(f"acl_set_fd_np failed with errno {ctypes.get_errno()}")
        finally:
            library.acl_free(empty)
        if _read_acl(fd, path):
            raise _AclUnverifiable("entries remained after clearing")
    except _AclUnverifiable as error:
        raise PrivateStorageError(
            PrivateStorageViolation.UNVERIFIABLE, location, path, detail=_ACL_UNVERIFIABLE
        ) from error
    return True


def _read_acl(fd: int | None, path: Path) -> tuple[_AclEntry, ...]:
    library = _libsystem()
    ctypes.set_errno(0)
    if fd is None:
        handle = library.acl_get_link_np(os.fsencode(path), _ACL_TYPE_EXTENDED)
    else:
        handle = library.acl_get_fd_np(fd, _ACL_TYPE_EXTENDED)
    if not handle:
        failure = ctypes.get_errno()
        if failure == errno.ENOENT:
            return ()
        raise _AclUnverifiable(f"reading the ACL failed with errno {failure}")
    try:
        size = library.acl_size(handle)
        if size < _FILESEC_HEADER.size:
            raise _AclUnverifiable("acl_size failed")
        buffer = ctypes.create_string_buffer(size)
        written = library.acl_copy_ext_native(buffer, handle, size)
    finally:
        library.acl_free(handle)
    if not _FILESEC_HEADER.size <= written <= size:
        raise _AclUnverifiable("acl_copy_ext_native failed")
    return _parse_filesec(buffer.raw[:written])


def _parse_filesec(raw: bytes) -> tuple[_AclEntry, ...]:
    magic, _owner, _group, count, _flags = _FILESEC_HEADER.unpack_from(raw)
    if magic != _KAUTH_FILESEC_MAGIC:
        raise _AclUnverifiable("unexpected ACL format")
    if count == _KAUTH_FILESEC_NOACL:
        return ()
    body = raw[_FILESEC_HEADER.size :]
    if len(body) != count * _FILESEC_ACE.size:
        raise _AclUnverifiable("ACL size does not match its entry count")
    return tuple(
        _AclEntry(kind=flags & _ACL_KIND_MASK, principal=principal, rights=rights)
        for principal, flags, rights in _FILESEC_ACE.iter_unpack(body)
    )


def _is_current_user(principal: bytes) -> bool:
    """Whether an ACL principal GUID is the effective user; an unknown one is not."""

    library = _libsystem()
    uid = os.geteuid()
    own = ctypes.create_string_buffer(_GUID_SIZE)
    if library.mbr_uid_to_uuid(uid, own) == 0 and own.raw == principal:
        return True
    identifier = ctypes.c_uint32()
    identifier_type = ctypes.c_int()
    if library.mbr_uuid_to_id(principal, ctypes.byref(identifier), ctypes.byref(identifier_type)):
        return False
    return identifier_type.value == _ID_TYPE_UID and identifier.value == uid


@functools.cache
def _libsystem() -> ctypes.CDLL:
    try:
        library = ctypes.CDLL(_LIBSYSTEM, use_errno=True)
        signatures: dict[str, tuple[type[object] | None, tuple[type[object], ...]]] = {
            "acl_get_fd_np": (ctypes.c_void_p, (ctypes.c_int, ctypes.c_int)),
            "acl_get_link_np": (ctypes.c_void_p, (ctypes.c_char_p, ctypes.c_int)),
            "acl_size": (ctypes.c_ssize_t, (ctypes.c_void_p,)),
            "acl_copy_ext_native": (
                ctypes.c_ssize_t,
                (ctypes.c_char_p, ctypes.c_void_p, ctypes.c_ssize_t),
            ),
            "acl_init": (ctypes.c_void_p, (ctypes.c_int,)),
            "acl_set_fd_np": (ctypes.c_int, (ctypes.c_int, ctypes.c_void_p, ctypes.c_int)),
            "acl_free": (ctypes.c_int, (ctypes.c_void_p,)),
            "mbr_uid_to_uuid": (ctypes.c_int, (ctypes.c_uint32, ctypes.c_char_p)),
            "mbr_uuid_to_id": (
                ctypes.c_int,
                (ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_int)),
            ),
        }
        for name, (restype, argtypes) in signatures.items():
            function = getattr(library, name)
            function.restype = restype
            function.argtypes = argtypes
    except (OSError, AttributeError) as error:
        raise _AclUnverifiable("libSystem ACL functions are unavailable") from error
    return library
