"""``metab TARGET --present``: what it reads, what it hands the app, and how it finds one.

The transcripts are the contract: ``tests/golden/cli-present.tryscript.md`` pins every
target shape and refusal of ``--present --dry-run``, and
``tests/golden/cli-present-delivery.txt`` (``tests/test_cli_present_golden.py``) pins
delivery with a recording ``open`` and fixture app bundles. This module checks what a
transcript cannot: the constants against the app's build scripts, the Info.plist reader's
edges, the bundle identifier's sources, and the LaunchServices lookup on a Mac.
"""

from __future__ import annotations

import os
import plistlib
import re
import struct
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import typer

from metabrowser.cache.urls import RepositorySelection
from metabrowser.cli import present
from metabrowser.cli.exit_codes import (
    PRESENT_BLOCKED_EXIT_CODE,
    PRESENT_NO_APP_EXIT_CODE,
    PRESENT_REFUSED_EXIT_CODE,
)
from metabrowser.cli.present import (
    BUNDLE_ID_ENV,
    DEFAULT_BUNDLE_IDS,
    DELIVERY_EXIT_CODES,
    DEV_BUNDLE_ID,
    INFO_PLIST_MAX_BYTES,
    OPENS_URLS_KEY,
    RELEASE_BUNDLE_ID,
    AppLookupError,
    Presentable,
    Refusal,
    declares_marker,
    deliver,
    present_bundle_ids,
    resolve_target,
)
from metabrowser.cli.selection_href import selection_view_href
from metabrowser.errors import CLIError

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON_SH = REPO_ROOT / "apps/macos/scripts/common.sh"


def test_the_bundle_identifiers_are_the_ones_the_app_is_built_with() -> None:
    text = COMMON_SH.read_text(encoding="utf-8")
    variants = dict(re.findall(r'^\s*(release|dev)\)\n\s*bundle_id="([^"]+)"', text, re.MULTILINE))

    assert variants == {"release": RELEASE_BUNDLE_ID, "dev": DEV_BUNDLE_ID}
    # Release first: an installed release is the app a user means.
    assert DEFAULT_BUNDLE_IDS == (RELEASE_BUNDLE_ID, DEV_BUNDLE_ID)


def test_every_delivery_code_ends_with_its_own_kind_of_status() -> None:
    # Delivered is 0; no app to take it and blocked are apart, so a caller can tell
    # "install the app" from "run this where LaunchServices answers" by the status alone.
    assert DELIVERY_EXIT_CODES["not_confirmed"] == 0
    statuses = set(DELIVERY_EXIT_CODES.values()) - {0}
    assert statuses == {PRESENT_NO_APP_EXIT_CODE, PRESENT_BLOCKED_EXIT_CODE}
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


@pytest.mark.parametrize(
    ("info", "expected"),
    [
        ({OPENS_URLS_KEY: True}, True),
        ({OPENS_URLS_KEY: False}, False),
        # Only a boolean declares it: a string or a number is not the key the app writes.
        ({OPENS_URLS_KEY: "YES"}, False),
        ({OPENS_URLS_KEY: 1}, False),
        ({}, False),
        ([OPENS_URLS_KEY], False),
        (b"not a property list", False),
        # Malformed property lists raise more than plistlib's own error: ExpatError for
        # the first three, IndexError and AttributeError for the next two; a deep binary
        # one raises RecursionError (below).
        (b'<?xml version="1.0"?><plist><dict><key>a</key>', False),
        (b"<plist><dict><key>a</key><true/></array></plist>", False),
        (b"<plist><dict>\x00</dict></plist>", False),
        (b"<plist><key>a</key></plist>", False),
        (b"<plist><date>nope</date></plist>", False),
    ],
)
def test_only_a_true_marker_says_the_app_takes_targets(
    tmp_path: Path, info: dict[str, object] | list[str] | bytes, expected: bool
) -> None:
    assert declares_marker(_bundle(tmp_path, info)) is expected


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


def test_a_deeply_nested_binary_info_plist_is_no_marker(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, _nested_binary_plist(5000))

    assert declares_marker(bundle) is False


def test_a_bundle_without_a_readable_info_plist_has_no_marker(tmp_path: Path) -> None:
    (tmp_path / "Bare.app").mkdir()

    assert declares_marker(tmp_path / "Bare.app") is False
    assert declares_marker(tmp_path / "Missing.app") is False


