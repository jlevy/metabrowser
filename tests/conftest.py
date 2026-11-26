"""Shared Metabrowser test fixtures."""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
import types
from collections.abc import Generator
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urljoin

import pytest

import metabrowser.builtin_plugins.agents.adapters  # noqa: F401  # pyright: ignore[reportUnusedImport]
from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from tests import (
    chrome_starts,
    suite_gates,
    suite_tiers,
    suite_timing,
    suite_workers,
    transient_output,
)
from tests.file_ages_git import (  # noqa: F401
    file_ages_git,  # pyright: ignore[reportUnusedImport]
    fixed_file_ages_git,  # pyright: ignore[reportUnusedImport]
)
from tests.github_pull_fixture import Origin, build_origin, copy_origin
from tests.process_group import owned_profile
from tests.required_tools import require_git, require_node

# Test discovery imports the server from several module scopes. Never let an
# operator's shell or dotenv configuration alter collection or load external plugins.
os.environ["METABROWSER_PLUGINS_DIRS"] = ""
# No server a test starts is an open, so none records its root as a recent target: not in
# a test's own configuration directory (`_isolated_configuration`), and not, from a
# module- or session-scoped fixture that starts before any test's exists, in the list of
# whoever runs the suite. A test of the record itself turns it back on.
os.environ["METABROWSER_RECORD_RECENT"] = "0"
# Nor does anything a test runs read or write the configuration directory of whoever runs
# the suite, where the recent targets live beside `config.yml`: a forget or a clear would
# change that list whatever the variable above says. Each test gets a directory of its own
# (`_isolated_configuration`); a fixture that starts before one exists gets the run's.
os.environ["METABROWSER_CONFIG_DIR"] = os.path.join(
    os.path.realpath(tempfile.gettempdir()), f"metabrowser-test-config-{os.getpid()}"
)
# Nor does any server a test starts write an event log (metabrowser.event_log) into the
# state directory of whoever runs the suite; and a read of the log, as `/api/event-log`
# does, reads an empty directory of the suite's own. A test of the log opens one itself.
os.environ["METABROWSER_EVENT_LOG"] = "0"
# Nor does a gh that fails make a test probe the network (metabrowser.network_cause): a
# test of the probe names a local target itself.
os.environ["METABROWSER_NETWORK_PROBE"] = "0"
# Nor does a `metab` a test starts, as a process or in process, keep a store of a
# checkout's origin (metabrowser.checkout_store), which would fetch that origin, a GitHub
# address in most fixtures, from the network (bead mb-i4x0). A test of the store keeps
# one in process with the `keeps_origin_store` fixture, and `remote_url_for` naming a
# local origin.
os.environ["METABROWSER_ORIGIN_STORE"] = "0"
os.environ["METABROWSER_STATE_DIR"] = os.path.join(
    tempfile.gettempdir(), f"metabrowser-test-state-{os.getpid()}"
)
for _capability_env in ("METAB_UNTRUSTED", "METAB_ACTIVE_CONTENT", "METAB_ALLOW_EDITS"):
    os.environ.pop(_capability_env, None)
# Where `--present` opens a target is the operator's preference; a test that reads one
# sets it.
os.environ.pop("METABROWSER_OPEN_IN", None)
# Nor does the reserve a first clone leaves free (metabrowser.cache.free_space) come from
# whoever runs the suite: with a large one exported, every `file://` first clone a test
# makes was refused (review C2 on #768). A test of the reserve sets it.
os.environ.pop("METABROWSER_CACHE_RESERVE_MB", None)

# The pre-push gate runs this suite inside a githook, and from a linked worktree git
# exports GIT_DIR there. It outranks the working directory and `git -C`, so a fixture
# that spawns git with the inherited environment acts on the developer's repository:
# its `git init` writes core.bare = true into the configuration every worktree
# shares. Scrub once, here, before any test module is imported, so a fixture that
# forgets to scrub its own calls cannot do that. A test that needs a poisoned GIT_DIR
# sets one itself. tests/test_git_hook_environment.py pins this.
for _name in _REPO_PINNING_GIT_VARS:
    os.environ.pop(_name, None)


