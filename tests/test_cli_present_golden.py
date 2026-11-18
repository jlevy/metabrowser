"""Golden CLI transcript: ``metab ROOT --present`` handing targets to the macOS app.

Each command runs the production CLI in-process with two substitutions, so the
transcript is the same on every platform and nothing reaches a real app:

- ``metabrowser.cli.present.bundle_lookup``, the LaunchServices lookup, answers from a
  table of fixture bundles, or raises :class:`~metabrowser.cli.present.AppLookupError` as
  a sandbox makes it. ``install_locations``, which reads the account's home folder, names
  the sandbox's ``Applications/Metabrowser.app`` as the user's install location
  (``APP_INSTALL_LOCATIONS``): the current app is there, and so, in home folders of their
  own, which a block names, are an older build without ``MetabrowserOpensURLs`` and a
  copy of Terminal; a development build and Terminal itself are elsewhere; and
- ``metabrowser.cli.present.open_executable``, ``/usr/bin/open``, is a stand-in that
  records its arguments and exits 0, or, under ``OPEN_STAND_IN_FAIL=1``, prints a line
  of the shape LaunchServices' failures take and exits 1. An ``open`` planted first on
  ``PATH`` would record itself as ``planted``; no block shows it, because ``--present``
  never looks ``open`` up on ``PATH``.

Each block lists the bundle identifiers looked up, with the bundle each named, and every
``open`` the command ran. The lookup itself runs against LaunchServices in
``tests/test_present.py`` on a Mac; what ``--present --dry-run`` resolves for every target
shape is ``tests/golden/cli-present.tryscript.md``.
"""

from __future__ import annotations

import os
import plistlib
import stat
from pathlib import Path
from typing import Final

import pytest

from metabrowser.cli import present
from metabrowser.cli.present import (
    APP_BUNDLE_NAME,
    DEV_BUNDLE_ID,
    OPENS_URLS_KEY,
    RELEASE_BUNDLE_ID,
    AppLookupError,
)
from tests.golden_harness import Invocation, block, check_golden, quoted, run_metab

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the open stand-in is a shell script")

_OPEN_STAND_IN: Final = """#!/bin/sh
printf '%s' "$OPEN_STAND_IN_NAME" >> "$OPEN_STAND_IN_LOG"
for argument in "$@"; do printf ' %s' "$argument" >> "$OPEN_STAND_IN_LOG"; done
printf '\\n' >> "$OPEN_STAND_IN_LOG"
if [ "$OPEN_STAND_IN_FAIL" = 1 ]; then
  echo "The application cannot be opened for an unexpected reason, error=-54" >&2
  exit 1
fi
"""
# A Metabrowser build installed under an identifier of its own, as a local fork's is.
OTHER_BUNDLE_ID: Final = "org.example.metabrowser-fork"
TERMINAL_BUNDLE_ID: Final = "com.apple.Terminal"


def _stand_in(directory: Path, name: str) -> Path:
    directory.mkdir()
    opener = directory / "open"
    opener.write_text(_OPEN_STAND_IN.replace('"$OPEN_STAND_IN_NAME"', f"'{name}'"))
    opener.chmod(opener.stat().st_mode | stat.S_IXUSR)
    return opener


