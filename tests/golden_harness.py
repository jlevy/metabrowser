"""The one harness the golden tests share.

Three kinds of committed expectation live under ``tests/``, and each has one way to be
compared and one way to be rewritten:

- an in-process console transcript, ``tests/golden/*.txt``: :func:`check_golden`;
- a recorded response fixture a browserless session replays,
  ``tests/fixtures/*.json``: :func:`check_recording`;
- a tryscript transcript, ``tests/golden/*.tryscript.md``, which tryscript itself
  compares and ``devtools/golden_fixup.py`` re-normalizes.

``GOLDEN_UPDATE=1`` is read here and nowhere else, so ``make golden-update`` rewrites
everything by running the modules its two lists name, and ``devtools/check_goldens.py``
fails when a module that calls this harness is missing from them.

The rest is what a transcript driver needs to pin values rather than hide them: one
in-process ``metab`` runner, one block renderer, labels for the values that depend on the
sandbox path, a pinned Git environment, and a fixed clock.

What a transcript may still replace, and why no fixture can pin it:

- ``<ROOT>``, ``<ORIGIN…>``, ``<PATH-…>``: the pytest sandbox path and URLs built on it;
- ``<SLUG…>``, ``<STORE…>``, ``<SOURCE…>``: identities hashed from such a URL;
- ``<VERSION>``, ``<STATE>``: the installed package version and its build annotation;
- ``<GIT_VERSION>``: the Git on ``PATH``;
- ``<TIME>``: a time written by a process the fixed clock cannot reach, which is a
  child killed mid-publication.

Everything else is literal. Commit IDs are literal because every origin is built with
:func:`pinned_git_env` or ``git fast-import``; times are literal because
:func:`fix_clock` replaces the clock.
"""

from __future__ import annotations

import difflib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any, Final

import pytest
from click import unstyle

import metabrowser
from metabrowser import mirror_refresh
from metabrowser.cache import records
from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.identity import cache_slug, repository_store_id, source_identity
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, classify_root_argument
from metabrowser.cli.main import _run_cli
from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.source import reset_source_session, serve_subject_opener
from tests.test_cache_acquire import _allow_installed_git

TESTS_DIR: Final = Path(__file__).resolve().parent
GOLDEN_DIR: Final = TESTS_DIR / "golden"
FIXTURES_DIR: Final = TESTS_DIR / "fixtures"
DOM_DIR: Final = TESTS_DIR / "dom"

UPDATE_ENV: Final = "GOLDEN_UPDATE"

# Where the fixed clock starts: the instant the pull-request fixtures already use, so a
# transcript that shows both a mirror's fetch and a record's reads one time.
CLOCK_START: Final = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

# Logger output ("HH:MM:SS name | message") depends on timing and on which tests
# configured logging first; it is not part of the CLI's console contract, so those lines
# are removed rather than pinned.
_LOG_LINE: Final = re.compile(r"^\d{2}:\d{2}:\d{2} \S+ \| .*\n?", re.MULTILINE)
_TIMESTAMP: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
TIME_PLACEHOLDER: Final = "<TIME>"


def updating() -> bool:
    """Whether this run rewrites expectations instead of comparing them."""

    return os.environ.get(UPDATE_ENV) == "1"


def _compare(path: Path, actual: str, *, hint: str) -> None:
    """Fail with a unified diff unless *path* holds *actual*; rewrite it when updating.

    UTF-8 whatever the locale says: the Git pin golden records display names in which a
    tree name that is not valid UTF-8 appears as U+FFFD.
    """

    shown = path.relative_to(TESTS_DIR)
    if updating():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        return
    if not path.is_file():
        pytest.fail(f"missing {shown}; {hint}")
    expected = path.read_text(encoding="utf-8")
    if actual != expected:
        diff = "".join(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=str(shown),
                tofile="actual",
            )
        )
        pytest.fail(f"{shown} does not match; {hint}\n{diff}")


def check_golden(name: str, actual: str) -> None:
    """Compare *actual* to ``tests/golden/<name>``; ``make golden-update`` rewrites it."""

    _compare(GOLDEN_DIR / name, actual, hint="after an intended change run `make golden-update`")


def check_recording(name: str, recorded: Any, *, transcript: str, indent: int = 2) -> None:
    """Compare *recorded* to ``tests/fixtures/<name>``, the input a session replays.

    *transcript* is the tryscript golden that pins the session, which reads the
    recording: a recording that changed has to be followed by that transcript, which is
    why ``make golden-update`` records first.
    """

    rendered = json.dumps(recorded, indent=indent, ensure_ascii=False) + "\n"
    _compare(
        FIXTURES_DIR / name,
        rendered,
        hint=(
            "the server answers differently now; after an intended change run "
            f"`make golden-update`, which also rewrites tests/golden/{transcript}"
        ),
    )


