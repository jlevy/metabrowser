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
``devtools/golden_update.py`` sets the switch for those runs and fails when a test in
them was skipped.

The rest is what a transcript driver needs to pin values rather than hide them: one
in-process ``metab`` runner, one block renderer, labels for the values that depend on the
sandbox path, a pinned Git environment, and a fixed clock.

What a transcript may still replace, and why no fixture can pin it:

- ``<ROOT>``, ``<ORIGIN…>``, ``<PATH-…>``: the pytest sandbox path and URLs built on it;
- ``<HOME>``: the application home under that sandbox, where a first clone says it goes;
- ``<SLUG…>``, ``<STORE…>``, ``<SOURCE…>``: identities hashed from such a URL;
- ``<VERSION>``, ``<STATE>``: the installed package version and its build annotation;
- ``<GIT_VERSION>``: the Git on ``PATH``;
- ``<TIME>``: a time written by a process the fixed clock cannot reach, which is a
  child killed mid-publication;
- ``<ELAPSED>``, ``<AGE>``: how long a clone took, and how long ago a cached one was
  fetched, as a real ``metab`` process says them: nothing replaces that process's
  clocks (:func:`elide_clone_timing`).

Everything else is literal. Commit IDs are literal because every origin is built with
:func:`pinned_git_env` or ``git fast-import``; times are literal because
:func:`fix_clock` replaces the clock, the one a clone's elapsed time is read from
included, so a clone always took ``0.0 s`` and never reaches its first status line.

Two markers stand for text the transcript itself pins, so a payload that repeats is
shown once. Each is written by its driver after comparing, never assumed, so what
stopped repeating is printed:

- ``<RECORD n>`` in ``cli-github-pull-refresh.txt``: a pull-request record equal to the
  one last printed in full above it (``tests/test_cli_github_pull_golden.py``);
- ``<N lines, from … on, are the same as in … above>`` in ``cli-git-pin-tree.txt``: a
  run of lines an earlier command of the transcript printed
  (``tests/test_cli_git_pin_golden.py``).

