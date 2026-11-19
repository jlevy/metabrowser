"""The recent targets store: order, one entry per root, the cap, damage, and writers at once.

``metabrowser.recent_targets`` keeps the one list of folders and repositories opened
lately, which ``metab --recent`` and the macOS app's File > Open Recent show. Every test
here names its own configuration directory, so none touches the list a developer's own
``metab`` keeps; ``tests/conftest.py`` also points ``METABROWSER_CONFIG_DIR`` at a
temporary directory for every test.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from metabrowser import recent_targets
from metabrowser.cli.common import LocalOpen, resolve_local_open
from metabrowser.cli.main import _app
from metabrowser.errors import CLIError
from metabrowser.recent_targets import (
    FORMAT,
    FORMAT_HISTORY,
    LOCK_FILE,
    MAX_RECENT_TARGETS,
    MAX_ROOT_BYTES,
    MIGRATIONS,
    RECORD_ENV,
    STORE_FILE,
    NewerFormatError,
    RecentTargetsError,
    UnrecordableRootError,
    clear,
    forget,
    format_number,
    read,
    record,
    record_quietly,
    recorded_path,
    recording_enabled,
)
from tests.child_io import read_line
from tests.test_nav_metadata_chrome import _free_port

_STAMP = "2026-11-18T03:14:15Z"


@pytest.fixture(autouse=True)
def _recording(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """The suite runs with recording off (``tests/conftest.py``); these tests are of it."""

    monkeypatch.setenv(RECORD_ENV, "1")


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A configuration directory that does not exist yet, as on a first run."""

    return tmp_path / "config" / "metabrowser"


def _roots(home: Path) -> list[str]:
    listing = read(home)
    assert listing.problem is None
    return [target.root for target in listing.targets]


def _store(home: Path, text: str) -> None:
    home.mkdir(parents=True, mode=0o700, exist_ok=True)
    path = home / STORE_FILE
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


# ── Order, one entry per root, and the cap ─────────────────────────


def test_a_missing_list_is_empty_and_reading_creates_nothing(home: Path) -> None:
    assert read(home) == recent_targets.Listing(())
    assert not home.exists()


def test_the_most_recently_opened_is_first(home: Path) -> None:
    for root in ("/work/a", "/work/b", "/work/c"):
        record("folder", root, directory=home)

    assert _roots(home) == ["/work/c", "/work/b", "/work/a"]


def test_opening_a_root_again_moves_its_one_entry_to_the_front(home: Path) -> None:
    record("folder", "/work/a", directory=home, opened_at="2026-11-01T00:00:00Z")
    record("folder", "/work/b", directory=home)
    record("folder", "/work/a", directory=home, opened_at=_STAMP)

    listing = read(home)
    assert [target.root for target in listing.targets] == ["/work/a", "/work/b"]
    assert listing.targets[0].opened_at == _STAMP


def test_a_folder_and_a_mirror_are_different_targets(home: Path) -> None:
    record("mirror", "https://github.com/jlevy/tbd", directory=home)
    record("folder", "/work/tbd", directory=home)

    assert [(target.mode, target.root) for target in read(home).targets] == [
        ("folder", "/work/tbd"),
        ("mirror", "https://github.com/jlevy/tbd"),
    ]


def test_the_oldest_entry_falls_off_past_the_cap(home: Path) -> None:
    for index in range(MAX_RECENT_TARGETS + 3):
        record("folder", f"/work/{index}", directory=home)

    roots = _roots(home)
    assert len(roots) == MAX_RECENT_TARGETS
    assert roots[0] == f"/work/{MAX_RECENT_TARGETS + 2}"
    assert roots[-1] == "/work/3"