class _Sandbox:
    """The fixture tree, the fixture apps, and what the stand-ins recorded."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = tmp_path
        self.monkeypatch = monkeypatch
        notes = tmp_path / "notes"
        (notes / "docs").mkdir(parents=True)
        (notes / "README.md").write_text("# Notes\n")
        (notes / "docs" / "guide.md").write_text("# Guide\n")
        (notes / "run-me.command").write_text("echo hi\n")
        # `~/Applications/Metabrowser.app` with the sandbox as the home folder, and in two
        # other home folders.
        self.current = _app(tmp_path / "Applications", "Metabrowser.app", {OPENS_URLS_KEY: True})
        self.older_home = tmp_path / "older-home"
        self.older = _app(self.older_home / "Applications", "Metabrowser.app", {})
        self.copy_home = tmp_path / "copy-home"
        terminal_info: dict[str, object] = {
            "CFBundleIdentifier": TERMINAL_BUNDLE_ID,
            "CFBundleName": "Terminal",
        }
        _app(self.copy_home / "Applications", "Metabrowser.app", terminal_info)
        # Where `make macos-app` leaves a development build, and where Terminal is.
        self.build = _app(
            tmp_path / "apps/macos/build/dev", "Metabrowser.app", {OPENS_URLS_KEY: True}
        )
        self.terminal = _app(tmp_path / "Utilities", "Terminal.app", terminal_info)
        self.opener = _stand_in(tmp_path / "system", "open")
        planted = _stand_in(tmp_path / "planted", "planted")
        self.log = tmp_path / "open.log"
        monkeypatch.setattr(present, "open_executable", str(self.opener))
        monkeypatch.setenv("PATH", f"{planted.parent}{os.pathsep}{os.environ.get('PATH', '')}")
        monkeypatch.setenv("OPEN_STAND_IN_LOG", str(self.log))
        monkeypatch.delenv("OPEN_STAND_IN_FAIL", raising=False)
        monkeypatch.delenv(present.BUNDLE_ID_ENV, raising=False)
        monkeypatch.delenv(present.ANY_APP_LOCATION_ENV, raising=False)
        self.home = tmp_path
        monkeypatch.setattr(
            present,
            "install_locations",
            lambda: (
                "/Applications/Metabrowser.app",
                str(self.home / "Applications/Metabrowser.app"),
            ),
        )
        monkeypatch.setenv("METABROWSER_PLUGINS_DIRS", "")
        monkeypatch.setenv("TERM", "dumb")
        monkeypatch.chdir(tmp_path)
        self.looked_up: list[str] = []
        self.apps: dict[str, Path] = {}
        self.platform = True
        self.unreachable = False

        def lookup(bundle_id: str) -> Path | None:
            if self.unreachable:
                self.looked_up.append(f"{bundle_id} -> error -10661")
                raise AppLookupError("LaunchServices could not be asked (error -10661)")
            bundle = self.apps.get(bundle_id)
            self.looked_up.append(f"{bundle_id} -> {bundle if bundle else 'none'}")
            return bundle

        self._lookup = lookup

    def run(
        self, args: list[str], *, env: dict[str, str] | None = None, home: Path | None = None
    ) -> str:
        """Run one command, with *home* as the account's home folder, and render its block."""

        self.home = home or self.root
        self.looked_up.clear()
        self.log.write_text("")
        self.monkeypatch.setattr(present, "bundle_lookup", self._lookup if self.platform else None)
        before = {name: os.environ.get(name) for name in env or {}}
        os.environ.update(env or {})
        try:
            result = run_metab(args)
        finally:
            for name, value in before.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        opened = self.log.read_text().splitlines()
        lookups = self.looked_up if self.platform else ["no LaunchServices on this platform"]
        prefix = "".join(f"{name}={value} " for name, value in (env or {}).items())
        command = prefix + "metab " + " ".join(quoted(argument) for argument in args)
        return self._labelled(result, command, lookups, opened, home=home)

    def _labelled(
        self,
        result: Invocation,
        command: str,
        lookups: list[str],
        opened: list[str],
        *,
        home: Path | None,
    ) -> str:
        # A block run with another home folder names it, so its install location is read.
        account = {"account_home": [str(home)]} if home else {}
        text = block(
            command,
            result.exit_code,
            result.stdout,
            result.stderr,
            **account,
            launch_services=lookups,
            open=opened,
        )
        for spelling in {str(self.root.resolve()), str(self.root)}:
            text = text.replace(spelling, "<ROOT>")
        return text


def _app(folder: Path, name: str, info: dict[str, object]) -> Path:
    bundle = folder / name
    (bundle / "Contents").mkdir(parents=True)
    (bundle / "Contents" / "Info.plist").write_bytes(
        plistlib.dumps(
            {"CFBundleIdentifier": DEV_BUNDLE_ID, "CFBundleName": APP_BUNDLE_NAME, **info}
        )
    )
    return bundle


