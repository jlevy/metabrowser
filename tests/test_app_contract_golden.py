"""Golden transcript of the macOS app's contract with ``metab``.

``apps/macos/metab-contract.toml`` declares every command the app runs and every route it
asks. This runs each one, with the argument list the declaration gives, through the
console script's entry point, and records in ``tests/golden/app-contract.txt`` what the
app reads of the answer and nothing else (``devtools/app_contract.py``):

- **the exit status;**
- **the declared keys of a JSON answer, in the framing ``metab`` printed it in.** The app
  finds a command's answer by the lines of its output, so an answer that began to be
  printed on one line, or with its text escaped, changes the transcript. An answer that
  lacks a declared key fails here;
- **the part of each declared line that the app parses,** with ``<text>`` for the rest;
- **that a value is there, and not what it says,** for text the app only shows and for a
  value it keeps or hands back unread: ``<text>`` and ``<opaque>``. A reworded message
  changes nothing here;
- **the lines of stderr that a reader looking for a JSON answer would take,** since one
  pipe carries both streams to the app, and no other line of it;
- **``<other>`` for a value that is none of those the app tells apart,** such as a
  source that is not ``published``: the app treats every other value alike.

So the transcript changes only when something the app reads changes, and never because
``metab`` added a field for another reader. ``tests/golden/app-contract-copies.txt``
records beside it what ``metab`` defines for each value the app holds a copy of.

The app's own tests read the transcript back (``AppContractTests.swift``): its argument
builders must write these command lines, and its readers must read these answers. So
the file is where the two sides meet, and a change to it runs the macOS workflow.

What differs from the app's own runs, and why:

- **A server never listens.** Serve mode runs to the point where uvicorn would take
  over, with the port search answering the port asked for, as ``tests/test_cli_golden.py``
  runs it. The stdin watch ``--exit-on-eof`` starts is replaced, since it would read this
  process's stdin; ``tests/test_stdin_lifeline.py`` runs the real one.
- **A route is asked with ``--api``,** which issues the request the app issues. The app
  checks the response's status and decodes its body whole, so a route's block is the
  status, written here as ``status: N``, and the declared keys; what ``--api`` prints
  around them, and how it frames them, is its own. ``--api`` writes the folder it
  serves as ``<ROOT>``, which is ``<SERVED>`` here, where ``<ROOT>`` is the sandbox.
- **A repository is a ``file://`` origin** built here. The app's is a GitHub URL, which
  no test may clone; the clone report and the mirror's identity are the same code.
- **The fixtures are this module's own:** the origin, and the cache the sources route is
  asked about, which holds what the app tells apart and nothing more. A fixture that
  other tests share would change this transcript whenever one of them needed another
  source, and a change here is one a release has to name.
- **The sandbox names its own configuration and cache directories,** as the app's live
  tests do, so nothing is read from or written to the account that runs the tests.
- **A link's dry run looks for no app.** Where ``--present`` would deliver a target is
  part of its answer and no part of what the app reads, and deciding it asks
  LaunchServices about the Mac the tests run on, so the sandbox sets
  ``METABROWSER_OPEN_IN=browser``, as ``cli-present.tryscript.md`` does.
- **The doctor asks stand-ins and an app the sandbox builds.** Its Git and GitHub CLI
  checks ask the ``git`` in ``tests/fixtures/doctor`` and the ``gh`` in
  ``tests/fixtures/github-status``, as ``cli-doctor.tryscript.md`` does, so a check's
  state is the one the block chose and not the host's. The app it is told it runs for is
  a bundle holding only an ``Info.plist`` whose minimum ``metab`` no release meets, so
  the ``metab`` check's warning does not move with this checkout's version. Its
  free-space floor follows ``METABROWSER_MAX_FIRST_CLONE_KB``, set to 1 here, so the
  disk the tests run on never makes the cache a problem.
"""

from __future__ import annotations

import importlib
import json
import os
import plistlib
import re
import shutil
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Final, TypeAliasType, cast, get_args
from unittest.mock import patch

import pytest

import metabrowser
from devtools import app_contract, swift_text
from devtools.app_contract import OPAQUE, SCENARIO_SECTION, SHOWN_OUTPUT, Surface
from metabrowser import recent_targets
from metabrowser.cli.doctor import DOCTOR_APP_ENV
from metabrowser.cli.present import MINIMUM_METAB_KEY
from metabrowser.git import process as git_process
from metabrowser.home import METABROWSER_CACHE_DIR_ENV
from metabrowser.normalize import ROOT_PLACEHOLDER
from metabrowser.open_in import OPEN_IN_ENV
from tests.cache_home_fixture import (
    ALIASED_AT,
    FixtureSource,
    _attach,
    _stage_and_publish_source,
    _stage_and_publish_store,
    build_empty_home,
)
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
    stable_console,
)
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git, _git

