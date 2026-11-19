"""``metab ROOT --present``: open a folder, a file, or a GitHub URL in the app or a browser.

This is the command-line half of opening anything in the native app. It is a client
mode: it reads ROOT as every mode reads it, clones and fetches nothing itself, and gives
the app what it needs through LaunchServices, which is how macOS opens a document in an
app (``open -b``). The app does the rest by running ``metab`` on what it was given, as
it does for a folder opened in Finder. Where the app is not used, it starts ``metab
ROOT`` detached, the serve mode that opens a browser once its page answers, and reports
the server. The ``open_in`` preference (:mod:`metabrowser.open_in`) chooses between the
two. A dry run loads nothing beyond what ``metab --version`` loads except this module,
the preference's reader, the property-list reader, and for a link the URL grammar,
which ``test_present_dry_run_loads_little_beyond_version`` in
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

**Deciding.** :func:`decide` reads the ``open_in`` preference and, unless it is
``browser``, looks for the app with :func:`find_app`: through LaunchServices, release
first, then the development build, or the one ``--app-bundle-id`` or
:data:`BUNDLE_ID_ENV` names. Every handoff first passes :func:`app_refusal`: the bundle
LaunchServices names is installed at one of :data:`APP_INSTALL_LOCATIONS`, is named
:data:`APP_BUNDLE_NAME`, and declares :data:`OPENS_URLS_KEY`, the marker of a Metabrowser
build that takes everything this mode sends. An app without the marker drops a URL while
``open`` still succeeds, an override naming another app must not receive a file it would
run, and a bundle registered somewhere else, a build in a cloned repository among them,
is not the app the user installed. ``auto`` goes to a browser when no app takes the
target, ``app`` goes nowhere then, and either goes nowhere when LaunchServices cannot be
asked, which in an agent's sandbox is most often the sandbox, whose browser would be
blocked as well. ``--dry-run`` decides and prints the decision, sending nothing and
starting no server.

**Delivering.** To the app, the handoff goes with ``open -b``. ``open`` returning 0
means LaunchServices took it, not that a window shows it, and the app cannot answer yet.
To a browser, :func:`serve_detached` starts ``metab ROOT`` in a session of its own, with
its output in a log file, and waits for its ``Serving`` line: that server opens the page
in a browser once it answers, as ``metab ROOT`` in a terminal does, and keeps serving
after this command exits, until ``kill`` stops it. The report names its address, its
process ID, and its log. Nothing confirms a window or a browser shows the target, so every
report says ``confirmed: false``.
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
import tempfile
import time
import unicodedata
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, NoReturn, cast
from urllib.parse import urlsplit

import typer

from metabrowser.cli.exit_codes import (
    PRESENT_BLOCKED_EXIT_CODE,
    PRESENT_NO_APP_EXIT_CODE,
    PRESENT_REFUSED_EXIT_CODE,
)
from metabrowser.errors import CLIError
from metabrowser.invisible_chars import display_segment
from metabrowser.open_in import (
    PRESENT_BROWSER_SETTING,
    OpenInPreference,
    browser_delivery_allowed,
    resolve_open_in,
)
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
# The Info.plist key, a string such as `0.13.0`, naming the oldest metab the app runs: its
# `MetabRequirement.minimumRelease`, which `tests/test_macos_app_pins.py` holds it to.
# `metab --doctor` reads it from the app it finds, to say whether this metab is new enough.
MINIMUM_METAB_KEY: Final = "MetabrowserMinimumMetab"
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

type AppRefusalCode = Literal[
    "not_macos",
    "app_not_found",
    "app_not_installed",
    "app_not_marked",
    "app_cannot_select_folder",
    "lookup_failed",
]
"""Why no app takes a target, which looking for it says before anything is sent."""

type DeliveryCode = Literal[
    "not_confirmed",
    "not_macos",
    "app_not_found",
    "app_not_installed",
    "app_not_marked",
    "app_cannot_select_folder",
    "lookup_failed",
    "open_failed",
    "server_started",
    "server_starting",
    "server_failed",
    "browser_off",
]
"""What became of a target that resolved: taken by LaunchServices, served for a browser,
or why neither."""

type Destination = Literal["app", "browser", "none"]
"""Where a target goes: the app, a browser on a server started for it, or nowhere."""

type DecisionCode = Literal[
    "app_found",
    "browser_preferred",
    "browser_fallback",
    "preference_unreadable",
    "not_macos",
    "app_not_found",
    "app_not_installed",
    "app_not_marked",
    "app_cannot_select_folder",
    "lookup_failed",
    "browser_off",
]
"""Why a dry run decided what it did: the app takes the target, the preference is
``browser``, no app takes it under ``auto``, the preference could not be read, the app
code that sends it nowhere, or a browser it would go to that ``config.yml`` turns off."""

# The exit status each delivery code ends the command with (`cli/exit_codes.py`). A
# server that exited before it said where it serves is a failure like any other, 1.
DELIVERY_EXIT_CODES: Final[dict[DeliveryCode, int]] = {
    "not_confirmed": 0,
    "not_macos": PRESENT_NO_APP_EXIT_CODE,
    "app_not_found": PRESENT_NO_APP_EXIT_CODE,
    "app_not_installed": PRESENT_NO_APP_EXIT_CODE,
    "app_not_marked": PRESENT_NO_APP_EXIT_CODE,
    "app_cannot_select_folder": PRESENT_NO_APP_EXIT_CODE,
    "lookup_failed": PRESENT_BLOCKED_EXIT_CODE,
    "open_failed": PRESENT_BLOCKED_EXIT_CODE,
    "server_started": 0,
    "server_starting": 0,
    "server_failed": 1,
    # Nothing takes the target: the app does not, and config.yml turns a browser off.
    "browser_off": PRESENT_NO_APP_EXIT_CODE,
}

# How long `--present` waits for a server it started to print where it serves, the
# `Serving <root> at <url>` line, and for that address to answer as the target's. Measured
# on 2026-11-18 on an Apple silicon Mac: under a load average of about 265 a folder's
# server printed the line 1.6 to 2.5 s after it started, five starts in a row; under 50
# to 70 a small folder's and this repository's checkout's answered `/api/identity` 0.7 to
# 1.1 s after, six starts. This is about eight times the slowest. A repository's first
# clone can take minutes, so past this the report says `server_starting`, and the server
# still opens the page once it answers. A module attribute so tests shorten it.
server_announce_timeout_s: float = 20.0
# How often the server's log is read while waiting: the interval `cli/http_readiness.py`
# polls at before a browser opens.
SERVER_POLL_S: Final = 0.05
# The route whose answer says which root a server serves (`root_identity.py`).
IDENTITY_ROUTE: Final = "/api/identity"
# The most of an identity response read, its status line and headers included. Its five
# fields are names of at most a path, an origin, and a pin, and its headers are a few
# more lines, so it is a few hundred bytes; a longer response is not an identity.
IDENTITY_MAX_BYTES: Final = 64 * 1024
# How long one identity request may take in all, from connecting to the last byte read,
# however slowly the peer sends. A started server answers it from memory, reading no
# store and running no Git (`root_identity.py`), so a request that takes this long is to
# a server still starting, and the next round asks again.
SERVER_IDENTITY_REQUEST_S: Final = 1.0
# An identity response's status line when the server found the route: HTTP/1.0 or 1.1,
# status 200, and any reason phrase.
_IDENTITY_OK: Final = re.compile(rb"HTTP/1\.[01] 200(?: .*)?")
# The server's last lines kept, to say why it failed; one is reported.
SERVER_LOG_TAIL_LINES: Final = 5
# A line of the server's output longer than this is skipped while waiting: the `Serving`
# line is at most a root of PATH_MAX (4096 on Linux, 1024 on macOS) and a loopback URL
# naming a path inside it, and a clone's progress is shorter.
SERVER_LOG_LINE_MAX_BYTES: Final = 16 * 1024
# The most of the server's output read each round. A clone's progress is a few hundred
# bytes a second, so this is never reached by a server at work, only by one gone wrong.
SERVER_LOG_READ_BYTES: Final = 1024 * 1024
# The name of a detached server's log, in the temporary folder (`server_log_directory`).
# Rerunning the command writes a new one, which is all a temporary folder may hold
# (AGENTS.md, Durable Storage); a restart that empties it has stopped the server too.
SERVER_LOG_PREFIX: Final = "metab-present-"

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


def app_refusal(bundle: Path, bundle_id: str) -> tuple[AppRefusalCode, str] | None:
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


# ── Deciding ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AppFinding:
    """What looking for the app found: the app that takes a target, or why none does."""

    bundle_id: str | None
    """The identifier whose bundle takes the target, or whose bundle was refused."""
    bundle_path: str | None
    """The bundle LaunchServices named for *bundle_id*, whose Info.plist was read."""
    refusal: tuple[AppRefusalCode, str] | None
    """Why no app takes the target, or ``None`` when the bundle above does."""


def find_app(target: Presentable, bundle_ids: Sequence[str]) -> AppFinding:
    """The first app of *bundle_ids* that LaunchServices has and trusts, sending nothing.

    A target the app can never take is refused before anything is asked. Each
    identifier's bundle is checked in turn, so a stray registration of one identifier
    does not hide an installed build of the next; the first refusal is reported only when
    no identifier's bundle passes.
    """

    if target.handoff is None:
        return AppFinding(
            None,
            None,
            (
                "app_cannot_select_folder",
                "the app opens a folder in a window of its own and cannot select one inside "
                "another; present that folder itself, or ROOT without --path",
            ),
        )
    return look_up_app(bundle_ids)


def look_up_app(bundle_ids: Sequence[str]) -> AppFinding:
    """The first app of *bundle_ids* that LaunchServices has and trusts, for any target
    with a handoff; :func:`find_app` without the target."""

    lookup = bundle_lookup
    if lookup is None:
        return AppFinding(
            None,
            None,
            (
                "not_macos",
                "the Metabrowser app runs on macOS only; serve the target with metab ROOT",
            ),
        )
    refused: AppFinding | None = None
    for bundle_id in bundle_ids:
        try:
            bundle = lookup(bundle_id)
        except AppLookupError as exc:
            return AppFinding(
                None, None, ("lookup_failed", f"{exc}; serve the target with metab ROOT instead")
            )
        if bundle is None:
            continue
        if (refusal := app_refusal(bundle, bundle_id)) is not None:
            refused = refused or AppFinding(bundle_id, str(bundle), refusal)
            continue
        return AppFinding(bundle_id, str(bundle), None)
    if refused is not None:
        return refused
    return AppFinding(
        None,
        None,
        (
            "app_not_found",
            f"LaunchServices knows no app {' or '.join(bundle_ids)}; install or build the "
            "Metabrowser app and open it once, or serve the target with metab ROOT",
        ),
    )


@dataclass(frozen=True, slots=True)
class Decision:
    """Where ``--present`` sends a target, and why."""

    preference: OpenInPreference | None
    """The ``open_in`` in effect, or ``None`` when it could not be read."""
    delivers_to: Destination
    code: DecisionCode
    message: str
    finding: AppFinding | None
    """What looking for the app found, or ``None`` when nothing looked."""
    fallback: tuple[AppRefusalCode, str] | None = None
    """Under ``auto``, why the app was passed over for a browser."""

    def as_json(self) -> dict[str, object]:
        return {
            "delivers_to": self.delivers_to,
            "open_in": self.preference.value if self.preference else None,
            "open_in_source": self.preference.source if self.preference else None,
            "bundle_id": self.finding.bundle_id if self.finding else None,
            "bundle_path": self.finding.bundle_path if self.finding else None,
            "code": self.code,
            "reason": self.message,
            "fallback": _fallback_json(self.fallback),
        }


_BROWSER_PREFERRED: Final = (
    "open_in is browser, so --present looks for no app and starts a metab server for the "
    "target that opens it in a browser"
)
_BROWSER_FALLBACK: Final = (
    "no app takes the target, so under open_in auto --present starts a metab server for it "
    "that opens it in a browser"
)


def decide(
    target: Presentable, preference: OpenInPreference, bundle_ids: Sequence[str]
) -> Decision:
    """Where *target* goes under *preference*, looking for the app unless it is ``browser``.

    Under ``auto`` a target no app takes goes to a browser, and one LaunchServices could
    not be asked about goes nowhere: in a sandbox that keeps ``metab`` from
    LaunchServices, a browser it starts would be kept from the screen as well, and the
    app may be there.
    """

    if preference.value == "browser":
        return Decision(preference, "browser", "browser_preferred", _BROWSER_PREFERRED, None)
    finding = find_app(target, bundle_ids)
    if finding.refusal is None:
        return Decision(
            preference,
            "app",
            "app_found",
            f"the app at {_shown(finding.bundle_path or '')} takes the target",
            finding,
        )
    code, message = finding.refusal
    if preference.value == "auto" and DELIVERY_EXIT_CODES[code] == PRESENT_NO_APP_EXIT_CODE:
        return Decision(
            preference, "browser", "browser_fallback", _BROWSER_FALLBACK, finding, finding.refusal
        )
    return Decision(preference, "none", code, message, finding)


_BROWSER_OFF: Final = (
    f"{PRESENT_BROWSER_SETTING} is false in config.yml, so --present starts no server for "
    "a browser and opens a target only in the app"
)


def allow_browser(decision: Decision, directory: Path | None = None) -> Decision:
    """*decision*, unless it starts a server for a browser that ``config.yml`` turns off.

    ``present_browser`` is read only here, once a server would start, so a target for the
    app is sent while ``config.yml`` is broken; a server is never started then. Raises
    :class:`~metabrowser.open_in.OpenInError` when the file cannot be read.
    """

    if decision.delivers_to != "browser" or browser_delivery_allowed(directory):
        return decision
    why = "open_in is browser" if decision.fallback is None else "no app takes the target"
    return Decision(
        decision.preference,
        "none",
        "browser_off",
        f"{why}, but {_BROWSER_OFF}",
        decision.finding,
        decision.fallback,
    )


# ── Delivering ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Delivery:
    """What ``--present`` did with a target: where it went, or why nowhere."""

    delivered_to: Destination
    bundle_id: str | None
    bundle_path: str | None
    """The bundle LaunchServices named for *bundle_id*, whose Info.plist was read."""
    code: DeliveryCode
    message: str
    url: str | None = None
    """The address the server started for a browser printed, once it printed one."""
    pid: int | None = None
    """The process ID of the server started for a browser."""
    log: str | None = None
    """The file the server started for a browser writes its output to."""
    fallback: tuple[AppRefusalCode, str] | None = None
    """Under ``auto``, why the app was passed over for a browser."""

    @property
    def exit_code(self) -> int:
        return DELIVERY_EXIT_CODES[self.code]


def _not_sent(
    code: DeliveryCode, message: str, bundle_id: str | None = None, bundle: str | None = None
) -> Delivery:
    return Delivery("none", bundle_id, bundle, code, message)


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


def send_to_app(target: Presentable, finding: AppFinding) -> Delivery:
    """Hand *target* to the app *finding* names, which ``open -b`` resolves to that bundle,
    or report why *finding* names none."""

    if finding.refusal is not None:
        return _not_sent(*finding.refusal, finding.bundle_id, finding.bundle_path)
    # `find_app` names an identifier for every app it passes, and passes none for a target
    # without a handoff.
    assert finding.bundle_id is not None and target.handoff is not None
    failure = _send(finding.bundle_id, target.handoff)
    if failure is not None:
        return _not_sent(
            "open_failed",
            f"{failure}; serve the target with metab ROOT instead",
            finding.bundle_id,
            finding.bundle_path,
        )
    return Delivery(
        "app",
        finding.bundle_id,
        finding.bundle_path,
        "not_confirmed",
        "LaunchServices took the target; the app does not reply yet, so nothing "
        "confirms that a window shows it",
    )


# The command that serves a target for a browser: this interpreter running the `metab`
# command line, so the server is the build that answered, wherever it is installed and
# whatever is first on PATH. `-I` keeps the working directory, which is the user's and
# may be any checkout, off the module path, as `diff/markdown_projection_worker.py` does
# for its child; `-u` writes each line to the log as it is printed, so the `Serving` line
# is there to read.
SERVER_COMMAND: Final = (sys.executable, "-I", "-u", "-m", "metabrowser.cli.main")
# The command a browser delivery starts: SERVER_COMMAND, or the stand-in a test sets.
server_command: tuple[str, ...] = SERVER_COMMAND


def server_log_directory() -> str:
    """Where a detached server's log goes: the temporary folder. Tests replace it."""

    return tempfile.gettempdir()


