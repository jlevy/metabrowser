"""``metab ROOT --present``: hand a folder, a file, or a GitHub URL to the macOS app.

This is the command-line half of opening anything in the native app. It is a client
mode: it reads ROOT as every mode reads it, clones and fetches nothing, starts no server,
and gives the app what it needs through LaunchServices, which is how macOS opens a
document in an app (``open -b``). The app does the rest by running ``metab`` on what it
was given, as it does for a folder opened in Finder. A dry run loads nothing beyond what
``metab --version`` loads except this module, the property-list reader, and for a link
the URL grammar, which ``test_present_dry_run_loads_little_beyond_version`` in
``tests/test_plugin_public_api.py`` holds.

**Resolving.** :func:`resolve_target` reads ROOT with the ``--path`` it came with:

- a folder is ``folder``, rooted there, at ``/view/``; with ``--path`` naming a folder
  inside it, at that folder's address;
- a file, or a folder with ``--path`` naming a file, is ``file``, rooted at the folder
  ``metab`` would serve, at the file's address;
- a GitHub URL is ``repository``, ``tree``, ``file`` (a ``blob`` or raw URL),
  ``commit``, or ``pull_request``, rooted at the canonical repository URL, which never
  names a ref, because the app keys a session by its repository.

``page`` is the address a server of the root opens, or ``None`` where only the mirror
knows it, which a consumer reads as the server's entry page: the server the app starts
resolves the URL itself and opens the right address. :func:`_source_page` says which
links leave one reading.

``handoff`` is exactly what ``open -b <bundle id>`` is given after the identifier: the
folder; a file named alone, which the app places in the most specific folder it has open
that holds it, and otherwise opens in its own folder, the ``root`` reported; ROOT and
then the file ``--path`` names in it, so that the app opens the root the user named and
shows the file there; or the canonical web URL. A folder inside the root has none,
because the app opens every folder in a window of its own.

Anything else is a :class:`Refusal` with a stable code and a one-line message that
names the fix. ``--dry-run`` stops here and prints the target, which is how the app
checks what a user typed without parsing a URL itself.

**Delivering.** :func:`deliver` finds the app through LaunchServices, release first,
then the development build, or the one ``--app-bundle-id`` or :data:`BUNDLE_ID_ENV`
names, and sends the handoff with ``open -b``. Every handoff first passes
:func:`app_refusal`: the bundle LaunchServices names is installed at one of
:data:`APP_INSTALL_LOCATIONS`, is named :data:`APP_BUNDLE_NAME`, and declares
:data:`OPENS_URLS_KEY`, the marker of a Metabrowser build that takes everything this mode
sends. An app without the marker drops a URL while ``open`` still succeeds, an override
naming another app must not receive a file it would run, and a bundle registered
somewhere else, a build in a cloned repository among them, is not the app the user
installed.
``open`` returning 0 means LaunchServices took the handoff, not that a window shows it,
and the app cannot answer yet, so every report says ``confirmed: false``.
"""

from __future__ import annotations

import ctypes
import json
import os
import plistlib
import re
import shlex
import stat
import subprocess
import sys
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, NoReturn

import typer

from metabrowser.cli.exit_codes import (
    PRESENT_BLOCKED_EXIT_CODE,
    PRESENT_NO_APP_EXIT_CODE,
    PRESENT_REFUSED_EXIT_CODE,
)
from metabrowser.errors import CLIError
from metabrowser.invisible_chars import display_segment
from metabrowser.view_routes import format_view_href

if TYPE_CHECKING:
    from metabrowser.cache.urls import RejectedRoot, RepositorySelection