def test_a_list_too_large_to_read_back_loses_its_oldest_entries(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A writer never publishes a file a reader would refuse as too large."""

    monkeypatch.setattr(recent_targets, "MAX_STORE_BYTES", 600)
    for index in range(12):
        record("folder", f"/work/a-rather-long-folder-name-{index:02d}", directory=home)

    assert (home / STORE_FILE).stat().st_size <= 600
    roots = _roots(home)
    assert 1 <= len(roots) < 12
    assert roots[0] == "/work/a-rather-long-folder-name-11"


def test_forgetting_removes_one_entry_and_clearing_removes_all(home: Path) -> None:
    for root in ("/work/a", "/work/b", "/work/c"):
        record("folder", root, directory=home)

    assert forget(frozenset({("folder", "/work/b")}), directory=home) == 1
    assert forget(frozenset({("folder", "/work/b")}), directory=home) == 0
    assert _roots(home) == ["/work/c", "/work/a"]
    assert clear(directory=home) == 2
    assert clear(directory=home) == 0
    assert _roots(home) == []


# ── Roots ──────────────────────────────────────────────────────────


def test_a_folder_is_one_root_however_it_is_reached(tmp_path: Path, home: Path) -> None:
    """Two paths to one folder are one entry: symbolic links are resolved."""

    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)

    record("folder", recorded_path(real), directory=home)
    record("folder", recorded_path(link), directory=home)

    assert _roots(home) == [recorded_path(real)]


@pytest.mark.macos_tier
def test_on_macos_a_folder_is_spelled_as_the_volume_spells_it(tmp_path: Path) -> None:
    """``realpath(3)``'s spelling, which the macOS app keys a folder's session by.

    In the macOS tier, as the other tests of its case-insensitive file system are
    (``docs/e2e-testing.md``): elsewhere, and on a Mac volume that tells case apart, two
    spellings are two folders and there is nothing to respell.
    """

    real = tmp_path / "MixedCase"
    real.mkdir()
    other = tmp_path / "mixedcase"
    if sys.platform != "darwin" or not other.exists():
        pytest.skip("the file system is case-sensitive, so mixedcase is not MixedCase")

    assert recorded_path(other) == recorded_path(real)
    assert recorded_path(other).endswith("/MixedCase")


def test_a_folder_that_cannot_be_opened_keeps_its_resolved_path(tmp_path: Path) -> None:
    gone = tmp_path / "gone"

    assert recorded_path(gone) == os.path.realpath(gone)


@pytest.mark.parametrize(
    "root",
    [
        "/work/plain",
        "/work/with space/and: colon/# hash/- dash",
        "/work/yes",
        "/work/123",
        "/work/café/日本語",
        "/work/quote\"s/and 'single'",
        "/work/zero\u200bwidth/rtl\u202eoverride/bom\ufeff/nbsp\u00a0x/\U0001f600",
        "/work/trailing space /ends with colon:",
        "/",
        "/work/" + "x" * (MAX_ROOT_BYTES - len("/work/")),
    ],
    ids=[
        "plain",
        "punctuation",
        "yes",
        "number",
        "unicode",
        "quotes",
        "invisible",
        "spaces",
        "root",
        "longest",
    ],
)
def test_a_root_is_read_back_exactly_as_recorded(home: Path, root: str) -> None:
    record("folder", root, directory=home)

    assert _roots(home) == [root]


@pytest.mark.parametrize(
    ("mode", "root", "reason"),
    [
        ("folder", "", "empty"),
        ("folder", "relative/path", "absolute path"),
        ("folder", "/work/line\nbreak", "control character"),
        ("folder", "/work/bell\x07", "control character"),
        ("folder", "/work/next\u0085line", "line separator"),
        ("folder", "/work/line\u2028separator", "line separator"),
        ("folder", "/work/paragraph\u2029separator", "line separator"),
        ("folder", "/" + "x" * MAX_ROOT_BYTES, "longer than"),
        ("folder", "/work/\udcff", "UTF-8"),
        ("mirror", "/a/path", "repository address"),
        ("mirror", "https://example.com/a b", "repository address"),
        ("window", "/work/a", "not a mode"),
    ],
)
def test_a_root_the_list_cannot_hold_is_refused(
    home: Path, mode: str, root: str, reason: str
) -> None:
    with pytest.raises(UnrecordableRootError, match=reason):
        record(mode, root, directory=home)  # pyright: ignore[reportArgumentType]

    assert not home.exists()


def test_the_file_is_the_same_with_and_without_libyaml(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PyYAML's own emitter and parser, its fallback without libyaml, agree with libyaml's.

    A build of PyYAML without the C extension must write the file a build with it reads,
    and the reverse: the two can be installed side by side, as a free-threaded
    interpreter's may be. A root with U+2028 or NEL is what told them apart: PyYAML's
    emitter wrote it raw in a quoted scalar, which did not read back as written, so no
    root may hold one.
    """

    roots = [
        "/work/plain",
        "/work/with space/and: colon/# hash/- dash",
        "/work/quote\"s/and 'single'",
        "/work/zero\u200bwidth/rtl\u202eoverride/bom\ufeff/nbsp\u00a0x/\U0001f600",
        "/work/café/日本語",
        "/work/" + "x" * (MAX_ROOT_BYTES - len("/work/")),
    ]
    for root in roots:
        record("folder", root, directory=home, opened_at=_STAMP)
    with_libyaml = (home / STORE_FILE).read_bytes()

    other = tmp_path / "other" / "metabrowser"
    # On a PyYAML built without libyaml both lists are written by its own emitter, and the
    # comparison says only that it is stable; the test still runs, since a skip here
    # belongs to no tier.
    monkeypatch.delattr(yaml, "CSafeDumper", raising=False)
    monkeypatch.delattr(yaml, "CBaseLoader", raising=False)
    for root in roots:
        record("folder", root, directory=other, opened_at=_STAMP)

    assert (other / STORE_FILE).read_bytes() == with_libyaml
    assert _roots(other) == list(reversed(roots))
    assert _roots(home) == list(reversed(roots))


# ── Folders that are gone ──────────────────────────────────────────


def test_a_folder_that_is_gone_stays_listed_and_is_never_looked_at(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Listing touches no listed path: a look can prompt on macOS, or hang on a volume."""

    gone = tmp_path / "unplugged" / "project"
    record("folder", str(gone), directory=home)
    looked: list[str] = []
    real_stat, real_open = os.stat, os.open

    def watching_stat(path: object, *args: object, **kwargs: object) -> os.stat_result:
        looked.append(str(path))
        return real_stat(path, *args, **kwargs)  # pyright: ignore[reportArgumentType, reportCallIssue]

    def watching_open(path: object, *args: object, **kwargs: object) -> int:
        looked.append(str(path))
        return real_open(path, *args, **kwargs)  # pyright: ignore[reportArgumentType, reportCallIssue]

    monkeypatch.setattr(os, "stat", watching_stat)
    monkeypatch.setattr(os, "lstat", watching_stat)
    monkeypatch.setattr(os, "open", watching_open)

    assert _roots(home) == [str(gone)]
    assert not [path for path in looked if "unplugged" in path]


# ── The file ───────────────────────────────────────────────────────


def test_the_file_is_private_yaml_with_its_format_first(home: Path) -> None:
    record("folder", "/work/a", directory=home, opened_at=_STAMP)
    record("mirror", "https://github.com/jlevy/tbd", directory=home, opened_at=_STAMP)

    text = (home / STORE_FILE).read_text(encoding="utf-8")
    assert text.startswith("# Metabrowser's recent targets")
    assert yaml.safe_load(text) == {
        "format": FORMAT,
        "targets": [
            {"mode": "mirror", "root": "https://github.com/jlevy/tbd", "opened_at": _STAMP},
            {"mode": "folder", "root": "/work/a", "opened_at": _STAMP},
        ],
    }
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    for name in (STORE_FILE, LOCK_FILE):
        assert stat.S_IMODE((home / name).stat().st_mode) == 0o600
    assert sorted(entry.name for entry in home.iterdir()) == [LOCK_FILE, STORE_FILE]


def test_the_format_is_the_last_of_its_history_with_a_step_from_each_older_one() -> None:
    """The application home's convention: an append-only history and a migration per step."""

    assert FORMAT_HISTORY[-1] == FORMAT
    numbers = [format_number(name) for name in FORMAT_HISTORY]
    assert None not in numbers
    assert numbers == sorted(set(numbers))  # pyright: ignore[reportArgumentType]
    assert set(MIGRATIONS) == set(FORMAT_HISTORY[:-1])
    assert format_number("mf01") == 1
    assert format_number("mf123") == 123
    for not_a_format in ("f01", "mf1", "mf", "MF01", "mf01 ", ""):
        assert format_number(not_a_format) is None


def test_a_file_from_a_newer_release_is_left_alone(home: Path) -> None:
    newer = "format: mf02\ntargets: []\nsomething_new: true\n"
    _store(home, newer)

    listing = read(home)
    assert listing.targets == ()
    assert listing.problem is not None
    assert "format mf02" in listing.problem and "Upgrade Metabrowser" in listing.problem
    with pytest.raises(NewerFormatError) as refused:
        record("folder", "/work/a", directory=home)
    assert refused.value.found == "mf02"
    with pytest.raises(NewerFormatError):
        clear(directory=home)
    assert (home / STORE_FILE).read_text(encoding="utf-8") == newer


_ENTRY = "- mode: folder\n  root: /work/a\n  opened_at: '2026-11-18T03:14:15Z'\n"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("{not yaml", "not YAML"),
        ("- a\n- b\n", "not a YAML mapping"),
        ("", "not a YAML mapping"),
        ("targets: []\n", "names no format"),
        ("format: 1\ntargets: []\n", "names no format"),
        ("format: mf00\ntargets: []\n", "no Metabrowser release wrote"),
        ("format: mf01\n", "holds no targets"),
        ("format: mf01\ntargets: nothing\n", "not a list"),
        ("format: mf01\ntargets:\n- just a string\n", "entry 1 is not"),
        ("format: mf01\ntargets:\n- mode: folder\n  root: /work/a\n", "entry 1 is not"),
        (
            "format: mf01\ntargets:\n- mode: Not A Mode\n  root: /work/a\n  opened_at: x\n",
            "entry 1 cannot be a target",
        ),
        (
            "format: mf01\ntargets:\n- mode: folder\n  root: work/a\n  opened_at: x\n",
            "entry 1 cannot be a target",
        ),
        (
            "format: mf01\ntargets:\n- mode: folder\n  root: /work/a\n  opened_at: yesterday\n",
            "entry 1 has no time",
        ),
        ("format: mf01\ntargets:\n" + _ENTRY + _ENTRY, "entry 2 repeats"),
        (
            "format: mf01\ntargets:\n"
            + "".join(
                f"- mode: folder\n  root: /work/{index}\n  opened_at: '{_STAMP}'\n"
                for index in range(MAX_RECENT_TARGETS + 1)
            ),
            "more than",
        ),
        ("format: mf01\ntargets: []\n# " + "x" * recent_targets.MAX_STORE_BYTES, "larger than"),
        (b"\xff\xfe not utf-8", "not YAML"),
    ],
    ids=[
        "not-yaml",
        "a-list",
        "empty",
        "no-format",
        "numeric-format",
        "unwritten-format",
        "no-targets",
        "targets-not-a-list",
        "entry-not-a-mapping",
        "entry-missing-a-field",
        "mode-that-is-no-name",
        "relative-folder",
        "bad-time",
        "repeated-root",
        "over-the-cap",
        "over-the-size",
        "not-utf-8",
    ],
)
def test_a_damaged_file_lists_as_empty_and_the_next_record_replaces_it(
    home: Path, text: str | bytes, reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    home.mkdir(parents=True, mode=0o700)
    path = home / STORE_FILE
    path.write_bytes(text if isinstance(text, bytes) else text.encode())
    path.chmod(0o600)

    listing = read(home)
    assert listing.targets == ()
    assert listing.problem is not None and reason in listing.problem
    assert "/work/" not in listing.problem, "a problem names no root"

    with caplog.at_level(logging.WARNING, logger="metabrowser.recent_targets"):
        record("folder", "/work/new", directory=home)
    assert _roots(home) == ["/work/new"]
    assert any("damaged" in message for message in caplog.messages)


@pytest.mark.parametrize(
    ("text", "unknown"),
    [
        ("format: mf01\ntargets: []\nlater: 1\n", "a key"),
        ("format: mf01\nlater: 1\ntargets:\n" + _ENTRY, "a key"),
        (
            "format: mf01\ntargets:\n" + _ENTRY + "- mode: remote\n  root: host:/srv\n"
            f"  opened_at: '{_STAMP}'\n",
            "a mode",
        ),
    ],
    ids=["key", "key-with-targets", "mode"],
)
def test_a_well_formed_file_with_something_unknown_is_a_newer_releases_and_is_left_alone(
    home: Path, text: str, unknown: str
) -> None:
    """A release that adds a mode or a key and forgets to raise the format costs no list.

    Mutation check: call these damage, as they were, and one ``--recent-add`` by an older
    ``metab`` replaces the newer one's whole list with its one entry.
    """

    _store(home, text)

    listing = read(home)
    assert listing.targets == ()
    assert listing.problem is not None
    assert f"holds {unknown} this release does not know" in listing.problem
    assert "Upgrade Metabrowser" in listing.problem
    for change in (
        lambda: record("folder", "/work/new", directory=home),
        lambda: forget(frozenset({("folder", "/work/a")}), directory=home),
        lambda: clear(directory=home),
    ):
        with pytest.raises(NewerFormatError) as refused:
            change()
        assert refused.value.found is None
    assert (home / STORE_FILE).read_text(encoding="utf-8") == text


def test_a_field_this_release_does_not_know_is_kept_until_its_entry_is_opened_again(
    home: Path,
) -> None:
    """A later release may add a field to an entry without a new format.

    This release lists the entry by what it knows, carries the field along through every
    rewrite, and drops it only from the entry it records again: that open is a new one,
    which the old field no longer describes.
    """

    _store(
        home,
        "format: mf01\ntargets:\n"
        "- mode: mirror\n  root: https://github.com/jlevy/tbd\n"
        f"  opened_at: '{_STAMP}'\n  target: https://github.com/jlevy/tbd/pull/12\n"
        "  checkout:\n    path: /work/tbd\n    remotes: [origin, upstream]\n"
        "  later: 'yes'\n" + _ENTRY,
    )
    later = {"checkout": {"path": "/work/tbd", "remotes": ["origin", "upstream"]}, "later": "yes"}

    listing = read(home)
    assert listing.problem is None
    assert [target.as_json() for target in listing.targets] == [
        {
            "mode": "mirror",
            "root": "https://github.com/jlevy/tbd",
            "opened_at": _STAMP,
            "target": "https://github.com/jlevy/tbd/pull/12",
        },
        {"mode": "folder", "root": "/work/a", "opened_at": _STAMP, "target": None},
    ]
    assert listing.targets[0].extra == later

    record("folder", "/work/b", directory=home)
    assert forget(frozenset({("folder", "/work/a")}), directory=home) == 1
    kept = yaml.safe_load((home / STORE_FILE).read_text(encoding="utf-8"))["targets"]
    assert [entry["root"] for entry in kept] == ["/work/b", "https://github.com/jlevy/tbd"]
    assert {name: kept[1][name] for name in later} == later
    assert read(home).targets[1].extra == later

    assert kept[1]["target"] == "https://github.com/jlevy/tbd/pull/12"

    record("mirror", "https://github.com/jlevy/tbd", directory=home)
    again = read(home).targets[0]
    assert (again.root, again.target, dict(again.extra)) == (
        "https://github.com/jlevy/tbd",
        None,
        {},
    )


# ── Where an open pointed ──────────────────────────────────────────


def test_an_entry_keeps_where_its_open_pointed_and_the_next_open_replaces_it(
    home: Path,
) -> None:
    """``target`` is not part of the key: it is the latest open's, or none."""

    record("folder", "/work/a", target="/work/a/docs/macos-app.md", directory=home)
    record("folder", "/work/b", directory=home)

    listing = read(home)
    assert [(entry.root, entry.target) for entry in listing.targets] == [
        ("/work/b", None),
        ("/work/a", "/work/a/docs/macos-app.md"),
    ]
    stored = yaml.safe_load((home / STORE_FILE).read_text(encoding="utf-8"))["targets"]
    assert "target" not in stored[0], "an entry without a target writes none"
    assert stored[1]["target"] == "/work/a/docs/macos-app.md"

    record("folder", "/work/a", directory=home)
    assert [(entry.root, entry.target) for entry in read(home).targets] == [
        ("/work/a", None),
        ("/work/b", None),
    ]
    record("folder", "/work/a", target="/work/a", directory=home)
    assert read(home).targets[0].target is None, "a target that is the root is none"


@pytest.mark.parametrize(
    ("mode", "root", "target", "reason"),
    [
        ("folder", "/work/a", "/work/other/notes.md", "not inside the root"),
        ("folder", "/work/a", "/work/ab", "not inside the root"),
        ("folder", "/work/a", "docs/macos-app.md", "not inside the root"),
        ("folder", "/work/a", "/work/a/line\nbreak", "control character"),
        ("folder", "/work/a", "/work/a/" + "x" * MAX_ROOT_BYTES, "longer than"),
        (
            "mirror",
            "https://github.com/jlevy/tbd",
            "https://github.com/jlevy/other/pull/1",
            "not inside the root",
        ),
        ("mirror", "https://github.com/jlevy/tbd", "https://github.com/jlevy/tbd/a b", "address"),
    ],
)
def test_a_target_the_list_cannot_hold_is_dropped_and_is_damage_in_the_file(
    home: Path, mode: str, root: str, target: str, reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The open is still recorded, without where it pointed; a file that holds such a
    target was not written by this release, so it is damaged."""

    with caplog.at_level(logging.INFO, logger="metabrowser.recent_targets"):
        entry = record(mode, root, target=target, directory=home)  # pyright: ignore[reportArgumentType]
    assert (entry.root, entry.target) == (root, None)
    assert [(listed.root, listed.target) for listed in read(home).targets] == [(root, None)]
    assert any(reason in message for message in caplog.messages)
    assert target not in "".join(caplog.messages), "a log line names no target"

    _store(
        home,
        f"format: mf01\ntargets:\n- mode: {mode}\n  root: {root}\n"
        f"  opened_at: '{_STAMP}'\n  target: {json.dumps(target)}\n",
    )
    listing = read(home)
    assert listing.targets == ()
    assert listing.problem is not None and "cannot have that target" in listing.problem


def test_a_root_on_its_own_takes_any_target_under_it(home: Path) -> None:
    record("folder", "/", target="/work/a.txt", directory=home)

    assert read(home).targets[0].target == "/work/a.txt"


def test_recent_add_of_a_file_records_its_folder_and_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file opens its folder, and the entry says the open pointed at the file."""

    monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(tmp_path / "config"))
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "notes.md").write_text("notes\n")
    runner = CliRunner()

    added = runner.invoke(_app, [str(folder / "notes.md"), "--recent-add"])

    assert added.exit_code == 0, added.output
    [entry] = read().targets
    assert (entry.mode, entry.root, entry.target) == (
        "folder",
        recorded_path(folder),
        recorded_path(folder / "notes.md"),
    )
    listed = runner.invoke(_app, ["--recent", "--json"])
    assert '"target": ' + json.dumps(recorded_path(folder / "notes.md")) in listed.output


