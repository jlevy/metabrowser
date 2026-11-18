"""Golden CLI transcript: ``metab TARGET --present`` handing targets to the macOS app.

Each command runs the production CLI in-process with two substitutions, so the
transcript is the same on every platform and nothing reaches a real app:

- ``metabrowser.cli.present.bundle_lookup``, the LaunchServices lookup, answers from a
  table of fixture bundles: one whose ``Info.plist`` declares ``MetabrowserOpensURLs``
  and one, an older app, that does not; and
- an ``open`` first on ``PATH`` records its arguments and exits 0, or, under
  ``OPEN_STAND_IN_FAIL=1``, prints what LaunchServices prints when it refuses and exits 1.

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
from metabrowser.cli.present import DEV_BUNDLE_ID, OPENS_URLS_KEY, RELEASE_BUNDLE_ID
from tests.golden_harness import Invocation, block, check_golden, quoted, run_metab

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the open stand-in is a shell script")

_OPEN_STAND_IN: Final = """#!/bin/sh
printf 'open' >> "$OPEN_STAND_IN_LOG"
for argument in "$@"; do printf ' %s' "$argument" >> "$OPEN_STAND_IN_LOG"; done
printf '\\n' >> "$OPEN_STAND_IN_LOG"
if [ "$OPEN_STAND_IN_FAIL" = 1 ]; then
  echo "The application cannot be opened for an unexpected reason, error=-54" >&2
  exit 1
fi
"""
OTHER_BUNDLE_ID: Final = "org.example.viewer"


class _Sandbox:
    """The fixture tree, the fixture apps, and what the stand-ins recorded."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = tmp_path
        self.monkeypatch = monkeypatch
        notes = tmp_path / "notes"
        (notes / "docs").mkdir(parents=True)
        (notes / "README.md").write_text("# Notes\n")
        (notes / "docs" / "guide.md").write_text("# Guide\n")
        self.current = _app(tmp_path, "Metabrowser.app", {OPENS_URLS_KEY: True})
        self.older = _app(tmp_path, "Metabrowser Older.app", {})
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        opener = bin_dir / "open"
        opener.write_text(_OPEN_STAND_IN)
        opener.chmod(opener.stat().st_mode | stat.S_IXUSR)
        self.log = tmp_path / "open.log"
        monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
        monkeypatch.setenv("OPEN_STAND_IN_LOG", str(self.log))
        monkeypatch.delenv("OPEN_STAND_IN_FAIL", raising=False)
        monkeypatch.delenv(present.BUNDLE_ID_ENV, raising=False)
        monkeypatch.setenv("METABROWSER_PLUGINS_DIRS", "")
        monkeypatch.setenv("TERM", "dumb")
        monkeypatch.chdir(tmp_path)
        self.looked_up: list[str] = []
        self.apps: dict[str, Path] = {}
        self.platform = True

        def lookup(bundle_id: str) -> Path | None:
            bundle = self.apps.get(bundle_id)
            self.looked_up.append(f"{bundle_id} -> {bundle if bundle else 'none'}")
            return bundle

        self._lookup = lookup

    def run(self, args: list[str], *, env: dict[str, str] | None = None) -> str:
        """Run one command and render its block, with what the stand-ins saw."""

        self.looked_up.clear()
        self.log.write_text("")
        self.monkeypatch.setattr(present, "bundle_lookup", self._lookup if self.platform else None)
        for name, value in (env or {}).items():
            self.monkeypatch.setenv(name, value)
        result = run_metab(args)
        for name in env or {}:
            self.monkeypatch.delenv(name)
        opened = self.log.read_text().splitlines()
        lookups = self.looked_up if self.platform else ["no LaunchServices on this platform"]
        prefix = "".join(f"{name}={value} " for name, value in (env or {}).items())
        command = prefix + "metab " + " ".join(quoted(argument) for argument in args)
        return self._labelled(result, command, lookups, opened)

    def _labelled(
        self, result: Invocation, command: str, lookups: list[str], opened: list[str]
    ) -> str:
        text = block(
            command,
            result.exit_code,
            result.stdout,
            result.stderr,
            launch_services=lookups,
            open=opened,
        )
        for spelling in {str(self.root.resolve()), str(self.root)}:
            text = text.replace(spelling, "<ROOT>")
        return text


