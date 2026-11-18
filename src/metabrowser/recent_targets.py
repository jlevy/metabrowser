"""Recent targets: the folders and repositories the user opened lately, kept for every shell.

One list, in one file beside ``config.yml``, that ``metab`` writes and every shell reads
through ``metab``: the command line (``--recent``), the macOS app's File > Open Recent,
and whatever comes later. A shell draws the list and never decides what is in it.
``docs/project/architecture/arch-recent-targets.md`` is the design; this module holds
the format, the bounds, and the reason beside each.

**The entry.** A :class:`RecentTarget` is a root and the mode it was opened in:

- ``folder``: an attached folder, by its absolute path with symbolic links resolved
  (:func:`folder_root`). ``metab FILE`` serves the file's folder, so that folder is the
  root.
- ``mirror``: a pinned revision of a repository in the cache, by the source's
  credential-free address as the root grammar normalizes it (``GitSource.normalized``),
  which for a GitHub URL is ``https://github.com/<owner>/<repo>`` whatever the URL
  selected inside it.

``mode`` is ``kind`` in ``GET /api/identity`` (:mod:`metabrowser.root_identity`), and
``mode`` with ``root`` is the key of the macOS app's session for the root, so one entry
is one window. A root never comes from an argument as typed, so no credential is stored.

**The file.** ``recent-targets.yml``: YAML, as ``config.yml`` and ``layout.yml`` are, so a
person can read it, with a ``format`` string and the ``targets``, most recently opened
first, one entry per root. The format string follows the application home's convention
(``cache/layout.py``): a short self-describing string, here ``mf`` and a number, an
append-only :data:`FORMAT_HISTORY`, a :data:`MIGRATIONS` step from each format to the
next, and a refusal of a format newer than this release reads. It is raised only for a
change an older reader would misread; a compatible change keeps it. The file is read
with PyYAML's base loader, which makes every scalar a string and builds no object, and
not with the schema library the cache's records use, which a folder's server never
loads (``tests/test_plugin_public_api.py``). The list names the user's folders, so it is
read and written only through :mod:`metabrowser.home`'s owner-only helpers.

**What can go wrong, and what happens.**

- *A file from a newer release* is left as it is: :func:`read` lists nothing and says
  to upgrade, and :func:`record` raises :class:`NewerFormatError`.
- *A damaged file* (not YAML, not this shape, or over a bound) lists as empty with the
  reason, and the next :func:`record` replaces it. Nothing else depends on the list.
- *A folder that is gone* stays listed. Nothing here looks at a listed path: on macOS a
  look can raise a privacy prompt, and on a dead network volume it can hang. A shell
  forgets the entry when the user tries to open it.
- *Two writers at once* each hold an exclusive ``flock`` on the lock file across their
  read, change, and atomic rename, so neither loses the other's entry. A reader takes
  no lock: a rename shows it the old file or the new.

A server records itself with :func:`record_quietly`, which never raises and never waits
longer than :data:`LOCK_WAIT_S`: the list is not worth delaying or failing a server for.
"""

from __future__ import annotations

import contextlib
import errno
import logging
import os
import re
import sys
import time
import unicodedata
from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal, cast

import yaml

from metabrowser.home import (
    PrivateFileTooLargeError,
    PrivateStorageError,
    SharedEntryPolicy,
    configuration_directory,
    ensure_storage_root,
    open_private_file,
    read_private_file_bounded,
    write_private_file_atomic,
)

try:
    import fcntl
except ImportError:  # Windows: the owner-only helpers refuse first, as unverifiable.
    fcntl = None

log = logging.getLogger(__name__)