def test_the_open_root_of_a_path_is_the_folder_or_a_files_folder(tmp_path: Path) -> None:
    """The rule a serve and ``--recent-add`` share, until the resolver replaces it."""

    folder = tmp_path / "folder"
    (folder / "sub").mkdir(parents=True)
    (folder / "sub" / "a.txt").write_text("a")
    link = tmp_path / "link"
    link.symlink_to(folder)

    assert resolve_local_open(link) == LocalOpen(folder.resolve(), None)
    assert resolve_local_open(link / "sub" / "a.txt") == LocalOpen(
        (folder / "sub").resolve(), (folder / "sub" / "a.txt").resolve()
    )
    with pytest.raises(CLIError, match="is not a directory"):
        resolve_local_open(tmp_path / "nowhere")


@pytest.mark.parametrize("change", ["clear", "forget"])
def test_clearing_or_forgetting_replaces_a_damaged_file(home: Path, change: str) -> None:
    """Either says it replaces the damaged file, so it does, with nothing to remove."""

    _store(home, "format: mf01\ntargets: nonsense\n")

    if change == "clear":
        assert clear(directory=home) == 0
    else:
        assert forget(frozenset({("folder", "/work/a")}), directory=home) == 0

    assert read(home) == recent_targets.Listing(())
    assert yaml.safe_load((home / STORE_FILE).read_text(encoding="utf-8")) == {
        "format": FORMAT,
        "targets": [],
    }


