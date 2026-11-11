"""What the served subject is called: a short name, a full name, and what kind of place it is.

Every window and tab of Metabrowser used to be titled "Metabrowser", so two servers could
not be told apart. :class:`RootIdentity` names the subject this server serves.
``GET /api/identity`` answers it, the shell's ``<title>`` is its ``title``, and a native
window titles itself from the same route, so a browser tab, an app window, and
``metab <root> --api /api/identity`` cannot disagree.

Each subject the source session can hold (:mod:`metabrowser.source`) is named this way:

- **A local folder** (``attached_filesystem``): ``metab <dir>``, and ``metab <file>``,
  which serves the file's folder, so its identity is that folder's. ``kind`` is
  ``folder``. ``short_name`` is the folder's own name, ``/`` for the filesystem root and
  ``~`` for the home folder itself; ``full_name`` is its absolute path with the home
  folder as ``~``. A checkout is a folder like any other, and a pull-request page a
  checkout's Pulls tab opens (``/pull/<n>``) is a view of that folder, not another
  subject, so it keeps the folder's name. A ``metab --remote`` folder is named by the
  server running on the remote host, so its ``~`` is that host's home folder.
- **A cached Git mirror** (``git_revision``): ``metab <git-url>``, a pinned revision of a
  mirror in the repository cache. ``kind`` is ``mirror``. ``short_name`` is the
  repository's name, as a checkout would be called (``MirrorDisplay.name``).
  ``full_name`` is the origin abbreviated by :func:`abbreviate_origin`, never the cache
  path, then what the pin is: ``@<ref>`` for a branch or tag, by the name the origin
  knows it by, as in ``github.com/jlevy/tbd@main``, and ``@<the commit's first 12 hex
  digits>`` for a commit with no ref.
- **A pull request's head** is a mirror pinned to ``refs/pull/<n>/head``, which a
  pull-request URL serves and a pin switch onto its head serves again. It is named as
  GitHub writes a pull request: ``short_name`` ``tbd #123`` and ``full_name``
  ``github.com/jlevy/tbd#123``. A pull-request page of a mirror pinned elsewhere is a
  view, like a checkout's, and keeps the pin's name.
- **An overlay mirror** (``--checkout``), which borrows objects from a checkout, is a
  mirror of its origin like any other and is named by that origin, not by the checkout.
- **A pin with no mirror** has no origin to take a name from, and is named as the
  navigation heading names it: by its ref's short name, or by its short commit when it
  has no ref. Every CLI mode serves a pin with its mirror, so only an in-process caller
  meets this.

Names are display text, never paths to open. A folder's name and path are the file
system's, and a mirror's origin and refs are what its owner chose, so every name passes
through :func:`~metabrowser.invisible_chars.display_segment`, as ``MirrorDisplay``'s
fields do: a control, format, or invisible character, and bytes that are not UTF-8,
become U+FFFD.

A page changes subject only by loading again: the ref selector, the freshness row's
offer, a pull-request page's switch to its head, and a diff's View file all navigate or
reload after ``POST /api/source/pin``. So the server-rendered ``<title>`` is current for
the life of a document, and no page fetches this route.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Final, Literal, TypedDict
from urllib.parse import unquote_to_bytes

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from metabrowser.invisible_chars import display_segment
from metabrowser.mirror_refresh import (
    MirrorDisplay,
    MirrorSession,
    mirror_session,
    pull_head_number,
)
from metabrowser.paths_safe import tilde_path
from metabrowser.source import (
    UnsupportedSourceCapabilityError,
    as_git_revision_subject,
    get_source_session,
    session_filesystem_root,
    unsupported_source_payload,
)

APP_NAME: Final = "Metabrowser"
# U+2022 BULLET between single spaces, as in ``fdu • Metabrowser``.
TITLE_SEPARATOR: Final = " \u2022 "
# How much of a commit ID a commit pin's full name shows, as the navigation heading does.
SHORT_COMMIT_CHARS: Final = 12

type IdentityKind = Literal["folder", "mirror"]

KIND_LABELS: Final[dict[IdentityKind, str]] = {
    "folder": "Local folder",
    "mirror": "Cached mirror",
}

# ``scheme://`` at the start of an origin.
_SCHEME: Final = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://")
# The scp-like form, ``[user@]host:path``; a bracketed IPv6 host keeps its colons.
_SCP: Final = re.compile(r"(?:[^@/:\[\]]+@)?(\[[^\]/]*\]|[^@/:\[\]]+):(.*)", re.DOTALL)
_FILE_SCHEME: Final = "file://"
_WWW: Final = "www."
_GIT_SUFFIX: Final = ".git"
# What is left of a last segment that is no name once ``.git`` is taken off.
_NO_NAME: Final = frozenset({"", ".", ".."})


class RootIdentity(TypedDict):
    """The envelope of ``GET /api/identity``.

    ``short_name`` is what a window is called, ``full_name`` the longer name that tells
    two of the same short name apart, and ``kind`` whether the subject is a local
    ``folder`` or a cached ``mirror``, with ``kind_label`` the words for it.
    ``title`` is ``<short_name> • Metabrowser``, the shell's ``<title>``.
    """

    short_name: str
    full_name: str
    kind: IdentityKind
    kind_label: str
    title: str


def _shown(text: str) -> str:
    """*text* as safe display text, keeping the bytes an undecodable file name carried."""

    return display_segment(text.encode("utf-8", "surrogateescape"))


def _identity(short_name: str, full_name: str, kind: IdentityKind) -> RootIdentity:
    short = _shown(short_name)
    return RootIdentity(
        short_name=short,
        full_name=_shown(full_name),
        kind=kind,
        kind_label=KIND_LABELS[kind],
        title=f"{short}{TITLE_SEPARATOR}{APP_NAME}",
    )


def user_home() -> Path | None:
    """The home folder with symbolic links resolved, or ``None`` when there is none.

    Resolved because a served root is, so a root under a home reached through a link is
    still shown under ``~``.
    """

    try:
        return Path.home().resolve()
    except (OSError, RuntimeError):
        return None


def folder_identity(root: Path, *, home: Path | None) -> RootIdentity:
    """What a served folder is called. *root* and *home* are resolved, as a served root is."""

    if home is not None and root == home:
        short_name = "~"
    elif root.parent == root:
        # The file system's root has no name of its own: ``/``.
        short_name = str(root)
    else:
        short_name = root.name
    full_name = tilde_path(root, home) if home is not None else str(root)
    return _identity(short_name, full_name, "folder")


def _local_path(spelled: str, *, home: Path | None, encoded: bool) -> str:
    """A ``file://`` origin's path or a local path, with the home folder as ``~``."""

    raw = unquote_to_bytes(spelled) if encoded else spelled.encode("utf-8", "surrogateescape")
    text = os.fsdecode(raw)
    if home is not None and text.startswith("/"):
        text = tilde_path(Path(text), home)
    return text