posix_only = pytest.mark.skipif(os.name != "posix", reason="the owner-only cache is POSIX-only")

CONTRACT: Final = app_contract.load()
REPO_ROOT: Final = Path(__file__).resolve().parent.parent
SHELL_CORE: Final = app_contract.APP_ROOT / "Sources" / "ShellCore"
FIXTURES: Final = Path(__file__).resolve().parent / "fixtures"
GH_STAND_IN: Final = Path(__file__).resolve().parent / "fixtures" / "github-status"
GIT_STAND_IN: Final = Path(__file__).resolve().parent / "fixtures" / "doctor"
# A minimum `metab` no release meets, so the doctor's `metab` check warns whatever this
# checkout's version is.
UNMET_MINIMUM: Final = "99.0.0"
VERSION_PLACEHOLDER: Final = "<VERSION>"
SERVED_PLACEHOLDER: Final = "<SERVED>"
# `metab VERSION`, then for a checkout a description in parentheses.
_VERSION_LINE: Final = re.compile(r"^metab (\S+)(?: \(.*\))?$", re.MULTILINE)
# A file name with every kind of character the view route escapes, and two it does not.
ESCAPED_FILE: Final = "sub dir/résumé notes #1~ (draft)?.md"
# Where the two port walks start: `LaunchLane.basePort` for a folder and a repository.
FOLDER_PORT: Final = "8411"
REPOSITORY_PORT: Final = "8475"


def _swift(relative: str) -> str:
    return (SHELL_CORE / relative).read_text(encoding="utf-8")


def _app_version_pattern() -> re.Pattern[str]:
    """``MetabVersion``'s pattern, read from its Swift source.

    The one extended regex literal in the file, whose syntax here is Python's too.
    """

    segments = swift_text.segments(_swift("Setup/MetabVersion.swift"))
    literals = [segment.text for segment in segments if segment.kind == "regex"]
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


def test_the_names_the_app_runs_and_installs_are_the_packages() -> None:
    """The app looks for a file named ``metab``, and tells uv to install ``metabrowser``.

    Neither name is a flag or a field, so no command shows it: the console script and the
    distribution are named in ``pyproject.toml``, and the app spells both by itself.
    """

    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    discovery = [
        segment.text for segment in swift_text.strings(_swift("Runtime/RuntimeDiscovery.swift"))
    ]
    requirement = [
        segment.text for segment in swift_text.strings(_swift("Setup/MetabVersion.swift"))
    ]
    assert "metab" in project["scripts"]
    assert "/metab" in discovery, "RuntimeDiscovery.swift no longer looks for a file named metab"
    name = project["name"]
    assert f"uv tool install {name}" in discovery
    assert any(
        literal.startswith(f"uv tool install --upgrade '{name}>=") for literal in requirement
    )


# ── What metab defines for each value the app copies ─────────────────


def _defined(reference: str) -> str:
    """What *reference* is set to, as one line of text that changes when it does.

    ``module:NAME`` is a module's attribute: a ``type`` alias of literals is its members,
    and a set is its members in order. ``pyproject.toml:dotted.key`` is that key of the
    project file. A console script is recorded as defined, and not by where it points:
    the app looks for a file of that name, and a script added beside it, or an entry
    point that moves, is nothing to the app.
    """

    source, _, name = reference.partition(":")
    value: object
    if source == "pyproject.toml":
        value = tomllib.loads((REPO_ROOT / source).read_text(encoding="utf-8"))
        for key in name.split("."):
            assert isinstance(value, dict) and key in value, f"pyproject.toml has no {name}"
            value = cast("dict[str, object]", value)[key]
        if name.startswith("project.scripts."):
            value = "defined"
    else:
        value = getattr(importlib.import_module(source), name)
        if isinstance(value, TypeAliasType):
            value = sorted(get_args(value.__value__))
        elif isinstance(value, set | frozenset):
            value = sorted(cast("set[str]", value))
    return json.dumps(value, ensure_ascii=False)


def test_golden_app_contract_copies() -> None:
    """Each definition of ``metab``'s that the app holds a copy of, as ``metab`` has it.

    ``tests/test_macos_app_pins.py`` holds the app's copy to the definition, so the two
    change together; this makes that change a change to a golden, which the changelog
    rule then requires a release to name (``devtools/check_app_contract.py``).
    """

    defined = {reference: _defined(reference) for reference in CONTRACT.value_references}
    assert app_contract.COPIES_NAME == "app-contract-copies.txt"
    check_golden("app-contract-copies.txt", app_contract.copies_text(defined))


# ── The transcript ───────────────────────────────────────────────────