def read_recording(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def run_session(script: str, *args: str) -> Any:
    """Run ``tests/dom/<script>`` under Node and return the transcript it prints."""

    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(DOM_DIR / script), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        f"{script} failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    return json.loads(result.stdout)


# ── Console transcripts ─────────────────────────────────────────────


def strip_logs(text: str) -> str:
    """Console output without ANSI styling or logger lines."""

    return _LOG_LINE.sub("", unstyle(text))


_BUILD_STATE: Final = re.compile(r"  \[dev build: [^\]]*\]")


def normalize_console(text: str, root: Path) -> str:
    """Rich-rendered console output with its sandbox root, build state, and padding removed."""

    out = strip_logs(text).replace(str(root), "<ROOT>")
    # A checkout annotates its build with how far past the tag it is and whether the
    # tree is dirty, which changes on every commit and every edit. That is the point of
    # the marker and the opposite of what a golden can record, so the shape is kept and
    # the contents are not. See metabrowser.build_version.
    out = _BUILD_STATE.sub("  [dev build: <STATE>]", out)
    # Rich pads rendered lines to the console width; the padding is not part of the CLI
    # contract and trips `git diff --check` on the goldens.
    return re.sub(r"[ \t]+$", "", out, flags=re.MULTILINE)


def block(
    command: str, exit_code: int | str, stdout: str, stderr: str, **sections: Sequence[str]
) -> str:
    """One command of a transcript: its line, exit status, and each stream in full.

    *sections* adds named line lists after the streams, such as the ``gh`` calls a
    command made.
    """

    text = f"# {command}\nexit: {exit_code}\n--- stdout ---\n{stdout}--- stderr ---\n{stderr}"
    for name, lines in sections.items():
        text += f"--- {name} ---\n" + "".join(f"{line}\n" for line in lines)
    return text


def quoted(argument: str) -> str:
    """*argument* as a shell would need it typed, for a transcript's command line."""

    return f"'{argument}'" if any(ch in argument for ch in "?#& ") else argument


@dataclass(frozen=True, slots=True)
class Invocation:
    """One finished ``metab`` command."""

    exit_code: int
    stdout: str
    stderr: str

    def block(self, command: str, **sections: Sequence[str]) -> str:
        return block(f"metab {command}", self.exit_code, self.stdout, self.stderr, **sections)

    def payload(self) -> Any:
        """The JSON envelope an ``--api`` command printed after its header lines."""

        return json.loads(self.stdout[self.stdout.index("{") :])


def run_metab(args: Sequence[str]) -> Invocation:
    """Run one ``metab`` command in-process through the console script's entry point.

    ``_run_cli`` is what the ``metab`` script calls, so a refusal is the ``Error:`` line
    and exit status a user sees rather than a test-only rendering of the exception.
    """

    out = io.StringIO()
    err = io.StringIO()
    exit_code = 0
    with redirect_stdout(out), redirect_stderr(err):
        try:
            _run_cli(list(args), prog_name="metab")
        except SystemExit as exc:
            exit_code = 0 if exc.code is None else exc.code if isinstance(exc.code, int) else 1
        sys.stdout.flush()
        sys.stderr.flush()
    return Invocation(exit_code, strip_logs(out.getvalue()), strip_logs(err.getvalue()))


def ok(args: Sequence[str]) -> Invocation:
    result = run_metab(args)
    assert result.exit_code == 0, result.stdout + result.stderr
    return result


def refused(args: Sequence[str]) -> Invocation:
    result = run_metab(args)
    assert result.exit_code == 1, result.stdout + result.stderr
    assert "Error: " in result.stderr
    return result


# ── Values a fixture cannot pin ─────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OriginIdentity:
    """What the cache derives from one origin URL, all of it a function of the URL."""

    url: str
    path: str
    source_id: str
    store_id: str
    slug: str


def origin_identity(url: str) -> OriginIdentity:
    classified = classify_root_argument(url)
    assert isinstance(classified, GitSource)
    source_id = source_identity(classified.transport, classified.normalized)
    slug = cache_slug(
        classified.transport, classified.normalized, source_id, slug_owner=lambda _candidate: None
    )
    return OriginIdentity(
        url=classified.normalized,
        path=classified.normalized.removeprefix("file://"),
        source_id=source_id,
        store_id=repository_store_id(source_id, "sha1"),
        slug=slug,
    )


# The Git a store was acquired with, where a store record quotes it. Addressed by its
# place in the record rather than by value: a fixture store records a fixed version,
# and on a host whose Git is that version a value label could not tell the two apart.
_RECORDED_GIT: Final = re.compile(r'("acquisition": \{\n\s*"git_version": )"\d+\.\d+\.\d+"')


@dataclass(slots=True)
class Labels:
    """Exact values that depend on the sandbox or the host, and the label each becomes.

    A label replaces one known value wherever it appears, so equal labels are equal
    values and a value nobody labelled stays literal. Nothing is replaced by key name: a
    field that happens to be called ``id`` or ``at`` is compared like any other. The
    installed package version is labelled where a record quotes it as a JSON string.
    """

    labels: dict[str, str] = field(
        default_factory=lambda: {json.dumps(metabrowser.__version__): '"<VERSION>"'}
    )

    def add(self, actual: str, label: str) -> None:
        self.labels[actual] = label

    def origin(
        self, url: str, suffix: str = "", *, store: str = "STORE", source: str = "SOURCE"
    ) -> OriginIdentity:
        """Label everything the cache derives from the origin at *url*."""

        identity = origin_identity(url)
        self.add(url, f"<ORIGIN{suffix}>")
        self.add(identity.url, f"<ORIGIN{suffix}>")
        self.add(identity.path, f"<PATH{suffix}>")
        self.add(identity.store_id, f"<{store}{suffix}>")
        self.add(identity.source_id, f"<{source}{suffix}>")
        self.add(identity.slug, f"<SLUG{suffix}>")
        return identity

    def apply(self, text: str) -> str:
        for actual in sorted(self.labels, key=len, reverse=True):
            text = text.replace(actual, self.labels[actual])
        return _RECORDED_GIT.sub(r'\1"<GIT_VERSION>"', text)


def _stamp(instant: datetime) -> str:
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(slots=True)
class FixedClock:
    """The one instant every in-process clock reads; it moves only when a session says."""

    now: datetime = CLOCK_START
    instants: set[str] = field(default_factory=lambda: {_stamp(CLOCK_START)})

    def read(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)
        self.instants.add(_stamp(self.now))

    def elide_other_times(self, text: str) -> str:
        """Replace every time this clock never read with ``<TIME>``.

        For a transcript that includes records written by a child process, whose clock
        cannot be replaced. Times this clock gave stay literal.
        """

        return _TIMESTAMP.sub(
            lambda found: found.group(0) if found.group(0) in self.instants else TIME_PLACEHOLDER,
            text,
        )


def fix_clock(monkeypatch: pytest.MonkeyPatch) -> FixedClock:
    """Make every record written in this process, and the freshness window, read one clock.

    ``metabrowser.cache.records.canonical_now`` is the one seam the cache writes times
    through. The clock that function reads is replaced rather than the function, so
    every module that imported the name reads the fixed clock whenever it was imported,
    and no binding outlives the test. The mirror's freshness reads its own ``_now_utc``,
    replaced with the same instant so ``stale`` is a function of the fixture.
    """

    clock = FixedClock()

    class ClockDatetime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:  # pyright: ignore[reportIncompatibleMethodOverride]
            return clock.read()

    monkeypatch.setattr(records, "datetime", ClockDatetime)
    monkeypatch.setattr(mirror_refresh, "_now_utc", clock.read)
    return clock


def pinned_git_env() -> dict[str, str]:
    """A Git environment in which a commit ID is a function of the recipe alone.

    Identity and both dates are fixed and no user or system configuration is read, so
    a repository built with ``git commit`` has the same commit IDs on every machine.
    """

    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(PINNED_GIT_IDENTITY)
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    return env


PINNED_GIT_IDENTITY: Final = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_AUTHOR_DATE": "2020-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2020-01-01T00:00:00Z",
}