# The bundle identifiers `apps/macos/scripts/common.sh` gives the two variants of the app:
# an official release, and every local build. `tests/test_present.py` holds both to it.
RELEASE_BUNDLE_ID: Final = "io.github.jlevy.metabrowser"
DEV_BUNDLE_ID: Final = "io.github.jlevy.metabrowser.dev"
DEFAULT_BUNDLE_IDS: Final = (RELEASE_BUNDLE_ID, DEV_BUNDLE_ID)
# Names the one app to look for, as `--app-bundle-id` does; the flag wins.
BUNDLE_ID_ENV: Final = "METABROWSER_APP_BUNDLE_ID"
# The Info.plist key, a boolean, that a Metabrowser build which opens everything
# `--present` sends declares true: folders, files, and GitHub URLs.
OPENS_URLS_KEY: Final = "MetabrowserOpensURLs"
# The `CFBundleName` `apps/macos/scripts/build-app.sh` writes for both variants (`product`
# in `common.sh`, which `tests/test_present.py` holds to this).
APP_BUNDLE_NAME: Final = "Metabrowser"
# Where an installed app is, and the only places `--present` sends to: the system's and
# the user's Applications folder, `~` being the account's home folder as the password
# database records it, never `$HOME`, which a harness or a script sets for other reasons
# (`install_locations`). LaunchServices registers a bundle wherever it was opened, a
# build under `apps/macos/build/` or a copy in a cloned repository included, and names
# one of them for an identifier, so a target goes only to a bundle it names at one of
# these paths. A check of the path is cheap and runs on every handoff; it is not a
# signature (a release's team identifier is not checked yet).
APP_INSTALL_LOCATIONS: Final = (
    "/Applications/Metabrowser.app",
    "~/Applications/Metabrowser.app",
)
# Set to exactly `1`, lets `--present` send to a bundle outside APP_INSTALL_LOCATIONS, such
# as a development build where `make macos-app` leaves it. For a developer testing a build
# in place; the bundle name and the marker are still required.
ANY_APP_LOCATION_ENV: Final = "METABROWSER_ALLOW_UNINSTALLED_APP"
# An app's Info.plist is a few kilobytes; a larger one is not read.
INFO_PLIST_MAX_BYTES: Final = 1024 * 1024
# How long `open` may take to hand LaunchServices the target. It returns once
# LaunchServices has it, without waiting for a window, but a launch of an app that is not
# running comes first. Not measured: it bounds a hang rather than estimating a cost, so
# it is generous. Past it the report says `open_failed`, though LaunchServices may still
# deliver what it was given. The hand check in docs/project/qa/qa-macos-app-hand-checks.md
# records how long `open` takes.
OPEN_TIMEOUT_S: Final = 30.0

# CFBundleIdentifier's alphabet, letters, digits, hyphens, and periods, in segments that
# start with a letter or a digit, so no value can read as an option after `open -b`.
_BUNDLE_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*(?:\.[A-Za-z0-9][A-Za-z0-9-]*)+$")

type PresentKind = Literal["folder", "file", "repository", "pull_request", "commit", "tree"]
"""What a target is. A file is ``file`` locally and on GitHub, a folder ``folder``
locally and ``tree`` on GitHub; ``root`` tells the two apart."""

type DeliveryCode = Literal[
    "not_confirmed",
    "not_macos",
    "app_not_found",
    "app_not_installed",
    "app_not_marked",
    "app_cannot_select_folder",
    "lookup_failed",
    "open_failed",
]
"""What became of a target that resolved: taken by LaunchServices, or why not sent."""

# The exit status each delivery code ends the command with (`cli/exit_codes.py`).
DELIVERY_EXIT_CODES: Final[dict[DeliveryCode, int]] = {
    "not_confirmed": 0,
    "not_macos": PRESENT_NO_APP_EXIT_CODE,
    "app_not_found": PRESENT_NO_APP_EXIT_CODE,
    "app_not_installed": PRESENT_NO_APP_EXIT_CODE,
    "app_not_marked": PRESENT_NO_APP_EXIT_CODE,
    "app_cannot_select_folder": PRESENT_NO_APP_EXIT_CODE,
    "lookup_failed": PRESENT_BLOCKED_EXIT_CODE,
    "open_failed": PRESENT_BLOCKED_EXIT_CODE,
}

_SOURCE_KINDS: Final[dict[str, PresentKind]] = {
    "repository": "repository",
    "tree": "tree",
    "blob": "file",
    "commit": "commit",
    "pull_request": "pull_request",
}


@dataclass(frozen=True, slots=True)
class Presentable:
    """A target ``--present`` can hand over, and what it hands over."""

    kind: PresentKind
    root: str
    page: str | None
    """The address in *root*, or ``None`` where only the mirror knows it."""
    handoff: tuple[str, ...] | None
    """What ``open -b <id>`` is given: absolute paths, or the canonical web URL; ``None``
    for a folder inside the root, which no handoff makes the app select."""

    def as_json(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "root": self.root,
            "page": self.page,
            "handoff": list(self.handoff) if self.handoff is not None else None,
            "refusal": None,
        }