# The cache the sources route is asked about: what the app tells apart of a page, and
# enough of it for a page of two to end with a cursor. In the order the route lists them:
# a repository that is listed and not published, one that is published, and the app's
# own, held under two addresses. The app looks for the last by its HTTPS address.
LISTED_ONLY: Final = FixtureSource("https", "https://github.com/octo/alpha")
ANOTHER: Final = FixtureSource("https", "https://github.com/octo/beta")
HELD_BY_SSH: Final = FixtureSource("ssh", "git@github.com:octo/demo.git")
HELD: Final = FixtureSource("https", "https://github.com/octo/demo")


def _cache(home: Path) -> None:
    """A cache that holds :data:`HELD` and :data:`ANOTHER`, and lists :data:`LISTED_ONLY`."""

    build_empty_home(home)
    for store, sources in ((HELD, (HELD, HELD_BY_SSH)), (ANOTHER, (ANOTHER,))):
        _stage_and_publish_store(home, store.store_key(), with_revision=True)
        for source in sources:
            _stage_and_publish_source(home, source, opened=False)
            _attach(home, source, store.store_key(), generation=1, at=ALIASED_AT)
    # Acquired, and never attached to its store: the route lists it as not published.
    _stage_and_publish_store(home, LISTED_ONLY.store_key(), with_revision=False)
    _stage_and_publish_source(home, LISTED_ONLY, opened=False)


def _origin(root: Path) -> str:
    """A bare origin with one commit on ``main``, and its ``file://`` address."""

    work = root / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("# Origin\n", encoding="utf-8")
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "first")
    origin = root / "origin.git"
    _git(work, "clone", "--bare", "--template=", "--", str(work), str(origin))
    return f"file://{origin.resolve()}"


_STATUS_LINE: Final = re.compile(r"^status: (\d+)$", re.MULTILINE)


class _Sandbox:
    """The folders, the origin, and the homes the transcript's commands run against."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = tmp_path
        self.monkeypatch = monkeypatch
        # Values the transcript writes as a label: a cursor is whatever the cache made it.
        self.labels: dict[str, str] = {}
        # The whole answer of the last command that printed JSON.
        self.answer: object = None
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
        self.held = tmp_path / "held"
        _cache(self.held)
        self.absent = tmp_path / "absent"
        self.config = tmp_path / "config"
        stable_console(monkeypatch)
        monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(self.config))
        monkeypatch.setenv("METABROWSER_PLUGINS_DIRS", "")
        monkeypatch.setenv(OPEN_IN_ENV, "browser")
        # The doctor reports GitHub CLI's state, which changes neither its exit status
        # nor anything the app reads; this gh answers it, so none a developer signed in
        # is asked.
        monkeypatch.setenv("PATH", f"{GH_STAND_IN}{os.pathsep}{os.environ.get('PATH', '')}")
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
        # A checkout of a GitHub repository, whose window a link's new mirror window of
        # that repository joins as a tab: its origin is what names the repository.
        self.checkout = tmp_path / "checkout"
        _git(tmp_path, "clone", "-q", "--template=", "--", self.origin, str(self.checkout))
        _git(self.checkout, "remote", "set-url", "origin", "git@github.com:Octo/Demo.git")

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
            return self._read_json(surface, result, scenario)
        patterns = {
            stream: [line.pattern for name in names if (line := CONTRACT.line(name))]
            for stream, names in (("stdout", surface.stdout), ("stderr", surface.stderr))
        }
        stdout = app_contract.read_lines(result.stdout, patterns["stdout"])
        stderr = app_contract.read_lines(result.stderr, patterns["stderr"])
        if result.exit_code == 0 and surface.stdout:
            assert stdout, f"{scenario}: printed none of the lines the app reads on stdout"
        return stdout, stderr

    def _read_json(self, surface: Surface, result: Invocation, scenario: str) -> tuple[str, str]:
        """A JSON answer cut to its declared keys, and the stderr beside it.

        A command's answer keeps the framing it was printed in, and what was printed
        before and after it, because the app finds it among the lines of both streams. A
        route's is its status and its declared keys, re-serialized: the app checks the
        one and decodes the other whole.
        """

        try:
            before, answer, raw, after = app_contract.split_json(result.stdout)
            read = app_contract.project(answer, surface.json, surface.recording)
            self.answer = answer
            if surface.kind == "route":
                status = _STATUS_LINE.search(before)
                assert status, f"{scenario}: --api printed no status above the answer"
                body = json.dumps(read, indent=2, ensure_ascii=False)
                printed = f"status: {status[1]}\n{body}\n"
                return printed.replace(ROOT_PLACEHOLDER, SERVED_PLACEHOLDER), ""
            framed = app_contract.dump(read, app_contract.framing_of(raw, answer))
        except app_contract.ContractError as error:
            pytest.fail(f"{scenario}: {error}")
        return before + framed + after, app_contract.framing_lines(result.stderr)

    def _normalized(self, text: str) -> str:
        for value, label in self.labels.items():
            text = text.replace(value, label)
        return normalize_console(label_home(text, self.home), self.root)


def _body(directory: Path, name: str, link: str) -> str:
    """A link request's body, as ``SourceLink`` sends it, written where ``--data`` reads it."""

    body = directory / f"{name}.json"
    body.write_text(json.dumps({"fetch": False, "link": link}) + "\n", encoding="utf-8")
    return str(body)