def pin_git_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix both commit dates for a fixture that builds its origin with its own identity.

    An origin recipe that sets the author and committer but inherits the dates then
    yields the same commit IDs on every machine, so a transcript can print them.
    """

    for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.setenv(name, PINNED_GIT_IDENTITY[name])


def pinned_git(root: Path, *args: str) -> str:
    """Run ``git -C root`` in :func:`pinned_git_env` and return its trimmed output."""

    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env=pinned_git_env(),
    ).stdout.strip()


def file_url(origin: Path) -> str:
    return f"file://{origin.resolve()}"


@dataclass(frozen=True, slots=True)
class CliSandbox:
    home: Path
    clock: FixedClock


def isolate_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliSandbox:
    """A private application home, a fixed clock, and a console no host setting changes.

    The acquisition floor admits the installed Git, as in every in-process acquisition
    test (``_allow_installed_git``).
    """

    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("METABROWSER_PLUGINS_DIRS", "")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("TZ", "UTC")
    _allow_installed_git(monkeypatch)
    return CliSandbox(home, fix_clock(monkeypatch))


# ── Recording what a served mirror answers ──────────────────────────

JSON_BODY: Final = {"content-type": "application/json"}


def answer(response: Any) -> dict[str, Any]:
    """One response as a session replays it: the status and the decoded body."""

    return {"status": response.status_code, "body": response.json()}


def serve_published(published: PublishedSource, *, serving: bool = False) -> None:
    """Serve *published* at its default revision, as ``metab <url>`` would.

    The source session starts fresh, because a recording holds session generations and
    an earlier test in the process may have left one open.
    """

    async def opener() -> GitRevisionSubject:
        return await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=published.default_revision,
            store_identity=published.store_id,
            ref=published.default_remote_ref,
        )

    reset_source_session()
    serve_subject_opener(opener)
    mirror_refresh.serve_mirror(StoreMirror.from_published(published), serving=serving)
