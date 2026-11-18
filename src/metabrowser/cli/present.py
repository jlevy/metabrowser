"""``metab TARGET --present``: hand a folder, a file, or a GitHub URL to the macOS app.

This is the command-line half of opening anything in the native app. It is a client
mode: it reads TARGET as ROOT is read, imports neither the server nor the inventory,
clones and fetches nothing, and gives the app one path or URL through LaunchServices,
which is how macOS opens a document in an app (``open -b``). The app does the rest by
running ``metab`` on what it was given, as it does for a folder opened in Finder.

**Resolving.** :func:`resolve_target` reads TARGET with the ``--path`` it came with:

- a folder is ``folder``, rooted there, at ``/view/``; with ``--path`` naming a folder
  inside it, at that folder's address;
- a file, or a folder with ``--path`` naming a file, is ``file``, rooted at the folder
  ``metab`` would serve, at the file's address;
- a GitHub URL is ``repository``, ``tree``, ``file`` (a ``blob`` or raw URL),
  ``commit``, or ``pull_request``, rooted at the canonical repository URL, which never
  names a ref, because the app keys a session by its repository.

A GitHub URL's ``page`` is the address a server of its pin opens: ``/pull/<n>`` with
its tab, ``/commit/<id>`` with the ID as the URL spells it, or ``/view/`` for a
repository. For a ``tree`` or ``blob`` URL only the mirror knows where a ref containing
``/`` ends (:class:`~metabrowser.cache.urls.RepositorySelection`), and nothing here reads
a mirror, so ``page`` takes the first segment as the ref, which is right for every ref
without a ``/``; the server the app starts resolves the URL itself and opens the right
address either way.

Anything else is a :class:`Refusal` with a stable code and a one-line message that
names the fix. ``--dry-run`` stops here and prints the target, which is how the app
checks what a user typed without parsing a URL itself.

**Delivering.** :func:`deliver` finds the app through LaunchServices, release first,
then the development build, or the one ``--app-bundle-id`` or
:data:`BUNDLE_ID_ENV` names, and sends the target with ``open -b``. A URL goes only to
an app whose ``Info.plist`` declares :data:`OPENS_URLS_KEY`, because an app without it
drops a URL silently while ``open`` still succeeds. A folder inside the root cannot be
selected in the app, which opens every folder as a window of its own, so it is not sent.
``open`` returning 0 means LaunchServices took the target, not that a window shows it,
and the app cannot answer yet, so every report says ``confirmed: false``.
"""

from __future__ import annotations

import ctypes
import json
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, NoReturn

import typer

from metabrowser.cli.exit_codes import PRESENT_NOT_DELIVERED_EXIT_CODE, PRESENT_REFUSED_EXIT_CODE
from metabrowser.errors import CLIError
from metabrowser.invisible_chars import display_segment
from metabrowser.view_routes import format_commit_href, format_view_href

if TYPE_CHECKING:
    from metabrowser.cache.urls import RejectedRoot, RepositorySelection

# The bundle identifiers `apps/macos/scripts/common.sh` gives the two variants of the app:
# an official release, and every local build. `tests/test_present.py` holds both to it.
RELEASE_BUNDLE_ID: Final = "io.github.jlevy.metabrowser"
DEV_BUNDLE_ID: Final = "io.github.jlevy.metabrowser.dev"
DEFAULT_BUNDLE_IDS: Final = (RELEASE_BUNDLE_ID, DEV_BUNDLE_ID)
# Names the one app to look for, as `--app-bundle-id` does; the flag wins.
BUNDLE_ID_ENV: Final = "METABROWSER_APP_BUNDLE_ID"
# The Info.plist key, a boolean, that an app which opens a GitHub URL sent to it declares.
OPENS_URLS_KEY: Final = "MetabrowserOpensURLs"
# An app's Info.plist is a few kilobytes; a larger one is not read.
INFO_PLIST_MAX_BYTES: Final = 1024 * 1024
# How long `open` may take to hand LaunchServices the target. It returns once
# LaunchServices has it, without waiting for a window, but a launch of an app that is not
# running comes first. Not measured: it bounds a hang rather than estimating a cost, so
# it is generous. Past it the report says `open_failed`, though LaunchServices may still
# deliver what it was given.
OPEN_TIMEOUT_S: Final = 30.0

