"""A checkout that lends an overlay store its objects, read through bounded files alone.

An overlay store is a repository store whose ``objects/info/alternates`` names a checkout
the reader named with ``--checkout``, so it holds only what that checkout lacks. Nothing
here starts Git in the checkout or writes to it: its configuration, its pointer files,
and its remote-tracking refs are files this module reads, each through
:func:`~metabrowser.repository_context.read_bounded_text`, which refuses anything but a
regular file. Git reads the borrowed objects as the store's own, under the store's
configuration, and never the checkout's.

The rules of what may lend, and why the store's refs are never seeded from it, are in
``docs/project/architecture/arch-repository-sources-and-provider-mirrors.md``. A lender
is the reader's own word: a checkout found by walking up from the working directory is
offered as a suggestion and never borrowed from, because a directory the reader merely
stands in can be made to pass as one.

:func:`check_lender` decides what a named checkout may do: it lends, or it says why it
cannot and the source is cloned instead (:class:`LenderRefusal`), or it is not a checkout
of this repository at all and the command stops (:class:`CheckoutRefusedError`).
:func:`negotiation_tips` reads the commits a fetch tells the origin it has. It is
recomputed before each fetch, since a tip the checkout has since lost makes Git refuse.
"""

from __future__ import annotations

import asyncio
import configparser
import logging
import os
import re
import secrets
import shlex
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from metabrowser.cache.atomic import read_record
from metabrowser.cache.identity import ObjectFormat
from metabrowser.cache.paths import store_record
from metabrowser.cache.providers import url_reducers
from metabrowser.cache.records import REPOSITORY_STORE_CONTRACT_ID, RepositoryStore, StoreLender
from metabrowser.cache.urls import GitSource, classify_root_argument
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    RepositoryStoreTarget,
    run_git,
)
from metabrowser.git.shallow import MAX_BOUNDARY_BYTES
from metabrowser.git.tree_source import display_segment
from metabrowser.git.wire import is_full_revision
from metabrowser.paths_safe import tilde_path
from metabrowser.repository_context import (
    MAX_GIT_CONFIG_BYTES,
    MAX_GIT_POINTER_BYTES,
    MAX_PACKED_REFS_BYTES,
    find_git_root,
    read_bounded_text,
    read_regular_file_head,
    resolve_common_dir,
    resolve_git_dir,
)

log = logging.getLogger(__name__)

# The most ``--negotiation-tip`` arguments one fetch passes, the default branch first. Git
# takes them only on its command line. Measured 2026-11-02 on macOS with Git 2.50.1, at a
# load average of 12, on a repository of 40,000 remote-tracking refs: reading them from
# files took 37 ms and filtering 4,096 through the store's batch check 64 ms, and a fetch
# ran in 1.4 s with no tips, 1.5 s with 4,096 (242 KB of arguments), and 1.8 s with 14,000,
# while 16,384 failed to start with ``Argument list too long`` at an ARG_MAX of 1 MiB. So the
# bound sits well below where the platform refuses, with room for a long environment, and
# 12 times above the 327 tips of the measured 1.2 GB repository, whose read took 9 ms. Past
# it a fetch still works and may ask for more: it gives the origin fewer places to stop.
MAX_NEGOTIATION_TIPS: Final = 4096
# Loose refs looked at under ``refs/remotes/<remote>/``, and how far down. A checkout's loose
# refs are its recent fetches, and ``git pack-refs`` collects the rest: the measured one has
# 39. A planted tree is not walked further.
_MAX_LOOSE_REFS: Final = 20_000
_MAX_LOOSE_DEPTH: Final = 32
# Directory entries looked at for a ``.promisor`` pack; the measured checkout has 142. A
# partial clone's configuration says so first, and past this bound it is taken at its word.
_MAX_PACK_ENTRIES: Final = 65_536
# Remotes a refusal lists; a checkout with more has a reader who knows them.
_MAX_REMOTES_NAMED: Final = 8
_CREDENTIALS: Final = re.compile(r"^(https?://)[^/@]*@", re.IGNORECASE)
_REMOTE_SECTION: Final = re.compile(r'^remote\s+"(.*)"$', re.IGNORECASE | re.DOTALL)
_REMOTE_NAME: Final = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._/-]{0,254}$")

type LenderRefusalCode = Literal[
    "partial_clone",
    "own_alternates",
    "object_format",
    "objects_unreadable",
    "boundary_unreadable",
    "path_not_recordable",
]