# No test reaches the gh a developer is signed in to. A real ``gh auth git-credential``,
# ``gh auth status``, or ``gh api`` call reads the keychain and can print or send a
# token, so every test runs with a failing stand-in first on PATH, which each call
# looks gh up on. The stand-in logs each call, with the test that made it, to
# GH_GUARD_LOG, and the terminal summary reports them. A test that needs gh installs
# its own fake later, which comes first; only the opt-in live smoke test, marked
# ``live_github`` and run with METABROWSER_LIVE_GITHUB=1, sees the real one.
_FAKE_GH = """#!/bin/sh
printf '%s\\t%s\\n' "${PYTEST_CURRENT_TEST:-unknown}" "$*" >> "$METABROWSER_TEST_GH_LOG"
echo "gh is not available to tests; install a fake gh for this test" >&2
exit 1
"""
GH_GUARD_LOG_ENV = "METABROWSER_TEST_GH_LOG"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--shard",
        type=suite_tiers.parse_shard,
        default=None,
        metavar="I/N",
        help="run the Ith of N disjoint parts of the selected tests (tests/suite_tiers.py)",
    )
    parser.addoption(
        "--shard-by",
        choices=suite_tiers.SHARD_UNITS,
        default=suite_tiers.BY_TEST,
        help="deal --shard's parts by single test, or by whole file (tests/suite_tiers.py)",
    )
    suite_timing.add_option(parser)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "live_github: an opt-in test that talks to github.com with the real gh"
    )
    config.addinivalue_line(
        "markers",
        "macos_tier: runs only on macOS, on its extended ACLs, its case-insensitive "
        "file system, or Apple's git shim; `make test-macos` runs these alone and fails "
        "if one skips",
    )
    for marker, meaning in suite_tiers.MARKER_HELP.items():
        config.addinivalue_line("markers", f"{marker}: {meaning}")
    # The hooks that judge a skip against its tier, and a marker against its meaning; see
    # tests/suite_gates.py.
    config.pluginmanager.register(suite_gates)
    # The chrome marker, --shard, and an empty tier; see tests/suite_tiers.py.
    config.pluginmanager.register(suite_tiers)
    config.pluginmanager.register(suite_tiers.EmptyTiers(), "suite-empty-tiers")
    # --file-durations; see tests/suite_timing.py.
    config.pluginmanager.register(suite_timing.FileTimes(), "suite-file-times")
    # Reports a pytest-xdist worker can send; see tests/suite_workers.py.
    config.pluginmanager.register(suite_workers)
    config.pluginmanager.register(suite_workers.StackDumps(), "suite-stack-dumps")


@pytest.fixture(autouse=True)
def fresh_markdown_child() -> Generator[None]:
    """Give each test its own process-wide Markdown child worker, and stop it after.

    ``shared_worker()`` keeps its refusals for the process, so without this a test whose
    document an earlier test had refused would pass without rendering anything (review A
    of #527, A13), and a worker a test left running would carry its child into the next.
    A test that runs the serve path in-process marks the process as serving pages, which
    starts the child ahead of documents; the next test begins as a one-shot command.

    A test whose event loop ended while the worker was still starting a child fails: it
    skipped the close the server's lifespan always makes (``ProjectionWorker.aclose``),
    which cancels the start on its own. ``asyncio.run`` cancels it together with the task
    connecting its pipes instead, and on CPython 3.12 and 3.13 a start cancelled while it
    spawns never finishes, so the run never returns (mb-4g7f). A run that escaped the hang
    leaves the start cancelled, which this reads. A child that was ready when its loop
    ended is only stopped here, as before.
    """

    from metabrowser.diff import markdown_projection_worker as worker_module

    shared = worker_module.shared_worker
    shared.cache_clear()
    serving = worker_module._SERVING  # pyright: ignore[reportPrivateUsage]
    serving.pages = False
    yield
    serving.pages = False
    if shared.cache_info().currsize:
        worker = shared()
        loop = worker._loop  # pyright: ignore[reportPrivateUsage]
        # The worker's own close and stop forget their start, so a start still kept was
        # ended, if at all, by its loop's end.
        start = worker._starting  # pyright: ignore[reportPrivateUsage]
        cut_off = (
            loop is not None
            and loop.is_closed()
            and start is not None
            and (not start.done() or start.cancelled())
        )
        # Its event loop may be closed by now; stopping kills the child by its process.
        with contextlib.suppress(RuntimeError):
            worker.stop()
        shared.cache_clear()
        if cut_off:
            pytest.fail(
                "The event loop that used the shared Markdown child worker ended while it"
                " was starting a child: end that loop with `await shared_worker().aclose()`,"
                " as the server's lifespan does",
                pytrace=False,
            )