def _repository_path(path: str) -> list[str]:
    """A remote origin's path segments without a trailing ``/.git`` or ``.git`` suffix."""

    segments = [segment for segment in path.split("/") if segment]
    if segments and segments[-1] == _GIT_SUFFIX:
        segments.pop()
    elif segments and segments[-1].removesuffix(_GIT_SUFFIX) not in _NO_NAME:
        segments[-1] = segments[-1].removesuffix(_GIT_SUFFIX)
    return segments


def abbreviate_origin(origin: str, *, home: Path | None) -> str:
    """*origin* as a full name shows it: host and path, without what every origin repeats.

    A remote origin drops its scheme, its user, a leading ``www.`` of its host, and a
    trailing ``.git``, and the scp-like ``git@host:owner/repo`` reads as
    ``host/owner/repo``, so ``https://github.com/jlevy/tbd.git``,
    ``ssh://git@github.com/jlevy/tbd``, and ``git@github.com:jlevy/tbd.git`` are all
    ``github.com/jlevy/tbd``. A port other than the default stays, since it names
    another server. A ``file://`` origin, or a local path, is its path with the home
    folder as ``~``, kept whole because it names a place on this machine.

    *origin* is what ``MirrorDisplay.origin`` shows, which for a ``file://`` origin under
    the home folder already reads ``file://~/…``. A percent-escape is decoded, so a name
    reads as it is written, and the result is display text: see :func:`_shown`.
    """

    if origin[: len(_FILE_SCHEME)].lower() == _FILE_SCHEME:
        return _shown(_local_path(origin[len(_FILE_SCHEME) :], home=home, encoded=True))
    if origin.startswith(("/", "~")):
        return _shown(_local_path(origin, home=home, encoded=False))
    scheme = _SCHEME.match(origin)
    if scheme is not None:
        authority, _, path = origin[scheme.end() :].partition("/")
        host = authority.rpartition("@")[2]
    else:
        scp = _SCP.fullmatch(origin)
        if scp is None:
            return _shown(origin)
        host, path = scp.group(1), scp.group(2)
    host = host.lower()
    if host.startswith(_WWW) and len(host) > len(_WWW):
        host = host.removeprefix(_WWW)
    shown = "/".join([host, *_repository_path(path)])
    return display_segment(unquote_to_bytes(shown))