def serving_url(line: str) -> str | None:
    """The address in a ``Serving <root> at <url>`` line, or ``None`` for any other line.

    The line is ``serve_until_interrupted``'s (``cli/serve.py``), optionally followed by
    ``  [dev build: …]``. The root may hold anything but a line break, `` at `` included,
    so the address is the token after the last `` at ``, and it must end the line; only
    plain HTTP to a loopback address with a port is one, as the macOS app's
    ``CLIServeLaunch.parseServingLine`` reads it.
    """

    if not line.startswith("Serving "):
        return None
    text = line
    suffix = text.rfind("  [dev build: ")
    if suffix != -1 and text.endswith("]"):
        text = text[:suffix]
    _, at, token = text.rpartition(" at ")
    if not at or not token.startswith("http://") or any(ch.isspace() for ch in token):
        return None
    try:
        parts = urlsplit(token)
        port = parts.port
    except ValueError:
        return None
    if parts.hostname not in {"127.0.0.1", "::1"} or port is None or parts.username is not None:
        return None
    return token


@dataclass(frozen=True, slots=True)
class _Announcement:
    """What a detached server said and did while ``--present`` waited."""

    url: str | None
    """The address its ``Serving`` line named, once it printed one."""
    answered: bool
    """Whether that address answered as a server of the target."""
    status: int | None
    """Its exit status, once it exited."""
    tail: tuple[str, ...]