@dataclass(frozen=True, slots=True)
class Refusal:
    """Why a target cannot be presented: a stable code and a line that names the fix."""

    code: str
    message: str

    def as_json(self) -> dict[str, object]:
        return {
            "kind": None,
            "root": None,
            "page": None,
            "handoff": None,
            "refusal": {"code": self.code, "message": self.message},
        }


def _shown(path: str | Path) -> str:
    """*path* for a message: one line, with nothing a terminal would act on."""

    return display_segment(os.fsencode(path))


def _addressable(path: Path) -> Refusal | None:
    text = str(path)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return Refusal(
            "unaddressable_path",
            f"{_shown(path)} is not valid UTF-8, so the app cannot name it; rename it",
        )
    if "\n" in text or "\r" in text:
        return Refusal(
            "unaddressable_path",
            f"{_shown(path)} holds a line break, which the app refuses in a path; rename it",
        )
    return None


def _view_href(logical_path: str) -> str | Refusal:
    try:
        return format_view_href(logical_path)
    except ValueError:
        return Refusal(
            "unaddressable_path",
            f"{_shown(logical_path)} has no address in Metabrowser; rename it",
        )


def _resolve_local(value: str, path: str) -> Presentable | Refusal:
    try:
        given = Path(value).expanduser()
    except RuntimeError:
        return Refusal("not_found", f"{_shown(value)} names no home folder; check the path")
    try:
        resolved = given.resolve(strict=True)
    except FileNotFoundError:
        return Refusal("not_found", f"nothing is at {_shown(given.absolute())}; check the path")
    except (OSError, RuntimeError) as exc:
        # A loop of links is a RuntimeError before Python 3.13, and an OSError from it.
        why = exc.strerror if isinstance(exc, OSError) and exc.strerror else "a loop of links"
        return Refusal("not_readable", f"{_shown(value)} cannot be read ({why}); check the path")
    if (refusal := _addressable(resolved)) is not None:
        return refusal
    if not os.access(resolved, os.R_OK):
        return Refusal("not_readable", f"{_shown(resolved)} cannot be read; check its permissions")
    if resolved.is_file():
        if path:
            return Refusal(
                "path_with_file",
                "--path selects inside a folder, and ROOT is a file; "
                "present the file alone, or name its folder as ROOT",
            )
        page = _view_href(resolved.name)
        if isinstance(page, Refusal):
            return page
        # Named alone, so the app places it as it places any file it is handed: in the
        # most specific open folder that holds it, else in this folder.
        return Presentable("file", str(resolved.parent), page, (str(resolved),))
    if not resolved.is_dir():
        return Refusal(
            "not_a_file_or_folder",
            f"{_shown(resolved)} is neither a file nor a folder; present a file or a folder",
        )
    root = str(resolved)
    if not path:
        return Presentable("folder", root, "/view/", (root,))
    selected = (resolved / path).resolve()
    if not selected.is_relative_to(resolved):
        return Refusal(
            "path_outside_root",
            f"--path names a place outside {_shown(resolved)}; name one inside it",
        )
    if not selected.exists():
        return Refusal(
            "path_not_found", f"--path names nothing in {_shown(resolved)}; check {_shown(path)}"
        )
    if (refusal := _addressable(selected)) is not None:
        return refusal
    logical = selected.relative_to(resolved).as_posix()
    if selected.is_dir():
        if not logical or logical == ".":
            return Presentable("folder", root, "/view/", (root,))
        page = _view_href(logical + "/")
        if isinstance(page, Refusal):
            return page
        return Presentable("folder", root, page, None)
    page = _view_href(logical)
    if isinstance(page, Refusal):
        return page
    return Presentable("file", root, page, (root, str(selected)))


def _rejected(rejected: RejectedRoot) -> Refusal:
    if rejected.detail:
        return Refusal(rejected.reason, rejected.detail)
    if rejected.reason == "empty":
        return Refusal("empty", "ROOT is empty; write . for the current folder")
    return Refusal(
        rejected.reason,
        "ROOT is neither a path that exists nor a GitHub URL; "
        "give a local file or folder, or a github.com URL",
    )


