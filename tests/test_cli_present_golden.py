"""Golden CLI transcript: ``metab ROOT --present`` opening targets in the app or a browser.

Each command runs the production CLI in-process with three substitutions, so the
transcript is the same on every platform and nothing reaches a real app or browser:

- ``metabrowser.cli.present.bundle_lookup``, the LaunchServices lookup, answers from a
  table of fixture bundles, or raises :class:`~metabrowser.cli.present.AppLookupError` as
  a sandbox makes it. ``install_locations``, which reads the account's home folder, names
  the sandbox's ``Applications/Metabrowser.app`` as the user's install location
  (``APP_INSTALL_LOCATIONS``): the current app is there, and so, in home folders of their
  own, which a block names, are an older build without ``MetabrowserOpensURLs`` and a
  copy of Terminal; a development build and Terminal itself are elsewhere;
- ``metabrowser.cli.present.open_executable``, ``/usr/bin/open``, is a stand-in that
  records its arguments and exits 0, or, under ``OPEN_STAND_IN_FAIL=1``, prints a line
  of the shape LaunchServices' failures take and exits 1. An ``open`` planted first on
  ``PATH`` would record itself as ``planted``; no block shows it, because ``--present``
  never looks ``open`` up on ``PATH``; and
- ``metabrowser.cli.present.server_command``, the detached ``metab ROOT`` a browser
  delivery starts, is a stand-in that records its arguments, says it serves at
  ``http://127.0.0.1:8413/view/``, and waits to be stopped. A block's ``server`` lines
  name what it was given, and say so when it was told to exit 1 before it says where
  it serves, or to say nothing for longer than ``--present`` waits. The server's process
  ID is shown as ``12345`` and its log's random name as ``XXXXXXXX``. Each stand-in is
  stopped after its block.

Each block lists the bundle identifiers looked up, with the bundle each named, and every
``open`` the command ran. The lookup itself runs against LaunchServices in
``tests/test_present.py`` on a Mac, and so does a real detached server; what
``--present --dry-run`` resolves for every target shape is
``tests/golden/cli-present.tryscript.md``. A ``--doctor`` block keeps only what it says
about ``open_in``: the line, or the JSON section, and the problems that name it.
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import signal
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
from metabrowser.config_file import CONFIG_RECORD
from metabrowser.home import configuration_directory, ensure_private_directory
from metabrowser.open_in import OPEN_IN_ENV
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
_SERVER_STAND_IN: Final = """#!/bin/sh
printf '%s\\n' "$$" >> "$SERVER_STAND_IN_PIDS"
printf 'metab' >> "$SERVER_STAND_IN_LOG"
for argument in "$@"; do printf ' %s' "$argument" >> "$SERVER_STAND_IN_LOG"; done
printf '\\n' >> "$SERVER_STAND_IN_LOG"
for last; do :; done
case "$SERVER_STAND_IN_MODE" in
  fail)
    echo "Cloning into the cache"
    echo "Error: the stand-in server exits, as it was told to" >&2
    exit 1;;
  slow)
    echo "Cloning into the cache"
    exec sleep 60;;