# Set to ``0`` (or ``false``, ``no``, ``off``), this keeps a process from recording
# anything: a serve does not record its root, and ``--recent-add`` records nothing. It
# is for a server nobody opened to read: a benchmark's, a test's, a development run of
# the macOS app, and the servers the app starts when it restores its last session, which
# is not an open. Listing, forgetting, and clearing are unaffected.
RECORD_ENV: Final = "METABROWSER_RECORD_RECENT"
_OFF: Final = frozenset({"0", "false", "no", "off"})
STORE_FILE: Final = "recent-targets.yml"
LOCK_FILE: Final = "recent-targets.lock"
# The format this release writes: ``mf`` for a Metabrowser format, then its number, so
# the string says what it is wherever it turns up. The number rises only for a change an
# older reader would misread; a compatible change keeps the string.
FORMAT: Final = "mf01"
# Every format a released Metabrowser has written, oldest first, ending with the current
# one. Adding a format appends it here and adds the migration from its predecessor.
FORMAT_HISTORY: Final[tuple[str, ...]] = (FORMAT,)

type Migration = Callable[[dict[str, Any]], dict[str, Any]]
# The step from each historical format's document to the next format's in FORMAT_HISTORY.
MIGRATIONS: Final[Mapping[str, Migration]] = {}
_FORMAT_PATTERN: Final = re.compile(r"mf([0-9]{2,})")
_HEADER: Final = (
    "# Metabrowser's recent targets: the folders and repositories opened lately, newest\n"
    "# first. metab writes this file as it serves; `metab --recent` lists it.\n"
)

# How many entries the list keeps; the oldest falls off. It is the longest list macOS
# itself offers for an app's recent documents (System Settings > Desktop & Dock > Recent
# documents: None, 5, 10, 15, 20, 30, or 50), so a File > Open Recent drawn from it is
# never longer than one a Mac user can already ask for, and five times macOS's default
# of 10, the cap that made folders go missing from the app's menu (mb-40k4).
MAX_RECENT_TARGETS: Final = 50
# The longest root recorded, in UTF-8 bytes: Linux's PATH_MAX, four times macOS's. No
# folder a server can open has a longer path, and a normalized address is far shorter.
MAX_ROOT_BYTES: Final = 4096
# The largest file read. A root holds no control or line-breaking character, and YAML at
# most doubles what
# is left to escape (a quote, or a character it writes as ``\xNN``), so 50 roots of 4,096
# bytes stay under this, and :func:`_serialize` drops the oldest entries of a list that
# would still exceed it and reads back what it wrote, so no writer publishes a file a
# reader refuses. Measured 2026-11-18 on an Apple-silicon Mac at load average 16, 200
# timed calls each, with libyaml: a list of 50 ordinary roots was 5.3 KiB and
# :func:`read` took a median 0.88 ms (p95 0.93 ms); a list of 50 roots of 4,096 quote
# characters was 203 KiB and took a median 11.9 ms (p95 12.2 ms). PyYAML's own parser,
# its fallback without libyaml, parsed the two files in 5 ms and 57 ms.
MAX_STORE_BYTES: Final = 512 * 1024
# How long a writer waits for another writer's lock before it gives up. In the same
# measurement one :func:`record` into a full list, which holds the lock across its read,
# its atomic write, and both fsyncs, took a median 3.3 ms (p95 3.7 ms, slowest 5.3 ms),
# so this covers hundreds of servers starting at once and still bounds what a wedged
# holder can cost a server's start.
LOCK_WAIT_S: Final = 2.0
_LOCK_RETRY_FIRST_S: Final = 0.005
_LOCK_RETRY_MAX_S: Final = 0.1
# A file system with no ``flock``, as some network mounts are.
_UNSUPPORTED_LOCK_ERRNOS: Final = frozenset(
    {errno.ENOLCK, errno.EOPNOTSUPP, errno.ENOTSUP, errno.EINVAL, errno.ENOSYS}
)
# macOS's MAXPATHLEN, the size of the buffer F_GETPATH fills.
_DARWIN_PATH_BYTES: Final = 1024

type TargetMode = Literal["folder", "mirror"]
MODES: Final[tuple[TargetMode, ...]] = ("folder", "mirror")