def _app(root: Path, name: str, info: dict[str, object]) -> Path:
    bundle = root / "Applications" / name
    (bundle / "Contents").mkdir(parents=True)
    (bundle / "Contents" / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleIdentifier": DEV_BUNDLE_ID, **info})
    )
    return bundle


def test_golden_present_hands_targets_to_the_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = _Sandbox(tmp_path, monkeypatch)
    blocks: list[str] = []

    # An app that opens URLs: every kind of target goes, each as `open -b` with the
    # absolute path or the canonical github.com URL.
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.current}
    blocks.append(sandbox.run(["notes", "--present", "--json"]))
    blocks.append(sandbox.run(["notes/README.md", "--present"]))
    blocks.append(sandbox.run(["notes", "--path", "docs/guide.md", "--present", "--json"]))
    blocks.append(sandbox.run(["https://github.com/octo/demo/pull/7/files", "--present", "--json"]))
    blocks.append(
        sandbox.run(
            [
                "https://raw.githubusercontent.com/Octo/Demo/main/docs/guide.md",
                "--present",
                "--json",
            ]
        )
    )
    blocks.append(sandbox.run(["git@github.com:octo/demo.git", "--present"]))

    # A folder inside the root is not sent: the app opens every folder as its own window.
    blocks.append(sandbox.run(["notes", "--path", "docs", "--present", "--json"]))

    # An older app without the marker would drop a URL, so it is sent folders only.
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.older}
    blocks.append(sandbox.run(["https://github.com/octo/demo", "--present", "--json"]))
    blocks.append(sandbox.run(["https://github.com/octo/demo", "--present"]))
    blocks.append(sandbox.run(["notes", "--present", "--json"]))

    # The release build wins over the development build when both are registered.
    sandbox.apps = {RELEASE_BUNDLE_ID: sandbox.current, DEV_BUNDLE_ID: sandbox.older}
    blocks.append(sandbox.run(["notes", "--present", "--json"]))

    # The flag, then the environment, names the one app to look for.
    sandbox.apps = {OTHER_BUNDLE_ID: sandbox.current, DEV_BUNDLE_ID: sandbox.older}
    blocks.append(sandbox.run(["notes", "--present", "--app-bundle-id", OTHER_BUNDLE_ID, "--json"]))
    blocks.append(
        sandbox.run(
            ["https://github.com/octo/demo", "--present", "--json"],
            env={present.BUNDLE_ID_ENV: OTHER_BUNDLE_ID},
        )
    )

    # No app: nothing is sent, and the reason names both variants looked for.
    sandbox.apps = {}
    blocks.append(sandbox.run(["notes", "--present", "--json"]))
    blocks.append(sandbox.run(["notes", "--present"]))

    # LaunchServices refuses: the report says so and names the command to run instead.
    sandbox.apps = {DEV_BUNDLE_ID: sandbox.current}
    blocks.append(sandbox.run(["notes", "--present", "--json"], env={"OPEN_STAND_IN_FAIL": "1"}))

    # A target that cannot be presented looks up nothing.
    blocks.append(sandbox.run(["missing", "--present", "--json"]))
    blocks.append(sandbox.run(["https://github.com/octo/demo/issues/5", "--present"]))

    # Off macOS there is no LaunchServices to ask.
    sandbox.platform = False
    blocks.append(sandbox.run(["notes", "--present", "--json"]))

    rendered = "".join(blocks)
    assert str(tmp_path) not in rendered
    check_golden("cli-present-delivery.txt", rendered)