# A ref spelled in full, which `resolve_ref_and_path` (`cache/resolve.py`) looks up in
# that namespace alone.
_EXPLICIT_REF_PREFIXES: Final = ((b"refs", b"heads"), (b"refs", b"tags"))


def _unambiguous_path(selection: RepositorySelection) -> tuple[bytes, ...] | None:
    """The path a ``tree`` or ``blob`` URL selects when every reading of it agrees.

    ``resolve_selection`` (``cache/resolve.py``) reads a leading ``HEAD`` as the default
    branch and the rest as the path. Otherwise it drops a leading ``refs/heads/`` or
    ``refs/tags/``, and tries each leading run of the segments left as a ref, the whole
    run included, which leaves an empty path: only the mirror can answer which. So one
    segment left is that ref at the top of its tree, and anything longer is ``None``,
    every ``blob`` among them (the reducer refuses a ``blob`` of one segment): a blob's
    ``release/v1`` may be one branch, which ``metab URL`` serves at ``/view/``.
    """

    segments = selection.ref_and_path
    if segments[:1] == (b"HEAD",):
        return segments[1:]
    if segments[:2] in _EXPLICIT_REF_PREFIXES:
        segments = segments[2:]
    if len(segments) == 1:
        return ()
    return None


def _source_page(selection: RepositorySelection) -> str | None:
    """The page a served pin of *selection* opens at, or ``None`` if only its mirror knows.

    A commit opens at ``/commit/<id>``, which the commit route answers only for a full
    ID, so an abbreviated one, which the mirror expands, has no page here. Nor has a
    Changes tab URL that anchors one file: the anchor is a hash of the file's path, which
    only the pull request's list of changed files, in the cache, can name.
    """

    # Imported for a source only: they load the Git tree source's path encoding and the
    # revision grammar, which no local target needs (docs/development.md, "Deferred
    # Imports").
    from metabrowser.cli.selection_href import selection_view_href
    from metabrowser.git.wire import is_full_revision

    if selection.kind == "commit":
        commit = selection.commit
        if commit is None or not is_full_revision(commit):
            return None
        return selection_view_href(selection, (), commit=commit)
    if selection.kind in {"tree", "blob"}:
        path = _unambiguous_path(selection)
        return None if path is None else selection_view_href(selection, path)
    if selection.pull_file is not None:
        return None
    return selection_view_href(selection, ())


def _resolve_source(value: str, path: str) -> Presentable | Refusal:
    # Imported for a source only, as `cli/main.py` does for ROOT: a local target reads
    # the filesystem and never the URL grammar.
    from metabrowser.cache.providers import url_reducers
    from metabrowser.cache.urls import LocalPath, RejectedRoot, classify_root_argument

    reducers = url_reducers()
    classified = classify_root_argument(value, reducers=reducers)
    if isinstance(classified, LocalPath):
        return _resolve_local(classified.value, path)
    if isinstance(classified, RejectedRoot):
        return _rejected(classified)
    selection = classified.selection
    handoff = None
    if selection is not None:
        handoff = next(
            (
                url
                for reducer in reducers
                if (url := reducer.web_url(classified.normalized, selection)) is not None
            ),
            None,
        )
    if selection is None or handoff is None:
        return Refusal(
            "unsupported_source",
            "--present opens a local file or folder, or a GitHub URL; give one of those",
        )
    if path:
        return Refusal(
            "path_with_url",
            "--path selects inside a local folder; for a GitHub URL, "
            "present the URL of the file or folder itself",
        )
    return Presentable(
        _SOURCE_KINDS[selection.kind],
        classified.normalized,
        _source_page(selection),
        (handoff,),
    )


def resolve_target(value: str, path: str, *, local: bool) -> Presentable | Refusal:
    """What ROOT with *path* presents, reading no repository and starting nothing.

    *local* is ROOT's own rule (``cli/main.py``): an argument that names an existing
    path, or that the grammar could only read as one, is that path, and anything else is
    classified as a source.
    """

    if local:
        return _resolve_local(value, path)
    return _resolve_source(value, path)