class CheckoutRefusedError(Exception):
    """The path named is not a checkout of this repository. ``str()`` is for the reader."""


class LenderGoneError(Exception):
    """The objects directory a store borrows from is not there. A fetch cannot run."""


@dataclass(frozen=True, slots=True)
class LenderRefusal:
    """Why a checkout of the right repository cannot lend. The source is cloned instead."""

    code: LenderRefusalCode
    message: str


@dataclass(frozen=True, slots=True)
class Lender:
    """A checkout that passed :func:`check_lender`, and what a store records of it."""

    common_dir: Path
    root: Path
    remote: str
    object_format: ObjectFormat

    @property
    def record(self) -> StoreLender:
        return StoreLender(
            objects=str(self.common_dir / "objects"), checkout=str(self.root), remote=self.remote
        )


def lender_boundary_path(lender: StoreLender) -> Path:
    """The lender's ``shallow`` file, beside the objects it borrows."""

    return Path(lender.objects).parent / "shallow"


def show_path(path: Path | str) -> str:
    """*path* as a person would type it: the home directory as ``~``, no control character."""

    candidate = Path(path)
    try:
        shown = tilde_path(candidate, Path.home())
    except (OSError, RuntimeError):
        shown = str(candidate)
    return display_segment(shown.encode("utf-8", "surrogateescape"))


def _shell_word(shown: str) -> str:
    """*shown* quoted for a command a reader may paste; a leading ``~/`` keeps expanding."""

    if shown == "~" or shown.startswith("~/"):
        return "~" + (("/" + shlex.quote(shown[2:])) if shown != "~" else "")
    return shlex.quote(shown)


def checkout_command(source_url: str, checkout: Path | str) -> str:
    """The command that serves *source_url* borrowing from *checkout*, ready to paste."""

    return f"metab {shlex.quote(source_url)} --checkout {_shell_word(show_path(checkout))}"


def _common_dir_of(root: Path) -> Path | None:
    """The directory holding the objects of the checkout at *root*, or ``None``.

    A checkout has ``.git``, a directory or for a linked worktree a file naming one, and
    that directory's ``commondir`` file names where its objects are. A path that is itself
    a Git directory, such as a bare clone, is taken as it is.
    """

    try:
        if os.path.lexists(root / ".git"):
            git_dir = resolve_git_dir(root)
        elif read_bounded_text(root / "HEAD", MAX_GIT_POINTER_BYTES) is not None:
            git_dir = root
        else:
            return None
        return None if git_dir is None else resolve_common_dir(git_dir)
    except (OSError, RuntimeError):
        # A symbolic link that loops, as a planted ``.git`` can be.
        return None


def _read_config(common_dir: Path) -> configparser.ConfigParser | None:
    """The checkout's own configuration file, as data; never Git's reading of it.

    Lines are stripped first, because the parser reads a more indented line as a
    continuation of the key above it, which would hide a setting. ``[include]`` is not
    followed: what decides anything here is also on disk, as a ``.promisor`` pack.
    """

    source = read_bounded_text(common_dir / "config", MAX_GIT_CONFIG_BYTES)
    if source is None:
        return None
    parser = configparser.ConfigParser(
        interpolation=None, strict=False, allow_no_value=True, delimiters=("=",)
    )
    try:
        parser.read_string("\n".join(line.strip() for line in source.splitlines()))
    except (configparser.Error, ValueError):
        return None
    return parser


def _remotes(parser: configparser.ConfigParser) -> list[tuple[str, str]]:
    """Each ``remote.<name>.url`` with a name usable as a ref path, ``origin`` first."""

    found: list[tuple[str, str]] = []
    for section in parser.sections():
        matched = _REMOTE_SECTION.match(section)
        if matched is None:
            continue
        url = parser.get(section, "url", fallback=None)
        name = matched.group(1)
        if url and _REMOTE_NAME.fullmatch(name) and ".." not in name:
            found.append((name, url.strip().strip('"')))
    return sorted(found, key=lambda pair: (pair[0] != "origin", pair[0]))


def _without_credentials(url: str) -> str:
    return _CREDENTIALS.sub(r"\1", url)


def _identity(url: str) -> GitSource | None:
    """The source a remote's URL names in the same grammar as the command line's.

    So every spelling a provider claims, ``git@github.com:o/r.git`` among them, is one
    identity. A URL holding credentials is compared without them.
    """

    classified = classify_root_argument(_without_credentials(url), reducers=url_reducers())
    return classified if isinstance(classified, GitSource) else None


