"""``metab TARGET --present``: what it reads, what it hands the app, and how it finds one.

The transcripts are the contract: ``tests/golden/cli-present.tryscript.md`` pins every
target shape and refusal of ``--present --dry-run``, and
``tests/golden/cli-present-delivery.txt`` and ``cli-present-browser.txt``
(``tests/test_cli_present_golden.py``) pin delivery with a recording ``open``, fixture app
bundles, and a stand-in server. This module checks what a
transcript cannot: the constants against the app's build scripts, the Info.plist reader's
edges, the bundle identifier's sources, and the LaunchServices lookup on a Mac.
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import signal
import socket
import struct
import subprocess
import sys
import textwrap
import threading
import time
import unicodedata
import urllib.request
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import get_args

import pytest
import typer

from metabrowser.cache.urls import FileAnchor, RepositorySelection
from metabrowser.cli import present
from metabrowser.cli.exit_codes import (
    PRESENT_BLOCKED_EXIT_CODE,
    PRESENT_NO_APP_EXIT_CODE,
    PRESENT_REFUSED_EXIT_CODE,
)
from metabrowser.cli.present import (
    ANY_APP_LOCATION_ENV,
    APP_BUNDLE_NAME,
    APP_INSTALL_LOCATIONS,
    BUNDLE_ID_ENV,
    DEFAULT_BUNDLE_IDS,
    DELIVERY_EXIT_CODES,
    DEV_BUNDLE_ID,
    INFO_PLIST_MAX_BYTES,
    MINIMUM_METAB_KEY,
    OPENS_URLS_KEY,
    RELEASE_BUNDLE_ID,
    SERVER_LOG_PREFIX,
    AppLookupError,
    DecisionCode,
    Delivery,
    DeliveryCode,
    Presentable,
    Refusal,
    allow_browser,
    app_refusal,
    decide,
    doctor_open_in,
    find_app,
    is_installed,
    present_bundle_ids,
    read_info_plist,
    resolve_target,
    send_to_app,
    serve_detached,
    serving_url,
)
from metabrowser.cli.selection_href import selection_view_href
from metabrowser.config_file import CONFIG_RECORD
from metabrowser.errors import CLIError
from metabrowser.home import (
    configuration_directory,
    ensure_private_directory,
    write_private_file_atomic,
)
from metabrowser.open_in import OPEN_IN_ENV, OpenInChoice, OpenInError, OpenInPreference
from tests.test_nav_metadata_chrome import _free_port

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON_SH = REPO_ROOT / "apps/macos/scripts/common.sh"
SERVER_STAND_IN = Path(__file__).with_name("present_server_standin.py")


def deliver(target: Presentable, bundle_ids: Sequence[str]) -> Delivery:
    """``--present --open-in app``'s delivery: look for the app, then send to it."""

    return send_to_app(target, find_app(target, bundle_ids))


def test_the_bundle_identifiers_are_the_ones_the_app_is_built_with() -> None:
    text = COMMON_SH.read_text(encoding="utf-8")
    variants = dict(re.findall(r'^\s*(release|dev)\)\n\s*bundle_id="([^"]+)"', text, re.MULTILINE))

    assert variants == {"release": RELEASE_BUNDLE_ID, "dev": DEV_BUNDLE_ID}
    # Release first: an installed release is the app a user means.
    assert DEFAULT_BUNDLE_IDS == (RELEASE_BUNDLE_ID, DEV_BUNDLE_ID)
    # Both variants are built as Metabrowser.app, named Metabrowser, which is the name the
    # trust check expects and the bundle every install location names.
    assert re.findall(r'^\s*product="([^"]+)"', text, re.MULTILINE) == [APP_BUNDLE_NAME]
    assert {Path(location).name for location in APP_INSTALL_LOCATIONS} == {f"{APP_BUNDLE_NAME}.app"}


def test_every_delivery_code_ends_with_its_own_kind_of_status() -> None:
    # Delivered, to the app or to a server for a browser, is 0; no app to take it and
    # blocked are apart, so a caller can tell "install the app" from "run this where
    # LaunchServices answers" by the status alone, and a server that did not start is a
    # failure like any other. Every code has a status, or a delivery would end in a
    # KeyError after it was sent.
    assert set(DELIVERY_EXIT_CODES) == set(get_args(DeliveryCode.__value__))
    delivered = {code for code, status in DELIVERY_EXIT_CODES.items() if status == 0}
    assert delivered == {"not_confirmed", "server_started", "server_starting"}
    statuses = set(DELIVERY_EXIT_CODES.values()) - {0}
    assert statuses == {CLIError("").exit_code, PRESENT_NO_APP_EXIT_CODE, PRESENT_BLOCKED_EXIT_CODE}
    assert DELIVERY_EXIT_CODES["server_failed"] == CLIError("").exit_code
    assert PRESENT_REFUSED_EXIT_CODE not in statuses
    assert DELIVERY_EXIT_CODES["app_not_found"] == PRESENT_NO_APP_EXIT_CODE
    assert DELIVERY_EXIT_CODES["lookup_failed"] == PRESENT_BLOCKED_EXIT_CODE
    assert DELIVERY_EXIT_CODES["open_failed"] == PRESENT_BLOCKED_EXIT_CODE


def _bundle(
    tmp_path: Path, info: dict[str, object] | list[str] | bytes, name: str = "App.app"
) -> Path:
    bundle = tmp_path / name
    (bundle / "Contents").mkdir(parents=True)
    data = info if isinstance(info, bytes) else plistlib.dumps(info)
    (bundle / "Contents" / "Info.plist").write_bytes(data)
    return bundle