def test_a_time_that_is_not_one_is_refused_before_anything_is_written(home: Path) -> None:
    with pytest.raises(UnrecordableRootError, match="UTC time"):
        record("folder", "/work/a", directory=home, opened_at="yesterday")

    assert not home.exists()


@pytest.mark.parametrize(
    "setting",
    [{"XDG_CONFIG_HOME": "relative/config"}, {"METABROWSER_CONFIG_DIR": ""}],
    ids=["relative-xdg", "empty-override"],
)
def test_a_setting_that_names_no_directory_is_one_sentence_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, setting: dict[str, str]
) -> None:
    """Before the list, a folder's serve never resolved the configuration directory."""

    monkeypatch.delenv("METABROWSER_CONFIG_DIR", raising=False)
    for name, value in setting.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(RecentTargetsError, match="must be a nonempty absolute path"):
        read()
    with pytest.raises(RecentTargetsError, match="must be a nonempty absolute path"):
        record("folder", "/work/a")
    with caplog.at_level(logging.WARNING, logger="metabrowser.recent_targets"):
        record_quietly("folder", "/work/a")
    assert len(caplog.records) == 1
    assert caplog.records[0].exc_info is None
    assert "must be a nonempty absolute path" in caplog.messages[0]
    assert f"{RECORD_ENV}=0" in caplog.messages[0]