def test_golden_present_hands_targets_to_the_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = _Sandbox(tmp_path, monkeypatch)
    blocks: list[str] = []
    as_json = ["--format", "json"]

    # A current app: every kind of target goes, as `open -b` with the folder, the root
    # and then the file, or the canonical github.com URL.
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.current}
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    blocks.append(sandbox.run(["notes/README.md", "--present"]))
    blocks.append(sandbox.run(["notes", "--path", "docs/guide.md", "--present", *as_json]))
    blocks.append(sandbox.run(["https://github.com/octo/demo/pull/7/files", "--present", *as_json]))
    blocks.append(
        sandbox.run(
            [
                "https://raw.githubusercontent.com/Octo/Demo/main/docs/guide.md",
                "--present",
                *as_json,
            ]
        )
    )
    blocks.append(sandbox.run(["git@github.com:octo/demo.git", "--present"]))

    # A folder inside the root is not sent: the app opens every folder as its own window.
    blocks.append(sandbox.run(["notes", "--path", "docs", "--present", *as_json]))

    # A development build where `make macos-app` leaves it is not installed, and is sent
    # nothing unless a developer says so with METABROWSER_ALLOW_UNINSTALLED_APP=1.
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.build}
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    blocks.append(sandbox.run(["notes", "--present"]))
    blocks.append(sandbox.run(["notes", "--present"], env={present.ANY_APP_LOCATION_ENV: "1"}))

    # An older build without the marker, installed, would drop a URL, and is sent nothing.
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.older}
    blocks.append(
        sandbox.run(
            ["https://github.com/octo/demo", "--present", *as_json], home=sandbox.older_home
        )
    )
    blocks.append(sandbox.run(["notes", "--present"], home=sandbox.older_home))

    # The release build wins over the development build when both are registered.
    sandbox.apps = {RELEASE_BUNDLE_ID: sandbox.current, DEV_BUNDLE_ID: sandbox.build}
    blocks.append(sandbox.run(["notes", "--present", *as_json]))

    # A stray registration of the release identifier, where it was built, does not hide
    # an installed development build: each identifier's bundle is checked in turn.
    sandbox.apps = {RELEASE_BUNDLE_ID: sandbox.build, DEV_BUNDLE_ID: sandbox.current}
    blocks.append(sandbox.run(["notes", "--present", *as_json]))

    # The flag, then the environment, names the one app to look for, which must still be
    # the installed Metabrowser app: an override naming Terminal is not handed a file it
    # would run, where Terminal is or copied to an install location.
    sandbox.apps = {
        OTHER_BUNDLE_ID: sandbox.current,
        DEV_BUNDLE_ID: sandbox.build,
        TERMINAL_BUNDLE_ID: sandbox.terminal,
    }
    blocks.append(sandbox.run(["notes", "--present", "--app-bundle-id", OTHER_BUNDLE_ID, *as_json]))
    blocks.append(
        sandbox.run(
            ["https://github.com/octo/demo", "--present", *as_json],
            env={present.BUNDLE_ID_ENV: OTHER_BUNDLE_ID},
        )
    )
    blocks.append(
        sandbox.run(
            ["notes/run-me.command", "--present", *as_json],
            env={present.BUNDLE_ID_ENV: TERMINAL_BUNDLE_ID},
        )
    )
    sandbox.apps = {TERMINAL_BUNDLE_ID: sandbox.copy_home / "Applications" / "Metabrowser.app"}
    blocks.append(
        sandbox.run(
            ["notes/run-me.command", "--present", "--app-bundle-id", TERMINAL_BUNDLE_ID],
            home=sandbox.copy_home,
        )
    )

    # No app: nothing is sent, and the reason names both variants looked for.
    sandbox.apps = {}
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    blocks.append(sandbox.run(["notes", "--present"]))

    # Blocked, with its own status: LaunchServices cannot be asked, as under a sandbox
    # that denies its database, or `open` fails.
    sandbox.unreachable = True
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    sandbox.unreachable = False
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.current}
    blocks.append(sandbox.run(["notes", "--present", *as_json], env={"OPEN_STAND_IN_FAIL": "1"}))

    # A target that cannot be presented looks up nothing.
    blocks.append(sandbox.run(["missing", "--present", *as_json]))
    blocks.append(sandbox.run(["https://github.com/octo/demo/issues/5", "--present"]))

    # The agent skill's two recipes, as `skills/metabrowser/SKILL.md` writes them, with
    # `--present` first so that a sandbox rule for that prefix matches them, once for
    # each status the skill tells apart; `tests/test_skill_commands.py` holds the skill
    # to these commands and to the fields their reports carry.
    skill = ["--present", "notes", *as_json]
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.current}
    blocks.append(sandbox.run(skill))
    blocks.append(sandbox.run(["--present", "notes", "--path", "docs/guide.md", *as_json]))
    blocks.append(sandbox.run(["--present", "missing", *as_json]))
    blocks.append(sandbox.run(skill, env={"OPEN_STAND_IN_FAIL": "1"}))
    sandbox.unreachable = True
    blocks.append(sandbox.run(skill))
    sandbox.unreachable = False
    sandbox.apps = {}
    blocks.append(sandbox.run(skill))

    # Off macOS there is no LaunchServices to ask.
    sandbox.platform = False
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    blocks.append(sandbox.run(skill))

    rendered = "".join(blocks)
    assert str(tmp_path) not in rendered
    assert "planted" not in rendered
    check_golden("cli-present-delivery.txt", rendered)