# CFBundleIdentifier's alphabet: letters, digits, hyphens, and periods.
_BUNDLE_ID: Final = re.compile(r"^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")

type PresentKind = Literal["folder", "file", "repository", "pull_request", "commit", "tree"]

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
    page: str
    handoff: str
    """What ``open`` is given: an absolute path, or the canonical web URL."""
    url: bool
    """The handoff is a URL, which only an app declaring :data:`OPENS_URLS_KEY` takes."""
    selects_folder: bool = False
    """The page is a folder inside the root, which the app cannot select."""

    def as_json(self) -> dict[str, object]:
        return {"kind": self.kind, "root": self.root, "page": self.page, "refusal": None}


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
                "--path selects inside a folder, and TARGET is a file; "
                "present the file alone, or name its folder as TARGET",
            )
        page = _view_href(resolved.name)
        if isinstance(page, Refusal):
            return page
        return Presentable("file", str(resolved.parent), page, str(resolved), url=False)
    if not resolved.is_dir():
        return Refusal(
            "not_a_file_or_folder",
            f"{_shown(resolved)} is neither a file nor a folder; present a file or a folder",
        )
    if not path:
        return Presentable("folder", str(resolved), "/view/", str(resolved), url=False)
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
            return Presentable("folder", str(resolved), "/view/", str(resolved), url=False)
        page = _view_href(logical + "/")
        if isinstance(page, Refusal):
            return page
        return Presentable(
            "folder", str(resolved), page, str(selected), url=False, selects_folder=True
        )
    page = _view_href(logical)
    if isinstance(page, Refusal):
        return page
    return Presentable("file", str(resolved), page, str(selected), url=False)


def _rejected(rejected: RejectedRoot) -> Refusal:
    if rejected.detail:
        return Refusal(rejected.reason, rejected.detail)
    if rejected.reason == "empty":
        return Refusal("empty", "TARGET is empty; write . for the current folder")
    return Refusal(
        rejected.reason,
        "TARGET is neither a path that exists nor a GitHub URL; "
        "give a local file or folder, or a github.com URL",
    )


def _source_page(selection: RepositorySelection) -> str:
    if selection.kind == "commit" and selection.commit is not None:
        return format_commit_href(selection.commit)
    # Imported for a source only: it loads the Git tree source's path encoding, which no
    # local target needs (docs/development.md, "Deferred Imports").
    from metabrowser.cli.selection_href import selection_view_href

    return selection_view_href(selection, selection.ref_and_path[1:])


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
            "--present opens a local file or folder, or a GitHub URL; "
            "serve another Git source with metab URL",
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
        handoff,
        url=True,
    )