# ── Tests that must not be silently absent ─────────────────────────────────────
# docs/e2e-testing.md ("Test Tiers") says which tier runs where.


@pytest.fixture(scope="session")
def node_on_path() -> str:
    """Behind ``needs_node``: without Node the run stops; see ``tests/required_tools.py``.

    Session scope puts it ahead of a module's own fixtures, which may spawn the tool.
    """

    return require_node()


@pytest.fixture(scope="session")
def git_on_path() -> str:
    """Behind ``needs_git``: without Git the run stops; see ``tests/required_tools.py``."""

    return require_git()


@pytest.fixture
def chrome_profile(tmp_path_factory: pytest.TempPathFactory) -> Generator[Path, None, None]:
    """A headless Chrome's profile directory, owned by the test that drives the browser.

    It is removed after the test. A process still naming it then escaped the test's
    process group: it is reported, failing the test, and left running; see
    ``tests/process_group.py``. Each Chrome the test starts through
    ``tests/dom/chrome-session.mjs`` is noted for the run's summary of starts
    (``tests/chrome_starts.py``).
    """

    starts = chrome_starts.log_path(tmp_path_factory.getbasetemp())
    with (
        owned_profile("metab-test-chrome-") as profile,
        pytest.MonkeyPatch.context() as patch,
    ):
        patch.setenv(chrome_starts.STARTS_ENV, str(starts))
        yield profile


@pytest.fixture(scope="session")
def _pull_origin_built(  # pyright: ignore[reportUnusedFunction]
    tmp_path_factory: pytest.TempPathFactory, git_on_path: str
) -> Origin:
    """The GitHub stand-in origin, built once. Only ``pull_origin`` reads it."""

    return build_origin(tmp_path_factory.mktemp("github-pull-origin"))


@pytest.fixture
def pull_origin(tmp_path: Path, _pull_origin_built: Origin) -> Origin:
    """This test's own copy of the GitHub stand-in origin, in its ``tmp_path``.

    A test fetches from the origin and some move its refs, so none is handed the one the
    session shares.
    """

    return copy_origin(_pull_origin_built, tmp_path)