def _same_repository(remote: GitSource, source: GitSource) -> bool:
    if remote.transport != source.transport:
        return False
    # GitHub compares owners and names without regard to case. A file:// path is the
    # file system's, and two of them can differ by case alone.
    if source.transport == "file":
        return remote.normalized == source.normalized
    return remote.normalized.lower() == source.normalized.lower()


def _matching_remote(remotes: list[tuple[str, str]], source: GitSource) -> str | None:
    for name, url in remotes:
        identity = _identity(url)
        if identity is not None and _same_repository(identity, source):
            return name
    return None


def _describe_remotes(remotes: list[tuple[str, str]]) -> str:
    shown: list[str] = []
    for name, url in remotes[:_MAX_REMOTES_NAMED]:
        identity = _identity(url)
        address = identity.normalized if identity is not None else _without_credentials(url)
        shown.append(f"{name} is {display_segment(address.encode('utf-8', 'surrogateescape'))}")
    return "; ".join(shown) if shown else "it has no remote"


def _partial_clone(parser: configparser.ConfigParser, common_dir: Path) -> bool:
    if parser.get("extensions", "partialclone", fallback=None):
        return True
    for section in parser.sections():
        if _REMOTE_SECTION.match(section) and (
            (parser.get(section, "promisor", fallback="") or "").strip().lower()
            in {"true", "yes", "on", "1"}
        ):
            return True
    try:
        with os.scandir(common_dir / "objects" / "pack") as entries:
            for count, entry in enumerate(entries):
                if count >= _MAX_PACK_ENTRIES:
                    return False
                if entry.name.endswith(".promisor"):
                    return True
    except OSError:
        return False
    return False


def _object_format(parser: configparser.ConfigParser) -> str:
    return (parser.get("extensions", "objectformat", fallback="sha1") or "sha1").strip().lower()


def _objects_readable(objects: Path) -> bool:
    try:
        status = os.stat(objects)
    except OSError:
        return False
    return (
        stat.S_ISDIR(status.st_mode)
        and status.st_uid == os.geteuid()
        and os.access(objects, os.R_OK | os.X_OK)
    )


def _boundary_is_plain(common_dir: Path) -> bool:
    """Whether ``shallow`` is absent or a regular file: a FIFO would block every Git read."""

    try:
        return stat.S_ISREG(os.stat(common_dir / "shallow").st_mode)
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _recordable(path: Path) -> bool:
    """Whether *path* can be a line of the alternates file and a record's text."""

    text = str(path)
    if len(text) > 4000 or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text):
        return False
    try:
        text.encode("utf-8")
    except UnicodeError:
        return False
    return True


def check_lender(named: Path, source: GitSource) -> Lender | LenderRefusal:
    """What the checkout the reader named at *named* may do for *source*.

    Raises :class:`CheckoutRefusedError` when it is no checkout of the repository. Its
    object format is compared with the origin's only once the origin has answered, by
    :func:`object_format_refusal`. Blocking and bounded; run it off the event loop.
    """

    try:
        root = named.expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        raise CheckoutRefusedError(f"--checkout {show_path(named)} cannot be read") from exc
    shown = show_path(root)
    common_dir = _common_dir_of(root)
    if common_dir is None:
        raise CheckoutRefusedError(
            f"--checkout {shown} is not a Git checkout: it has no .git and is no Git directory"
        )
    parser = _read_config(common_dir)
    if parser is None:
        raise CheckoutRefusedError(
            f"--checkout {shown}: its Git configuration could not be read, so which repository "
            "it holds is unknown"
        )
    remotes = _remotes(parser)
    remote = _matching_remote(remotes, source)
    if remote is None:
        raise CheckoutRefusedError(
            f"--checkout {shown} is not a checkout of {source.normalized}: "
            f"{_describe_remotes(remotes)}"
        )
    objects = common_dir / "objects"
    refusal: LenderRefusal | None = None
    if _partial_clone(parser, common_dir):
        refusal = LenderRefusal(
            "partial_clone", "the checkout is a partial clone, which cannot be borrowed from"
        )
    elif os.path.lexists(objects / "info" / "alternates"):
        refusal = LenderRefusal("own_alternates", "the checkout borrows objects itself")
    elif not _objects_readable(objects):
        refusal = LenderRefusal("objects_unreadable", "the checkout's objects could not be read")
    elif not _boundary_is_plain(common_dir):
        refusal = LenderRefusal(
            "boundary_unreadable", "the checkout's shallow file is not a regular file"
        )
    elif not (_recordable(objects) and _recordable(common_dir)):
        refusal = LenderRefusal(
            "path_not_recordable", "the checkout's path holds characters Git cannot borrow through"
        )
    if refusal is not None:
        return refusal
    object_format = _object_format(parser)
    if object_format not in {"sha1", "sha256"}:
        return LenderRefusal(
            "object_format", "the checkout's object format is not one Metabrowser reads"
        )
    return Lender(
        common_dir=common_dir,
        # What every worktree of the repository shares: a linked worktree can be removed
        # while the objects stay, and the name shown should outlast it.
        root=common_dir.parent if common_dir.name == ".git" else common_dir,
        remote=remote,
        object_format="sha256" if object_format == "sha256" else "sha1",
    )