esac
echo "Serving $last at http://127.0.0.1:8413/view/"
exec sleep 60
"""
# How long `--present` waits for the stand-in to say where it serves: long enough for a
# loaded machine to start a shell, and short where a block shows a server still starting.
_ANNOUNCE_S: Final = 30.0
_SLOW_ANNOUNCE_S: Final = 0.5
# What a block says the stand-in was told to do.
_SERVER_MODES: Final = {"fail": "told to exit 1 first", "slow": "told to say nothing yet"}
_SHOWN_PID: Final = "12345"
_LOG_NAME: Final = re.compile(r"(metab-present-)[a-z0-9_]+(\.log)")
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
        # What the server stand-in is told to do: serve, or one of _SERVER_MODES.
        self.server_mode = ""
        server = tmp_path / "server" / "metab"
        server.parent.mkdir()
        server.write_text(_SERVER_STAND_IN)
        server.chmod(server.stat().st_mode | stat.S_IXUSR)
        self.served = tmp_path / "server.log"
        self.pids = tmp_path / "server.pids"
        logs = tmp_path / "logs"
        logs.mkdir()
        monkeypatch.setattr(present, "server_command", (str(server),))
        monkeypatch.setattr(present, "server_log_directory", lambda: str(logs))
        monkeypatch.setenv("SERVER_STAND_IN_LOG", str(self.served))
        monkeypatch.setenv("SERVER_STAND_IN_PIDS", str(self.pids))
        monkeypatch.delenv(OPEN_IN_ENV, raising=False)
        self.config = configuration_directory()
        # The settings config.yml was last written with, which each block names.
        self.configured: list[str] = []

        def lookup(bundle_id: str) -> Path | None:
            if self.unreachable:
                self.looked_up.append(f"{bundle_id} -> error -10661")
                raise AppLookupError("LaunchServices could not be asked (error -10661)")
            bundle = self.apps.get(bundle_id)
            self.looked_up.append(f"{bundle_id} -> {bundle if bundle else 'none'}")
            return bundle

        self._lookup = lookup

    def configure(self, settings: str | None) -> list[str]:
        """Write config.yml's ``config`` mapping with *settings* appended, or remove it."""

        path = self.config / CONFIG_RECORD
        if settings is None:
            path.unlink(missing_ok=True)
            self.configured = []
            return []
        ensure_private_directory(self.config)
        lines = [
            "softschema:",
            "  contract: metabrowser.config:ApplicationConfig/v1",
            "  envelope: config",
            "  status: permissive",
            "config:",
            "  format: f01",
            "  written_by: 0.13.0",
            "  upgrades: []",
            *settings.splitlines(),
        ]
        path.write_text("".join(f"{line}\n" for line in lines))
        path.chmod(0o600)
        self.configured = settings.splitlines()
        return self.configured

    def run(
        self,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
        home: Path | None = None,
        doctor: bool = False,
    ) -> str:
        """Run one command, with *home* as the account's home folder, and render its block."""

        self.home = home or self.root
        self.looked_up.clear()
        self.log.write_text("")
        self.served.write_text("")
        self.pids.write_text("")
        self.monkeypatch.setattr(present, "bundle_lookup", self._lookup if self.platform else None)
        self.monkeypatch.setattr(
            present,
            "server_announce_timeout_s",
            _SLOW_ANNOUNCE_S if self.server_mode == "slow" else _ANNOUNCE_S,
        )
        environment = {**(env or {}), "SERVER_STAND_IN_MODE": self.server_mode}
        before = {name: os.environ.get(name) for name in environment}
        os.environ.update(environment)
        try:
            result = run_metab(args)
        finally:
            for name, value in before.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            pids = self._stop_servers()
        opened = self.log.read_text().splitlines()
        mode = f"  [stand-in {_SERVER_MODES[self.server_mode]}]" if self.server_mode else ""
        served = [line + mode for line in self.served.read_text().splitlines()]
        lookups = self.looked_up if self.platform else ["no LaunchServices on this platform"]
        prefix = "".join(f"{name}={value} " for name, value in (env or {}).items())
        command = prefix + "metab " + " ".join(quoted(argument) for argument in args)
        if doctor:
            result = _doctor_open_in(result, json_output="--json" in args)
        return self._labelled(result, command, lookups, opened, home=home, served=served, pids=pids)

    def _stop_servers(self) -> set[str]:
        """Stop each server stand-in the command started; return their process IDs."""

        pids = set(self.pids.read_text().split())
        for pid in map(int, pids):
            try:
                reaped, _status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                continue
            if reaped == 0:
                os.kill(pid, signal.SIGTERM)
                os.waitpid(pid, 0)
        return pids

    def _labelled(
        self,
        result: Invocation,
        command: str,
        lookups: list[str],
        opened: list[str],
        *,
        home: Path | None,
        served: list[str],
        pids: set[str],
    ) -> str:
        # A block run with another home folder names it, so its install location is read,
        # and one run with config.yml names the settings it adds.
        account = {"account_home": [str(home)]} if home else {}
        configured = {"config_yml": self.configured} if self.configured else {}
        text = block(
            command,
            result.exit_code,
            _masked(result.stdout, pids),
            _masked(result.stderr, pids),
            **account,
            **configured,
            launch_services=lookups,
            open=opened,
            server=served,
        )
        for spelling in {str(self.root.resolve()), str(self.root)}:
            text = text.replace(spelling, "<ROOT>")
        return text


_PID_FIELDS: Final = re.compile(r'("pid": |pid: |kill )(\d+)')


def _masked(text: str, pids: set[str]) -> str:
    """*text* with the server's process ID and its log's random name fixed."""

    text = _PID_FIELDS.sub(
        lambda found: found[1] + (_SHOWN_PID if found[2] in pids else found[2]), text
    )
    return _LOG_NAME.sub(r"\1XXXXXXXX\2", text)


