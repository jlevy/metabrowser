"""Golden transcript of the macOS app's contract with ``metab``.

``apps/macos/metab-contract.toml`` declares every command the app runs and every route it
asks. This runs each one, with the argument list the declaration gives, through the
console script's entry point, and records in ``tests/golden/app-contract.txt`` what the
app reads of the answer and nothing else: the exit status, the declared keys of a JSON
answer, and the declared lines of a stream (``devtools/app_contract.py``). An answer
that lacks a declared key fails here, so the transcript changes only when something the
app reads changes, and never because ``metab`` added a field for another reader.

The app's own tests read the transcript back (``AppContractTests.swift``): its argument
builders must write these command lines, and its readers must read these answers. So
the file is where the two sides meet, and a change to it runs the macOS workflow.

What differs from the app's own runs, and why:

- **A server never listens.** Serve mode runs to the point where uvicorn would take
  over, with the port search answering the port asked for, as ``tests/test_cli_golden.py``
  runs it. The stdin watch ``--exit-on-eof`` starts is replaced, since it would read this
  process's stdin; ``tests/test_stdin_lifeline.py`` runs the real one.
- **A route is asked with ``--api``,** which issues the request the app issues and prints
  the status the app checks. ``--api`` writes the folder it serves as ``<ROOT>``, which
  is ``<SERVED>`` here, where ``<ROOT>`` is the sandbox.
- **A repository is a ``file://`` origin** built here. The app's is a GitHub URL, which
  no test may clone; the clone report and the mirror's identity are the same code.
- **The sandbox names its own configuration and cache directories,** as the app's live
  tests do, so nothing is read from or written to the account that runs the tests.
- **A link's dry run looks for no app.** Where ``--present`` would deliver a target is
  part of its answer and no part of what the app reads, and deciding it asks
  LaunchServices about the Mac the tests run on, so the sandbox sets
  ``METABROWSER_OPEN_IN=browser``, as ``cli-present.tryscript.md`` does.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Final
from unittest.mock import patch

import pytest

import metabrowser
from devtools import app_contract, swift_text
from devtools.app_contract import SCENARIO_SECTION, SHOWN_OUTPUT, Surface
from metabrowser import recent_targets
from metabrowser.home import METABROWSER_CACHE_DIR_ENV
from metabrowser.normalize import ROOT_PLACEHOLDER
from metabrowser.open_in import OPEN_IN_ENV
from tests.cache_home_fixture import build_populated_home
from tests.golden_harness import (
    Invocation,
    block,
    check_golden,
    fix_clock,
    label_home,
    normalize_console,
    pin_git_dates,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git
from tests.test_serve_pin import _origin

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="the owner-only cache is POSIX-only"),
    needs_git,
]

CONTRACT: Final = app_contract.load()
GH_STAND_IN: Final = Path(__file__).resolve().parent / "fixtures" / "github-status"
VERSION_PLACEHOLDER: Final = "<VERSION>"
SERVED_PLACEHOLDER: Final = "<SERVED>"
# `metab VERSION`, then for a checkout a description in parentheses.
_VERSION_LINE: Final = re.compile(r"^metab (\S+)(?: \(.*\))?$", re.MULTILINE)
# A file name with every kind of character the view route escapes, and two it does not.
ESCAPED_FILE: Final = "sub dir/résumé notes #1~ (draft)?.md"
# Where the two port walks start: `LaunchLane.basePort` for a folder and a repository.
FOLDER_PORT: Final = "8411"
REPOSITORY_PORT: Final = "8475"


def _app_version_pattern() -> re.Pattern[str]:
    """``MetabVersion``'s pattern, read from its Swift source.

    The one extended regex literal in the file, whose syntax here is Python's too.
    """

    source = (
        app_contract.APP_ROOT / "Sources" / "ShellCore" / "Setup" / "MetabVersion.swift"
    ).read_text(encoding="utf-8")
    literals = [segment.text for segment in swift_text.segments(source) if segment.kind == "regex"]
    assert len(literals) == 1, f"MetabVersion.swift holds {len(literals)} regex literals, not 1"
    return re.compile(literals[0].removeprefix("#/").removesuffix("/#"))


def _elide_version(text: str) -> str:
    """*text* with the version of each ``metab VERSION`` line elided, once it is checked.

    The version changes with every commit, so the transcript cannot hold it; what the app
    needs of it is that ``MetabVersion`` reads it, which is checked before it is elided.
    """

    pattern = _app_version_pattern()

    def elide(found: re.Match[str]) -> str:
        assert pattern.fullmatch(found[1]), (
            f"metab prints the version {found[1]!r}, which MetabVersion in the macOS app "
            "cannot read"
        )
        return f"metab {VERSION_PLACEHOLDER}"

    return _VERSION_LINE.sub(elide, text)


def test_the_version_metab_prints_is_one_the_app_reads() -> None:
    """``MetabVersion`` reads this build's version, and the forms a release takes."""

    pattern = _app_version_pattern()
    printed = _VERSION_LINE.search(run_metab(["--version"]).stdout)
    assert printed, "metab --version no longer prints `metab VERSION`"
    for version in (printed[1], metabrowser.__version__, "0.13.0", "0.13.0rc1", "0.13.1.post2"):
        assert pattern.fullmatch(version), f"MetabVersion cannot read {version!r}"
    assert not pattern.fullmatch("v0.13.0")