def _is_target_identity(answer: object, target: Presentable) -> bool:
    """Whether *answer*, a ``GET /api/identity`` body, names *target*'s root.

    A folder's server names its folder as ``folder_identity`` does; a mirror's names its
    origin and then its pin (``@<ref>``, ``@<commit>``) or pull request (``#<n>``).
    """

    # Imported here, once a server has said where it serves: the names come from the
    # session modules, which a dry run never loads (about 60 to 130 ms more, measured on
    # 2026-11-18 on an Apple silicon Mac under a load average of 50 to 80).
    from metabrowser.root_identity import abbreviate_origin, folder_identity, user_home

    if not isinstance(answer, dict):
        return False
    fields = cast(dict[object, object], answer)
    kind, name = fields.get("kind"), fields.get("full_name")
    if not isinstance(name, str):
        return False
    if os.path.isabs(target.root):
        expected = folder_identity(Path(target.root), home=user_home())["full_name"]
        return kind == "folder" and name == expected
    origin = abbreviate_origin(target.root, home=None).casefold()
    return kind == "mirror" and name.casefold().startswith((f"{origin}@", f"{origin}#"))


def _identity_body(host: str, port: int, deadline: float) -> bytes | None:
    """The body of a ``200`` answer to ``GET /api/identity`` at *host*:*port*, or None.

    The request ends at the *deadline* on ``time.monotonic()``, however slowly the peer
    sends: each read waits only for the time left, and at most ``IDENTITY_MAX_BYTES``
    are read. It asks over HTTP/1.0 with ``Connection: close``, so the response ends
    where the server closes, and a response the server sends in chunks is not an
    identity.
    """

    # Imported here: only a browser delivery asks, and the dry run's imports are counted.
    import socket

    authority = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
    request = (
        f"GET {IDENTITY_ROUTE} HTTP/1.0\r\nHost: {authority}\r\n"
        "Accept-Encoding: identity\r\nConnection: close\r\n\r\n"
    ).encode("ascii")
    received = bytearray()
    try:
        left = deadline - time.monotonic()
        if left <= 0:
            return None
        with socket.create_connection((host, port), timeout=left) as connection:
            connection.sendall(request)
            while len(received) <= IDENTITY_MAX_BYTES:
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                connection.settimeout(left)
                chunk = connection.recv(IDENTITY_MAX_BYTES + 1 - len(received))
                if not chunk:
                    break
                received += chunk
    except OSError:
        return None
    if len(received) > IDENTITY_MAX_BYTES:
        return None
    head, separator, body = bytes(received).partition(b"\r\n\r\n")
    status_line, *header_lines = head.split(b"\r\n")
    if not separator or _IDENTITY_OK.fullmatch(status_line) is None:
        return None
    headers: dict[bytes, bytes] = {}
    for line in header_lines:
        name, colon, value = line.partition(b":")
        if not colon:
            return None
        headers[name.strip().lower()] = value.strip()
    if headers.get(b"transfer-encoding", b"identity").lower() != b"identity":
        return None
    declared = headers.get(b"content-length")
    if declared is not None and (not declared.isdigit() or int(declared) != len(body)):
        return None
    return body