@pytest.fixture(scope="session")
def _gh_guard_bin(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:  # pyright: ignore[reportUnusedFunction]
    directory = tmp_path_factory.mktemp("no-real-gh")
    gh = directory / "gh"
    gh.write_text(_FAKE_GH, encoding="utf-8")
    gh.chmod(0o755)
    return str(directory), str(directory / "calls.log")


@pytest.fixture(autouse=True)
def _no_real_gh(  # pyright: ignore[reportUnusedFunction]
    request: pytest.FixtureRequest, _gh_guard_bin: tuple[str, str]
) -> Generator[None, None, None]:
    """Put the failing stand-in gh first on PATH, except for the opt-in live smoke test.

    Its own ``MonkeyPatch``, not the ``monkeypatch`` fixture: requesting that here would
    set it up before every module's own autouse fixtures, so a test's patches would be
    undone only after those fixtures' teardown had run against them.
    """

    live = request.node.get_closest_marker("live_github") is not None
    if live and os.environ.get("METABROWSER_LIVE_GITHUB") == "1":
        yield
        return
    directory, log = _gh_guard_bin
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PATH", directory + os.pathsep + os.environ.get("PATH", ""))
        patch.setenv(GH_GUARD_LOG_ENV, log)
        yield


@pytest.fixture(autouse=True)
def _fresh_github_status() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Start each test with no kept GitHub status answer.

    The status check keeps an answer for a few seconds per gh and configuration
    (``gh_status.GH_STATUS_TTL_S``), and tests swap what one fake gh answers between
    commands, which that key cannot see.
    """

    from metabrowser.builtin_plugins.github.gh_status import forget_github_status

    forget_github_status()
    yield
    forget_github_status()


@pytest.hookimpl(wrapper=True)
def pytest_runtestloop(session: pytest.Session) -> Generator[None, object, object]:
    """Warm Chrome up once before a run with a test that drives it, so the runner's cold
    first start falls outside every test's bounds, and write how that went to the
    terminal at once (``tests/chrome_starts.py``).

    A run that collection errors will stop, as pytest's own loop then does, is not
    warmed: that could cost the warm-up's whole bound before the run stops."""

    option = session.config.option
    stopping = session.testsfailed and not option.continue_on_collection_errors
    if (
        not option.collectonly
        and not stopping
        and any(item.get_closest_marker(suite_tiers.CHROME_MARKER) for item in session.items)
    ):
        basetemp = session.config._tmp_path_factory.getbasetemp()  # pyright: ignore[reportAttributeAccessIssue]
        told = chrome_starts.warm_up(basetemp)
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if isinstance(reporter, pytest.TerminalReporter):
            for line in told:
                reporter.write_line(line)
            reporter.flush()
    return (yield)


_SUMMARY_LINES = pytest.StashKey[list[str]]()
_TMP_PATH = pytest.StashKey[Path]()
_FAILED = pytest.StashKey[bool]()


@pytest.hookimpl(wrapper=True)
def pytest_fixture_setup(
    fixturedef: pytest.FixtureDef[object], request: pytest.FixtureRequest
) -> Generator[None, object, object]:
    """Note the test's ``tmp_path``, however it was asked for, for its reports below."""

    result = yield
    if fixturedef.argname == "tmp_path" and isinstance(result, Path):
        request.node.stash[_TMP_PATH] = result
    return result


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item) -> Generator[None, pytest.TestReport, object]:
    """Empty the test's ``tmp_path`` after its teardown report, unless one of its reports
    failed (``tests/transient_output.py``).

    The teardown report is made after every fixture's teardown, so a test whose setup
    errored, or whose teardown failed after its call passed, keeps its directory, as one
    whose call failed does. Outermost, so that the report seen is the one pytest records,
    after an expected failure is marked as one.
    """

    report = yield
    failed = item.stash.get(_FAILED, False) or report.failed
    item.stash[_FAILED] = failed
    path = item.stash.get(_TMP_PATH, None)
    if report.when == "teardown" and path is not None and not failed:
        transient_output.empty(path)
    return report


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Read what the terminal summary reports from the run's base directory, then release
    the locks of sessions whose process has gone and remove a passing run's base directory
    (``tests/transient_output.py``).

    First, because pytest's own ``pytest_sessionfinish`` then prunes older sessions'
    directories, and the terminal summary is written only after that. A base directory
    given with ``--basetemp``, as pytest-xdist gives each worker its own, is not this
    session's to remove. Nothing here raises: from this hook an exception would replace the
    run's report, its failures included, with pytest's internal error.
    """

    config = session.config
    try:
        basetemp = config._tmp_path_factory.getbasetemp()  # pyright: ignore[reportAttributeAccessIssue]
    except OSError as error:
        config.stash[_SUMMARY_LINES] = [f"transient output: no base directory: {error}"]
        return
    config.stash[_SUMMARY_LINES] = _summary_lines(basetemp)
    if config.option.basetemp is None:
        transient_output.end_session(basetemp, passed=exitstatus == 0)


def _summary_lines(basetemp: Path) -> list[str]:
    try:
        return [*_gh_guard_lines(basetemp), *chrome_starts.summary(basetemp)]
    except Exception as error:
        # An error in reading the logs would otherwise replace the run's whole report
        # (pytest_sessionfinish above), which matters more than these lines.
        return [f"summary: the run's logs could not be read: {error!r}"]


def _gh_guard_lines(basetemp: Path) -> list[str]:
    # pytest also links ``no-real-ghcurrent`` to the numbered directory; read each once.
    # Under pytest-xdist each worker's base is ``popen-gw<N>`` in this one, with its own
    # stand-in and log, and the summary this process prints reads them all.
    patterns = ("no-real-gh*/calls.log", "popen-gw*/no-real-gh*/calls.log")
    logs = {log.resolve() for pattern in patterns for log in basetemp.glob(pattern)}
    lines: list[str] = []
    calls: list[str] = []
    for log in sorted(logs):
        try:
            # The stand-in logs a call's arguments as they were given, in any encoding.
            calls += log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as error:
            lines.append(f"gh guard: {log} could not be read: {error}")
    if calls:
        tests = sorted({line.split("\t", 1)[0].rsplit(" ", 1)[0] for line in calls})
        lines.append(
            f"gh guard: {len(calls)} gh call(s) reached the failing stand-in, "
            f"from {len(tests)} test(s): " + ", ".join(tests)
        )
    return lines


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Say which tests would have run gh, so a new one is noticed, and how the run's
    Chrome starts went (``tests/chrome_starts.py``), as ``pytest_sessionfinish`` read
    them."""

    for line in terminalreporter.config.stash.get(_SUMMARY_LINES, []):
        terminalreporter.write_line(line)