def mirror_identity(
    *, display: MirrorDisplay | None, ref: str | None, commit: str, home: Path | None
) -> RootIdentity:
    """What a pinned revision is called, from its mirror's *display* and what it is pinned to.

    *ref* is the store ref the pin was resolved from, ``None`` for a commit pinned by its
    ID, and *commit* the full commit ID every read uses.
    """

    # Imported where a pin is named, as ``source_status`` does: the revision tree source
    # is a pin's module, and a folder's server never loads it.
    from metabrowser.git.tree_source import ref_short_name

    short_commit = commit[:SHORT_COMMIT_CHARS]
    ref_name = ref_short_name(ref)
    pull = pull_head_number(ref)
    if display is None:
        label = ref_name if ref_name is not None else short_commit
        return _identity(label, label if ref_name is None else f"{label}@{short_commit}", "mirror")
    origin = abbreviate_origin(display.origin, home=home)
    if pull is not None:
        return _identity(f"{display.name} #{pull}", f"{origin}#{pull}", "mirror")
    pinned = ref_name if ref_name is not None else short_commit
    return _identity(display.name, f"{origin}@{pinned}", "mirror")


def root_identity(mirror: MirrorSession | None) -> RootIdentity:
    """What the active session's subject is called. Runs no Git and reads no store.

    *mirror* is the served mirror's session, which names a pin's repository and origin.
    A subject that is neither a pin nor a folder raises
    :class:`~metabrowser.source.UnsupportedSourceCapabilityError`; none exists today.
    """

    pin = as_git_revision_subject(get_source_session().subject)
    if pin is not None:
        return mirror_identity(
            display=mirror.mirror.display if mirror is not None else None,
            ref=pin.ref,
            commit=pin.commit_oid,
            home=user_home(),
        )
    return folder_identity(session_filesystem_root(), home=user_home())


async def api_identity(request: Request) -> JSONResponse:
    """``GET /api/identity`` -- what this server's subject is called, as a window titles it."""

    try:
        identity = root_identity(mirror_session(request.app))
    except UnsupportedSourceCapabilityError as exc:
        return JSONResponse(unsupported_source_payload(exc), status_code=409)
    return JSONResponse(dict(identity))


IDENTITY_ROUTES = [Route("/api/identity", api_identity)]


__all__ = [
    "APP_NAME",
    "IDENTITY_ROUTES",
    "KIND_LABELS",
    "SHORT_COMMIT_CHARS",
    "TITLE_SEPARATOR",
    "IdentityKind",
    "RootIdentity",
    "abbreviate_origin",
    "api_identity",
    "folder_identity",
    "mirror_identity",
    "root_identity",
    "user_home",
]