# The canonical RFC 3339 UTC spelling the cache's records use (``cache/records.py``).
_TIMESTAMP: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_ENTRY_KEYS: Final = frozenset({"mode", "root", "opened_at"})
# The Unicode categories of the characters no root may hold: controls (C0, DEL, and C1,
# which has NEL) and the line and paragraph separators. A terminal acts on the first, and
# YAML reads NEL, U+2028, and U+2029 as line breaks: PyYAML's own emitter, its fallback
# without libyaml, wrote them raw in a quoted scalar, which did not read back as written,
# while libyaml escapes them. Without them the two emitters write the same text, which
# `test_the_file_is_the_same_with_and_without_libyaml` holds.
_LINE_BREAKING: Final = frozenset({"Cc", "Zl", "Zp"})


@dataclass(frozen=True, slots=True)
class RecentTarget:
    """One root the user opened, the mode it was opened in, and when."""

    mode: TargetMode
    root: str
    opened_at: str

    @property
    def key(self) -> tuple[TargetMode, str]:
        """What makes two entries the same target: the mode and the root."""

        return (self.mode, self.root)

    def as_json(self) -> dict[str, str]:
        return {"mode": self.mode, "root": self.root, "opened_at": self.opened_at}


@dataclass(frozen=True, slots=True)
class Listing:
    """What :func:`read` found: the entries, or why there are none to show.

    ``problem`` is ``None`` for a list that was read, an empty or missing one included.
    Otherwise it is a sentence for the user, and ``targets`` is empty.
    """

    targets: tuple[RecentTarget, ...]
    problem: str | None = None


class RecentTargetsError(Exception):
    """The list could not be read or changed. ``str()`` is for the user and names no path."""


class NewerFormatError(RecentTargetsError):
    """The file was written by a newer release, so this one leaves it alone."""

    def __init__(self, found: str) -> None:
        super().__init__(
            f"the recent targets file uses format {found}, and this release reads formats "
            f"up to {FORMAT}. Upgrade Metabrowser to list or record recent targets"
        )
        self.found: str = found


class UnrecordableRootError(ValueError):
    """A root the list cannot hold; ``str()`` says why."""


class _Damaged(Exception):
    """The file is not a list this release wrote; ``str()`` says how."""


# ── Roots ──────────────────────────────────────────────────────────


def folder_root(path: Path) -> str:
    """The root a served folder is recorded under: resolved, as the file system spells it.

    *path* is the folder a server serves. Symbolic links are resolved, as ``run_serve``
    resolves them, and on macOS the path is then spelled as the volume spells it, which
    ``realpath(3)`` does and Python's does not: on a volume that ignores case,
    ``~/Src/Repo`` and ``~/src/repo`` are one folder, and the macOS app names it by
    ``realpath(3)``. A path that cannot be opened keeps its resolved spelling.
    """

    resolved = os.path.realpath(path)
    if sys.platform != "darwin" or fcntl is None:
        return resolved
    try:
        fd = os.open(resolved, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    except OSError:
        return resolved
    try:
        spelled = fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(_DARWIN_PATH_BYTES))
    except OSError:
        return resolved
    finally:
        os.close(fd)
    return os.fsdecode(spelled.split(b"\0", 1)[0]) or resolved


def _checked_root(mode: str, root: str) -> str | None:
    """Why *root* cannot be an entry of *mode*, or ``None`` when it can."""

    if mode not in MODES:
        return f"{mode!r} is not a mode; the modes are folder and mirror"
    if not root:
        return "the root is empty"
    try:
        size = len(root.encode("utf-8"))
    except UnicodeEncodeError:
        return "the root is not valid UTF-8"
    if size > MAX_ROOT_BYTES:
        return f"the root is longer than {MAX_ROOT_BYTES} bytes"
    if any(unicodedata.category(ch) in _LINE_BREAKING for ch in root):
        return "the root holds a control character or a line separator"
    if mode == "folder" and not root.startswith("/"):
        return "a folder's root is an absolute path"
    if mode == "mirror" and (root.startswith("/") or any(ch.isspace() for ch in root)):
        return "a mirror's root is a repository address"
    return None


