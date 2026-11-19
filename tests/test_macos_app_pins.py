"""The macOS app's copies of ``metab``'s values, each held to its definition here.

The app copies a few of ``metab``'s constants into Swift, where nothing imports them:
the bounds on acquiring a source, which a repository's start must outlast; the port walk,
which keeps the two launch gates' ranges apart; the hosts of the GitHub reducer; and the
page size of the cache's sources route. Its ``Info.plist`` also declares the key
``--present`` reads before it sends anything, and the oldest ``metab`` it runs, which
``--doctor`` reads; each install's upgrade step is the doctor's. It also reads two kinds
of ``metab``'s output: the clone report a repository's start writes to stderr, which its
status view shows, and the state an ``Error:`` line names, which says when GitHub is why
a start failed; its tests parse samples of each, which are held here to what ``metab``
writes.
These checks run in CI's Python jobs, which run on every change, so a change on either
side fails here, where the macOS workflow's path filter would not have run the app's own
tests (review A5 on #539).
"""

from __future__ import annotations

import asyncio
import io
import os
import plistlib
import re
import tomllib
from pathlib import Path
from typing import Any, Final, cast, get_args

import pytest

from metabrowser.builtin_plugins.github import gh as github_gh
from metabrowser.builtin_plugins.github import provider as github_provider
from metabrowser.builtin_plugins.github import urls as github_urls
from metabrowser.cache.acquire import RESERVATION_WAIT_S
from metabrowser.cache.origin import (
    REMOTE_PROBE_TIMEOUT_S,
    RemoteFailureState,
    describe_remote_failure,
)
from metabrowser.cache.projection import MAX_PAGE_LIMIT, sources_response
from metabrowser.cache.records import canonical_now
from metabrowser.cli import clone_report
from metabrowser.cli.clone_report import LOG_INTERVAL_S, CloneReport, saying_while_waiting
from metabrowser.cli.doctor import (
    CHECKOUT_PROJECT,
    CHECKOUT_VENV,
    METAB_UPGRADE_COMMANDS,
    PIPX_METADATA,
    UV_RECEIPT,
)
from metabrowser.cli.present import (
    MINIMUM_METAB_KEY,
    OPENS_URLS_KEY,
    Presentable,
    resolve_target,
)
from metabrowser.git.process import GIT_ACQUISITION_TIMEOUT_S
from metabrowser.git.progress import GitProgress
from metabrowser.home import METABROWSER_CACHE_DIR_ENV
from metabrowser.server_utils import DEFAULT_PORT_SEARCH_COUNT
from metabrowser.settings import DEFAULT_BROWSER_PORT
from tests.cache_home_fixture import FLASK_HTTPS, build_populated_home

APP = Path(__file__).resolve().parent.parent / "apps" / "macos"
SHELL_CORE = APP / "Sources" / "ShellCore"
SHELL_CORE_TESTS = APP / "Tests" / "ShellCoreTests"
GOLDEN = Path(__file__).resolve().parent / "golden"
PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
CHANGELOG = PYPROJECT.parent / "CHANGELOG.md"


def _swift_value(relative: str, declaration: str) -> str:
    """What ``declaration`` (``static let NAME``, with or without a type) is set to."""

    source = (SHELL_CORE / relative).read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^\s*(?:public\s+)?static\s+let\s+{re.escape(declaration)}(?:\s*:\s*[\w<>]+)?\s*=\s*(.+?)\s*$",
        re.MULTILINE,
    )
    found = pattern.findall(source)
    assert len(found) == 1, f"{declaration} is not set once in {relative}: {found}"
    return found[0]


def _swift_seconds(relative: str, declaration: str) -> float:
    value = _swift_value(relative, declaration)
    match = re.fullmatch(r"\.seconds\((\d+(?:\.\d+)?)\)", value)
    assert match, f"{declaration} in {relative} is not .seconds(N): {value}"
    return float(match.group(1))