def resolve_target(value: str, path: str, *, local: bool) -> Presentable | Refusal:
    """What TARGET with *path* presents, reading no repository and starting nothing.

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


def _launch_services_bundle(bundle_id: str) -> Path | None:
    """The app bundle LaunchServices opens for *bundle_id*, or ``None`` if it has none.

    ``LSCopyApplicationURLsForBundleIdentifier`` lists every registered copy with the one
    LaunchServices prefers first, which is the one ``open -b`` opens. It reads the
    database ``open -b`` reads, so it finds an app wherever it was registered, which
    Spotlight's index (``mdfind``) does not promise: Spotlight can be off, or leave out
    the folder an app is in. On 2026-11-17 one lookup took 9 ms on a Mac.
    """

    try:
        cf = ctypes.CDLL(_CORE_FOUNDATION)
        ls = ctypes.CDLL(_CORE_SERVICES)
    except OSError as exc:
        raise AppLookupError(f"LaunchServices could not be loaded ({exc})") from exc
    cf.CFStringCreateWithCString.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32)
    cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    cf.CFRelease.argtypes = (ctypes.c_void_p,)
    cf.CFRelease.restype = None
    cf.CFArrayGetCount.argtypes = (ctypes.c_void_p,)
    cf.CFArrayGetCount.restype = ctypes.c_long
    cf.CFArrayGetValueAtIndex.argtypes = (ctypes.c_void_p, ctypes.c_long)
    cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
    cf.CFURLGetFileSystemRepresentation.argtypes = (
        ctypes.c_void_p,
        ctypes.c_bool,
        ctypes.c_char_p,
        ctypes.c_long,
    )
    cf.CFURLGetFileSystemRepresentation.restype = ctypes.c_bool
    ls.LSCopyApplicationURLsForBundleIdentifier.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    ls.LSCopyApplicationURLsForBundleIdentifier.restype = ctypes.c_void_p

    name = cf.CFStringCreateWithCString(None, bundle_id.encode("ascii"), _CF_STRING_ENCODING_UTF8)
    if not name:
        raise AppLookupError("the bundle identifier could not be passed to LaunchServices")
    try:
        urls = ls.LSCopyApplicationURLsForBundleIdentifier(name, None)
    finally:
        cf.CFRelease(name)
    if not urls:
        return None
    try:
        if cf.CFArrayGetCount(urls) < 1:
            return None
        buffer = ctypes.create_string_buffer(_PATH_BUFFER_BYTES)
        if not cf.CFURLGetFileSystemRepresentation(
            cf.CFArrayGetValueAtIndex(urls, 0), True, buffer, _PATH_BUFFER_BYTES
        ):
            raise AppLookupError("LaunchServices named an app with no file-system path")
        return Path(os.fsdecode(buffer.value))
    finally:
        cf.CFRelease(urls)


# How an app bundle is looked up, and `None` where there is no LaunchServices. A module
# attribute so tests replace it, and the delivery goldens run on every platform.
bundle_lookup: Callable[[str], Path | None] | None = (
    _launch_services_bundle if sys.platform == "darwin" else None
)


def opens_urls(bundle: Path) -> bool:
    """Whether the app at *bundle* declares that it opens a URL sent to it."""

    info = bundle / "Contents" / "Info.plist"
    try:
        with info.open("rb") as stream:
            data = stream.read(INFO_PLIST_MAX_BYTES + 1)
    except OSError:
        return False
    if len(data) > INFO_PLIST_MAX_BYTES:
        return False
    try:
        plist = plistlib.loads(data)
    except (plistlib.InvalidFileException, ValueError, OverflowError):
        return False
    return isinstance(plist, dict) and plist.get(OPENS_URLS_KEY) is True


# ── Delivering ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Delivery:
    """What ``--present`` did with a target: where it went, or why nowhere."""

    delivered_to: Literal["app", "none"]
    bundle_id: str | None
    code: str
    message: str

    @property
    def reason(self) -> str:
        return f"{self.code}: {self.message}"


def _not_sent(code: str, message: str, bundle_id: str | None = None) -> Delivery:
    return Delivery("none", bundle_id, code, message)


def _send(bundle_id: str, handoff: str) -> str | None:
    """Give *handoff* to the app through ``open -b``; ``None``, or why it failed."""

    opener = shutil.which("open")
    if opener is None:
        return "there is no open command on PATH"
    try:
        result = subprocess.run(
            [opener, "-b", bundle_id, handoff],
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
    """Hand *target* to the first app of *bundle_ids* LaunchServices has, if it takes it."""

    lookup = bundle_lookup
    if lookup is None:
        return _not_sent(
            "not_macos",
            "the Metabrowser app runs on macOS only; serve the target with metab TARGET",
        )
    found: tuple[str, Path] | None = None
    for bundle_id in bundle_ids:
        try:
            bundle = lookup(bundle_id)
        except AppLookupError as exc:
            return _not_sent("lookup_failed", f"{exc}; serve the target with metab TARGET")
        if bundle is not None:
            found = (bundle_id, bundle)
            break
    if found is None:
        return _not_sent(
            "app_not_found",
            f"LaunchServices knows no app {' or '.join(bundle_ids)}; install or build the "
            "Metabrowser app and open it once, or serve the target with metab TARGET",
        )
    bundle_id, bundle = found
    if target.selects_folder:
        return _not_sent(
            "app_cannot_select_folder",
            "the app opens a folder in a window of its own and cannot select one inside "
            f"another; present {_shown(target.handoff)} itself, or TARGET without --path",
            bundle_id,
        )
    if target.url and not opens_urls(bundle):
        return _not_sent(
            "app_opens_no_urls",
            f"the app at {_shown(bundle)} does not declare {OPENS_URLS_KEY}, so it would "
            "drop a URL; update it to a build that opens GitHub URLs",
            bundle_id,
        )
    failure = _send(bundle_id, target.handoff)
    if failure is not None:
        return _not_sent(
            "open_failed",
            f"{failure}; run {_shown(shlex.join(['open', '-b', bundle_id, target.handoff]))} "
            "yourself, outside any sandbox",
            bundle_id,
        )
    return Delivery(
        "app",
        bundle_id,
        "not_confirmed",
        f"LaunchServices took the target for the app at {_shown(bundle)}; the app does not "
        "reply yet, so nothing confirms that a window shows it",
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


def _refuse(refusal: Refusal, *, as_json: bool, dry_run: bool) -> NoReturn:
    if as_json:
        if dry_run:
            _print_json(refusal.as_json())
        else:
            _print_json(
                {
                    "delivered_to": "none",
                    "bundle_id": None,
                    "target": refusal.as_json(),
                    "confirmed": False,
                    "reason": f"{refusal.code}: {refusal.message}",
                }
            )
    else:
        typer.echo(f"Error: {refusal.message} ({refusal.code})", err=True)
    _exit(PRESENT_REFUSED_EXIT_CODE)


def _target_lines(target: Presentable) -> list[str]:
    return [f"kind: {target.kind}", f"root: {_shown(target.root)}", f"page: {target.page}"]


def run_present(
    value: str,
    *,
    local: bool,
    path: str,
    dry_run: bool,
    as_json: bool,
    app_bundle_id: str | None,
) -> None:
    """Resolve TARGET and, unless *dry_run*, hand it to the app; exit with what happened."""

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
        _print_json(
            {
                "delivered_to": delivery.delivered_to,
                "bundle_id": delivery.bundle_id,
                "target": target.as_json(),
                "confirmed": False,
                "reason": delivery.reason,
            }
        )
    elif delivery.delivered_to == "app":
        lines = [
            "delivered_to: app",
            f"bundle_id: {delivery.bundle_id}",
            *_target_lines(target),
            "confirmed: false",
            f"reason: {delivery.reason}",
        ]
        typer.echo("\n".join(lines))
    else:
        typer.echo(f"Error: not sent to the app: {delivery.message} ({delivery.code})", err=True)
    if delivery.delivered_to != "app":
        _exit(PRESENT_NOT_DELIVERED_EXIT_CODE)


__all__ = [
    "BUNDLE_ID_ENV",
    "DEFAULT_BUNDLE_IDS",
    "DEV_BUNDLE_ID",
    "OPENS_URLS_KEY",
    "RELEASE_BUNDLE_ID",
    "AppLookupError",
    "Delivery",
    "Presentable",
    "Refusal",
    "bundle_lookup",
    "deliver",
    "opens_urls",
    "present_bundle_ids",
    "resolve_target",
    "run_present",
]