# ── Reading ────────────────────────────────────────────────────────


def format_number(value: str) -> int | None:
    """The ordinal of a format spelling such as ``mf01``, or ``None`` for anything else."""

    match = _FORMAT_PATTERN.fullmatch(value)
    return None if match is None else int(match.group(1))


def _current_document(document: dict[str, Any]) -> dict[str, Any]:
    """*document* stepped to this release's format, or the refusal its format earns."""

    found = document.get("format")
    number = format_number(found) if isinstance(found, str) else None
    if not isinstance(found, str) or number is None:
        raise _Damaged("it names no format")
    if number > cast(int, format_number(FORMAT)):
        raise NewerFormatError(found)
    if found not in FORMAT_HISTORY:
        raise _Damaged(f"it names format {found}, which no Metabrowser release wrote")
    for older in FORMAT_HISTORY[FORMAT_HISTORY.index(found) : -1]:
        document = MIGRATIONS[older](document)
    return document


def _parse(payload: bytes) -> tuple[RecentTarget, ...]:
    """The entries of a file a release wrote; anything else is :class:`_Damaged`.

    The base loader makes every scalar a string, so a root that reads as a number, a
    date, or ``yes`` stays the text it is, and a tag constructs nothing.
    """

    loader = getattr(yaml, "CBaseLoader", yaml.BaseLoader)
    try:
        loaded = yaml.load(payload.decode("utf-8"), Loader=loader)
    except (UnicodeDecodeError, yaml.YAMLError, RecursionError) as error:
        raise _Damaged("it is not YAML") from error
    if not isinstance(loaded, dict):
        raise _Damaged("it is not a YAML mapping")
    fields = _current_document(cast(dict[str, Any], loaded))
    if set(fields) != {"format", "targets"}:
        raise _Damaged("it does not hold exactly a format and its targets")
    entries = fields["targets"]
    if not isinstance(entries, list):
        raise _Damaged("its targets are not a list")
    raw_entries = cast(list[object], entries)
    if len(raw_entries) > MAX_RECENT_TARGETS:
        raise _Damaged(f"it lists more than {MAX_RECENT_TARGETS} targets")
    targets: list[RecentTarget] = []
    seen: set[tuple[str, str]] = set()
    for position, entry in enumerate(raw_entries, start=1):
        if not isinstance(entry, dict):
            raise _Damaged(f"entry {position} is not a mode, a root, and a time")
        values = cast(dict[str, object], entry)
        if frozenset(values) != _ENTRY_KEYS:
            raise _Damaged(f"entry {position} is not a mode, a root, and a time")
        mode, root, opened_at = values["mode"], values["root"], values["opened_at"]
        if not isinstance(mode, str) or not isinstance(root, str):
            raise _Damaged(f"entry {position} is not a mode, a root, and a time")
        if (reason := _checked_root(mode, root)) is not None:
            # The reason, never the root: this sentence reaches a terminal and a log.
            raise _Damaged(f"entry {position} cannot be a target: {reason}")
        if not isinstance(opened_at, str) or _TIMESTAMP.fullmatch(opened_at) is None:
            raise _Damaged(f"entry {position} has no time it was opened")
        if (mode, root) in seen:
            raise _Damaged(f"entry {position} repeats an earlier one")
        seen.add((mode, root))
        targets.append(RecentTarget(cast(TargetMode, mode), root, opened_at))
    return tuple(targets)


def _load(directory: Path, *, shared: SharedEntryPolicy) -> tuple[RecentTarget, ...]:
    """The stored entries; none for a missing file. Raises :class:`_Damaged` and
    :class:`NewerFormatError` as :func:`_parse` does, and a storage refusal as it is."""

    try:
        payload = read_private_file_bounded(
            directory, STORE_FILE, max_bytes=MAX_STORE_BYTES, shared=shared
        )
    except FileNotFoundError:
        return ()
    except PrivateFileTooLargeError as error:
        raise _Damaged(f"it is larger than {MAX_STORE_BYTES} bytes") from error
    return _parse(payload)