@posix_only
@needs_git
def test_golden_app_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = _Sandbox(tmp_path, monkeypatch)
    run = sandbox.run
    served = str(sandbox.served)
    mirror = sandbox.origin
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
        run("identity/checkout", {"root": str(sandbox.checkout)}),
        run("source-status/folder", {"root": served}),
        # A repository: its first start clones, and the next finds the clone.
        run("serve/repository-cloned", repository),
        run("serve/repository-cached", repository),
        run("identity/mirror", {"root": mirror}),
        run("source-status/mirror", {"root": mirror}),
        # A link into the mirror's repository opens at its page; one into another is refused.
        run("source-link/repository", {"root": mirror, "body": _body(tmp_path, "link", mirror)}),
        run(
            "source-link/elsewhere",
            {"root": mirror, "body": _body(tmp_path, "elsewhere", f"{mirror}-other")},
            status=1,
        ),
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
    blocks.append(run("cache-sources/held", page, cache=sandbox.held))
    blocks.append(run("cache-sources/first-page", short, cache=sandbox.held))
    # The cursor is the cache's to choose, so the transcript shows that the page gave one
    # and that handing it back gives the next page, and not what it is.
    cursor = cast("dict[str, object]", sandbox.answer)["next_after"]
    assert isinstance(cursor, str) and cursor, "a page shorter than the cache gave no cursor"
    sandbox.labels[cursor] = OPAQUE
    blocks.append(
        run(
            "cache-sources/next-page",
            {**short, "after": f"&after={cursor}"},
            cache=sandbox.held,
        )
    )
    assert cast("dict[str, object]", sandbox.answer)["next_after"] is None
    # Where Metabrowser's own event log is: a state directory with two segments, newest
    # first in the answer, and one with a log directory and no segment.
    state = sandbox.root / "events-state"
    log = state / "events"
    state.mkdir(mode=0o700)
    log.mkdir(mode=0o700)
    for segment in sorted((FIXTURES / "event-log").glob("events-*.jsonl")):
        shutil.copy(segment, log / segment.name)
        (log / segment.name).chmod(0o600)
    quiet = sandbox.root / "quiet-state" / "events"
    quiet.parent.mkdir(mode=0o700)
    quiet.mkdir(mode=0o700)
    blocks.append(
        run("event-log/found", {"folder": support}, env={"METABROWSER_STATE_DIR": str(state)})
    )
    blocks.append(
        run(
            "event-log/empty", {"folder": support}, env={"METABROWSER_STATE_DIR": str(quiet.parent)}
        )
    )
    blocks += _doctor(sandbox)
    assert app_contract.GOLDEN_NAME == "app-contract.txt"
    check_golden("app-contract.txt", "".join(blocks))


def _doctor(sandbox: _Sandbox) -> list[str]:
    """Help > Check Setup…: a setup with nothing to fix, and one with something of each
    kind, as the app runs it.

    The second names the app's bundle as the app does, which holds a minimum no
    ``metab`` meets; asks a ``gh`` that no account signed in to; and finds the cache at a
    relative path, which is a problem. The ``git`` is the stand-in's, and the Git
    executable ``metab`` keeps for its lifetime is found again before and after, so
    neither the host's ``git`` reaches these blocks nor the stand-in a later test.
    """

    bundle = sandbox.root / "Metabrowser.app"
    (bundle / "Contents").mkdir(parents=True)
    (bundle / "Contents" / "Info.plist").write_bytes(
        plistlib.dumps(
            {"CFBundleIdentifier": "io.github.jlevy.metabrowser", MINIMUM_METAB_KEY: UNMET_MINIMUM}
        )
    )
    with sandbox.monkeypatch.context() as patched:
        patched.setenv("PATH", f"{GIT_STAND_IN}{os.pathsep}{os.environ['PATH']}")
        patched.setenv("METABROWSER_MAX_FIRST_CLONE_KB", "1")
        git_process.git_executable.cache_clear()
        git_process.detect_git_version.cache_clear()
        try:
            return [
                sandbox.run("doctor/clean"),
                sandbox.run(
                    "doctor/as-the-app",
                    env={DOCTOR_APP_ENV: str(bundle), "FAKE_GH_STATUS": "signed-out"},
                    cache=Path("relative"),
                    status=1,
                ),
            ]
        finally:
            git_process.git_executable.cache_clear()
            git_process.detect_git_version.cache_clear()