def _swift_int(relative: str, declaration: str) -> int:
    value = _swift_value(relative, declaration)
    assert re.fullmatch(r"\d+", value), (
        f"{declaration} in {relative} is not a whole number: {value}"
    )
    return int(value)


DEADLINE = "Supervision/StartupDeadline.swift"


def _minimum_metab() -> tuple[int, int, int]:
    value = _swift_value("Setup/MetabVersion.swift", "minimumRelease")
    match = re.fullmatch(r"\[(\d+), (\d+), (\d+)\]", value)
    assert match, f"MetabRequirement.minimumRelease is not [X, Y, Z]: {value}"
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def test_the_apps_minimum_metab_is_a_minor_release() -> None:
    """The minimum is ``X.Y.0`` (``docs/publishing.md#choosing-a-version``), and a checkout
    reports the next minor release as its development version, so it can meet it. With the
    default patch bump a checkout past 0.12.0 reported ``0.12.1.devN``, below ``0.13.0``.
    """

    minimum = _minimum_metab()
    assert minimum[2] == 0, (
        f"MetabRequirement.minimumRelease is {list(minimum)}, a patch release: a change "
        "the app needs ships in a new minor or major release "
        "(docs/publishing.md#choosing-a-version), so the minimum is X.Y.0"
    )
    tool = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]
    assert tool["uv-dynamic-versioning"]["bump"] == {"enable": True, "index": 1}, (
        "a checkout must report the next minor release as its development version, so it "
        "meets a minimum raised to that release"
    )


def test_a_checkout_rebuilds_its_version_after_a_commit_or_a_tag() -> None:
    """``make install`` is what the app tells a checkout's user to run, and it reaches a
    raised minimum only if the editable install's version is rebuilt when the commit or
    the tags change; by default uv rebuilds it only when ``pyproject.toml`` changes.
    """

    tool = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]
    keys = tool["uv"]["cache-keys"]
    assert {"file": "pyproject.toml"} in keys
    assert {"git": {"commit": True, "tags": True}} in keys