_CURRENT_INFO: dict[str, object] = {"CFBundleName": APP_BUNDLE_NAME, OPENS_URLS_KEY: True}


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A home folder of the test's own, whose `Applications` is an install location.

    It replaces `install_locations`, the seam the account's home folder is read through,
    so `$HOME` is left alone, as it grants nothing.
    """

    folder = tmp_path / "home"
    folder.mkdir()
    user = str(folder / "Applications" / f"{APP_BUNDLE_NAME}.app")
    monkeypatch.setattr(
        present, "install_locations", lambda: ("/Applications/Metabrowser.app", user)
    )
    monkeypatch.delenv(ANY_APP_LOCATION_ENV, raising=False)
    return folder


def _installed(home: Path, info: dict[str, object] | list[str] | bytes) -> Path:
    """A bundle at the user's install location, *home* being the account's home."""

    return _bundle(home / "Applications", info, f"{APP_BUNDLE_NAME}.app")


@pytest.mark.parametrize(
    ("info", "says"),
    [
        (_CURRENT_INFO, None),
        ({"CFBundleName": APP_BUNDLE_NAME, OPENS_URLS_KEY: False}, OPENS_URLS_KEY),
        # Only a boolean declares it: a string or a number is not the key the app writes.
        ({"CFBundleName": APP_BUNDLE_NAME, OPENS_URLS_KEY: "YES"}, OPENS_URLS_KEY),
        ({"CFBundleName": APP_BUNDLE_NAME, OPENS_URLS_KEY: 1}, OPENS_URLS_KEY),
        ({"CFBundleName": APP_BUNDLE_NAME}, OPENS_URLS_KEY),
        ({"CFBundleName": "Terminal", OPENS_URLS_KEY: True}, f"not named {APP_BUNDLE_NAME}"),
        ({OPENS_URLS_KEY: True}, f"not named {APP_BUNDLE_NAME}"),
        ([OPENS_URLS_KEY], f"not named {APP_BUNDLE_NAME}"),
        (b"not a property list", f"not named {APP_BUNDLE_NAME}"),
        # Malformed property lists raise more than plistlib's own error: ExpatError for
        # the first three, IndexError and AttributeError for the next two; a deep binary
        # one raises RecursionError (below).
        (b'<?xml version="1.0"?><plist><dict><key>a</key>', f"not named {APP_BUNDLE_NAME}"),
        (b"<plist><dict><key>a</key><true/></array></plist>", f"not named {APP_BUNDLE_NAME}"),
        (b"<plist><dict>\x00</dict></plist>", f"not named {APP_BUNDLE_NAME}"),
        (b"<plist><key>a</key></plist>", f"not named {APP_BUNDLE_NAME}"),
        (b"<plist><date>nope</date></plist>", f"not named {APP_BUNDLE_NAME}"),
    ],
)
def test_an_installed_bundle_needs_the_name_and_a_true_marker(
    home: Path, info: dict[str, object] | list[str] | bytes, says: str | None
) -> None:
    refused = app_refusal(_installed(home, info), DEV_BUNDLE_ID)

    if says is None:
        assert refused is None
    else:
        assert refused is not None and refused[0] == "app_not_marked"
        assert says in refused[1]


def _nested_binary_plist(depth: int) -> bytes:
    """A binary property list of *depth* arrays, each holding the next."""

    # One-element arrays (0xA1) whose two-byte reference names the next object, then true.
    objects = [b"\xa1" + struct.pack(">H", index + 1) for index in range(depth)] + [b"\x09"]
    offsets: list[int] = []
    body = b"bplist00"
    for item in objects:
        offsets.append(len(body))
        body += item
    table = len(body)
    body += b"".join(struct.pack(">H", offset) for offset in offsets)
    return body + struct.pack(">6xBBQQQ", 2, 2, len(objects), 0, table)


def test_a_deeply_nested_binary_info_plist_is_unreadable(tmp_path: Path) -> None:
    assert read_info_plist(_bundle(tmp_path, _nested_binary_plist(5000))) is None


def test_a_bundle_without_a_readable_info_plist_has_none(tmp_path: Path) -> None:
    (tmp_path / "Bare.app").mkdir()

    assert read_info_plist(tmp_path / "Bare.app") is None
    assert read_info_plist(tmp_path / "Missing.app") is None


def test_an_oversized_info_plist_is_not_read(tmp_path: Path) -> None:
    padding = "x" * INFO_PLIST_MAX_BYTES
    bundle = _bundle(tmp_path, {**_CURRENT_INFO, "Padding": padding})

    assert read_info_plist(bundle) is None


@pytest.mark.skipif(os.name != "posix", reason="a FIFO and /dev/zero are POSIX")
def test_an_info_plist_that_is_not_a_regular_file_is_not_waited_on(tmp_path: Path) -> None:
    fifo = tmp_path / "Pipe.app" / "Contents"
    fifo.mkdir(parents=True)
    os.mkfifo(fifo / "Info.plist")
    device = tmp_path / "Device.app" / "Contents"
    device.mkdir(parents=True)
    (device / "Info.plist").symlink_to("/dev/zero")
    folder = tmp_path / "Folder.app" / "Contents" / "Info.plist"
    folder.mkdir(parents=True)
    linked = tmp_path / "Linked.app" / "Contents"
    linked.mkdir(parents=True)
    (linked / "Info.plist").symlink_to(folder)

    # A FIFO with no writer would block an ordinary open for good, and a folder opens but
    # cannot be read.
    for name in ("Pipe.app", "Device.app", "Folder.app", "Linked.app"):
        assert read_info_plist(tmp_path / name) is None, name


@pytest.mark.skipif(os.name != "posix", reason="a folder Info.plist is opened as POSIX opens")
def test_a_folder_info_plist_at_an_install_location_is_not_marked(home: Path) -> None:
    bundle = home / "Applications" / f"{APP_BUNDLE_NAME}.app"
    (bundle / "Contents" / "Info.plist").mkdir(parents=True)

    refused = app_refusal(bundle, DEV_BUNDLE_ID)

    assert refused is not None and refused[0] == "app_not_marked"


def test_the_flag_names_the_app_before_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(BUNDLE_ID_ENV, raising=False)
    assert present_bundle_ids(None) == DEFAULT_BUNDLE_IDS

    monkeypatch.setenv(BUNDLE_ID_ENV, "org.example.viewer")
    assert present_bundle_ids(None) == ("org.example.viewer",)
    assert present_bundle_ids("org.example.other") == ("org.example.other",)

    monkeypatch.setenv(BUNDLE_ID_ENV, "")
    assert present_bundle_ids(None) == DEFAULT_BUNDLE_IDS


@pytest.mark.parametrize(
    "value",
    [
        "metabrowser",
        "io.github.jlevy.metabrowser app",
        "a..b",
        ".a.b",
        # Option-shaped: a value that begins a segment with a hyphen would sit right
        # after `open -b`.
        "-a.--args",
        "--args.x",
        "a.-b",
    ],
)
def test_a_bundle_identifier_is_checked_before_anything_is_looked_up(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.delenv(BUNDLE_ID_ENV, raising=False)
    with pytest.raises(typer.BadParameter):
        present_bundle_ids(value)
    monkeypatch.setenv(BUNDLE_ID_ENV, value)
    with pytest.raises(CLIError, match=BUNDLE_ID_ENV):
        present_bundle_ids(None)


def test_nothing_is_delivered_where_there_is_no_launch_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(present, "bundle_lookup", None)
    target = Presentable("folder", "/srv/notes", "/view/", ("/srv/notes",))

    delivery = deliver(target, DEFAULT_BUNDLE_IDS)

    assert (delivery.delivered_to, delivery.bundle_id, delivery.code) == ("none", None, "not_macos")
    assert delivery.exit_code == PRESENT_NO_APP_EXIT_CODE


def _refuse_to_open(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point `open` at a program that fails the test if anything runs it."""

    opener = tmp_path / "open-must-not-run"
    opener.write_text("#!/bin/sh\necho ran >&2\nexit 99\n")
    opener.chmod(0o755)
    monkeypatch.setattr(present, "open_executable", str(opener))


def test_a_lookup_that_cannot_ask_launch_services_is_blocked_not_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def lookup(bundle_id: str) -> Path | None:
        raise AppLookupError("LaunchServices could not be asked (error -10661)")

    monkeypatch.setattr(present, "bundle_lookup", lookup)
    _refuse_to_open(monkeypatch, tmp_path)
    target = Presentable("folder", "/srv/notes", "/view/", ("/srv/notes",))

    delivery = deliver(target, DEFAULT_BUNDLE_IDS)

    assert (delivery.delivered_to, delivery.code) == ("none", "lookup_failed")
    assert "error -10661" in delivery.message
    assert delivery.exit_code == PRESENT_BLOCKED_EXIT_CODE