# ── Finding the app ─────────────────────────────────────────────────


class AppLookupError(Exception):
    """LaunchServices could not be asked; ``str()`` says why."""


_CORE_FOUNDATION: Final = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
_CORE_SERVICES: Final = "/System/Library/Frameworks/CoreServices.framework/CoreServices"
_CF_STRING_ENCODING_UTF8: Final = 0x08000100
# MAXPATHLEN is 1024 on macOS; the buffer is roomier than any path it can return.
_PATH_BUFFER_BYTES: Final = 4096
# `kLSApplicationNotFoundErr`, LaunchServices' answer for an identifier it has no app
# for. Any other error means it could not be asked, as when a sandbox denies its
# database: on 2026-11-17 a lookup under `sandbox-exec` denying `com.apple.lsd.mapdb`
# answered -10661 for every identifier, an installed app's included.
_LS_APPLICATION_NOT_FOUND: Final = -10814


def _launch_services_bundle(bundle_id: str) -> Path | None:
    """The app bundle LaunchServices opens for *bundle_id*, or ``None`` if it has none.

    ``LSCopyApplicationURLsForBundleIdentifier`` lists every registered copy with the one
    LaunchServices prefers first, which is the one ``open -b`` opens. It reads the
    database ``open -b`` reads, so it finds an app wherever it was registered, which
    Spotlight's index (``mdfind``) does not promise: Spotlight can be off, or leave out
    the folder an app is in. On 2026-11-17 one lookup took 9 ms on a Mac. Raises
    :class:`AppLookupError` when LaunchServices cannot be loaded or asked, which is not
    the same answer as an app it does not have.
    """

    try:
        cf = ctypes.CDLL(_CORE_FOUNDATION)
        ls = ctypes.CDLL(_CORE_SERVICES)
        create_string = cf.CFStringCreateWithCString
        release = cf.CFRelease
        array_count = cf.CFArrayGetCount
        array_value = cf.CFArrayGetValueAtIndex
        url_path = cf.CFURLGetFileSystemRepresentation
        error_code = cf.CFErrorGetCode
        copy_urls = ls.LSCopyApplicationURLsForBundleIdentifier
    except (OSError, AttributeError) as exc:
        # AttributeError: a symbol the framework no longer exports. The lookup function
        # has been deprecated since macOS 12.
        raise AppLookupError(f"LaunchServices could not be loaded ({exc})") from exc
    create_string.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32)
    create_string.restype = ctypes.c_void_p
    release.argtypes = (ctypes.c_void_p,)
    release.restype = None
    array_count.argtypes = (ctypes.c_void_p,)
    array_count.restype = ctypes.c_long
    array_value.argtypes = (ctypes.c_void_p, ctypes.c_long)
    array_value.restype = ctypes.c_void_p
    url_path.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_char_p, ctypes.c_long)
    url_path.restype = ctypes.c_bool
    error_code.argtypes = (ctypes.c_void_p,)
    error_code.restype = ctypes.c_long
    copy_urls.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    copy_urls.restype = ctypes.c_void_p

    name = create_string(None, bundle_id.encode("ascii"), _CF_STRING_ENCODING_UTF8)
    if not name:
        raise AppLookupError("the bundle identifier could not be passed to LaunchServices")
    error = ctypes.c_void_p()
    try:
        urls = copy_urls(name, ctypes.byref(error))
    finally:
        release(name)
    code: int | None = None
    if error.value:
        try:
            code = int(error_code(error))
        finally:
            release(error)
    if not urls:
        if code is None or code == _LS_APPLICATION_NOT_FOUND:
            return None
        raise AppLookupError(f"LaunchServices could not be asked (error {code})")
    try:
        if array_count(urls) < 1:
            return None
        buffer = ctypes.create_string_buffer(_PATH_BUFFER_BYTES)
        if not url_path(array_value(urls, 0), True, buffer, _PATH_BUFFER_BYTES):
            raise AppLookupError("LaunchServices named an app with no file-system path")
        return Path(os.fsdecode(buffer.value))
    finally:
        release(urls)


# How an app bundle is looked up, and `None` where there is no LaunchServices. A module
# attribute so tests replace it, and the delivery goldens run on every platform.
bundle_lookup: Callable[[str], Path | None] | None = (
    _launch_services_bundle if sys.platform == "darwin" else None
)