def test_an_oversized_info_plist_is_not_read(tmp_path: Path) -> None:
    padding = "x" * INFO_PLIST_MAX_BYTES
    bundle = _bundle(tmp_path, {OPENS_URLS_KEY: True, "Padding": padding})

    assert declares_marker(bundle) is False


@pytest.mark.skipif(os.name != "posix", reason="a FIFO and /dev/zero are POSIX")
def test_an_info_plist_that_is_not_a_regular_file_is_not_waited_on(tmp_path: Path) -> None:
    fifo = tmp_path / "Pipe.app" / "Contents"
    fifo.mkdir(parents=True)
    os.mkfifo(fifo / "Info.plist")
    device = tmp_path / "Device.app" / "Contents"
    device.mkdir(parents=True)
    (device / "Info.plist").symlink_to("/dev/zero")

    # A FIFO with no writer would block an ordinary open for good.
    assert declares_marker(tmp_path / "Pipe.app") is False
    assert declares_marker(tmp_path / "Device.app") is False


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


@pytest.mark.skipif(os.name != "posix", reason="the refusing open is a shell script")
def test_a_bundle_without_the_marker_is_sent_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # An override can name any app, such as Terminal, which runs a `.command` file it is
    # handed, so a file goes only where a URL goes: to a bundle with the marker.
    terminal = _bundle(tmp_path, {"CFBundleIdentifier": "com.apple.Terminal"}, "Terminal.app")
    monkeypatch.setattr(present, "bundle_lookup", lambda bundle_id: terminal)
    _refuse_to_open(monkeypatch, tmp_path)
    script = tmp_path / "run-me.command"
    script.write_text("echo hi\n")
    target = resolve_target(str(script), "", local=True)
    assert isinstance(target, Presentable)

    delivery = deliver(target, ("com.apple.Terminal",))

    assert (delivery.delivered_to, delivery.code) == ("none", "app_not_marked")
    assert delivery.bundle_path == str(terminal)
    assert delivery.exit_code == PRESENT_NO_APP_EXIT_CODE


def test_the_first_app_launch_services_has_is_the_one_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    asked: list[str] = []
    dev = _bundle(tmp_path, {})

    def lookup(bundle_id: str) -> Path | None:
        asked.append(bundle_id)
        return dev if bundle_id == DEV_BUNDLE_ID else None

    monkeypatch.setattr(present, "bundle_lookup", lookup)
    # A folder inside the root is refused after the lookup, so nothing runs `open`.
    target = Presentable("folder", "/srv/notes", "/view/docs/", None)

    delivery = deliver(target, DEFAULT_BUNDLE_IDS)

    assert asked == [RELEASE_BUNDLE_ID, DEV_BUNDLE_ID]
    assert (delivery.delivered_to, delivery.bundle_id) == ("none", DEV_BUNDLE_ID)
    assert delivery.code == "app_cannot_select_folder"


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


@pytest.mark.parametrize(
    ("url", "page"),
    [
        # One reading only: the page is known without a mirror.
        ("https://github.com/o/r/tree/main", "/view/"),
        ("https://github.com/o/r/tree/refs/tags/v1.0", "/view/"),
        ("https://github.com/o/r/blob/refs/heads/main/README.md", "/view/g1-UkVBRE1FLm1k"),
        (
            "https://raw.githubusercontent.com/o/r/refs/heads/main/README.md",
            "/view/g1-UkVBRE1FLm1k",
        ),
        ("https://github.com/o/r/tree/HEAD/docs/a", "/view/g1-ZG9jcw/g1-YQ/"),
        (f"https://github.com/o/r/commit/{_FULL_ID}", f"/commit/{_FULL_ID}"),
        # Only the mirror knows where the ref ends, or what an abbreviation names.
        ("https://github.com/o/r/tree/claude/metab-present/docs/project", None),
        ("https://github.com/o/r/tree/release/v1/docs", None),
        ("https://github.com/o/r/blob/main/docs/guide.md", None),
        ("https://github.com/o/r/tree/refs/heads/release/v1", None),
        ("https://github.com/o/r/commit/0123456", None),
    ],
)
def test_a_link_has_a_page_only_where_one_reading_gives_it(url: str, page: str | None) -> None:
    target = resolve_target(url, "", local=False)

    assert isinstance(target, Presentable)
    assert target.page == page