def object_format_refusal(lender: Lender, advertised: ObjectFormat) -> LenderRefusal | None:
    """A refusal when the checkout's objects cannot be the origin's, whose format is known now."""

    if lender.object_format == advertised:
        return None
    return LenderRefusal(
        "object_format",
        f"the checkout's objects are {lender.object_format} and the origin's are {advertised}",
    )


def suggested_checkout(source: GitSource, working_directory: Path) -> Path | None:
    """The checkout of *source* enclosing *working_directory*, to suggest and never to use.

    The nearest ``.git`` decides, as Git's own discovery does. A directory the reader
    merely stands in can be made to pass for this, which is exactly why it only earns a
    line of text.
    """

    try:
        start = working_directory.resolve()
    except (OSError, RuntimeError):
        return None
    try:
        root = find_git_root(start)
    except (OSError, RuntimeError):
        return None
    if root is None:
        return None
    common_dir = _common_dir_of(root)
    parser = None if common_dir is None else _read_config(common_dir)
    if parser is None or _matching_remote(_remotes(parser), source) is None:
        return None
    return root


def _write_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(6)}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def attach_lender(git_dir: Path, lender: StoreLender) -> None:
    """Make the store at *git_dir* borrow from *lender*: the alternates file and the boundary.

    ``shallow`` is a symbolic link to the checkout's, so the store's boundary is the
    checkout's current one and follows it when the checkout deepens. Where the checkout is
    not shallow the link dangles, and Git treats the store as not shallow. The link is
    replaced by :func:`own_boundary` before any command that could write through it.
    """

    _write_atomic(git_dir / "objects" / "info" / "alternates", lender.objects + "\n")
    boundary = git_dir / "shallow"
    temporary = boundary.with_name(f".shallow.{secrets.token_hex(6)}")
    temporary.symlink_to(lender_boundary_path(lender))
    os.replace(temporary, boundary)


def rebind_lender(git_dir: Path, lender: StoreLender) -> None:
    """Point a store whose lender has gone at *lender*, keeping a boundary it owns.

    A boundary the store owns may lack commits at which the new checkout's history stops,
    and a walk across one would die on a missing parent, so it gains them. A boundary only
    cuts the graph, and a cut never makes a merge base certain and wrong.
    """

    boundary = git_dir / "shallow"
    if boundary.is_symlink() or not boundary.exists():
        attach_lender(git_dir, lender)
        return
    owned = read_bounded_text(boundary, MAX_BOUNDARY_BYTES) or ""
    lent = read_bounded_text(lender_boundary_path(lender), MAX_BOUNDARY_BYTES) or ""
    _write_atomic(git_dir / "objects" / "info" / "alternates", lender.objects + "\n")
    _write_atomic(boundary, "".join(f"{oid}\n" for oid in sorted({*owned.split(), *lent.split()})))


def own_boundary(git_dir: Path) -> None:
    """Replace the store's link to the checkout's boundary by a file the store owns.

    Git writes ``shallow`` through a lock file beside it, and it locks the target of a
    symbolic link rather than the link: measured 2026-11-02 with Git 2.50.1, a
    ``fetch --deepen`` with the link in place left the store's link as it was and replaced
    the *checkout's* file. Nothing may write there, so this runs under the fetch lock
    before any command that writes the boundary. A dangling link is removed, since Git
    would create its lock file at the target. A link that cannot be copied raises, and
    the command does not run. Afterwards the store's boundary is a subset of what the
    checkout has at most, which is still only a cut of the graph.
    """

    boundary = git_dir / "shallow"
    if not boundary.is_symlink():
        return
    if not os.path.exists(boundary):
        boundary.unlink()
        return
    text = read_bounded_text(boundary, MAX_BOUNDARY_BYTES)
    if text is None:
        raise OSError("the checkout's shallow file could not be copied")
    _write_atomic(boundary, text)