@pytest.fixture(autouse=True)
def _reset_capabilities() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Keep the process capability block isolated between tests."""
    from metabrowser.capabilities import DEFAULT_CAPABILITIES, set_capabilities

    set_capabilities(DEFAULT_CAPABILITIES)
    yield
    set_capabilities(DEFAULT_CAPABILITIES)


@pytest.fixture
def keeps_origin_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let an application in process keep a store of its checkout's origin, as one does
    outside the suite, which keeps none (``METABROWSER_ORIGIN_STORE`` above). A test
    that uses it points ``remote_url_for`` at a local origin, or fetches nothing."""
    from metabrowser.checkout_store import ORIGIN_STORE_ENV

    monkeypatch.delenv(ORIGIN_STORE_ENV, raising=False)


@pytest.fixture(autouse=True)
def _reset_served_mirror() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Never let a mirror one test served reach the next test's application lifespan."""
    from metabrowser.mirror_refresh import serve_mirror

    serve_mirror(None)
    yield
    serve_mirror(None)


@pytest.fixture(autouse=True)
def _reset_served_source() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Give every test a fresh source session, and put back the served root it found.

    The session, its generation counter, the subject opener and the served root are
    process globals. Rendering the shell, serving a folder or attaching a subject
    leaves them behind, so a later test would count its generations from where an
    earlier one stopped and pass in one module order only. With this fixture a test
    sets a root or attaches a subject and needs no ``try``/``finally`` to undo it.

    Two things stay with the test. A subject it opened is its own to close: the reset
    only drops the reference. And a reset in a test body is still right where the test
    models a second server process.
    """
    from metabrowser import paths_safe
    from metabrowser.source import reset_source_session

    root = paths_safe.ROOT_DIR
    reset_source_session()
    yield
    if root != paths_safe.ROOT_DIR:
        # Fires the root callbacks, so per-root caches do not outlive the root either.
        paths_safe._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
    reset_source_session()


@pytest.fixture(autouse=True)
def _reset_rate_budget() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Start every test with no observed GitHub rate budget and no hold, as a new process.

    The governor keeps them per process, so a refusal one test replays would otherwise hold
    background work in every test after it until the replayed reset time.
    """
    from metabrowser.builtin_plugins.github import gh, gh_budget

    # The account check's last answer is per process too (gh.gh_account): a test starts
    # with none, so its first check is unconditional whatever ran before it.
    gh_budget.forget()
    gh.forget_account()
    yield
    gh_budget.forget()
    gh.forget_account()


@pytest.fixture(autouse=True)
def _reset_label_sets() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Start every test with no parsed label set and no unwritten outcome, as a new process.

    ``pull_labels`` keeps both per process, by home and source, and the fixtures share one
    source, so a set one test parsed or a refusal it remembered would reach the next. A
    process that never imported it holds neither, and is not made to import it here.
    """

    def forget() -> None:
        loaded = sys.modules.get("metabrowser.builtin_plugins.github.pull_labels")
        if loaded is not None:
            loaded.forget()

    forget()
    yield
    forget()


@pytest.fixture(autouse=True)
def _reset_probe_turns() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Start every test with no probe in flight and none refused, as a new process.

    ``served_pull`` keeps both per process, by a pull request's refresh key, and the
    fixtures share one repository and one clock, so a refusal one test left would hold
    back the next test's probe. A process that never imported it holds neither.
    """

    def forget() -> None:
        loaded = sys.modules.get("metabrowser.builtin_plugins.github.served_pull")
        if loaded is not None:
            loaded.forget_probes()

    forget()
    yield
    forget()


