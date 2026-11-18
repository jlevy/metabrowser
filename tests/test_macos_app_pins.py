"""The macOS app's copies of ``metab``'s values, each held to its definition here.

The app copies a few of ``metab``'s constants into Swift, where nothing imports them:
the bounds on acquiring a source, which a repository's start must outlast; the port walk,
which keeps the two launch gates' ranges apart; the hosts of the GitHub reducer; and the
page size of the cache's sources route. Its ``Info.plist`` also declares the key
``--present`` reads before it sends anything. These checks run in CI's Python jobs, which
run on every change, so a change on either side fails here, where the macOS workflow's
path filter would not have run the app's own tests (review A5 on #539).
"""

from __future__ import annotations

import os
import plistlib
import re
from pathlib import Path
from typing import Any, cast

import pytest

from metabrowser.builtin_plugins.github import urls as github_urls
from metabrowser.cache.acquire import RESERVATION_WAIT_S
from metabrowser.cache.origin import REMOTE_PROBE_TIMEOUT_S
from metabrowser.cache.projection import MAX_PAGE_LIMIT, sources_response
from metabrowser.cli.clone_report import LOG_INTERVAL_S
from metabrowser.cli.present import OPENS_URLS_KEY, Presentable, resolve_target
from metabrowser.git.process import GIT_ACQUISITION_TIMEOUT_S
from metabrowser.home import METABROWSER_CACHE_DIR_ENV
from metabrowser.server_utils import DEFAULT_PORT_SEARCH_COUNT
from metabrowser.settings import DEFAULT_BROWSER_PORT
from tests.cache_home_fixture import FLASK_HTTPS, build_populated_home

APP = Path(__file__).resolve().parent.parent / "apps" / "macos"
SHELL_CORE = APP / "Sources" / "ShellCore"


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