def read(directory: Path | None = None) -> Listing:
    """The recent targets, most recently opened first. Changes nothing on disk.

    A missing file, or a missing configuration directory, is an empty list. A damaged
    file or one from a newer release is an empty list with a ``problem``. A
    configuration directory that is not private to the user is refused, and a file that
    cannot be read raises :class:`RecentTargetsError`.
    """

    home = configuration_directory() if directory is None else directory
    try:
        return Listing(_load(home, shared="refuse"))
    except NewerFormatError as error:
        message = str(error)
        return Listing((), f"{message[0].upper()}{message[1:]}.")
    except _Damaged as error:
        return Listing(
            (),
            f"The recent targets file is damaged ({error}), so nothing is listed; "
            "the next folder or repository opened replaces it.",
        )
    except PrivateStorageError as error:
        raise RecentTargetsError(str(error)) from error
    except OSError as error:
        raise RecentTargetsError(
            f"the recent targets file could not be read ({_why(error)})"
        ) from error


# ── Writing ────────────────────────────────────────────────────────


def _why(error: OSError) -> str:
    return os.strerror(error.errno) if error.errno is not None else "a file system error"


def _serialize(targets: list[RecentTarget]) -> bytes:
    """The file for *targets*, dropping the oldest of a list too large to read back.

    What is written is read back before it is returned, so a root YAML would not hand
    back unchanged is found here and never published.
    """

    dumper = getattr(yaml, "CSafeDumper", yaml.SafeDumper)
    while True:
        document = {"format": FORMAT, "targets": [target.as_json() for target in targets]}
        text = yaml.dump(
            document,
            Dumper=dumper,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            # One line to an entry's root, however long: a folded path is hard to read.
            width=2 * MAX_ROOT_BYTES + 64,
        )
        payload = (_HEADER + text).encode("utf-8")
        if len(payload) <= MAX_STORE_BYTES or not targets:
            break
        targets = targets[:-1]
    if _parse(payload) != tuple(targets):
        raise RecentTargetsError("the recent targets list does not survive being written")
    return payload


@contextlib.contextmanager
def _writing(home: Path) -> Generator[None]:
    """Hold the list's writer lock, waiting at most :data:`LOCK_WAIT_S` for another's.

    The lock file is opened read-only, which is enough for ``flock`` and lets a lock
    file that became shared be tightened rather than refused. Closing the descriptor
    releases the lock, and so does the kernel when a holder dies.
    """

    if fcntl is None:
        raise RecentTargetsError("this platform has no file locks for the recent targets list")
    fd = open_private_file(home, LOCK_FILE, os.O_RDONLY | os.O_CREAT)
    try:
        deadline = time.monotonic() + LOCK_WAIT_S
        delay = _LOCK_RETRY_FIRST_S
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise RecentTargetsError(
                        "another Metabrowser process has held the recent targets list "
                        f"for {LOCK_WAIT_S:g} seconds"
                    ) from error
                time.sleep(delay)
                delay = min(delay * 2, _LOCK_RETRY_MAX_S)
            except OSError as error:
                if error.errno in _UNSUPPORTED_LOCK_ERRNOS:
                    raise RecentTargetsError(
                        "the configuration directory's file system has no file locks, "
                        "which the recent targets list needs"
                    ) from error
                raise
        yield
    finally:
        os.close(fd)


type _Change = Callable[[tuple[RecentTarget, ...]], tuple[RecentTarget, ...] | None]
"""The new list for the stored one, or ``None`` to write nothing."""