def _packed_remote_refs(common_dir: Path, prefix: str) -> dict[str, str]:
    """The refs under *prefix* in ``packed-refs``, up to the bound on what is read of it.

    The part that fits is used, since a tip is only a hint about what the origin need not
    send: a checkout with an enormous file gives fewer hints rather than none.
    """

    data = read_regular_file_head(common_dir / "packed-refs", MAX_PACKED_REFS_BYTES)
    if data is None:
        return {}
    refs: dict[str, str] = {}
    for line in data.decode("utf-8", "surrogateescape").splitlines():
        if not line or line.startswith(("#", "^")):
            continue
        oid, separator, ref = line.partition(" ")
        if separator and ref.startswith(prefix) and is_full_revision(oid):
            refs[ref] = oid
    return refs


def _loose_remote_refs(common_dir: Path, prefix: str) -> dict[str, str]:
    """The refs under *prefix* as loose files; a symbolic ref such as ``HEAD`` names no tip."""

    refs: dict[str, str] = {}
    start = common_dir / prefix
    base_depth = len(start.parts)
    seen = 0
    for directory, subdirectories, files in os.walk(start, followlinks=False):
        if len(Path(directory).parts) - base_depth >= _MAX_LOOSE_DEPTH:
            subdirectories.clear()
        for name in files:
            seen += 1
            if seen > _MAX_LOOSE_REFS:
                return refs
            path = Path(directory) / name
            text = read_bounded_text(path, MAX_GIT_POINTER_BYTES)
            value = "" if text is None else text.strip()
            if is_full_revision(value):
                refs[path.relative_to(common_dir).as_posix()] = value
    return refs


def negotiation_tips(lender: StoreLender, *, preferred: str | None = None) -> tuple[str, ...]:
    """The commits the lender's remote-tracking refs name, at most :data:`MAX_NEGOTIATION_TIPS`.

    Only ``refs/remotes/<remote>/``, the commits of the origin the checkout has already
    fetched: its local branches never leave the machine, and a fork's own branches are
    no tips when the repository is its ``upstream``. Loose files override ``packed-refs``,
    as they do in Git. *preferred* is the origin's default branch, whose tip goes first so
    a long list that is cut keeps it. A checkout using reftable has neither file, and the
    answer is empty: the first fetch costs more, and nothing fails. Blocking and bounded.
    """

    common_dir = Path(lender.objects).parent
    prefix = f"refs/remotes/{lender.remote}/"
    refs = _packed_remote_refs(common_dir, prefix)
    refs.update(_loose_remote_refs(common_dir, prefix))
    head = prefix + "HEAD"
    refs.pop(head, None)
    ordered: list[str] = []
    if preferred is not None:
        first = refs.get(prefix + preferred)
        if first is not None:
            ordered.append(first)
    ordered.extend(oid for _ref, oid in sorted(refs.items()))
    return tuple(dict.fromkeys(ordered))[:MAX_NEGOTIATION_TIPS]


def read_alternates(git_dir: Path) -> str | None:
    """What the store's alternates file names: ``None`` when it has none.

    A file that cannot be read as text is reported as an empty name, which no record
    equals, rather than as no file.
    """

    path = git_dir / "objects" / "info" / "alternates"
    if not os.path.lexists(path):
        return None
    return (read_bounded_text(path, MAX_GIT_POINTER_BYTES) or "").strip()


def lender_present(lender: StoreLender) -> bool:
    """Whether the directory a store borrows from is there. One ``stat``."""

    return os.path.isdir(lender.objects)


def read_store_lender(home: Path, store_key: str) -> StoreLender | None:
    """What the store's record says it borrows from; ``None`` for a full store.

    Read for each fetch, so a repair by another process is seen. Blocking.
    """

    try:
        store = read_record(
            home, store_record(store_key, "store.yml"), REPOSITORY_STORE_CONTRACT_ID, shared="keep"
        )
    except FileNotFoundError:
        return None
    return store.lender if isinstance(store, RepositoryStore) else None