# The `open` that hands LaunchServices the target: the system's, by its one location on
# macOS, never whichever `open` comes first on PATH. A module attribute so tests replace
# it with a recording stand-in.
open_executable: str = "/usr/bin/open"


def read_info_plist(bundle: Path) -> dict[str, object] | None:
    """The property list at *bundle*'s ``Contents/Info.plist``, or ``None``.

    Reads a regular file only, without waiting on one that is not (a FIFO would block)
    or reading a directory, and at most :data:`INFO_PLIST_MAX_BYTES`; anything it cannot
    read or parse, or that is not a dictionary, is ``None``.
    """

    info = bundle / "Contents" / "Info.plist"
    try:
        descriptor = os.open(info, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        data = os.read(descriptor, INFO_PLIST_MAX_BYTES + 1)
    except OSError:
        return None
    finally:
        os.close(descriptor)
    if len(data) > INFO_PLIST_MAX_BYTES:
        return None
    try:
        plist = plistlib.loads(data)
    except Exception:
        # A malformed property list raises from the XML parser or the binary reader, and
        # what it raises is not one class: ExpatError, IndexError, AttributeError, and
        # RecursionError are among them. Every one means the same here, no property list,
        # so nothing is sent.
        return None
    if not isinstance(plist, dict):
        return None
    return {str(key): value for key, value in plist.items()}


def _account_home() -> str:
    """The home folder the password database records for this process's user."""

    # Imported here: only a handoff needs it, and the module is POSIX's.
    import pwd

    return pwd.getpwuid(os.getuid()).pw_dir


def install_locations() -> tuple[str, ...]:
    """:data:`APP_INSTALL_LOCATIONS`, with ``~`` the account's home folder.

    A module function, so tests replace it rather than ``$HOME``.
    """

    home = _account_home()
    return tuple(
        home + location[1:] if location.startswith("~/") else location
        for location in APP_INSTALL_LOCATIONS
    )


def _comparable(path: str) -> str:
    """*path* with its folder's links resolved and one Unicode spelling.

    Only the folder is resolved, so a link at an install location stays a link.
    CoreFoundation spells a path decomposed and a home folder may be spelled composed,
    so both sides are compared composed.
    """

    folder, name = os.path.split(os.path.normpath(path))
    return unicodedata.normalize("NFC", os.path.join(os.path.realpath(folder), name))


def is_installed(bundle: Path) -> bool:
    """Whether *bundle*, as LaunchServices names it, is one of :func:`install_locations`.

    A link at an install location to a bundle elsewhere is not an install, whichever
    path LaunchServices names: its own is refused here, and its target is not at an
    install location.
    """

    if os.path.islink(bundle):
        return False
    named = _comparable(str(bundle))
    return any(named == _comparable(location) for location in install_locations())


def _any_location_allowed() -> bool:
    return os.environ.get(ANY_APP_LOCATION_ENV) == "1"


def app_refusal(bundle: Path, bundle_id: str) -> tuple[DeliveryCode, str] | None:
    """Why the app at *bundle*, found for *bundle_id*, is sent nothing, or ``None``.

    Every handoff, a file's or a URL's, needs all three: the bundle is installed
    (:func:`is_installed`, unless :data:`ANY_APP_LOCATION_ENV` is ``1``), its Info.plist
    names it :data:`APP_BUNDLE_NAME`, and it declares :data:`OPENS_URLS_KEY` true. A
    refusal names the bundle and what to install where, and never asks for anything to
    be done with the bundle it refused, which may be one the user never installed.
    """

    if not _any_location_allowed() and not is_installed(bundle):
        allowed = " or ".join(APP_INSTALL_LOCATIONS)
        if bundle_id in DEFAULT_BUNDLE_IDS:
            named = (
                f"LaunchServices names the app at {_shown(bundle)}, which is not installed in "
                "an Applications folder"
            )
        else:
            named = (
                f"LaunchServices names the app at {_shown(bundle)} for {bundle_id}, which is "
                "not a Metabrowser app installed in an Applications folder"
            )
        return (
            "app_not_installed",
            f"{named}; --present sends only to an app at {allowed}, so install the "
            "Metabrowser app at one of them",
        )
    info = read_info_plist(bundle)
    if info is None or info.get("CFBundleName") != APP_BUNDLE_NAME:
        return (
            "app_not_marked",
            f"the app at {_shown(bundle)} is not named {APP_BUNDLE_NAME} in its Info.plist, "
            "so it is not the Metabrowser app; install a current Metabrowser build",
        )
    if info.get(OPENS_URLS_KEY) is not True:
        return (
            "app_not_marked",
            f"the app at {_shown(bundle)} does not declare {OPENS_URLS_KEY}, so it is not a "
            "Metabrowser build that takes what --present sends; update it to a current build",
        )
    return None


# ── Delivering ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Delivery:
    """What ``--present`` did with a target: where it went, or why nowhere."""

    delivered_to: Literal["app", "none"]
    bundle_id: str | None
    bundle_path: str | None
    """The bundle LaunchServices named for *bundle_id*, whose Info.plist was read."""
    code: DeliveryCode
    message: str

    @property
    def exit_code(self) -> int:
        return DELIVERY_EXIT_CODES[self.code]


def _not_sent(
    code: DeliveryCode, message: str, bundle_id: str | None = None, bundle: Path | None = None
) -> Delivery:
    return Delivery("none", bundle_id, str(bundle) if bundle else None, code, message)


def _send(bundle_id: str, handoff: Sequence[str]) -> str | None:
    """Give *handoff* to the app through ``open -b``; ``None``, or why it failed."""

    try:
        result = subprocess.run(
            [open_executable, "-b", bundle_id, *handoff],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=OPEN_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"open did not return within {OPEN_TIMEOUT_S:g} s"
    except OSError as exc:
        return f"open could not run ({exc.strerror})"
    if result.returncode == 0:
        return None
    said = next((line for line in reversed(result.stderr.splitlines()) if line.strip()), "")
    detail = f": {display_segment(said.strip().encode())}" if said else ""
    return f"open exited with status {result.returncode}{detail}"


def deliver(target: Presentable, bundle_ids: Sequence[str]) -> Delivery:
    """Hand *target* to the first app of *bundle_ids* that LaunchServices has and trusts.

    A target the app can never take is refused before anything is asked. Each
    identifier's bundle is checked in turn, so a stray registration of one identifier
    does not hide an installed build of the next; the first refusal is reported only when
    no identifier's bundle passes. Each handoff goes to the identifier whose bundle
    passed, which ``open -b`` resolves to the bundle LaunchServices named for it.
    """

    if target.handoff is None:
        return _not_sent(
            "app_cannot_select_folder",
            "the app opens a folder in a window of its own and cannot select one inside "
            "another; present that folder itself, or ROOT without --path",
        )
    lookup = bundle_lookup
    if lookup is None:
        return _not_sent(
            "not_macos",
            "the Metabrowser app runs on macOS only; serve the target with metab ROOT",
        )
    refused: Delivery | None = None
    for bundle_id in bundle_ids:
        try:
            bundle = lookup(bundle_id)
        except AppLookupError as exc:
            return _not_sent("lookup_failed", f"{exc}; serve the target with metab ROOT instead")
        if bundle is None:
            continue
        if (refusal := app_refusal(bundle, bundle_id)) is not None:
            refused = refused or _not_sent(*refusal, bundle_id, bundle)
            continue
        failure = _send(bundle_id, target.handoff)
        if failure is not None:
            return _not_sent(
                "open_failed",
                f"{failure}; serve the target with metab ROOT instead",
                bundle_id,
                bundle,
            )
        return Delivery(
            "app",
            bundle_id,
            str(bundle),
            "not_confirmed",
            "LaunchServices took the target; the app does not reply yet, so nothing "
            "confirms that a window shows it",
        )
    if refused is not None:
        return refused
    return _not_sent(
        "app_not_found",
        f"LaunchServices knows no app {' or '.join(bundle_ids)}; install or build the "
        "Metabrowser app and open it once, or serve the target with metab ROOT",
    )


def present_bundle_ids(flag: str | None) -> tuple[str, ...]:
    """The apps to look for: the flag's, the environment's, or both variants."""

    if flag is not None:
        if _BUNDLE_ID.fullmatch(flag) is None:
            raise typer.BadParameter(
                f"{flag!r} is not a bundle identifier, such as {RELEASE_BUNDLE_ID}",
                param_hint="--app-bundle-id",
            )
        return (flag,)
    named = os.environ.get(BUNDLE_ID_ENV, "")
    if named:
        if _BUNDLE_ID.fullmatch(named) is None:
            raise CLIError(
                f"{BUNDLE_ID_ENV} is not a bundle identifier, such as {RELEASE_BUNDLE_ID}"
            )
        return (named,)
    return DEFAULT_BUNDLE_IDS


# ── Reporting ───────────────────────────────────────────────────────


def _print_json(payload: dict[str, object]) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _exit(code: int) -> NoReturn:
    raise typer.Exit(code=code)


def _report(
    delivery: Delivery | None, target: Presentable | Refusal, code: str, reason: str
) -> dict[str, object]:
    return {
        "delivered_to": delivery.delivered_to if delivery else "none",
        "bundle_id": delivery.bundle_id if delivery else None,
        "bundle_path": delivery.bundle_path if delivery else None,
        "target": target.as_json(),
        "confirmed": False,
        "code": code,
        "reason": reason,
    }


def _refuse(refusal: Refusal, *, as_json: bool, dry_run: bool) -> NoReturn:
    if as_json:
        if dry_run:
            _print_json(refusal.as_json())
        else:
            _print_json(_report(None, refusal, refusal.code, refusal.message))
    else:
        typer.echo(f"Error: {refusal.message} ({refusal.code})", err=True)
    _exit(PRESENT_REFUSED_EXIT_CODE)


def _target_lines(target: Presentable) -> list[str]:
    page = target.page if target.page is not None else "(the server's entry page)"
    handoff = (
        shlex.join(_shown(argument) for argument in target.handoff)
        if target.handoff is not None
        else "(none)"
    )
    return [
        f"kind: {target.kind}",
        f"root: {_shown(target.root)}",
        f"page: {page}",
        f"handoff: {handoff}",
    ]


def run_present(
    value: str,
    *,
    local: bool,
    path: str,
    dry_run: bool,
    as_json: bool,
    app_bundle_id: str | None,
) -> None:
    """Resolve ROOT and, unless *dry_run*, hand it to the app; exit with what happened."""

    bundle_ids = () if dry_run else present_bundle_ids(app_bundle_id)
    target = resolve_target(value, path, local=local)
    if isinstance(target, Refusal):
        _refuse(target, as_json=as_json, dry_run=dry_run)
    if dry_run:
        if as_json:
            _print_json(target.as_json())
        else:
            typer.echo("\n".join(_target_lines(target)))
        return
    delivery = deliver(target, bundle_ids)
    if as_json:
        _print_json(_report(delivery, target, delivery.code, delivery.message))
    elif delivery.delivered_to == "app":
        lines = [
            "delivered_to: app",
            f"bundle_id: {delivery.bundle_id}",
            f"bundle_path: {_shown(delivery.bundle_path or '')}",
            *_target_lines(target),
            "confirmed: false",
            f"code: {delivery.code}",
            f"reason: {delivery.message}",
        ]
        typer.echo("\n".join(lines))
    else:
        typer.echo(f"Error: not sent to the app: {delivery.message} ({delivery.code})", err=True)
    if delivery.exit_code:
        _exit(delivery.exit_code)


__all__ = [
    "BUNDLE_ID_ENV",
    "DEFAULT_BUNDLE_IDS",
    "DELIVERY_EXIT_CODES",
    "DEV_BUNDLE_ID",
    "OPENS_URLS_KEY",
    "RELEASE_BUNDLE_ID",
    "ANY_APP_LOCATION_ENV",
    "APP_BUNDLE_NAME",
    "APP_INSTALL_LOCATIONS",
    "AppLookupError",
    "Delivery",
    "DeliveryCode",
    "PresentKind",
    "Presentable",
    "Refusal",
    "bundle_lookup",
    "app_refusal",
    "deliver",
    "install_locations",
    "is_installed",
    "open_executable",
    "present_bundle_ids",
    "read_info_plist",
    "resolve_target",
    "run_present",
]