def _answers_as_target(url: str, target: Presentable, timeout_s: float) -> bool:
    """Whether the server at *url* answers ``GET /api/identity`` as a server of *target*
    within *timeout_s* in all.

    A server prints where it serves after it finds a free port and before it binds it,
    so two started together can print the same address, and the one that binds second
    exits. An answer for the target says a server of the target has started there; one
    for another root says the address is another server's. Two servers of the same root
    that print the same address are not told apart this way: the one that exits leaves
    the other serving the same target, and binding before printing (``mb-afxa``) would
    keep them from printing the same address at all. An answer that is not JSON, or is
    nested too deeply to parse, is not the target's either.
    """

    deadline = time.monotonic() + timeout_s
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        return False
    if parts.hostname is None or port is None:
        return False
    body = _identity_body(parts.hostname, port, deadline)
    if body is None:
        return False
    try:
        answer: object = json.loads(body)
    except (ValueError, RecursionError):
        return False
    return _is_target_identity(answer, target)


def _await_server(
    server: subprocess.Popen[bytes], log_path: str, target: Presentable, timeout_s: float
) -> _Announcement:
    """Read *log_path* until the server answers as *target*'s, exits, or *timeout_s* ends.

    Answering takes two steps: the ``Serving`` line names an address, and that address
    then answers ``GET /api/identity`` for the target. The log is read throughout, so an
    exit after the line still reports what the server said last. The exit is checked
    before each read, so the read after an exit sees all it wrote. A line is complete at
    its newline; a carriage return ends one too, as progress does.
    """

    deadline = time.monotonic() + timeout_s
    tail: deque[str] = deque(maxlen=SERVER_LOG_TAIL_LINES)
    pending = b""
    skipping = False
    status: int | None = None
    url: str | None = None
    with open(log_path, "rb") as log:
        while True:
            if status is None:
                status = server.poll()
            # At most this much each round, so a server that writes faster than this reads
            # still meets the deadline below.
            budget = SERVER_LOG_READ_BYTES
            while budget > 0 and (chunk := log.read(min(budget, SERVER_LOG_LINE_MAX_BYTES))):
                budget -= len(chunk)
                pending += chunk
                *lines, pending = re.split(rb"\r\n|\r|\n", pending)
                for raw in lines:
                    if skipping:
                        skipping = False
                        continue
                    line = raw.decode("utf-8", errors="replace")
                    if line.strip():
                        tail.append(line)
                    if url is None:
                        url = serving_url(line)
                if len(pending) > SERVER_LOG_LINE_MAX_BYTES:
                    pending = b""
                    skipping = True
            if status is not None and budget > 0:
                if pending.strip() and not skipping:
                    tail.append(pending.decode("utf-8", errors="replace"))
                return _Announcement(url, False, status, tuple(tail))
            left = deadline - time.monotonic()
            if (
                url is not None
                and left > 0
                and _answers_as_target(url, target, min(SERVER_IDENTITY_REQUEST_S, left))
                and server.poll() is None
            ):
                return _Announcement(url, True, None, tuple(tail))
            if time.monotonic() >= deadline:
                return _Announcement(url, False, None, tuple(tail))
            time.sleep(SERVER_POLL_S)