def test_a_folder_that_is_gone_is_forgotten_through_a_link_above_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``/tmp/x`` on macOS is listed as ``/private/tmp/x``, and is forgotten by either."""

    monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(tmp_path / "config"))
    real = tmp_path / "real"
    (real / "project").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real)
    runner = CliRunner()
    assert runner.invoke(_app, [str(link / "project"), "--recent-add"]).exit_code == 0
    assert [target.root for target in read().targets] == [recorded_path(real / "project")]
    (real / "project").rmdir()

    forgotten = runner.invoke(_app, [str(link / "project"), "--recent-forget"])

    assert forgotten.exit_code == 0, forgotten.output
    assert "Forgotten." in forgotten.output
    assert read().targets == ()


def test_a_hand_edited_file_with_unquoted_values_is_read(home: Path) -> None:
    """Every scalar is read as text, so an unquoted time or a root like a number is kept."""

    _store(
        home,
        "format: mf01\ntargets:\n- mode: folder\n  root: /2026\n  opened_at: 2026-11-18T03:14:15Z\n",
    )

    assert read(home).targets == (recent_targets.RecentTarget("folder", "/2026", _STAMP),)


def test_a_yaml_tag_constructs_nothing(home: Path) -> None:
    _store(home, "format: mf01\ntargets: !!python/object/apply:os.system ['true']\n")

    listing = read(home)
    assert listing.targets == ()
    assert listing.problem is not None


# ── Owner-only storage ─────────────────────────────────────────────


def test_a_configuration_directory_others_can_read_is_refused_and_left_as_it_is(
    home: Path,
) -> None:
    record("folder", "/work/a", directory=home)
    home.chmod(0o755)

    with pytest.raises(RecentTargetsError, match="accessible to other users"):
        read(home)
    with pytest.raises(RecentTargetsError, match="accessible to other users"):
        record("folder", "/work/b", directory=home)
    assert stat.S_IMODE(home.stat().st_mode) == 0o755


# ── Writers at once ────────────────────────────────────────────────

_WRITER = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from metabrowser import recent_targets

    home, writer, count = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    recent_targets.LOCK_WAIT_S = float(sys.argv[4])
    for index in range(count):
        recent_targets.record("folder", f"/work/writer-{writer}/root-{index}", directory=home)
    """
)
# How long the writers below wait for the lock, and how long the test waits for each.
# This test is about what the lock excludes; how long a writer may wait is
# test_a_writer_gives_up_on_a_lock_held_too_long_and_a_server_starts_anyway's. Its burst
# is not servers starting at once: each writer here takes the lock five times running,
# and the one that has just released it takes it again before a waiter's next try (in 27
# to 32 of the 39 handoffs of each of 8 bursts on 2026-11-18, at load average 300), so
# the writer served last waits behind nearly every other writer's records, where a
# server waits behind one record for each server starting with it. That wait passed
# LOCK_WAIT_S on a loaded free-threaded CI runner (run 44386715486). A writer still gives
# up before the test stops waiting for it, so a lock never released fails as its error.
_WRITERS_LOCK_WAIT_S = 30.0
_WRITERS_TIMEOUT_S = 50