@pytest.fixture(autouse=True)
def _reset_prefetch_lanes() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Start every test with no prefetch lane, as a new process.

    ``pull_prefetch`` keeps one lane per repository a process serves, and an idle lane a
    page asked for lately keeps a scan's records from the cores walk (``reserved``), so a
    lane one test left, asked for at the shared clock, would hold back the next test's
    walk. A process that never imported it holds none.
    """

    def forget() -> None:
        loaded = sys.modules.get("metabrowser.builtin_plugins.github.pull_prefetch")
        if loaded is not None:
            loaded.forget_lanes()

    forget()
    yield
    forget()


@pytest.fixture(scope="session")
def _no_server_command(tmp_path_factory: pytest.TempPathFactory) -> str:  # pyright: ignore[reportUnusedFunction]
    refuser = tmp_path_factory.mktemp("no-detached-server") / "metab"
    refuser.write_text(
        "#!/bin/sh\necho 'no metab server starts in a test; set present.server_command' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    refuser.chmod(0o755)
    return str(refuser)


@pytest.fixture(autouse=True)
def _no_detached_server(_no_server_command: str) -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Start no real server from ``metab --present``, unless a test names its own.

    A browser delivery starts ``metab ROOT`` detached, which outlives the test and opens
    the page in the browser of whoever runs the suite. Every test starts with
    ``present.server_command`` set to a program that exits 1 at once, as a server that
    cannot start does; a test that needs a server sets its own. Its own ``MonkeyPatch``,
    as ``_no_real_gh`` explains.
    """

    from metabrowser.cli import present

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(present, "server_command", (_no_server_command,))
        yield


@pytest.fixture(autouse=True)
def _restore_environment() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Put back whatever a test, or the code it ran, changed in ``os.environ``.

    The CLI exports what it resolves: ``--log-level`` and the dotenv chain both write
    ``os.environ``. ``monkeypatch.delenv`` on a name that is absent records no undo, so
    a value written that way outlived its test. A debug log level left by a dotenv
    test then put tracebacks into the stderr of every in-process command that ran
    after it, which the default module order happened to hide.
    """
    # pytest keeps the running test's name in this one and rewrites it for each phase.
    own = "PYTEST_CURRENT_TEST"
    before = {name: value for name, value in os.environ.items() if name != own}
    yield
    for name in os.environ.keys() - before.keys() - {own}:
        del os.environ[name]
    for name, value in before.items():
        if os.environ.get(name) != value:
            os.environ[name] = value


@pytest.fixture(autouse=True)
def _reset_browser_response_caches() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Keep route response caches isolated between tests."""
    yield
    try:
        from metabrowser.server import reset_response_caches_for_tests

        reset_response_caches_for_tests()
    except Exception:
        # Defensive: never let cleanup failure mask a test failure.
        pass