# The servers this command started and left running. Each one's Popen is held so that,
# collected, it does not warn that its child still runs: leaving it running is the point.
_detached: list[subprocess.Popen[bytes]] = []


def _serve_arguments(value: str, path: str) -> list[str]:
    """``metab ROOT``, with ``--path``, as the server is started: options before ``--``,
    so ROOT is read as ROOT whatever it begins with, and without ``--no-open``."""

    return [*server_command, *(("--path", path) if path else ()), "--", value]


def serve_detached(
    target: Presentable,
    value: str,
    path: str,
    *,
    fallback: tuple[AppRefusalCode, str] | None = None,
) -> Delivery:
    """Start ``metab ROOT`` for a browser, detached, and report it once it answers.

    *value* and *path* are ROOT and ``--path`` as given, which the server is given too;
    *target* is what they resolved to, whose root the server must answer for before the
    report says it started.

    The server runs in a session of its own, with stdin at ``/dev/null``, its output in a
    log file, and no other descriptor this command was given (``subprocess`` closes the
    rest), so neither this command's exit nor its terminal's hangup reaches it, and
    nothing reading this command's output waits on the server.
    It is serve mode, which opens the page in a browser once it answers: what a user who
    ran ``metab ROOT`` would get, in the same working directory and environment.
    """

    argv = _serve_arguments(value, path)
    if os.name != "posix":
        return Delivery(
            "none",
            None,
            None,
            "server_failed",
            "a detached server needs a POSIX session of its own, which this platform lacks; "
            "serve the target with metab ROOT",
            fallback=fallback,
        )
    try:
        descriptor, log_path = tempfile.mkstemp(
            prefix=SERVER_LOG_PREFIX, suffix=".log", dir=server_log_directory()
        )
    except OSError as exc:
        return Delivery(
            "none",
            None,
            None,
            "server_failed",
            f"no log file for the server could be made ({exc.strerror}); serve the target "
            "with metab ROOT",
            fallback=fallback,
        )
    try:
        server = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=descriptor,
            stderr=descriptor,
            # setsid() in the child, which every POSIX Python has. Not os.posix_spawn's
            # setsid, which a Python built without POSIX_SPAWN_SETSID refuses ("setsid
            # unavailable on this platform"), as the Linux 3.13 in CI did on 2026-11-18.
            start_new_session=True,
        )
    except OSError as exc:
        return Delivery(
            "none",
            None,
            None,
            "server_failed",
            f"the metab server could not start ({exc.strerror or exc}); serve the target "
            "with metab ROOT",
            log=log_path,
            fallback=fallback,
        )
    finally:
        os.close(descriptor)
    _detached.append(server)
    pid = server.pid
    heard = _await_server(server, log_path, target, server_announce_timeout_s)
    log = _shown(log_path)
    if heard.status is not None:
        said = f": {display_segment(heard.tail[-1].encode())}" if heard.tail else ""
        when = "after it said where it serves" if heard.url else "before it said where it serves"
        return Delivery(
            "none",
            None,
            None,
            "server_failed",
            f"the metab server for the target exited with status {heard.status} {when}"
            f"{said}; its output is in {log}",
            log=log_path,
            fallback=fallback,
        )
    if heard.url is None or not heard.answered:
        said = (
            "has not said where it serves"
            if heard.url is None
            else f"said it serves at {heard.url}, which has not answered as the target's"
        )
        return Delivery(
            "browser",
            None,
            None,
            "server_starting",
            f"a metab server for the target runs detached and {said} after "
            f"{server_announce_timeout_s:g} s, as a first clone can take minutes; it opens "
            f"the page in a browser once it answers. Its output is in {log}; stop it with "
            f"kill {pid}",
            pid=pid,
            log=log_path,
            fallback=fallback,
        )
    return Delivery(
        "browser",
        None,
        None,
        "server_started",
        f"a metab server for the target runs detached at {heard.url}, which answers as the "
        f"target's, and opens it in a browser once the page answers; nothing confirms that "
        f"a browser shows it. Its output is in {log}; stop it with kill {pid}",
        url=heard.url,
        pid=pid,
        log=log_path,
        fallback=fallback,
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


@dataclass(frozen=True, slots=True)
class DoctorOpenIn:
    """``metab --doctor``'s report of the preference and what looking for the app found."""

    section: dict[str, object]
    """The ``open_in`` object of ``--doctor --json``."""
    line: str
    """The line ``--doctor`` prints."""
    problems: tuple[str, ...]
    """A setting that cannot be read, or settings under which nothing takes a target."""
    app_path: str | None = None
    """The app that takes a target, when one was looked for and found."""
    app_minimum_metab: str | None = None
    """The oldest ``metab`` that app runs, from its :data:`MINIMUM_METAB_KEY`, if it names one."""


def doctor_open_in() -> DoctorOpenIn:
    """The preference, where it was read, whether a browser may be used, and, unless the
    preference is ``browser``, the app found.

    Looks the app up as ``--present`` would for a folder, sending nothing. A setting that
    cannot be read is a problem, and so are settings under which nothing takes a target:
    ``app`` where no app takes one, and ``present_browser: false`` with ``browser``, or
    with ``auto`` where no app takes one. LaunchServices that cannot be asked is not,
    since only where the command runs decides that.
    """

    problems: list[str] = []
    try:
        preference: OpenInPreference | None = resolve_open_in(None)
    except CLIError as exc:
        preference = None
        problems.append(f"open_in: {exc}")
    finding: AppFinding | None = None
    if preference is None or preference.value != "browser":
        try:
            bundle_ids = present_bundle_ids(None)
        except CLIError as exc:
            problems.append(f"open_in: {exc}")
        else:
            finding = look_up_app(bundle_ids)
    app: dict[str, object] | None = None
    app_path: str | None = None
    minimum_metab: str | None = None
    if finding is not None:
        if finding.refusal is None and finding.bundle_path is not None:
            app_path = finding.bundle_path
            declared = (read_info_plist(Path(app_path)) or {}).get(MINIMUM_METAB_KEY)
            minimum_metab = declared if isinstance(declared, str) and declared else None
        app = {
            "found": finding.refusal is None,
            "bundle_id": finding.bundle_id,
            "bundle_path": finding.bundle_path,
            "code": finding.refusal[0] if finding.refusal else "app_found",
            "reason": finding.refusal[1] if finding.refusal else "the app takes a target",
            "minimum_metab": minimum_metab,
        }
    no_app = (
        finding is not None
        and finding.refusal is not None
        and DELIVERY_EXIT_CODES[finding.refusal[0]] == PRESENT_NO_APP_EXIT_CODE
    )
    try:
        browser: bool | None = browser_delivery_allowed()
    except CLIError as exc:
        browser = None
        problems.append(f"open_in: {exc}")
    if preference is not None and finding is not None and finding.refusal is not None and no_app:
        if preference.value == "app":
            problems.append(
                f"open_in is app ({preference.source}), and no app takes a target: "
                f"{finding.refusal[1]}"
            )
        elif browser is False:
            problems.append(
                f"open_in is {preference.value} ({preference.source}), no app takes a target "
                f"({finding.refusal[1]}), and {_BROWSER_OFF}: --present opens nothing"
            )
    if preference is not None and preference.value == "browser" and browser is False:
        problems.append(
            f"open_in is browser ({preference.source}), and {_BROWSER_OFF}: --present opens nothing"
        )
    section: dict[str, object] = {
        "value": preference.value if preference else None,
        "source": preference.source if preference else None,
        PRESENT_BROWSER_SETTING: browser,
        "app": app,
    }
    if finding is None:
        found = "--present looks for no app"
    elif finding.refusal is None:
        found = f"the app: {_shown(finding.bundle_path or '')} ({finding.bundle_id})"
    else:
        found = f"the app: none ({finding.refusal[0]})"
    named = f"{preference.value} ({preference.source})" if preference else "unreadable"
    off = (
        f"; {PRESENT_BROWSER_SETTING}: false, so no server for a browser"
        if browser is False
        else ""
    )
    return DoctorOpenIn(
        section,
        f"metab --doctor: open_in {named}; {found}{off}",
        tuple(problems),
        app_path=app_path,
        app_minimum_metab=minimum_metab,
    )


# ── Reporting ───────────────────────────────────────────────────────


def _print_json(payload: dict[str, object]) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _exit(code: int) -> NoReturn:
    raise typer.Exit(code=code)


def _fallback_json(fallback: tuple[AppRefusalCode, str] | None) -> dict[str, str] | None:
    if fallback is None:
        return None
    return {"code": fallback[0], "reason": fallback[1]}


def _report(
    delivery: Delivery | None,
    target: Presentable | Refusal,
    code: str,
    reason: str,
    preference: OpenInPreference,
) -> dict[str, object]:
    return {
        "delivered_to": delivery.delivered_to if delivery else "none",
        "open_in": preference.value,
        "open_in_source": preference.source,
        "bundle_id": delivery.bundle_id if delivery else None,
        "bundle_path": delivery.bundle_path if delivery else None,
        "url": delivery.url if delivery else None,
        "pid": delivery.pid if delivery else None,
        "log": delivery.log if delivery else None,
        "target": target.as_json(),
        "confirmed": False,
        "code": code,
        "reason": reason,
        "fallback": _fallback_json(delivery.fallback if delivery else None),
    }


def _refuse(
    refusal: Refusal, *, as_json: bool, dry_run: bool, preference: OpenInPreference | None
) -> NoReturn:
    if as_json:
        if dry_run or preference is None:
            _print_json({**refusal.as_json(), "decision": None})
        else:
            _print_json(_report(None, refusal, refusal.code, refusal.message, preference))
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


def _preference_line(preference: OpenInPreference | None) -> str:
    if preference is None:
        return "open_in: (unreadable)"
    return f"open_in: {preference.value} ({preference.source})"


def _fallback_lines(fallback: tuple[AppRefusalCode, str] | None) -> list[str]:
    return [] if fallback is None else [f"fallback: {fallback[0]}: {fallback[1]}"]


def _settings(
    open_in: str | None, app_bundle_id: str | None
) -> tuple[OpenInPreference, tuple[str, ...]]:
    """The preference and, unless it is ``browser``, the apps to look for.

    Raises :class:`CLIError` for a setting that cannot be read, and
    :class:`typer.BadParameter` for an ``--app-bundle-id`` that is not an identifier.
    """

    preference = resolve_open_in(open_in)
    if preference.value == "browser":
        if app_bundle_id is not None:
            # Checked, so a malformed flag is the usage error it is whatever the preference.
            present_bundle_ids(app_bundle_id)
        return preference, ()
    return preference, present_bundle_ids(app_bundle_id)


def _print_decision(target: Presentable, decision: Decision, *, as_json: bool) -> None:
    if as_json:
        _print_json({**target.as_json(), "decision": decision.as_json()})
        return
    lines = [
        *_target_lines(target),
        _preference_line(decision.preference),
        f"delivers_to: {decision.delivers_to}",
        f"code: {decision.code}",
        f"reason: {decision.message}",
        *_fallback_lines(decision.fallback),
    ]
    typer.echo("\n".join(lines))


def _dry_run(
    value: str,
    *,
    local: bool,
    path: str,
    as_json: bool,
    open_in: str | None,
    app_bundle_id: str | None,
) -> None:
    """Resolve ROOT and decide where it goes, sending nothing and starting nothing.

    Its status says only whether ROOT resolved, so a consumer that checks a target, as
    the macOS app checks a link, is not failed by a preference it never uses: a setting
    that cannot be read is the decision's ``preference_unreadable``.
    """

    settings: tuple[OpenInPreference, tuple[str, ...]] | None = None
    unreadable: str | None = None
    try:
        settings = _settings(open_in, app_bundle_id)
    except CLIError as exc:
        unreadable = str(exc)
    target = resolve_target(value, path, local=local)
    if isinstance(target, Refusal):
        _refuse(target, as_json=as_json, dry_run=True, preference=None)
    if settings is None:
        decision = Decision(None, "none", "preference_unreadable", unreadable or "unreadable", None)
    else:
        decision = decide(target, *settings)
        try:
            decision = allow_browser(decision)
        except CLIError as exc:
            decision = Decision(
                decision.preference, "none", "preference_unreadable", str(exc), decision.finding
            )
    _print_decision(target, decision, as_json=as_json)


def run_present(
    value: str,
    *,
    local: bool,
    path: str,
    dry_run: bool,
    as_json: bool,
    app_bundle_id: str | None,
    open_in: str | None = None,
) -> None:
    """Resolve ROOT, decide where it goes, and unless *dry_run* send it there.

    Exits with what happened: a refusal, no app under ``app``, LaunchServices that could
    not be asked, or a server that did not start.
    """

    if dry_run:
        _dry_run(
            value,
            local=local,
            path=path,
            as_json=as_json,
            open_in=open_in,
            app_bundle_id=app_bundle_id,
        )
        return
    preference, bundle_ids = _settings(open_in, app_bundle_id)
    target = resolve_target(value, path, local=local)
    if isinstance(target, Refusal):
        _refuse(target, as_json=as_json, dry_run=False, preference=preference)
    decision = allow_browser(decide(target, preference, bundle_ids))
    if decision.delivers_to == "browser":
        delivery = serve_detached(target, value, path, fallback=decision.fallback)
    elif decision.code == "browser_off":
        found = decision.finding
        delivery = Delivery(
            "none",
            found.bundle_id if found else None,
            found.bundle_path if found else None,
            "browser_off",
            decision.message,
            fallback=decision.fallback,
        )
    else:
        # A decision for the app, or for nowhere, follows looking for the app.
        assert decision.finding is not None
        delivery = send_to_app(target, decision.finding)
    if as_json:
        _print_json(_report(delivery, target, delivery.code, delivery.message, preference))
    elif delivery.delivered_to == "none":
        where = "served" if delivery.code in {"server_failed", "browser_off"} else "sent to the app"
        typer.echo(f"Error: not {where}: {delivery.message} ({delivery.code})", err=True)
    else:
        lines = [f"delivered_to: {delivery.delivered_to}", _preference_line(preference)]
        if delivery.delivered_to == "app":
            lines += [
                f"bundle_id: {delivery.bundle_id}",
                f"bundle_path: {_shown(delivery.bundle_path or '')}",
            ]
        else:
            lines += [
                f"url: {delivery.url or '(not yet)'}",
                f"pid: {delivery.pid}",
                f"log: {_shown(delivery.log or '')}",
            ]
        lines += [
            *_target_lines(target),
            "confirmed: false",
            f"code: {delivery.code}",
            f"reason: {delivery.message}",
            *_fallback_lines(delivery.fallback),
        ]
        typer.echo("\n".join(lines))
    if delivery.exit_code:
        _exit(delivery.exit_code)


__all__ = [
    "ANY_APP_LOCATION_ENV",
    "APP_BUNDLE_NAME",
    "APP_INSTALL_LOCATIONS",
    "BUNDLE_ID_ENV",
    "DEFAULT_BUNDLE_IDS",
    "DELIVERY_EXIT_CODES",
    "DEV_BUNDLE_ID",
    "MINIMUM_METAB_KEY",
    "OPENS_URLS_KEY",
    "RELEASE_BUNDLE_ID",
    "SERVER_COMMAND",
    "SERVER_LOG_PREFIX",
    "AppFinding",
    "AppLookupError",
    "Decision",
    "DecisionCode",
    "Delivery",
    "DeliveryCode",
    "Destination",
    "PresentKind",
    "Presentable",
    "Refusal",
    "app_refusal",
    "bundle_lookup",
    "decide",
    "DoctorOpenIn",
    "doctor_open_in",
    "allow_browser",
    "find_app",
    "look_up_app",
    "install_locations",
    "is_installed",
    "open_executable",
    "present_bundle_ids",
    "read_info_plist",
    "resolve_target",
    "run_present",
    "send_to_app",
    "serve_detached",
    "server_announce_timeout_s",
    "server_command",
    "server_log_directory",
    "serving_url",
]