def _record_open(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point `open` at a stand-in that records its arguments; return the record."""

    log = tmp_path / "open.log"
    opener = tmp_path / "open-stand-in"
    opener.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\n')
    opener.chmod(0o755)
    monkeypatch.setattr(present, "open_executable", str(opener))
    return log


def test_only_the_two_install_locations_are_installed(home: Path) -> None:
    assert is_installed(Path("/Applications/Metabrowser.app"))
    assert is_installed(home / "Applications" / "Metabrowser.app")
    assert is_installed(Path("/Applications/Metabrowser.app/"))
    # A build where `make macos-app` leaves it, another name, another folder, or a path
    # that only passes through an install location, is not an install.
    assert not is_installed(Path("/src/metabrowser/apps/macos/build/dev/Metabrowser.app"))
    assert not is_installed(Path("/Applications/Metabrowser Dev.app"))
    assert not is_installed(Path("/Applications/Tools/Metabrowser.app"))
    assert not is_installed(Path("/Applications/Metabrowser.app/Contents/../../Evil.app"))
    assert not is_installed(home / "Metabrowser.app")


def test_home_grants_no_trust(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # `$HOME` pointed into a tree someone else wrote does not move the user's install
    # location: it is the account's home folder, from the password database.
    planted = _bundle(tmp_path / "clone" / "Applications", _CURRENT_INFO, "Metabrowser.app")
    monkeypatch.setenv("HOME", str(tmp_path / "clone"))

    assert not is_installed(planted)
    assert str(tmp_path) not in " ".join(present.install_locations())


@pytest.mark.skipif(os.name != "posix", reason="symbolic links")
def test_a_link_at_an_install_location_is_not_an_install(home: Path, tmp_path: Path) -> None:
    build = _bundle(tmp_path / "apps/macos/build/dev", _CURRENT_INFO, "Metabrowser.app")
    link = home / "Applications" / "Metabrowser.app"
    link.parent.mkdir(parents=True)
    link.symlink_to(build, target_is_directory=True)

    # Whichever LaunchServices names, the link or where it leads, it is refused.
    assert not is_installed(link)
    assert not is_installed(build)


@pytest.mark.skipif(os.name != "posix", reason="symbolic links")
def test_an_install_location_reached_through_a_linked_folder_or_spelled_decomposed_is_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The account's home is spelled composed and reached through a link; CoreFoundation
    # names the bundle decomposed, at the real folder.
    real = tmp_path / unicodedata.normalize("NFD", "renée")
    real.mkdir()
    composed = tmp_path / "home-link"
    composed.symlink_to(real, target_is_directory=True)
    user = str(composed / "Applications" / "Metabrowser.app")
    monkeypatch.setattr(present, "install_locations", lambda: (user,))
    bundle = _bundle(real / "Applications", _CURRENT_INFO, "Metabrowser.app")

    assert is_installed(Path(unicodedata.normalize("NFD", str(bundle))))
    assert is_installed(Path(unicodedata.normalize("NFC", str(bundle))))


@pytest.mark.skipif(os.name != "posix", reason="the open stand-ins are shell scripts")
def test_a_bundle_elsewhere_is_sent_nothing_unless_a_developer_allows_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, home: Path
) -> None:
    build = _bundle(tmp_path / "apps/macos/build/dev", _CURRENT_INFO, "Metabrowser.app")
    monkeypatch.setattr(present, "bundle_lookup", lambda bundle_id: build)
    _refuse_to_open(monkeypatch, tmp_path)
    target = Presentable("folder", "/srv/notes", "/view/", ("/srv/notes",))

    refused = deliver(target, (DEV_BUNDLE_ID,))

    assert (refused.delivered_to, refused.code) == ("none", "app_not_installed")
    assert refused.exit_code == PRESENT_NO_APP_EXIT_CODE
    # The message names where the bundle is and where to install the app, and asks for
    # nothing to be done with the bundle it refused.
    assert str(build) in refused.message
    assert all(location in refused.message for location in APP_INSTALL_LOCATIONS)
    assert "install the Metabrowser app at one of them" in refused.message
    assert "copy" not in refused.message and "move" not in refused.message
    # Only exactly `1` is the developer's word.
    monkeypatch.setenv(ANY_APP_LOCATION_ENV, "true")
    assert deliver(target, (DEV_BUNDLE_ID,)).code == "app_not_installed"

    monkeypatch.setenv(ANY_APP_LOCATION_ENV, "1")
    log = _record_open(monkeypatch, tmp_path)
    allowed = deliver(target, (DEV_BUNDLE_ID,))

    assert (allowed.delivered_to, allowed.code) == ("app", "not_confirmed")
    assert log.read_text() == f"-b {DEV_BUNDLE_ID} /srv/notes\n"
    # The override moves the location only: the marker is still required.
    unmarked = _bundle(tmp_path / "old-build", {"CFBundleName": APP_BUNDLE_NAME}, "Metabrowser.app")
    refusal = app_refusal(unmarked, DEV_BUNDLE_ID)
    assert refusal is not None and refusal[0] == "app_not_marked"


@pytest.mark.skipif(os.name != "posix", reason="the refusing open is a shell script")
def test_an_app_an_override_names_is_sent_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, home: Path
) -> None:
    # An override can name any app, such as Terminal, which runs a `.command` file it is
    # handed, so a file goes only where a URL goes: to the installed Metabrowser app.
    terminal = _bundle(tmp_path, {"CFBundleIdentifier": "com.apple.Terminal"}, "Terminal.app")
    monkeypatch.setattr(present, "bundle_lookup", lambda bundle_id: terminal)
    _refuse_to_open(monkeypatch, tmp_path)
    script = tmp_path / "run-me.command"
    script.write_text("echo hi\n")
    target = resolve_target(str(script), "", local=True)
    assert isinstance(target, Presentable)

    delivery = deliver(target, ("com.apple.Terminal",))

    assert (delivery.delivered_to, delivery.code) == ("none", "app_not_installed")
    assert delivery.bundle_path == str(terminal)
    assert "for com.apple.Terminal, which is not a Metabrowser app installed" in delivery.message
    assert delivery.exit_code == PRESENT_NO_APP_EXIT_CODE
    # Copied to an install location, it is still not the Metabrowser app.
    monkeypatch.setattr(
        present, "bundle_lookup", lambda bundle_id: _installed(home, {"CFBundleName": "Terminal"})
    )
    assert deliver(target, ("com.apple.Terminal",)).code == "app_not_marked"


@pytest.mark.skipif(os.name != "posix", reason="the open stand-ins are shell scripts")
def test_a_stray_registration_of_the_release_does_not_hide_an_installed_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, home: Path
) -> None:
    stray = _bundle(tmp_path / "clone", _CURRENT_INFO, "Metabrowser.app")
    installed = _installed(home, _CURRENT_INFO)
    asked: list[str] = []

    def lookup(bundle_id: str) -> Path | None:
        asked.append(bundle_id)
        return stray if bundle_id == RELEASE_BUNDLE_ID else installed

    monkeypatch.setattr(present, "bundle_lookup", lookup)
    log = _record_open(monkeypatch, tmp_path)
    target = Presentable("folder", "/srv/notes", "/view/", ("/srv/notes",))

    delivery = deliver(target, DEFAULT_BUNDLE_IDS)

    assert asked == [RELEASE_BUNDLE_ID, DEV_BUNDLE_ID]
    assert (delivery.code, delivery.bundle_id, delivery.bundle_path) == (
        "not_confirmed",
        DEV_BUNDLE_ID,
        str(installed),
    )
    assert log.read_text() == f"-b {DEV_BUNDLE_ID} /srv/notes\n"
    # With no identifier's bundle passing, the first refusal is the one reported.
    installed_info = installed / "Contents" / "Info.plist"
    installed_info.write_bytes(plistlib.dumps({"CFBundleName": APP_BUNDLE_NAME}))
    asked.clear()
    refused = deliver(target, DEFAULT_BUNDLE_IDS)
    assert asked == [RELEASE_BUNDLE_ID, DEV_BUNDLE_ID]
    assert (refused.code, refused.bundle_id) == ("app_not_installed", RELEASE_BUNDLE_ID)


def test_a_folder_inside_root_is_refused_before_launch_services_is_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def lookup(bundle_id: str) -> Path | None:
        raise AssertionError("a target with no handoff asked LaunchServices")

    monkeypatch.setattr(present, "bundle_lookup", lookup)
    target = Presentable("folder", "/srv/notes", "/view/docs/", None)

    delivery = deliver(target, DEFAULT_BUNDLE_IDS)

    assert (delivery.code, delivery.bundle_id, delivery.bundle_path) == (
        "app_cannot_select_folder",
        None,
        None,
    )
    assert delivery.exit_code == PRESENT_NO_APP_EXIT_CODE
    # Off macOS too: the target is refused for what it is, not for the platform.
    monkeypatch.setattr(present, "bundle_lookup", None)
    assert deliver(target, DEFAULT_BUNDLE_IDS).code == "app_cannot_select_folder"


def test_the_identifiers_are_looked_up_in_order_until_one_is_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    asked: list[str] = []

    def lookup(bundle_id: str) -> Path | None:
        asked.append(bundle_id)
        return None

    monkeypatch.setattr(present, "bundle_lookup", lookup)
    target = Presentable("folder", "/srv/notes", "/view/", ("/srv/notes",))

    delivery = deliver(target, DEFAULT_BUNDLE_IDS)

    assert asked == [RELEASE_BUNDLE_ID, DEV_BUNDLE_ID]
    assert (delivery.code, delivery.bundle_id) == ("app_not_found", None)


@pytest.mark.macos_tier
@pytest.mark.skipif(sys.platform != "darwin", reason="LaunchServices is macOS's")
def test_launch_services_names_a_registered_app_and_no_unknown_one() -> None:
    lookup = present.bundle_lookup
    assert lookup is not None

    finder = lookup("com.apple.finder")
    assert finder is not None and finder.suffix == ".app" and finder.is_dir()
    assert lookup("io.github.jlevy.metabrowser.no-such-variant") is None


# What an agent's sandbox can deny: LaunchServices' database. A lookup under it cannot tell
# an installed app from a missing one, so it must say it could not ask.
_DENY_LAUNCH_SERVICES = (
    '(version 1)(allow default)(deny mach-lookup (global-name "com.apple.lsd.mapdb"))'
)


@pytest.mark.macos_tier
@pytest.mark.skipif(not Path("/usr/bin/sandbox-exec").exists(), reason="needs sandbox-exec")
def test_a_lookup_launch_services_will_not_answer_is_a_lookup_failure() -> None:
    probe = textwrap.dedent(
        """
        from metabrowser.cli.present import AppLookupError, bundle_lookup
        try:
            print("found", bundle_lookup("com.apple.finder"))
        except AppLookupError as exc:
            print("failed", exc)
        """
    )
    result = subprocess.run(
        ["/usr/bin/sandbox-exec", "-p", _DENY_LAUNCH_SERVICES, sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("failed LaunchServices could not be asked"), result.stdout


def test_a_loop_of_links_is_refused_as_unreadable(tmp_path: Path) -> None:
    (tmp_path / "a").symlink_to(tmp_path / "b")
    (tmp_path / "b").symlink_to(tmp_path / "a")

    refusal = resolve_target(str(tmp_path / "a"), "", local=True)

    assert isinstance(refusal, Refusal)
    assert refusal.code == "not_readable"


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="an owner-only folder is readable to root"
)
def test_a_folder_that_cannot_be_read_is_refused(tmp_path: Path) -> None:
    closed = tmp_path / "closed"
    closed.mkdir()
    closed.chmod(0)
    try:
        refusal = resolve_target(str(closed), "", local=True)
    finally:
        closed.chmod(0o700)

    assert isinstance(refusal, Refusal)
    assert refusal.code == "not_readable"


def test_a_path_the_app_cannot_name_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "line\nbreak"
    broken.mkdir()

    refusal = resolve_target(str(broken), "", local=True)

    assert isinstance(refusal, Refusal)
    assert refusal.code == "unaddressable_path"
    # The message stays one line, whatever the path holds.
    assert "\n" not in refusal.message


def test_a_missing_path_is_named_with_its_home_folder_expanded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    refusal = resolve_target("~/missing", "", local=True)

    assert isinstance(refusal, Refusal)
    assert refusal.code == "not_found"
    assert f"{tmp_path}/missing" in refusal.message


_FULL_ID = "0123456789abcdef0123456789abcdef01234567"


def test_a_served_commit_url_opens_at_the_commit_it_resolved_to() -> None:
    # Serving a commit URL opens its page, with the full ID the mirror resolved, which is
    # the page `--present` reports for a full ID; a short one has no page without the
    # mirror, and the commit route refuses it.
    short = RepositorySelection(kind="commit", commit="0123456")
    in_pull = RepositorySelection(kind="commit", commit=_FULL_ID, pull_request=7)

    assert selection_view_href(short, (), commit=_FULL_ID) == f"/commit/{_FULL_ID}"
    assert selection_view_href(in_pull, (), commit=_FULL_ID) == f"/commit/{_FULL_ID}"
    assert selection_view_href(short, ()) == "/view/"
    # Only a commit's selection opens at a commit, whatever the pin resolved to.
    tree = RepositorySelection(kind="tree", ref_and_path=(b"main", b"docs"))
    assert selection_view_href(tree, (b"docs",), commit=_FULL_ID).startswith("/view/")


_DIGEST = "b335630551682c19a781afebcf4d07bf978fb1f8ac04c6bf87428ed5106870f5"


def test_a_served_changes_url_opens_at_the_file_its_anchor_resolved_to() -> None:
    # The file its anchor names, once the provider has resolved it, each segment encoded;
    # without one, the Changes tab itself. A file belongs to the Changes tab only.
    anchored = RepositorySelection(
        kind="pull_request", pull_request=7, pull_tab="files", pull_file=FileAnchor(_DIGEST)
    )
    checks = RepositorySelection(kind="pull_request", pull_request=7, pull_tab="checks")

    assert selection_view_href(anchored, (), pull_file="docs/a b.md") == (
        "/pull/7/files/docs/a%20b.md"
    )
    assert selection_view_href(anchored, ()) == "/pull/7/files"
    assert selection_view_href(checks, (), pull_file="docs/a.md") == "/pull/7/checks"


@pytest.mark.parametrize(
    ("url", "page"),
    [
        # One reading only: the page is known without a mirror.
        ("https://github.com/o/r/tree/main", "/view/"),
        ("https://github.com/o/r/tree/refs/tags/v1.0", "/view/"),
        ("https://github.com/o/r/blob/HEAD/README.md", "/view/g1-UkVBRE1FLm1k"),
        ("https://github.com/o/r/tree/HEAD/docs/a", "/view/g1-ZG9jcw/g1-YQ/"),
        (f"https://github.com/o/r/commit/{_FULL_ID}", f"/commit/{_FULL_ID}"),
        # Only the mirror knows where the ref ends, or what an abbreviation names.
        ("https://github.com/o/r/tree/claude/metab-present/docs/project", None),
        ("https://github.com/o/r/tree/release/v1/docs", None),
        ("https://github.com/o/r/blob/main/docs/guide.md", None),
        ("https://github.com/o/r/tree/refs/heads/release/v1", None),
        # A blob of two segments may be one ref, `release/v1`, with an empty path, which
        # `metab URL` serves at `/view/` (tests/test_github_serve.py), or a ref and a file.
        ("https://github.com/o/r/blob/release/v1", None),
        ("https://raw.githubusercontent.com/o/r/release/v1", None),
        ("https://github.com/o/r/blob/refs/heads/release/v1", None),
        ("https://github.com/o/r/blob/refs/heads/main/README.md", None),
        ("https://raw.githubusercontent.com/o/r/refs/heads/main/README.md", None),
        ("https://github.com/o/r/commit/0123456", None),
        # Which file a Changes tab's anchor names is in the pull request's list of
        # changed files, in the cache; the anchor is a hash of its path.
        ("https://github.com/o/r/pull/7/files", "/pull/7/files"),
        (f"https://github.com/o/r/pull/7/files#diff-{_DIGEST}R3", None),
    ],
)
def test_a_link_has_a_page_only_where_one_reading_gives_it(url: str, page: str | None) -> None:
    target = resolve_target(url, "", local=False)

    assert isinstance(target, Presentable)
    assert target.page == page


# ── Deciding where a target goes ────────────────────────────────────

_FOLDER = Presentable("folder", "/srv/notes", "/view/", ("/srv/notes",))
_INSIDE = Presentable("folder", "/srv/notes", "/view/docs/", None)


def _lookup_from(
    monkeypatch: pytest.MonkeyPatch, apps: dict[str, Path], *, unreachable: bool = False
) -> list[str]:
    """Answer LaunchServices lookups from *apps*; return the identifiers asked about."""

    asked: list[str] = []

    def lookup(bundle_id: str) -> Path | None:
        asked.append(bundle_id)
        if unreachable:
            raise AppLookupError("LaunchServices could not be asked (error -10661)")
        return apps.get(bundle_id)

    monkeypatch.setattr(present, "bundle_lookup", lookup)
    return asked


def test_every_app_refusal_is_a_delivery_code_and_a_decision_code() -> None:
    refusals = set(get_args(present.AppRefusalCode.__value__))
    assert refusals <= set(get_args(DeliveryCode.__value__))
    assert refusals <= set(get_args(DecisionCode.__value__))
    # Under `auto`, exactly the refusals that end with "no app" fall back to a browser.
    assert {code for code in refusals if DELIVERY_EXIT_CODES[code] != PRESENT_NO_APP_EXIT_CODE} == {
        "lookup_failed"
    }


@pytest.mark.parametrize(
    ("choice", "app", "unreachable", "target", "expected"),
    [
        ("auto", True, False, _FOLDER, ("app", "app_found", None)),
        ("auto", False, False, _FOLDER, ("browser", "browser_fallback", "app_not_found")),
        ("auto", True, False, _INSIDE, ("browser", "browser_fallback", "app_cannot_select_folder")),
        ("auto", True, True, _FOLDER, ("none", "lookup_failed", None)),
        ("app", True, False, _FOLDER, ("app", "app_found", None)),
        ("app", False, False, _FOLDER, ("none", "app_not_found", None)),
        ("app", True, False, _INSIDE, ("none", "app_cannot_select_folder", None)),
        ("app", True, True, _FOLDER, ("none", "lookup_failed", None)),
        ("browser", True, False, _FOLDER, ("browser", "browser_preferred", None)),
        ("browser", True, True, _INSIDE, ("browser", "browser_preferred", None)),
    ],
)
def test_the_preference_and_what_looking_found_decide_where_a_target_goes(
    monkeypatch: pytest.MonkeyPatch,
    home: Path,
    choice: OpenInChoice,
    app: bool,
    unreachable: bool,
    target: Presentable,
    expected: tuple[str, str, str | None],
) -> None:
    bundle = _installed(home, _CURRENT_INFO)
    asked = _lookup_from(
        monkeypatch, {DEV_BUNDLE_ID: bundle} if app else {}, unreachable=unreachable
    )

    decision = decide(target, OpenInPreference(choice, "config"), DEFAULT_BUNDLE_IDS)

    fallback = decision.fallback[0] if decision.fallback else None
    assert (decision.delivers_to, decision.code, fallback) == expected
    report = decision.as_json()
    assert (report["open_in"], report["open_in_source"]) == (choice, "config")
    assert report["delivers_to"] == decision.delivers_to
    if choice == "browser":
        # `browser` looks for no app at all.
        assert (asked, decision.finding, report["bundle_id"]) == ([], None, None)
    elif target.handoff is None:
        # A target the app can never take is refused before LaunchServices is asked.
        assert asked == []
    if decision.code == "app_found":
        assert (report["bundle_id"], report["bundle_path"]) == (DEV_BUNDLE_ID, str(bundle))


def _configured(directory: Path, settings: str) -> Path:
    """A configuration directory whose config.yml's ``config`` mapping adds *settings*."""

    ensure_private_directory(directory)
    header = (
        "softschema:\n  contract: metabrowser.config:ApplicationConfig/v1\n"
        "  envelope: config\n  status: permissive\n"
        "config:\n  format: f01\n  written_by: 0.13.0\n  upgrades: []\n"
    )
    write_private_file_atomic(directory, CONFIG_RECORD, (header + settings).encode())
    return directory


@pytest.mark.parametrize(
    ("choice", "app", "expected"),
    [
        ("browser", True, ("none", "browser_off", None)),
        ("auto", False, ("none", "browser_off", "app_not_found")),
        ("auto", True, ("app", "app_found", None)),
        ("app", False, ("none", "app_not_found", None)),
    ],
)
def test_a_browser_that_config_yml_turns_off_takes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    home: Path,
    tmp_path: Path,
    choice: OpenInChoice,
    app: bool,
    expected: tuple[str, str, str | None],
) -> None:
    """``present_browser: false`` turns a decision for a browser into one for nowhere,
    whatever the preference, and leaves a decision for the app as it was."""

    bundle = _installed(home, _CURRENT_INFO)
    _lookup_from(monkeypatch, {DEV_BUNDLE_ID: bundle} if app else {})
    off = _configured(tmp_path / "config", "  present_browser: false\n")

    decided = decide(_FOLDER, OpenInPreference(choice, "flag"), DEFAULT_BUNDLE_IDS)
    decision = allow_browser(decided, off)

    fallback = decision.fallback[0] if decision.fallback else None
    assert (decision.delivers_to, decision.code, fallback) == expected
    if decision.code == "browser_off":
        assert DELIVERY_EXIT_CODES["browser_off"] == PRESENT_NO_APP_EXIT_CODE
        assert "present_browser is false in config.yml" in decision.message
    # Allowed, or unset, a browser decision stands.
    on = _configured(tmp_path / "on", "  present_browser: true\n")
    assert allow_browser(decided, on) == decided
    assert allow_browser(decided, tmp_path / "unset") == decided