def test_writers_at_once_lose_no_entry(home: Path) -> None:
    """Several ``metab`` processes starting together each end up in the list.

    Mutation check: without the lock, two writers read the same list and the second
    rename drops the first's entry.
    """

    writers, each = 8, 5
    assert writers * each <= MAX_RECENT_TARGETS
    wait = f"{_WRITERS_LOCK_WAIT_S:g}"
    children = [
        subprocess.Popen(
            [sys.executable, "-c", _WRITER, str(home), str(writer), str(each), wait],
            stderr=subprocess.PIPE,
            text=True,
        )
        for writer in range(writers)
    ]
    for child in children:
        _, errors = child.communicate(timeout=_WRITERS_TIMEOUT_S)
        assert child.returncode == 0, errors

    roots = _roots(home)
    assert sorted(roots) == sorted(
        f"/work/writer-{writer}/root-{index}" for writer in range(writers) for index in range(each)
    )
    for writer in range(writers):
        # Each writer's own entries are newest first, whatever the others did between.
        own = [root for root in roots if root.startswith(f"/work/writer-{writer}/")]
        assert own == [f"/work/writer-{writer}/root-{index}" for index in reversed(range(each))]
    assert sorted(entry.name for entry in home.iterdir()) == [LOCK_FILE, STORE_FILE]