def _change(directory: Path | None, change: _Change) -> tuple[RecentTarget, ...]:
    """Apply *change* to the stored list under the writer lock; return what was stored.

    A damaged file is treated as an empty list, which the write then replaces. A file
    from a newer release raises :class:`NewerFormatError` and is not written.
    """

    home = configuration_directory() if directory is None else directory
    try:
        ensure_storage_root(home)
        with _writing(home):
            try:
                before = _load(home, shared="repair")
            except _Damaged as error:
                log.warning("replacing the recent targets file, which is damaged: %s", error)
                before = ()
            after = change(before)
            if after is not None:
                write_private_file_atomic(home, STORE_FILE, _serialize(list(after)))
            return before
    except PrivateStorageError as error:
        raise RecentTargetsError(str(error)) from error
    except OSError as error:
        raise RecentTargetsError(
            f"the recent targets file could not be written ({_why(error)})"
        ) from error


def recording_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Whether this process records what it opens: true unless :data:`RECORD_ENV` says no."""

    variables = os.environ if environ is None else environ
    return variables.get(RECORD_ENV, "").strip().lower() not in _OFF


def now() -> str:
    """The current time as an entry spells it."""

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(
    mode: TargetMode, root: str, *, directory: Path | None = None, opened_at: str | None = None
) -> RecentTarget:
    """Put *root*, opened in *mode*, at the front of the list; return its entry.

    An entry the list already holds for the root moves to the front with the new time,
    and the oldest entry past :data:`MAX_RECENT_TARGETS` falls off. *root* is a folder's
    :func:`folder_root` or a source's normalized address; one the list cannot hold raises
    :class:`UnrecordableRootError`, and a list that cannot be written raises
    :class:`RecentTargetsError`.
    """

    if (reason := _checked_root(mode, root)) is not None:
        raise UnrecordableRootError(reason)
    target = RecentTarget(mode, root, now() if opened_at is None else opened_at)

    def to_front(before: tuple[RecentTarget, ...]) -> tuple[RecentTarget, ...]:
        others = (entry for entry in before if entry.key != target.key)
        return (target, *others)[:MAX_RECENT_TARGETS]

    _change(directory, to_front)
    return target


def forget(roots: frozenset[tuple[str, str]], *, directory: Path | None = None) -> int:
    """Remove the entries whose ``(mode, root)`` is in *roots*; return how many there were.

    A list that holds none of them is not written.
    """

    def without(before: tuple[RecentTarget, ...]) -> tuple[RecentTarget, ...] | None:
        after = tuple(entry for entry in before if entry.key not in roots)
        return None if len(after) == len(before) else after

    before = _change(directory, without)
    return sum(1 for entry in before if entry.key in roots)


def clear(*, directory: Path | None = None) -> int:
    """Empty the list; return how many entries it held. An empty list is not written."""

    return len(_change(directory, lambda before: () if before else None))


def record_quietly(mode: TargetMode, root: str) -> None:
    """Record a root a server is about to serve, and never raise.

    A failure is logged once as a warning that says what to do, without the root or a
    path, and the server starts regardless. With :data:`RECORD_ENV` off, nothing is
    recorded and nothing is read or written.
    """

    if not recording_enabled():
        log.debug("not recording a recent target: %s is off", RECORD_ENV)
        return
    try:
        record(mode, root)
    except UnrecordableRootError as error:
        log.info("this root is not recorded as a recent target: %s", error)
    except RecentTargetsError as error:
        log.warning("this root is not recorded as a recent target: %s", error)
    except Exception:
        log.warning("this root is not recorded as a recent target", exc_info=True)


__all__ = [
    "FORMAT",
    "FORMAT_HISTORY",
    "LOCK_FILE",
    "LOCK_WAIT_S",
    "MAX_RECENT_TARGETS",
    "MAX_ROOT_BYTES",
    "MAX_STORE_BYTES",
    "MIGRATIONS",
    "MODES",
    "RECORD_ENV",
    "STORE_FILE",
    "Listing",
    "NewerFormatError",
    "RecentTarget",
    "RecentTargetsError",
    "TargetMode",
    "UnrecordableRootError",
    "clear",
    "folder_root",
    "forget",
    "format_number",
    "now",
    "read",
    "record",
    "recording_enabled",
    "record_quietly",
]