def test_a_config_yml_it_cannot_read_starts_no_server(tmp_path: Path) -> None:
    broken = tmp_path / "config"
    ensure_private_directory(broken)
    write_private_file_atomic(broken, CONFIG_RECORD, b"config: [unclosed\n")
    browser = decide(_FOLDER, OpenInPreference("browser", "flag"), ())
    with pytest.raises(OpenInError, match="is not YAML"):
        allow_browser(browser, broken)
    # A decision for nowhere, or for the app, does not read the file.
    nowhere = present.Decision(None, "none", "lookup_failed", "blocked", None)
    assert allow_browser(nowhere, broken) is nowhere


@pytest.mark.parametrize(
    ("line", "url"),
    [
        ("Serving /srv/notes at http://127.0.0.1:8413/view/", "http://127.0.0.1:8413/view/"),
        (
            "Serving /srv/notes at http://127.0.0.1:8413/view/README.md  [dev build: 0.12.1.dev3]",
            "http://127.0.0.1:8413/view/README.md",
        ),
        # The root may hold " at "; the address is the token after the last one.
        ("Serving /srv/met at noon at http://127.0.0.1:8414/", "http://127.0.0.1:8414/"),
        ("Serving /srv/notes at http://[::1]:8413/view/", "http://[::1]:8413/view/"),
        ("Serving /srv/notes at http://example.com:8413/view/", None),
        ("Serving /srv/notes at https://127.0.0.1:8413/view/", None),
        ("Serving /srv/notes at http://127.0.0.1/view/", None),
        ("Serving /srv/notes at http://127.0.0.1:99999/view/", None),
        ("Serving /srv/notes at http://someone@127.0.0.1:8413/view/", None),
        ("Serving /srv/notes at http://127.0.0.1:8413/view/ (ready)", None),
        ("Cloning https://github.com/octo/demo at http://127.0.0.1:8413/", None),
        ("Serving /srv/notes", None),
    ],
)
def test_only_a_serving_line_with_a_loopback_address_names_the_server(
    line: str, url: str | None
) -> None:
    assert serving_url(line) == url


