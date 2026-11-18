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
import sys
from pathlib import Path

import pytest
import typer

from metabrowser.cache.providers import installed_providers, url_reducers
from metabrowser.cli import present
from metabrowser.cli.present import (
    BUNDLE_ID_ENV,
    DEFAULT_BUNDLE_IDS,
    DEV_BUNDLE_ID,
    INFO_PLIST_MAX_BYTES,
    OPENS_URLS_KEY,
    RELEASE_BUNDLE_ID,
    Presentable,
    Refusal,
    deliver,
    opens_urls,
    present_bundle_ids,
    resolve_target,
)
from metabrowser.errors import CLIError

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON_SH = REPO_ROOT / "apps/macos/scripts/common.sh"


def test_the_bundle_identifiers_are_the_ones_the_app_is_built_with() -> None:
    text = COMMON_SH.read_text(encoding="utf-8")
    variants = dict(re.findall(r'^\s*(release|dev)\)\n\s*bundle_id="([^"]+)"', text, re.MULTILINE))

    assert variants == {"release": RELEASE_BUNDLE_ID, "dev": DEV_BUNDLE_ID}
    # Release first: an installed release is the app a user means.
    assert DEFAULT_BUNDLE_IDS == (RELEASE_BUNDLE_ID, DEV_BUNDLE_ID)


def test_url_reducers_are_the_providers_reducers() -> None:
    assert [type(reducer) for reducer in url_reducers()] == [
        type(provider.reducer) for provider in installed_providers()
    ]


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
    ],
)
def test_only_a_true_marker_says_the_app_opens_urls(
    tmp_path: Path, info: dict[str, object] | list[str] | bytes, expected: bool
) -> None:
    assert opens_urls(_bundle(tmp_path, info)) is expected


def test_a_bundle_without_a_readable_info_plist_opens_no_urls(tmp_path: Path) -> None:
    (tmp_path / "Bare.app").mkdir()

    assert opens_urls(tmp_path / "Bare.app") is False
    assert opens_urls(tmp_path / "Missing.app") is False


def test_an_oversized_info_plist_is_not_read(tmp_path: Path) -> None:
    padding = "x" * INFO_PLIST_MAX_BYTES
    bundle = _bundle(tmp_path, {OPENS_URLS_KEY: True, "Padding": padding})

    assert opens_urls(bundle) is False


def test_the_flag_names_the_app_before_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(BUNDLE_ID_ENV, raising=False)
    assert present_bundle_ids(None) == DEFAULT_BUNDLE_IDS

    monkeypatch.setenv(BUNDLE_ID_ENV, "org.example.viewer")
    assert present_bundle_ids(None) == ("org.example.viewer",)
    assert present_bundle_ids("org.example.other") == ("org.example.other",)

    monkeypatch.setenv(BUNDLE_ID_ENV, "")
    assert present_bundle_ids(None) == DEFAULT_BUNDLE_IDS


@pytest.mark.parametrize(
    "value", ["metabrowser", "io.github.jlevy.metabrowser app", "a..b", ".a.b"]
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
    target = Presentable("folder", "/srv/notes", "/view/", "/srv/notes", url=False)

    delivery = deliver(target, DEFAULT_BUNDLE_IDS)

    assert (delivery.delivered_to, delivery.bundle_id, delivery.code) == ("none", None, "not_macos")


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
    target = Presentable(
        "folder", "/srv/notes", "/view/docs/", "/srv/notes/docs", url=False, selects_folder=True
    )

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