They are two operations and share no code: the first replaces one JSON value by its
key, the second the longest run of lines two outputs share.
"""

from __future__ import annotations

import difflib
import io
import json
import os
import re
import subprocess
import sys
import time
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
from metabrowser.cli import clone_report
from metabrowser.cli.main import _run_cli
from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.source import reset_source_session, serve_subject_opener
from tests.required_tools import require_node
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
HOME_LABEL: Final = "<HOME>"


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
    """Run ``tests/dom/<script>`` under Node and return the transcript it prints.

    Node is a prerequisite: without it ``require_node`` stops the run, or skips where
    ``tests/required_tools.py`` says a developer allowed that.
    """

    result = subprocess.run(
        [require_node(), str(DOM_DIR / script), *args],
        capture_output=True,
        text=True,
        timeout=50,
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

    @property
    def error(self) -> str:
        """The ``Error:`` line a refusal printed, without what a clone said before it.

        A first clone names its URL and the cache directory on stderr before it can
        fail, and both are the user's own. What a failure must not carry is in the
        message: a staging path, Git's argument vector, Git's own text.
        """

        start = self.stderr.index("Error: ")
        return self.stderr[start:]


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
        # The store's directory is named by its key, which a served mirror's status
        # shows in its location.
        self.add(identity.store_id.removeprefix("sha256:"), f"<STORE_KEY{suffix}>")
        self.add(identity.source_id, f"<{source}{suffix}>")
        self.add(identity.slug, f"<SLUG{suffix}>")
        return identity

    def apply(self, text: str) -> str:
        for actual in sorted(self.labels, key=len, reverse=True):
            text = text.replace(actual, self.labels[actual])
        return _RECORDED_GIT.sub(r'\1"<GIT_VERSION>"', text)


_CLONED_IN: Final = re.compile(r"^(cloned \S+ in )\d+(?:\.\d)? s", re.MULTILINE)
_CLONE_STATUS: Final = re.compile(r"^cloning \S+: .* \(\d+(?:\.\d)? s\)\n", re.MULTILINE)
_FETCHED_AGO: Final = re.compile(
    r"^(using the clone of .*, fetched )(?:less than a minute|\d+ (?:minute|hour|day)s?) ago$",
    re.MULTILINE,
)
ELAPSED_PLACEHOLDER: Final = "<ELAPSED>"
AGE_PLACEHOLDER: Final = "<AGE>"


def elide_clone_timing(stderr: str) -> str:
    """What an unpatched ``metab`` process said of its clone, without the machine's speed.

    The time the clone took becomes ``<ELAPSED>``, and how long ago a later command
    found it fetched becomes ``<AGE>``. A status line, which is written only when a
    clone has run ten seconds since its last line, is removed: whether one appears says
    how loaded the machine was and nothing about the command.
    """

    stderr = _CLONE_STATUS.sub("", stderr)
    stderr = _CLONED_IN.sub(rf"\g<1>{ELAPSED_PLACEHOLDER}", stderr)
    return _FETCHED_AGO.sub(rf"\g<1>{AGE_PLACEHOLDER}", stderr)


# The lines of a command's output that name the application home, whole. Two are a
# command's own stderr and say where clones are kept: a URL, the home's cache directory
# and nothing under it, and for a hit how long ago it was fetched. The third is the one
# field of a route's answer that names a path in the cache: the location of a served
# mirror in its status, which is the store's bare repository and nothing else.
_HOME_LINES: Final = (
    r"cloning \S+ into {home}/cache",
    r"using the clone of \S+ cached in {home}/cache"
    r"(?:, fetched (?:less than a minute ago|\d+ (?:minute|hour|day)s? ago|<AGE>))?",
    r'\s*"location": "{home}/cache/repository-stores/(?:<STORE_KEY[^>"]*>|[0-9a-f]{{64}})'
    r'/repository\.git",',
)


def first_clone_stderr(url: str, home: Path, *, then: str = "") -> str:
    """A pattern for everything a first clone writes to stderr when it is not timed.

    For a test whose clock is the machine's: where the clone goes, and that it is done,
    in so many seconds and with a size if Git reported one. Match it whole, so that a
    line naming a store or a staging entry cannot stand beside these two.
    """

    done = re.escape(f"cloned {url} in ") + r"\d+(?:\.\d)? s(?: \([\d.]+ (?:bytes?|[KMG]iB)\))?"
    following = re.escape(f"; {then}") if then else ""
    return re.escape(f"cloning {url} into {home}/cache\n") + done + following + r"\n"


def cache_hit_stderr(url: str, home: Path) -> str:
    """A pattern for the one line a cache hit writes to stderr, with whatever age."""

    age = r"(?:less than a minute|\d+ (?:minute|hour|day)s?) ago"
    return re.escape(f"using the clone of {url} cached in {home}/cache, fetched ") + age + r"\n"


def label_home(text: str, home: Path, label: str = HOME_LABEL) -> str:
    """*text* with the application home *home* as *label*, checked to be where it may be.

    A first clone says where it goes and a cache hit says where it was found, each in
    one line of stderr, and a served mirror's status says where the mirror is kept, in
    its ``location``. The home is named nowhere else in what a command prints: not in an
    identity line or an error, and not in any other field of a route's answer. The
    clone's lines name the cache directory and stop, and the location is the store's
    bare repository exactly: a line that went on to a staging entry, or named a store
    anywhere else, is refused here, before an update could write it into a transcript.
    """

    labelled = text.replace(str(home), label)
    allowed = [re.compile(line.format(home=re.escape(label))) for line in _HOME_LINES]
    for line in labelled.splitlines():
        assert label not in line or any(pattern.fullmatch(line) for pattern in allowed), (
            f"the application home is named outside the lines that may name it: {line}"
        )
    return labelled


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
    replaced with the same instant so ``stale`` is a function of the fixture. What a
    clone says of itself reads a monotonic clock, which stands still: its elapsed time
    is ``0.0 s`` however loaded the machine, and no status line is ever due.
    """

    clock = FixedClock()

    class ClockDatetime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:  # pyright: ignore[reportIncompatibleMethodOverride]
            return clock.read()

    monkeypatch.setattr(records, "datetime", ClockDatetime)
    monkeypatch.setattr(mirror_refresh, "_now_utc", clock.read)
    monkeypatch.setattr(clone_report, "_monotonic", float)
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
    test. That goes through ``_allow_installed_git``, which asks
    ``tests/admitted_git.py`` whether this run names an admitted release, so
    ``tests/suite_gates.py`` sees the module that called and holds it to
    ``ADMITTED_GIT_TESTS``.
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