# ── Serving for a browser ───────────────────────────────────────────


def _server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: str) -> Path:
    """Serve with a stand-in that records its arguments and runs *body*; return the record."""

    record = tmp_path / "server.args"
    script = tmp_path / "server-stand-in"
    script.write_text(f'#!/bin/sh\nprintf \'%s\\n\' "$*" > "{record}"\n{body}\n')
    script.chmod(0o755)
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(present, "server_command", (str(script),))
    monkeypatch.setattr(present, "server_log_directory", lambda: str(logs))
    return record


def _stop(pid: int | None) -> None:
    """Stop and reap a server a test started, unless it has exited and been reaped."""

    if pid is None:
        return
    try:
        reaped, _status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return
    if reaped == 0:
        os.kill(pid, signal.SIGTERM)
        os.waitpid(pid, 0)


_SERVES: str = f'exec "{sys.executable}" -I "{SERVER_STAND_IN}" "$@"'
_LOOPBACK_VIEW = re.compile(r"http://127\.0\.0\.1:\d+/view/")


def _notes(tmp_path: Path) -> tuple[Presentable, str]:
    """A folder target and ROOT as given for it."""

    notes = tmp_path / "notes"
    notes.mkdir(exist_ok=True)
    return Presentable("folder", str(notes.resolve()), "/view/", None), str(notes)