def test_the_apps_minimum_metab_is_released_or_next() -> None:
    """The minimum is the latest release's next minor at most, since a checkout reports
    that as its development version, and ``isReleased`` is true only once the latest
    release meets it, or the app would send users to an upgrade PyPI cannot satisfy.

    The latest release is the first ``## X.Y.Z`` heading in ``CHANGELOG.md``, which the
    release-preparation pull request adds before the tag (``docs/publishing.md``).
    """

    headings = re.findall(
        r"^## (\d+)\.(\d+)\.(\d+)$", CHANGELOG.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert headings, "CHANGELOG.md names no release"
    major, minor, patch = (int(part) for part in headings[0])
    latest = (major, minor, patch)
    minimum = _minimum_metab()
    released = _swift_value("Setup/MetabVersion.swift", "isReleased")
    assert released in {"true", "false"}, f"MetabRequirement.isReleased is {released}"
    assert minimum <= (major, minor + 1, 0), (
        f"MetabRequirement.minimumRelease is {list(minimum)}, beyond {major}.{minor + 1}.0, "
        f"the next minor after the latest release, {major}.{minor}.{patch}: a checkout "
        "reports that as its development version, so the app would refuse every one"
    )
    if minimum > latest:
        assert released == "false", (
            f"MetabRequirement.minimumRelease is {list(minimum)}, newer than the latest "
            f"release, {major}.{minor}.{patch}, so isReleased must be false: the upgrade "
            "command the app shows would ask PyPI for a release it does not have"
        )


def test_the_acquisition_bounds_are_metabs() -> None:
    probe = _swift_seconds(DEADLINE, "remoteProbe")
    fetch = _swift_seconds(DEADLINE, "fetch")
    validation = _swift_seconds(DEADLINE, "validation")
    attempts = _swift_int(DEADLINE, "attempts")
    assert probe == REMOTE_PROBE_TIMEOUT_S
    assert fetch == GIT_ACQUISITION_TIMEOUT_S
    # MetabAcquisition.reservationWait is RESERVATION_WAIT_S's expression.
    assert attempts * (probe + fetch + validation) == RESERVATION_WAIT_S
    assert _swift_seconds(DEADLINE, "progressLineInterval") == LOG_INTERVAL_S


def test_the_port_walk_is_metabs() -> None:
    launch = "Supervision/ServerLaunch.swift"
    assert _swift_int(launch, "defaultBasePort") == DEFAULT_BROWSER_PORT
    assert _swift_int(launch, "portSearchCount") == DEFAULT_PORT_SEARCH_COUNT
    # The repositories' walk starts a whole walk past the folders' range, and so past 8443.
    assert _swift_value(launch, "repositoryBasePort") == "defaultBasePort + 2 * portSearchCount"


def test_the_link_hosts_are_the_github_reducers() -> None:
    value = _swift_value("Folders/PresentPlan.swift", "hosts")
    hosts = set(re.findall(r'"([^"]+)"', value))
    assert hosts == set(github_urls._WEB_HOSTS) | {github_urls._RAW_HOST}


def test_the_cache_page_is_the_routes_largest() -> None:
    assert _swift_int("Folders/RepositoryCache.swift", "pageLimit") == MAX_PAGE_LIMIT


@pytest.mark.skipif(os.name != "posix", reason="owner-only storage needs POSIX")
def test_the_cache_answer_the_app_reads_is_metabs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``RepositoryCache.read`` finds a repository by keys and a value of the sources route.

    A renamed key, or another value for a published source, would make the app ask before
    every link with CI green on both sides (review C6 on #539). A source published as
    ``metab URL`` publishes one has them, under the root the dry run reports for a link
    into the repository, which is what the app compares ``display_url`` with.
    """

    swift = (SHELL_CORE / "Folders" / "RepositoryCache.swift").read_text(encoding="utf-8")
    read = ("sources", "identity", "display_url", "publication", "published", "problems")
    for literal in (*read, "next_after"):
        assert f'"{literal}"' in swift, f"RepositoryCache.swift no longer reads {literal!r}"

    home = tmp_path / "home"
    monkeypatch.setenv(METABROWSER_CACHE_DIR_ENV, str(home))
    build_populated_home(home)
    status, answer = sources_response(limit=MAX_PAGE_LIMIT, after=None)
    assert status == 200
    page = cast("dict[str, Any]", answer)
    assert "next_after" in page

    target = resolve_target("https://github.com/Pallets/Flask/pull/1", "", local=False)
    assert isinstance(target, Presentable)
    assert target.root == FLASK_HTTPS.address
    rows = [
        row
        for row in page["sources"]
        if row["identity"] is not None and row["identity"]["display_url"] == target.root
    ]
    assert len(rows) == 1
    assert rows[0]["publication"] == "published"
    assert rows[0]["problems"] == []


def test_the_app_declares_what_present_reads() -> None:
    """``--present`` sends a URL only to a bundle that declares the key (review A7)."""

    info = plistlib.loads((APP / "Resources" / "Info.plist").read_bytes())
    assert info.get(OPENS_URLS_KEY) is True
    # File > Open Recent lists repositories only when the bundle declares the same key.
    assert _swift_value("Folders/RecentTargets.swift", "opensURLsKey") == f'"{OPENS_URLS_KEY}"'


def test_the_app_declares_its_minimum_metab_for_the_doctor() -> None:
    """``metab --doctor`` reads the oldest ``metab`` the app it finds runs from that app's
    ``Info.plist`` (``MINIMUM_METAB_KEY``), so Terminal can say whether its ``metab`` is
    new enough; the value is the app's own ``MetabRequirement.minimumRelease``.
    """

    info = plistlib.loads((APP / "Resources" / "Info.plist").read_bytes())
    assert info.get(MINIMUM_METAB_KEY) == ".".join(str(part) for part in _minimum_metab())


# The MetabInstall case for each of the doctor's install methods.
_SWIFT_INSTALL_CASES: Final = {
    "uv_tool": ".uvTool",
    "pipx": ".pipx",
    "checkout": ".checkout",
    "environment": ".other",
}


def test_the_apps_upgrade_steps_are_the_doctors() -> None:
    """The app names the step that upgrades a ``metab`` too old to run (``MetabInstall``),
    and ``metab --doctor`` names the same step for one older than the app it finds
    (``METAB_UPGRADE_COMMANDS``): each install gets the same command on both sides, read
    from the same files.
    """

    source = (SHELL_CORE / "Setup" / "MetabVersion.swift").read_text(encoding="utf-8")
    body = re.search(
        r"public func upgradeCommand\(minimum: String\) -> String \{\n(.*?)\n    \}\n",
        source,
        re.DOTALL,
    )
    assert body is not None, "MetabInstall.upgradeCommand(minimum:) not found"
    commands: dict[str, str] = {}
    for line in body.group(1).splitlines():
        case = re.fullmatch(r'\s*case ([^:]+): "(.*)"', line)
        if case is not None:
            for name in case.group(1).split(","):
                commands[name.strip()] = case.group(2)
    assert set(commands) == set(_SWIFT_INSTALL_CASES.values())
    for method, template in METAB_UPGRADE_COMMANDS.items():
        swift = template.replace("{minimum}", "\\(minimum)")
        assert commands[_SWIFT_INSTALL_CASES[method]] == swift, (
            f"MetabInstall {_SWIFT_INSTALL_CASES[method]} is not the doctor's step for {method}"
        )
    for declaration, value in (
        ("uvReceipt", UV_RECEIPT),
        ("pipxMetadata", PIPX_METADATA),
        ("checkoutVenv", CHECKOUT_VENV),
    ):
        assert _swift_value("Setup/MetabVersion.swift", declaration) == f'"{value}"'
    project = _swift_value("Setup/MetabVersion.swift", "checkoutProject")
    assert CHECKOUT_PROJECT.pattern.count(project) == 1, (
        f"MetabInstall.checkoutProject {project} is not the project CHECKOUT_PROJECT names"
    )


def _swift_samples(name: str, enum: str) -> set[str]:
    """The one-line string literals in ``enum <enum> { … }`` of ``Tests/ShellCoreTests/<name>``.

    Only that enum's: the rest of the file also holds lines a test expects the app to
    reject, such as a pull request step without its elapsed time, and a sample set that
    took those in would accept ``metab`` writing one (review A2 on #571).
    """

    source = (SHELL_CORE_TESTS / name).read_text(encoding="utf-8")
    body = re.search(rf"^enum {re.escape(enum)} \{{\n(.*?)^\}}$", source, re.DOTALL | re.MULTILINE)
    assert body, f"{name} no longer declares enum {enum}"
    return set(re.findall(r'"((?:[^"\\\n]|\\.)*)"', body.group(1)))


def test_the_clone_report_the_app_reads_is_metabs(monkeypatch: pytest.MonkeyPatch) -> None:
    """``StartProgress`` parses the lines a repository's start writes without a terminal.

    ``CloneReport`` writes each sample ``StartProgressTests.swift`` parses, with the clock
    fixed, so a change to what ``metab`` says while it clones fails here rather than
    leaving the app's status view with nothing to say.
    """

    samples = _swift_samples("StartProgressTests.swift", "CloneReportSamples")
    # The test file expects the app to ignore this line, a pull request step without its
    # elapsed time, so it must not count as a sample: metab writing it fails here.
    assert "reading pull request 12" not in samples

    clock = [0.0]
    monkeypatch.setattr(clone_report, "_monotonic", lambda: clock[0])
    mib = 1024**2
    stream = io.StringIO()
    report = CloneReport(
        "https://github.com/octo/demo",
        "~/.cache/metabrowser",
        then="starting the server",
        stream=stream,
    )
    report.phase("fetching every object")
    clock[0] = 12.0
    report.tick()
    clock[0] = 40.0
    rate = int(9.5 * mib)
    for received in (334, 742):
        report.progress(
            GitProgress(
                stage="receiving",
                done=received,
                total=742,
                received_bytes=received * mib,
                bytes_per_second=rate,
            )
        )
    clock[0] = 104.0
    report.phase("done")
    report.cache_hit(canonical_now())

    async def read_pull_request() -> None:
        clock[0] = 0.0
        async with saying_while_waiting("reading pull request 12", stream=stream):
            clock[0] = 5.5
            await asyncio.sleep(clone_report.WAIT_QUIET_S + 0.2)

    asyncio.run(read_pull_request())
    written = stream.getvalue().splitlines()
    assert len(written) == 6, written
    missing = set(written) - samples
    assert not missing, f"StartProgressTests.swift no longer parses what metab writes: {missing}"


def test_the_github_failures_the_app_reads_are_metabs(monkeypatch: pytest.MonkeyPatch) -> None:
    """``GitHubFailure`` reads states ``metab`` names, from the lines ``metab`` prints.

    The states in its table are ``metab``'s; the clone failures ``GitHubFailureTests.swift``
    diagnoses are the lines ``describe_remote_failure`` builds, prefixed as the CLI prints
    an error; and the hint it reads to tell that no ``gh`` was found is the one the GitHub
    provider gives. A start that fails as ``cli-github-not-found.txt`` records ends with
    the not-found lines.

    Its ``not_logged_in`` and ``gh_missing`` samples are placeholders: the GitHub plugin's
    messages name no state and reach no start's ``Error:`` line, so they are built here
    from those messages with the state appended, a format ``metab`` does not print. They
    hold the samples to the plugin's wording only, until the GitHub status check
    (``mb-si2g``) decides how a start reports either state.
    """

    swift = (SHELL_CORE / "Folders" / "GitHubFailure.swift").read_text(encoding="utf-8")
    table = re.search(r"static let kinds: \[String: Kind\] = \[(.*?)\n    \]", swift, re.DOTALL)
    assert table, "GitHubFailure.swift no longer declares its kinds"
    named = set(re.findall(r'"([a-z_]+)": \.', table.group(1)))
    states = set(get_args(RemoteFailureState.__value__)) | set(
        get_args(github_gh.GhFailureState.__value__)
    )
    assert named, "GitHubFailure.kinds names no state"
    assert named <= states, f"states metab never names: {named - states}"

    prefix = _swift_value("Folders/GitHubFailure.swift", "errorPrefix").strip('"')
    hint = _swift_value("Folders/GitHubFailure.swift", "installHint").strip('"')
    repository = "https://github.com/octo/absent"
    monkeypatch.setattr(github_provider, "gh_executable", lambda: "/opt/homebrew/bin/gh")
    found = prefix + describe_remote_failure("not_found_or_private", repository)
    monkeypatch.setattr(github_provider, "gh_executable", lambda: None)
    without_gh = prefix + describe_remote_failure("not_found_or_private", repository)
    assert hint in without_gh and hint not in found

    printed = (GOLDEN / "cli-github-not-found.txt").read_text(encoding="utf-8").splitlines()
    assert found in printed and without_gh in printed

    demo = "https://github.com/octo/demo"
    samples = _swift_samples("GitHubFailureTests.swift", "GitHubFailureSamples")
    printed_states = ("network_unreachable", "timed_out", "rate_limited", "server_error")
    placeholders = {
        f"{prefix}{github_gh._SIGN_IN_MESSAGE} (not_logged_in)",
        f"{prefix}{github_gh.GhUnavailableError()} (gh_missing)",
    }
    built = {
        found,
        without_gh,
        *(prefix + describe_remote_failure(state, demo) for state in printed_states),
        *placeholders,
    }
    missing = built - samples
    assert not missing, f"GitHubFailureTests.swift no longer diagnoses what metab prints: {missing}"