def test_a_writer_gives_up_on_a_lock_held_too_long_and_a_server_starts_anyway(
    home: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    record("folder", "/work/a", directory=home)
    monkeypatch.setattr(recent_targets, "LOCK_WAIT_S", 0.2)
    holder = os.open(home / LOCK_FILE, os.O_RDONLY)
    try:
        fcntl.flock(holder, fcntl.LOCK_EX)
        with pytest.raises(RecentTargetsError, match="has held the recent targets list"):
            record("folder", "/work/b", directory=home)
        monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(home))
        with caplog.at_level(logging.WARNING, logger="metabrowser.recent_targets"):
            record_quietly("folder", "/work/b")
        assert any("not recorded as a recent target" in message for message in caplog.messages)
        # It says how to stop a warning that would otherwise come with every serve.
        assert any(f"{RECORD_ENV}=0" in message for message in caplog.messages)
        assert "/work/b" not in "".join(caplog.messages), "a log line names no root"
        # A reader takes no lock.
        assert _roots(home) == ["/work/a"]
    finally:
        os.close(holder)

    record("folder", "/work/b", directory=home)
    assert _roots(home) == ["/work/b", "/work/a"]


def test_a_root_a_server_cannot_record_does_not_stop_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(tmp_path / "config"))

    with caplog.at_level(logging.INFO, logger="metabrowser.recent_targets"):
        record_quietly("folder", "/work/line\nbreak")

    assert any("control character" in message for message in caplog.messages)
    assert read().targets == ()