class _Sandbox:
    """The folders, the origin, and the homes the transcript's commands run against."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = tmp_path
        self.monkeypatch = monkeypatch
        self.served = tmp_path / "served"
        (self.served / "sub dir").mkdir(parents=True)
        (self.served / "README.md").write_text("# Served\n", encoding="utf-8")
        (self.served / ESCAPED_FILE).write_text("# Notes\n", encoding="utf-8")
        self.other = tmp_path / "other"
        self.other.mkdir()
        self.support = tmp_path / "support"
        self.support.mkdir()
        # Where a mirror is cloned, and two caches the sources route is asked about.
        self.home = tmp_path / "home"
        self.populated = tmp_path / "populated"
        build_populated_home(self.populated)
        self.absent = tmp_path / "absent"
        self.config = tmp_path / "config"
        monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(self.config))
        monkeypatch.setenv("METABROWSER_PLUGINS_DIRS", "")
        monkeypatch.setenv(OPEN_IN_ENV, "browser")
        # The doctor reports GitHub CLI's state, which changes neither its exit status
        # nor anything the app reads; this gh answers it, so none a developer signed in
        # is asked.
        monkeypatch.setenv("PATH", f"{GH_STAND_IN}{os.pathsep}{os.environ.get('PATH', '')}")
        monkeypatch.setenv("TERM", "dumb")
        # Outside the sandbox, so a folder's full name is its path until a block says
        # otherwise.
        monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
        monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)
        monkeypatch.delenv(recent_targets.RECORD_ENV, raising=False)
        monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
        _allow_installed_git(monkeypatch)
        pin_git_dates(monkeypatch)
        # A clone took 0.0 s, and each recent target was opened a second after the last.
        fix_clock(monkeypatch)
        opened = iter(f"2026-11-18T03:14:{second:02d}Z" for second in range(15, 60))
        monkeypatch.setattr(recent_targets, "now", lambda: next(opened))
        self.origin = _origin(tmp_path)

    def run(
        self,
        scenario: str,
        values: Mapping[str, str] | None = None,
        *,
        env: Mapping[str, str] | None = None,
        cache: Path | None = None,
        status: int = 0,
    ) -> str:
        """Run *scenario*'s command with *values* for its placeholders, and render its
        block: the command line, the exit status, and what the app reads of the output."""

        surface = CONTRACT.surface(scenario.partition("/")[0])
        assert surface is not None, f"{scenario}: metab-contract.toml declares no such surface"
        argv = [word.format(**(values or {})) for word in surface.argv]
        with self.monkeypatch.context() as patched:
            patched.setenv(METABROWSER_CACHE_DIR_ENV, str(cache or self.home))
            for name, value in (env or {}).items():
                patched.setenv(name, value)
            result = self._invoke(surface, argv)
        assert result.exit_code == status, f"{scenario}: {result.stdout}{result.stderr}"
        stdout, stderr = self._read_as_the_app(surface, result, scenario)
        assignments = [f"{name}={value}" for name, value in (env or {}).items()]
        command = " ".join([*assignments, "metab", *(quoted(word) for word in argv)])
        return block(
            self._normalized(command),
            result.exit_code,
            _elide_version(self._normalized(stdout)),
            self._normalized(stderr),
            **{SCENARIO_SECTION: [scenario]},
        )

    def _invoke(self, surface: Surface, argv: list[str]) -> Invocation:
        if "--exit-on-eof" not in argv or "--version" in argv:
            return run_metab(argv)
        port = int(argv[argv.index("--port") + 1])
        with (
            patch("metabrowser.cli.serve._QuietForceExitServer") as server,
            patch("metabrowser.cli.serve.find_available_local_port", return_value=port),
            patch("metabrowser.cli.main.stop_when_stdin_closes") as lifeline,
        ):
            result = run_metab(argv)
        if result.exit_code == 0:
            # The flag asked for the watch, and the server would bind what the app named.
            assert lifeline.call_count == 1, surface.id
            config = server.call_args.args[0]
            assert (config.host, config.port) == (argv[argv.index("--host") + 1], port)
        return result

    def _read_as_the_app(
        self, surface: Surface, result: Invocation, scenario: str
    ) -> tuple[str, str]:
        """The two streams with only what the declaration says the app reads."""

        if surface.shown:
            said = bool(result.stdout.strip() or result.stderr.strip())
            return (f"{SHOWN_OUTPUT}\n" if said else "", "")
        if surface.json:
            start = result.stdout.find("{")
            assert start >= 0, f"{scenario}: printed no JSON object: {result.stdout!r}"
            answer = json.loads(result.stdout[start:])
            read = app_contract.project(answer, surface.json)
            # The lines above a route's answer: the route, and the status the app checks.
            printed = result.stdout[:start] + json.dumps(read, indent=2, ensure_ascii=False)
            return printed.replace(ROOT_PLACEHOLDER, SERVED_PLACEHOLDER) + "\n", ""
        patterns = {
            stream: [line.pattern for name in names if (line := CONTRACT.line(name))]
            for stream, names in (("stdout", surface.stdout), ("stderr", surface.stderr))
        }
        stdout = app_contract.kept_lines(result.stdout, patterns["stdout"])
        stderr = app_contract.kept_lines(result.stderr, patterns["stderr"])
        if result.exit_code == 0 and surface.stdout:
            assert stdout, f"{scenario}: printed none of the lines the app reads on stdout"
        return stdout, stderr

    def _normalized(self, text: str) -> str:
        return normalize_console(label_home(text, self.home), self.root)


def test_golden_app_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = _Sandbox(tmp_path, monkeypatch)
    run = sandbox.run
    served = str(sandbox.served)
    mirror = sandbox.origin.url
    folder = {"root": served, "port": FOLDER_PORT}
    repository = {"root": mirror, "port": REPOSITORY_PORT}
    blocks = [
        # Setup: what a `metab` the app can run answers, and what one built before a
        # flag answers.
        run("version-probe"),
        run("version"),
        run("unknown-option", status=2),
        # File > Open Recent, around the servers that fill it.
        run("recent-list/empty"),
        run("serve/folder", folder),
        run("recent-list/after-an-open"),
        run(
            "serve/not-an-open",
            {"root": str(sandbox.other), "port": FOLDER_PORT},
            env={recent_targets.RECORD_ENV: "0"},
        ),
        run("recent-add/repository", {"target": "https://github.com/Octo/Demo/pull/12"}),
        run("recent-list/listed"),
        run("recent-forget/folder", {"root": served}),
        run("recent-clear"),
    ]
    # A list a newer release wrote lists as empty, with why.
    (sandbox.config / recent_targets.STORE_FILE).write_text(
        "format: mf99\ntargets: []\n", encoding="utf-8"
    )
    blocks.append(run("recent-list/problem"))
    (sandbox.config / recent_targets.STORE_FILE).unlink()
    blocks += [
        # A file opened in a folder, and what a folder's window is called.
        run("serve-path/file", {**folder, "path": ESCAPED_FILE}),
        run("identity/folder", {"root": served}),
        run("identity/under-home", {"root": served}, env={"HOME": str(tmp_path)}),
        run("source-status/folder", {"root": served}),
        # A repository: its first start clones, and the next finds the clone.
        run("serve/repository-cloned", repository),
        run("serve/repository-cached", repository),
        run("identity/mirror", {"root": mirror}),
        run("source-status/mirror", {"root": mirror}),
        run("acquire/in-terminal", {"url": mirror}),
    ]
    # What a GitHub link opens: each kind the app knows, and a refusal.
    for name, link, status in (
        ("repository", "https://github.com/Octo/Demo.git", 0),
        ("pull-request", "https://github.com/octo/demo/pull/12/files", 0),
        ("commit", "https://github.com/octo/demo/commit/523f476b", 0),
        ("tree", "https://github.com/octo/demo/tree/main/docs", 0),
        ("file", "https://raw.githubusercontent.com/octo/demo/main/README.md?token=dropped", 0),
        ("refused", "https://github.com/octo/demo/issues/1", 3),
    ):
        blocks.append(run(f"present-dry-run/{name}", {"link": link}, status=status))
    # Whether the cache holds a repository: none, one page, and a cursor to the next.
    support = str(sandbox.support)
    page = {"folder": support, "limit": "100", "after": ""}
    short = {"folder": support, "limit": "2", "after": ""}
    blocks.append(run("cache-sources/none", page, cache=sandbox.absent))
    blocks.append(run("cache-sources/held", page, cache=sandbox.populated))
    first = run("cache-sources/first-page", short, cache=sandbox.populated)
    blocks.append(first)
    cursor = re.search(r'"next_after": "([a-z0-9-]+)"', first)
    assert cursor, "a page shorter than the cache gave no cursor"
    blocks.append(
        run(
            "cache-sources/next-page",
            {**short, "after": f"&after={cursor[1]}"},
            cache=sandbox.populated,
        )
    )
    blocks.append(run("doctor"))
    assert app_contract.GOLDEN_NAME == "app-contract.txt"
    check_golden("app-contract.txt", "".join(blocks))