@pytest.fixture(autouse=True)
def _reset_process_caches() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Drop the process-wide state that could change a later test's verdict.

    Application-cache probe results are keyed by device and inode, and a freed inode can
    come back as another test's home. The ignore cache outlives its test by its TTL, keyed
    by a root path a test can reuse. The catalog revision counts distinct catalogs for the
    process, so a test would read a value set by whichever tests ran before it, and the
    catalog caches are left filled. Held private directories keep their descriptors open,
    and a test that stages a race against the first open of a directory needs that open
    to happen.

    Left alone because a stale value cannot reach another test: ``tree_source._POOLS`` and
    ``dotenv._reported``, keyed by a path under the ``tmp_path`` of the test that made
    them, and ``server._EXTRA_ALLOWED_HOSTS``, where tests only add a host the default
    list already holds.
    """
    yield
    from metabrowser import events_route, home, tree
    from metabrowser.cache import probe

    home._HELD_DIRECTORIES.clear()  # pyright: ignore[reportPrivateUsage]
    probe._RESULTS.clear()  # pyright: ignore[reportPrivateUsage]
    tree._IGNORE_CACHE.clear()  # pyright: ignore[reportPrivateUsage]
    events_route._CATALOG_BODY_CACHE.clear()  # pyright: ignore[reportPrivateUsage]
    events_route._CATALOG_ETAG_BY_CHECKPOINT.clear()  # pyright: ignore[reportPrivateUsage]
    events_route._CATALOG_REVISION.update(identity=None, value=0)  # pyright: ignore[reportPrivateUsage]
    # Kept by commit IDs alone, which the fixtures share, so one test's measurement would
    # answer another's without the store bank the second one checks.
    from metabrowser.git.change_size import clear_kept_sizes

    clear_kept_sizes()


class DocumentReference(NamedTuple):
    """One URL a browser would fetch or follow from a served document."""

    tag: str
    attribute: str
    value: str
    resolved: str


# The attributes whose value is a URL the browser resolves against the
# document's own address. Enough for the static pages these tests serve;
# a fixture that needs another element adds it here.
_REFERENCE_ATTRIBUTES: dict[str, str] = {
    "a": "href",
    "embed": "src",
    "frame": "src",
    "iframe": "src",
    "img": "src",
    "link": "href",
    "script": "src",
    "source": "src",
}


class _ReferenceCollector(HTMLParser):
    def __init__(self, document_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._document_url = document_url
        self.references: list[DocumentReference] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name == "base":
            # Resolution below is relative to the document URL. A document
            # that moves its base would make every answer here wrong, so
            # refuse rather than report a plausible lie.
            assert not any(key.lower() == "href" for key, _ in attrs), (
                "document_references does not honour <base href>"
            )
            return
        attribute = _REFERENCE_ATTRIBUTES.get(name)
        if attribute is None:
            return
        for key, value in attrs:
            if key.lower() == attribute and value:
                self.references.append(
                    DocumentReference(
                        tag=name,
                        attribute=attribute,
                        value=value,
                        resolved=urljoin(self._document_url, value),
                    )
                )


def document_references(document: str, document_url: str) -> list[DocumentReference]:
    """Resolve the URLs a browser would request from a served document.

    ``urljoin`` performs the same RFC 3986 resolution a browser applies to
    a relative reference against the document's own URL, so this answers
    "where would the next request go" without running a browser. It says
    nothing about whether a browser issues those requests or what it does
    with the bytes; only the address is derived here.
    """

    collector = _ReferenceCollector(document_url)
    collector.feed(document)
    collector.close()
    return collector.references


class SyntheticIndexWriter:
    """Dict-like façade for building a Python provider handle in tests.

    Several rollup tests assemble an index in memory instead of on disk. The
    index keeps derived structures alongside ``_entries`` (the parent/child
    grouping and the subtree-aggregate memo), so assigning into ``_entries``
    directly would leave those out of sync and produce empty rollups. Writing
    through the real store path keeps a synthetic index behaving like a
    walked one.
    """

    __slots__ = ("_index",)

    def __init__(self, index: object) -> None:
        self._index = index

    def __setitem__(self, path: str, entry: object) -> None:
        assert getattr(entry, "path", None) == path, "entry.path must match its key"
        self._index._replace_index_entry(entry)  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _isolated_configuration(tmp_path: Path) -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Isolate configuration without changing other fixtures' monkeypatch lifetime."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("METABROWSER_CONFIG_DIR", str(tmp_path / "metabrowser-config"))
        yield


@pytest.fixture(autouse=True)
def _reset_delivery() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """A test that runs a serve mode says it serves for local use; the next one starts
    from the default, which compresses for every client (metabrowser.delivery)."""
    from metabrowser import delivery

    delivery.serve_locally(False)
    yield
    delivery.serve_locally(False)


@pytest.fixture(autouse=True)
def _one_module_per_name() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """A test leaves each ``metabrowser`` module as one object, however it is reached.

    Importing a submodule sets it as an attribute of its package, so a test that forgot a
    module from ``sys.modules`` and imported it again leaves the package holding the new
    one when the old is put back, and ``from metabrowser.git import content_routes`` (a
    test's patch) then reaches a module the server's own import does not (mb-6byq).
    `tests/forgotten_module.py` forgets a module and leaves no such trace.
    """

    yield
    split: list[str] = []
    for name, module in list(sys.modules.items()):
        if not name.startswith("metabrowser."):
            continue
        parent_name, _, child = name.rpartition(".")
        held = getattr(sys.modules.get(parent_name), child, None)
        if isinstance(held, types.ModuleType) and held is not module:
            split.append(name)
    assert not split, (
        f"after this test {split} is one module in sys.modules and another as its package's "
        "attribute: a test that forgets a module must put both back (tests/forgotten_module.py)"
    )