_DEMO = Presentable(
    "repository", "https://github.com/octo/demo", "/view/", ("https://github.com/octo/demo",)
)


def _other_server(tmp_path: Path) -> tuple[subprocess.Popen[str], str]:
    """A stand-in serving another folder, and the address it says it serves at."""

    other = tmp_path / "other"
    other.mkdir()
    server = subprocess.Popen(
        [sys.executable, "-I", str(SERVER_STAND_IN), "--", str(other)],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert server.stdout is not None
    url = serving_url(server.stdout.readline().strip())
    assert url is not None
    return server, url


posix_only = pytest.mark.skipif(os.name != "posix", reason="a detached server is POSIX's")


@posix_only
def test_a_server_that_says_where_it_serves_runs_detached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    record = _server(monkeypatch, tmp_path, _SERVES)
    target, value = _notes(tmp_path)

    delivery = serve_detached(target, value, "docs/guide.md")
    try:
        assert (delivery.delivered_to, delivery.code, delivery.exit_code) == (
            "browser",
            "server_started",
            0,
        )
        assert delivery.url is not None and _LOOPBACK_VIEW.fullmatch(delivery.url)
        # `metab ROOT` with its --path, options before `--`, and without --no-open, so it
        # opens the browser itself.
        assert record.read_text() == f"--path docs/guide.md -- {value}\n"
        assert delivery.pid is not None and delivery.log is not None
        # A session of its own, so neither this command's exit nor a hangup reaches it.
        assert os.getsid(delivery.pid) == delivery.pid
        log = Path(delivery.log)
        assert log.parent == tmp_path / "logs" and log.name.startswith(SERVER_LOG_PREFIX)
        assert log.stat().st_mode & 0o777 == 0o600
        assert log.read_text().startswith(f"Serving {value} at ")
        assert f"stop it with kill {delivery.pid}" in delivery.message
    finally:
        _stop(delivery.pid)


@posix_only
def test_a_checkout_is_recognized_as_the_server_that_answers_for_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A folder that holds a `.git` entry answers `kind` `git`, and `--present` still sees
    its own server: it once waited its 20 s for a `folder` and reported `server_starting`."""

    _server(monkeypatch, tmp_path, _SERVES)
    target, value = _notes(tmp_path)
    (tmp_path / "notes" / ".git").mkdir()

    delivery = serve_detached(target, value, "")
    try:
        assert (delivery.delivered_to, delivery.code, delivery.exit_code) == (
            "browser",
            "server_started",
            0,
        )
        assert delivery.url is not None and _LOOPBACK_VIEW.fullmatch(delivery.url)
    finally:
        _stop(delivery.pid)


@posix_only
def test_progress_and_an_overlong_line_do_not_hide_the_serving_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _server(
        monkeypatch,
        tmp_path,
        "printf 'Receiving objects:  10%%\\rReceiving objects: 100%%\\r\\n'\n"
        "head -c 40000 /dev/zero | tr '\\000' x\necho\n" + _SERVES,
    )

    delivery = serve_detached(*_notes(tmp_path), "")
    try:
        assert delivery.code == "server_started"
        assert delivery.url is not None and _LOOPBACK_VIEW.fullmatch(delivery.url)
    finally:
        _stop(delivery.pid)


@posix_only
def test_a_server_that_exits_first_failed_and_names_its_last_line_and_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _server(
        monkeypatch,
        tmp_path,
        "echo 'Cloning octo/demo'\necho 'Error: no such repository' >&2\nexit 2",
    )

    delivery = serve_detached(_DEMO, _DEMO.root, "")

    assert (delivery.delivered_to, delivery.code, delivery.exit_code) == (
        "none",
        "server_failed",
        1,
    )
    assert (delivery.url, delivery.pid) == (None, None)
    assert delivery.log is not None
    assert delivery.message == (
        "the metab server for the target exited with status 2 before it said where it "
        f"serves: Error: no such repository; its output is in {delivery.log}"
    )


@posix_only
def test_a_server_that_has_not_said_where_by_the_deadline_is_still_starting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _server(monkeypatch, tmp_path, "echo 'Cloning octo/demo'\nexec sleep 30")
    monkeypatch.setattr(present, "server_announce_timeout_s", 0.3)

    delivery = serve_detached(_DEMO, _DEMO.root, "")
    try:
        assert (delivery.delivered_to, delivery.code, delivery.exit_code) == (
            "browser",
            "server_starting",
            0,
        )
        assert delivery.url is None and delivery.pid is not None
        assert f"stop it with kill {delivery.pid}" in delivery.message
        assert os.waitpid(delivery.pid, os.WNOHANG) == (0, 0)
    finally:
        _stop(delivery.pid)


@posix_only
def test_the_server_holds_no_descriptor_this_command_was_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A harness reading this command's output to its end must not wait on the server."""

    _server(monkeypatch, tmp_path, _SERVES)
    read_end, write_end = os.pipe()
    os.set_inheritable(write_end, True)
    delivery = None
    try:
        delivery = serve_detached(*_notes(tmp_path), "")
        assert delivery.code == "server_started"
        os.close(write_end)
        write_end = -1
        os.set_blocking(read_end, False)
        # Every writer is closed, so the read ends at once instead of waiting on the server.
        assert os.read(read_end, 1) == b""
    finally:
        if write_end != -1:
            os.close(write_end)
        os.close(read_end)
        _stop(delivery.pid if delivery else None)


@posix_only
def test_a_server_that_cannot_start_or_log_is_reported_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _server(monkeypatch, tmp_path, _SERVES)
    monkeypatch.setattr(present, "server_command", (str(tmp_path / "no-such-metab"),))
    target, value = _notes(tmp_path)
    missing = serve_detached(target, value, "")
    assert (missing.code, missing.exit_code, missing.pid) == ("server_failed", 1, None)
    assert missing.message.startswith("the metab server could not start (")

    monkeypatch.setattr(present, "server_log_directory", lambda: str(tmp_path / "no-such-logs"))
    unlogged = serve_detached(target, value, "")
    assert (unlogged.code, unlogged.log) == ("server_failed", None)
    assert unlogged.message.startswith("no log file for the server could be made (")


@posix_only
def test_a_server_that_loses_the_address_it_named_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two servers started together can name the same free port; the second to bind
    exits. The address answers for the other server's root, so this one is not reported
    started, and its exit is reported with its last line."""

    other, url = _other_server(tmp_path)
    try:
        _server(monkeypatch, tmp_path, f"SERVER_STAND_IN_TAKEN_URL={url} {_SERVES}")
        delivery = serve_detached(*_notes(tmp_path), "")
    finally:
        other.terminate()
        other.wait()

    assert (delivery.delivered_to, delivery.code, delivery.exit_code, delivery.url) == (
        "none",
        "server_failed",
        1,
        None,
    )
    assert delivery.message.startswith(
        "the metab server for the target exited with status 1 after it said where it "
        "serves: ERROR:    [Errno 48] error while attempting to bind on address: "
        "address already in use; its output is in "
    )


@posix_only
def test_an_address_that_answers_for_another_root_is_not_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A server that names an address another root's server answers, and keeps running,
    is still starting when the wait ends, and the report gives no address."""

    other, url = _other_server(tmp_path)
    try:
        _server(monkeypatch, tmp_path, f'echo "Serving notes at {url}"\nexec sleep 30')
        # Long enough for a loaded machine to start the shell that prints the line.
        monkeypatch.setattr(present, "server_announce_timeout_s", 3.0)
        delivery = serve_detached(*_notes(tmp_path), "")
        try:
            assert (delivery.delivered_to, delivery.code, delivery.url) == (
                "browser",
                "server_starting",
                None,
            )
            assert f"said it serves at {url}, which has not answered as the target's" in (
                delivery.message
            )
        finally:
            _stop(delivery.pid)
    finally:
        other.terminate()
        other.wait()


@pytest.mark.parametrize(
    ("answer", "target", "same"),
    [
        ({"kind": "folder", "full_name": "<notes>"}, "notes", True),
        # A checkout's server says `git`, and is still the target's own.
        ({"kind": "git", "full_name": "<notes>"}, "notes", True),
        ({"kind": "git", "full_name": "<notes>/docs"}, "notes", False),
        ({"kind": "folder", "full_name": "<notes>/docs"}, "notes", False),
        ({"kind": "mirror", "full_name": "<notes>"}, "notes", False),
        ({"kind": "mirror", "full_name": "github.com/octo/demo@main"}, "demo", True),
        ({"kind": "mirror", "full_name": "github.com/Octo/Demo@0123456789ab"}, "demo", True),
        ({"kind": "mirror", "full_name": "github.com/octo/demo#7"}, "demo", True),
        ({"kind": "mirror", "full_name": "github.com/octo/demo-fork@main"}, "demo", False),
        ({"kind": "folder", "full_name": "github.com/octo/demo@main"}, "demo", False),
        ({"kind": "mirror"}, "demo", False),
        (["github.com/octo/demo@main"], "demo", False),
    ],
)
def test_an_identity_answer_names_the_target_or_not(
    tmp_path: Path, answer: object, target: str, same: bool
) -> None:
    notes, _value = _notes(tmp_path)
    if isinstance(answer, dict) and answer.get("kind") in ("folder", "git"):
        # A folder outside the home folder is named by its path, as `folder_identity` says.
        answer = {**answer, "full_name": answer["full_name"].replace("<notes>", notes.root)}
    chosen = notes if target == "notes" else _DEMO
    assert present._is_target_identity(answer, chosen) is same


def _peer(respond: Callable[[socket.socket, threading.Event], None]) -> tuple[str, threading.Event]:
    """A loopback peer that reads one request and answers it with *respond*, its address
    as a server prints it, and an event that tells a slow answer to stop."""

    listener = socket.create_server(("127.0.0.1", 0))
    stop = threading.Event()

    def serve() -> None:
        with listener:
            connection, _address = listener.accept()
            with connection:
                connection.recv(4096)
                # The request may close before a slow answer ends.
                with suppress(OSError):
                    respond(connection, stop)

    threading.Thread(target=serve, daemon=True).start()
    host, port = listener.getsockname()[:2]
    return f"http://{host}:{port}/view/", stop


def _answer(response: bytes) -> Callable[[socket.socket, threading.Event], None]:
    def respond(connection: socket.socket, _stop: threading.Event) -> None:
        connection.sendall(response)

    return respond


def test_an_identity_request_ends_on_time_however_slowly_the_peer_sends(
    tmp_path: Path,
) -> None:
    """A peer that sends a byte at a time, each sooner than the request's timeout, would
    keep a per-read timeout waiting for the whole 64 KiB; the request ends at its total
    time instead, and the address is not the target's."""

    def drip(connection: socket.socket, stop: threading.Event) -> None:
        connection.sendall(b"HTTP/1.0 200 OK\r\nX-Drip: ")
        while not stop.wait(0.02):
            connection.sendall(b"a")

    url, stop = _peer(drip)
    started = time.monotonic()
    try:
        answered = present._answers_as_target(url, _notes(tmp_path)[0], 0.5)
    finally:
        stop.set()
    assert answered is False
    # The request's 0.5 s and room for a loaded machine; reading the 64 KiB a byte at a
    # time takes over 20 minutes.
    assert time.monotonic() - started < 5.0


@pytest.mark.parametrize(
    ("response", "same"),
    [
        (b"HTTP/1.1 200 OK\r\nContent-Length: <length>\r\n\r\n<identity>", True),
        (b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n<identity>", True),
        (b"HTTP/1.1 404 Not Found\r\n\r\n<identity>", False),
        (b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n<identity>", False),
        (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n<identity>", False),
        (b"HTTP/1.1 200 OK\r\nnot a header\r\n\r\n<identity>", False),
        (b"<identity>", False),
        # Nested deeper than Python's recursion limit: the parser's RecursionError.
        (b"HTTP/1.0 200 OK\r\n\r\n" + b"[" * 60_000, False),
        (b"HTTP/1.0 200 OK\r\n\r\n<identity>" + b" " * present.IDENTITY_MAX_BYTES, False),
    ],
)
def test_an_identity_response_answers_as_the_target_or_not(
    tmp_path: Path, response: bytes, same: bool
) -> None:
    """What the request reads: one ``200`` response, read to its close, its declared
    length if any, at most ``IDENTITY_MAX_BYTES``, and a body that parses as JSON."""

    target = _notes(tmp_path)[0]
    identity = json.dumps({"kind": "folder", "full_name": target.root}).encode()
    response = response.replace(b"<length>", str(len(identity)).encode())
    url, _stop = _peer(_answer(response.replace(b"<identity>", identity)))
    assert present._answers_as_target(url, target, 5.0) is same


@posix_only
def test_a_real_server_serves_the_target_detached_until_killed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The production command, with a stand-in browser: the address answers, the server
    opens it in the browser, and ``kill`` stops it, as the report says."""

    root = tmp_path / "notes"
    root.mkdir()
    (root / "README.md").write_text("# Notes\n")
    opened = tmp_path / "browser.log"
    browser = tmp_path / "browser"
    browser.write_text(f'#!/bin/sh\nprintf \'%s\\n\' "$1" >> "{opened}"\n')
    browser.chmod(0o755)
    monkeypatch.setenv("BROWSER", str(browser))
    # `metab ROOT` searches upward from the default port, which a parallel worker's
    # server can take between this server's probe and its bind; an ephemeral port
    # starts the search where no fixed-port server is.
    monkeypatch.setattr(
        present, "server_command", (*present.SERVER_COMMAND, "--port", str(_free_port()))
    )
    monkeypatch.setattr(present, "server_log_directory", lambda: str(tmp_path))

    target = resolve_target(str(root), "README.md", local=False)
    assert isinstance(target, Presentable)
    delivery = serve_detached(target, str(root), "README.md")
    try:
        assert delivery.code == "server_started", delivery.message
        assert delivery.url is not None and delivery.pid is not None
        assert delivery.url.startswith("http://127.0.0.1:")
        assert delivery.url.endswith("/view/README.md")
        # The server opens the browser once its page answers, a moment after the line.
        deadline = time.monotonic() + 15
        while not (opened.exists() and opened.read_text()) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert opened.read_text().splitlines() == [delivery.url]
        direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with direct.open(delivery.url, timeout=10) as response:
            assert response.status == 200
        os.kill(delivery.pid, signal.SIGTERM)
        _reaped, status = os.waitpid(delivery.pid, 0)
        assert os.WIFEXITED(status) or os.WIFSIGNALED(status)
    finally:
        _stop(delivery.pid)


# ── What --doctor reports ───────────────────────────────────────────


def test_doctor_reports_a_browser_preference_and_looks_for_no_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _lookup_from(monkeypatch, {})
    monkeypatch.setenv(OPEN_IN_ENV, "browser")

    report = doctor_open_in()

    assert report.section == {
        "value": "browser",
        "source": "environment",
        "present_browser": True,
        "app": None,
    }
    assert (
        report.line == "metab --doctor: open_in browser (environment); --present looks for no app"
    )
    assert (report.problems, asked) == ((), [])


def test_doctor_reports_the_app_auto_finds(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    bundle = _installed(home, _CURRENT_INFO)
    _lookup_from(monkeypatch, {DEV_BUNDLE_ID: bundle})
    monkeypatch.delenv(BUNDLE_ID_ENV, raising=False)

    report = doctor_open_in()

    assert report.section == {
        "value": "auto",
        "source": "default",
        "present_browser": True,
        "app": {
            "found": True,
            "bundle_id": DEV_BUNDLE_ID,
            "bundle_path": str(bundle),
            "code": "app_found",
            "reason": "the app takes a target",
            "minimum_metab": None,
        },
    }
    assert report.line == (
        f"metab --doctor: open_in auto (default); the app: {bundle} ({DEV_BUNDLE_ID})"
    )
    assert report.problems == ()
    assert (report.app_path, report.app_minimum_metab) == (str(bundle), None)


@pytest.mark.parametrize(
    ("declared", "minimum"),
    [
        ("0.13.0", "0.13.0"),
        # Only a nonempty string names a release: anything else is no minimum.
        ("", None),
        (13, None),
        (["0.13.0"], None),
    ],
)
def test_doctor_reads_the_minimum_metab_the_app_found_declares(
    monkeypatch: pytest.MonkeyPatch, home: Path, declared: object, minimum: str | None
) -> None:
    """The `metab` check of `--doctor` compares this `metab` with it (`cli/doctor.py`)."""

    bundle = _installed(home, {**_CURRENT_INFO, MINIMUM_METAB_KEY: declared})
    _lookup_from(monkeypatch, {DEV_BUNDLE_ID: bundle})
    monkeypatch.delenv(BUNDLE_ID_ENV, raising=False)

    report = doctor_open_in()

    app = report.section["app"]
    assert isinstance(app, dict)
    assert app["minimum_metab"] == minimum
    assert (report.app_path, report.app_minimum_metab) == (str(bundle), minimum)


@pytest.mark.parametrize(
    ("choice", "unreachable", "problem"),
    [
        ("auto", False, False),
        ("app", False, True),
        # Only where the command runs decides whether LaunchServices answers.
        ("app", True, False),
    ],
)
def test_doctor_reports_no_app_as_a_problem_only_when_the_preference_needs_one(
    monkeypatch: pytest.MonkeyPatch, choice: str, unreachable: bool, problem: bool
) -> None:
    _lookup_from(monkeypatch, {}, unreachable=unreachable)
    monkeypatch.delenv(BUNDLE_ID_ENV, raising=False)
    monkeypatch.setenv(OPEN_IN_ENV, choice)

    report = doctor_open_in()

    app = report.section["app"]
    assert isinstance(app, dict)
    assert app["found"] is False
    assert app["code"] == ("lookup_failed" if unreachable else "app_not_found")
    assert report.line.endswith(f"; the app: none ({app['code']})")
    if problem:
        assert report.problems == (
            f"open_in is app (environment), and no app takes a target: {app['reason']}",
        )
    else:
        assert report.problems == ()


@pytest.mark.parametrize(
    ("choice", "app", "problem"),
    [
        ("browser", False, "open_in is browser (environment), and present_browser is false"),
        ("auto", False, "open_in is auto (environment), no app takes a target ("),
        ("auto", True, None),
    ],
)
def test_doctor_reports_a_browser_turned_off_and_settings_that_open_nothing(
    monkeypatch: pytest.MonkeyPatch, home: Path, choice: str, app: bool, problem: str | None
) -> None:
    bundle = _installed(home, _CURRENT_INFO)
    _lookup_from(monkeypatch, {DEV_BUNDLE_ID: bundle} if app else {})
    monkeypatch.delenv(BUNDLE_ID_ENV, raising=False)
    monkeypatch.setenv(OPEN_IN_ENV, choice)
    _configured(configuration_directory(), "  present_browser: false\n")

    report = doctor_open_in()

    assert report.section["present_browser"] is False
    assert report.line.endswith("; present_browser: false, so no server for a browser")
    if problem is None:
        assert report.problems == ()
    else:
        assert len(report.problems) == 1 and report.problems[0].startswith(problem)
        assert report.problems[0].endswith(": --present opens nothing")


def test_doctor_reports_a_preference_it_cannot_read_and_still_looks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _lookup_from(monkeypatch, {})
    monkeypatch.delenv(BUNDLE_ID_ENV, raising=False)
    monkeypatch.setenv(OPEN_IN_ENV, "sometimes")

    report = doctor_open_in()

    assert (report.section["value"], report.section["source"]) == (None, None)
    assert report.problems == (
        f"open_in: {OPEN_IN_ENV} is not auto, app, or browser; set it to one, or unset it",
    )
    assert report.line.startswith("metab --doctor: open_in unreadable; the app: none")
    assert asked == list(DEFAULT_BUNDLE_IDS)