# What stands in a recording for the directory a recorder builds in, for the application
# home inside it, and for the key of each store it serves, in the order it names them.
# A stand-in key is not hexadecimal, so nothing takes it for a real one:
# devtools/golden_fixup.py patterns a real key in a transcript, and a session's
# transcript must keep these literal.
SANDBOX_STAND_IN: Final = "/sandbox"
APPLICATION_HOME_STAND_IN: Final = "/sandbox/application-home"
STORE_KEY_STAND_INS: Final = ("store-key-1", "store-key-2")


def stand_in_sandbox(
    recorded: Any, sandbox: Path, *store_keys: str, home: Path | None = None
) -> Any:
    """*recorded* without what names this run: its directory, and its stores' keys.

    A served mirror's status says what it mirrors and where it is kept. Both are paths
    under the directory the recorder built them in, and a store's key is derived from
    its origin's address, so from that directory too. Each exact value is replaced
    wherever it stands, and nothing is replaced by a field's name: a path a response
    should not carry shows in the recording as ``/sandbox/…`` rather than being hidden.

    *home* is the application home when a location spells it out, which it does when
    the home is not under the user's home directory.
    """

    assert len(store_keys) <= len(STORE_KEY_STAND_INS), "add a stand-in for each store served"
    text = json.dumps(recorded)
    for key, stand_in in zip(store_keys, STORE_KEY_STAND_INS, strict=False):
        text = text.replace(key, stand_in)
    if home is not None:
        text = text.replace(json.dumps(str(home))[1:-1], APPLICATION_HOME_STAND_IN)
    return json.loads(text.replace(json.dumps(str(sandbox))[1:-1], SANDBOX_STAND_IN))


def answer(response: Any) -> dict[str, Any]:
    """One response as a session replays it: the status and the decoded body."""

    return {"status": response.status_code, "body": response.json()}


def settle(client: Any) -> dict[str, Any]:
    """Poll ``/api/source/status`` as a page does until no refresh runs; return that status."""

    deadline = time.monotonic() + 50
    while True:
        status: dict[str, Any] = client.get("/api/source/status").json()
        if not status["refreshing"]:
            return status
        assert time.monotonic() < deadline, "the refresh did not finish"
        time.sleep(0.02)


def serve_published(published: PublishedSource, *, serving: bool = False) -> None:
    """Tell the next application lifespan to serve *published* at its default revision.

    Nothing is opened here: the ``TestClient`` a recorder then starts opens the pin, as
    the lifespan of ``metab <url>`` does. *serving* is serve mode, in which that
    lifespan refreshes a stale mirror by itself; without it the mirror is served as a
    one-shot command serves it, and only a request starts a refresh.

    The source session is reset first. Each test already starts from a fresh one
    (``_reset_served_source`` in ``tests/conftest.py``), so this reset is for a recorder
    that serves more than once in one test, as ``tests/test_diff_view_file_session.py``
    does when it models a server restarted on another repository: the generations it
    records must count from the restart.
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