def _doctor_open_in(result: Invocation, *, json_output: bool) -> Invocation:
    """What ``--doctor`` said about ``open_in``: its line, or its JSON section, and the
    problems that name it."""

    if json_output:
        payload = json.loads(result.stdout)
        kept = {
            "ok": payload["ok"],
            "open_in": payload["open_in"],
            "problems": [problem for problem in payload["problems"] if "open_in" in problem],
        }
        return Invocation(result.exit_code, json.dumps(kept, indent=2) + "\n", "")
    stdout = "".join(
        f"{line}\n"
        for line in result.stdout.splitlines()
        if line.startswith("metab --doctor: open_in")
    )
    stderr = "".join(f"{line}\n" for line in result.stderr.splitlines() if "open_in" in line)
    return Invocation(result.exit_code, stdout, stderr)


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
    app_only = ["--open-in", "app"]

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
    # Under `auto` it opens in a browser instead, on a server started for it.
    blocks.append(sandbox.run(["notes", "--path", "docs", "--present", *app_only, *as_json]))
    blocks.append(sandbox.run(["notes", "--path", "docs", "--present", *as_json]))

    # A development build where `make macos-app` leaves it is not installed, and is sent
    # nothing unless a developer says so with METABROWSER_ALLOW_UNINSTALLED_APP=1.
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.build}
    blocks.append(sandbox.run(["notes", "--present", *app_only, *as_json]))
    blocks.append(sandbox.run(["notes", "--present", *app_only]))
    blocks.append(
        sandbox.run(["notes", "--present", *app_only], env={present.ANY_APP_LOCATION_ENV: "1"})
    )

    # An older build without the marker, installed, would drop a URL, and is sent nothing.
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.older}
    blocks.append(
        sandbox.run(
            ["https://github.com/octo/demo", "--present", *app_only, *as_json],
            home=sandbox.older_home,
        )
    )
    blocks.append(sandbox.run(["notes", "--present", *app_only], home=sandbox.older_home))

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
            ["notes/run-me.command", "--present", *app_only, *as_json],
            env={present.BUNDLE_ID_ENV: TERMINAL_BUNDLE_ID},
        )
    )
    sandbox.apps = {TERMINAL_BUNDLE_ID: sandbox.copy_home / "Applications" / "Metabrowser.app"}
    blocks.append(
        sandbox.run(
            ["notes/run-me.command", "--present", "--app-bundle-id", TERMINAL_BUNDLE_ID, *app_only],
            home=sandbox.copy_home,
        )
    )

    # No app: under `app` nothing is sent, and the reason names both variants looked for.
    sandbox.apps = {}
    blocks.append(sandbox.run(["notes", "--present", *app_only, *as_json]))
    blocks.append(sandbox.run(["notes", "--present", *app_only]))

    # Under `auto`, the default, a target no app takes opens in a browser: `--present`
    # starts `metab ROOT` detached, with its --path, and reports its address, process,
    # and log; the server opens the page in a browser once it answers. A development
    # build that is not installed is passed over as well.
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    blocks.append(sandbox.run(["notes", "--path", "docs/guide.md", "--present"]))
    blocks.append(sandbox.run(["https://github.com/octo/demo/pull/7", "--present", *as_json]))
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.build}
    blocks.append(sandbox.run(["notes", "--present", *as_json]))

    # A server that exits before it says where it serves fails the command, naming its
    # last line and its log; one that has not said by the deadline, as a first clone
    # may not, is still starting, and opens the page once it answers.
    sandbox.apps = {}
    sandbox.server_mode = "fail"
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    blocks.append(sandbox.run(["notes", "--present"]))
    sandbox.server_mode = "slow"
    blocks.append(sandbox.run(["https://github.com/octo/demo", "--present", *as_json]))
    blocks.append(sandbox.run(["https://github.com/octo/demo", "--present"]))
    sandbox.server_mode = ""

    # `browser` looks for no app, from the flag, the environment, or config.yml, in that
    # order; `--app-bundle-id` names an app it would never look for.
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.current}
    blocks.append(sandbox.run(["notes", "--present", "--open-in", "browser", *as_json]))
    blocks.append(sandbox.run(["notes", "--present", *as_json], env={OPEN_IN_ENV: "browser"}))
    sandbox.configure("  open_in: browser")
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    blocks.append(sandbox.run(["notes", "--present", *as_json], env={OPEN_IN_ENV: "auto"}))
    blocks.append(sandbox.run(["notes", "--present", "--open-in", "app", *as_json]))
    sandbox.configure(None)
    blocks.append(
        sandbox.run(
            ["notes", "--present", "--open-in", "browser", "--app-bundle-id", OTHER_BUNDLE_ID]
        )
    )

    # A preference that is not a choice is refused where it was read, before anything
    # is looked up or started; the flag and the environment still choose while
    # config.yml is broken.
    blocks.append(sandbox.run(["notes", "--present", "--open-in", "sometimes"]))
    blocks.append(sandbox.run(["notes", "--present", *as_json], env={OPEN_IN_ENV: "sometimes"}))
    sandbox.configure("  open_in: sometimes")
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    blocks.append(sandbox.run(["notes", "--present", "--open-in", "app", *as_json]))
    sandbox.configure(None)

    # Blocked, with its own status: LaunchServices cannot be asked, as under a sandbox
    # that denies its database, or `open` fails. Under `auto` too: a sandbox that keeps
    # `metab` from LaunchServices would keep a browser it started from the screen.
    sandbox.unreachable = True
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    sandbox.unreachable = False
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.current}
    blocks.append(sandbox.run(["notes", "--present", *as_json], env={"OPEN_STAND_IN_FAIL": "1"}))

    # A target that cannot be presented looks up nothing and starts nothing.
    blocks.append(sandbox.run(["missing", "--present", *as_json]))
    blocks.append(sandbox.run(["https://github.com/octo/demo/issues/5", "--present"]))

    # A dry run decides where the target would go and says why, sending nothing and
    # starting nothing; its status says only whether ROOT resolved.
    blocks.append(sandbox.run(["notes", "--present", "--dry-run", *as_json]))
    blocks.append(sandbox.run(["notes", "--present", "--dry-run"]))
    blocks.append(
        sandbox.run(["notes", "--present", "--dry-run", "--open-in", "browser", *as_json])
    )
    sandbox.apps = {}
    blocks.append(sandbox.run(["notes", "--present", "--dry-run", *as_json]))
    blocks.append(sandbox.run(["notes", "--present", "--dry-run", *app_only, *as_json]))
    sandbox.unreachable = True
    blocks.append(sandbox.run(["notes", "--present", "--dry-run", *as_json]))
    sandbox.unreachable = False
    blocks.append(
        sandbox.run(["notes", "--present", "--dry-run", *as_json], env={OPEN_IN_ENV: "sometimes"})
    )
    blocks.append(sandbox.run(["missing", "--present", "--dry-run", *as_json]))

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
    blocks.append(sandbox.run(["--present", "notes", "--open-in", "app", *as_json]))
    blocks.append(sandbox.run(["--present", "notes", "--open-in", "browser", *as_json]))
    sandbox.server_mode = "slow"
    blocks.append(sandbox.run(skill))
    sandbox.server_mode = "fail"
    blocks.append(sandbox.run(skill))
    sandbox.server_mode = ""

    # Off macOS there is no LaunchServices to ask: `auto` serves for a browser.
    sandbox.platform = False
    blocks.append(sandbox.run(["notes", "--present", *as_json]))
    blocks.append(sandbox.run(["notes", "--present", *app_only, *as_json]))
    blocks.append(sandbox.run(skill))

    # `--doctor` reports the preference, where it was read, and what looking for the app
    # found, sending nothing; a preference it cannot read, or `app` with no app to take a
    # target, is a problem.
    sandbox.platform = True
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.current}
    blocks.append(sandbox.run(["--doctor"], doctor=True))
    blocks.append(sandbox.run(["--doctor", "--json"], doctor=True))
    blocks.append(sandbox.run(["--doctor"], env={OPEN_IN_ENV: "browser"}, doctor=True))
    sandbox.apps = {}
    blocks.append(sandbox.run(["--doctor", "--json"], doctor=True))
    sandbox.configure("  open_in: app")
    blocks.append(sandbox.run(["--doctor"], doctor=True))
    blocks.append(sandbox.run(["--doctor", "--json"], doctor=True))
    sandbox.configure(None)
    blocks.append(sandbox.run(["--doctor", "--json"], env={OPEN_IN_ENV: "sometimes"}, doctor=True))

    rendered = "".join(blocks)
    assert str(tmp_path) not in rendered
    assert "planted" not in rendered
    check_golden("cli-present-delivery.txt", rendered)