async def _object_kinds(target: RepositoryStoreTarget, oids: list[str]) -> list[tuple[str, str]]:
    """Each object ID with the type the store reads it as, or ``missing``, in one Git process."""

    out = await run_git(
        ["cat-file", "--batch-check=%(objectname) %(objecttype)"],
        target=target,
        policy=ACQUISITION_POLICY,
        stdin_bytes="".join(f"{oid}\n" for oid in oids).encode("ascii"),
    )
    kinds: list[tuple[str, str]] = []
    for line in out.decode("ascii", errors="replace").splitlines():
        oid, _, kind = line.partition(" ")
        kinds.append((oid, kind))
    return kinds


async def sweep_dangling_refs(target: RepositoryStoreTarget, lock_fd: int) -> tuple[str, ...]:
    """Delete every ref whose object the store cannot read; the names deleted, sorted.

    One dangling ref wedges every fetch, the refresh that would prune it included: Git's
    connectivity check dies on ``bad object``. A checkout that pruned a branch the origin
    deleted makes one by collecting its objects, so an overlay is swept before each fetch,
    holding the fetch lock (*lock_fd*). A ref the origin still has comes back with the
    fetch. Measured 2026-11-02: 0.12 s on a replica, 0.25 s at 1,632 refs.
    """

    listed = await run_git(
        ["for-each-ref", "--format=%(objectname) %(refname)"],
        target=target,
        policy=ACQUISITION_POLICY,
    )
    rows: list[tuple[str, str]] = []
    for line in listed.decode("utf-8", "surrogateescape").splitlines():
        oid, separator, ref = line.partition(" ")
        if separator:
            rows.append((oid, ref))
    if not rows:
        return ()
    missing = {
        oid
        for oid, kind in await _object_kinds(target, sorted({oid for oid, _ref in rows}))
        if kind == "missing"
    }
    dangling = sorted(ref for oid, ref in rows if oid in missing)
    if dangling:
        await run_git(
            ["update-ref", "--no-deref", "--stdin"],
            target=target,
            policy=ACQUISITION_POLICY,
            pass_fds=(lock_fd,),
            stdin_bytes="".join(f"delete {ref}\n" for ref in dangling).encode(
                "utf-8", "surrogateescape"
            ),
        )
    return tuple(dangling)


async def negotiation_tip_args(
    target: RepositoryStoreTarget, lender: StoreLender, *, preferred: str | None = None
) -> tuple[str, ...]:
    """``--negotiation-tip=<oid>`` for each lender tip the store reads as a commit.

    Without any, Git offers the store's own refs and the origin sends more; with one the
    store cannot read, Git refuses (``the object ... does not exist``). So they are
    filtered through the store's own batch check, each time.
    """

    tips = await asyncio.to_thread(negotiation_tips, lender, preferred=preferred)
    if not tips:
        return ()
    kinds = dict(await _object_kinds(target, list(tips)))
    return tuple(f"--negotiation-tip={oid}" for oid in tips if kinds.get(oid) == "commit")


async def prepare_overlay_fetch(
    target: RepositoryStoreTarget, lender: StoreLender, lock_fd: int, *, preferred: str | None
) -> tuple[str, ...]:
    """What every fetch into an overlay does first, under the fetch lock (*lock_fd*).

    Refuses a lender that has gone, since no fetch can succeed then; sweeps; returns the
    arguments that keep the fetch to what the checkout lacks. Raises
    :class:`LenderGoneError`, or a ``GitError`` when the store cannot be read.
    """

    if not await asyncio.to_thread(lender_present, lender):
        raise LenderGoneError
    swept = await sweep_dangling_refs(target, lock_fd)
    if swept:
        log.debug("swept refs whose objects the checkout no longer has: %s", swept[:8])
    return await negotiation_tip_args(target, lender, preferred=preferred)


__all__ = [
    "LenderGoneError",
    "lender_present",
    "negotiation_tip_args",
    "prepare_overlay_fetch",
    "read_alternates",
    "read_store_lender",
    "sweep_dangling_refs",
    "MAX_NEGOTIATION_TIPS",
    "CheckoutRefusedError",
    "Lender",
    "LenderRefusal",
    "LenderRefusalCode",
    "attach_lender",
    "check_lender",
    "checkout_command",
    "lender_boundary_path",
    "negotiation_tips",
    "object_format_refusal",
    "own_boundary",
    "rebind_lender",
    "show_path",
    "suggested_checkout",
]