# ── Opting out ─────────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "OFF", " 0 "])
def test_recording_is_off_when_the_variable_says_so(value: str) -> None:
    assert not recording_enabled({RECORD_ENV: value})


@pytest.mark.parametrize("environ", [{}, {RECORD_ENV: "1"}, {RECORD_ENV: ""}, {RECORD_ENV: "yes"}])
def test_recording_is_on_otherwise(environ: dict[str, str]) -> None:
    assert recording_enabled(environ)


def test_a_server_told_not_to_record_touches_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With the opt-out, a serve's record reads and writes nothing, the directory included."""

    config = tmp_path / "config"
    monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(config))
    monkeypatch.setenv(RECORD_ENV, "0")

    record_quietly("folder", "/work/a")

    assert not config.exists()
    # The store itself is not what the variable governs: a caller that records, records.
    record("folder", "/work/b", directory=config)
    assert _roots(config) == ["/work/b"]


# ── A real serve ───────────────────────────────────────────────────


@pytest.mark.skipif(os.name == "nt", reason="POSIX pipes")
@pytest.mark.parametrize("root_is_file", [False, True], ids=["folder", "file"])
def test_a_serve_records_its_folder_before_it_announces_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root_is_file: bool
) -> None:
    """``metab ROOT`` is in the list by the time its ``Serving`` line can be read.

    That is what the macOS app relies on: the server it starts for a folder records the
    folder, and ``metab FILE`` records the file's folder, which is what it serves, with
    the file as where the open pointed.
    """

    config = tmp_path / "config"
    monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(config))
    served = tmp_path / "served"
    served.mkdir()
    (served / "a.txt").write_text("a")
    console_script = Path(sys.executable).with_name("metab")
    process = subprocess.Popen(
        [
            str(console_script),
            str(served / "a.txt" if root_is_file else served),
            "--no-open",
            "--exit-on-eof",
            # Not the default port, which parallel workers' servers search from too.
            "--port",
            str(_free_port()),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        line = read_line(process)
        assert line.startswith("Serving "), line
        assert [(entry.mode, entry.root, entry.target) for entry in read(config).targets] == [
            (
                "folder",
                recorded_path(served),
                recorded_path(served / "a.txt") if root_is_file else None,
            )
        ]
        # A server of another folder that is not an open, as one the macOS app restores
        # is not, serves and leaves the list as it was.
        quiet = subprocess.Popen(
            [
                str(console_script),
                str(tmp_path),
                "--no-open",
                "--exit-on-eof",
                "--port",
                str(_free_port()),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env={**os.environ, RECORD_ENV: "0"},
        )
        try:
            assert read_line(quiet).startswith("Serving ")
            assert [target.root for target in read(config).targets] == [recorded_path(served)]
        finally:
            _stop(quiet)
    finally:
        _stop(process)


def _stop(process: subprocess.Popen[str]) -> None:
    """Close the server's stdin, which stops it, and wait for it within a bound."""

    assert process.stdin is not None
    process.stdin.close()
    process.stdin = None
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            stream.close()
