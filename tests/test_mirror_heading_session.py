"""The mirror-heading session runs the shell's heading code on what the server serves.

A page of a served mirror is headed by the repository's name and says where the mirror
is kept (``mb-fndz``). The server writes both into the navigation heading, the status
route reports them as data, and the shell's own code turns them into the main heading
and the tooltips. ``tests/dom/mirror-heading-session.js`` runs that code, and
``tests/golden/cli-ui-mirror-heading.tryscript.md`` pins its transcript.

So that the session reads the real server's output, its input is
``tests/fixtures/mirror-heading-shell.json``: for a folder, for a mirror, and for a mirror
whose origin has markup and an invisible character in its name, the tab title, the
navigation heading with its data attributes as a browser's ``dataset`` gives them, and the
status fields the heading is rendered from. The first test here serves all three and
fails when the recording no longer matches; ``make golden-update`` rewrites it and then
the transcript.

Two things in a recording are this run's own and are replaced by stand-ins
(``stand_in_sandbox``): the directory everything is built in, and each store's key, which
is derived from its origin's address and so from that directory. The home directory is set to a directory
of the run, so the application home is under it and a location is recorded with ``~``,
as a reader's is.
"""

from __future__ import annotations

import asyncio
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.urls import GitSource, classify_root_argument
from tests.golden_harness import (
    SANDBOX_STAND_IN,
    STORE_KEY_STAND_INS,
    check_recording,
    run_session,
    serve_published,
    stand_in_sandbox,
)
from tests.required_tools import needs_git
from tests.source_mirror_fixture import build_origin
from tests.test_cache_acquire import _allow_installed_git

RECORDING = "mirror-heading-shell.json"
TRANSCRIPT = "cli-ui-mirror-heading.tryscript.md"

# An origin's directory with markup and U+202E RIGHT-TO-LEFT OVERRIDE in its name.
_HOSTILE = "a<b>&\u202ex.git"

# An application home whose own name has markup in it, for the same mirror's location.
_HOSTILE_HOME = 'odd"<&>home'

_TITLE = re.compile(r"<title>(.*?)</title>")
_HEADING = re.compile(r'<a href="/view/" class="header-path"[^>]*>(.*?)</a>', re.S)

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
pytestmark = [posix_only, needs_git]


class _HeadingAttributes(HTMLParser):
    """The navigation heading's ``data-`` attributes, named as ``dataset`` names them."""

    def __init__(self) -> None:
        super().__init__()
        self.dataset: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a" or ("class", "header-path") not in attrs:
            return
        assert self.dataset is None, "the page has two navigation headings"
        self.dataset = {}
        for name, value in attrs:
            if name.startswith("data-"):
                head, *rest = name.removeprefix("data-").split("-")
                self.dataset[head + "".join(part.capitalize() for part in rest)] = value or ""


def _page(client: TestClient, kind: str) -> dict[str, Any]:
    shell = client.get("/view/")
    assert shell.status_code == 200, shell.text
    attributes = _HeadingAttributes()
    attributes.feed(shell.text)
    assert attributes.dataset is not None
    status = client.get("/api/source/status").json()
    return {
        "kind": kind,
        "title": _TITLE.findall(shell.text),
        "heading": _HEADING.findall(shell.text),
        "dataset": attributes.dataset,
        "status": {key: status[key] for key in ("name", "origin", "location", "pin", "ref_name")},
    }


def _acquire(origin: Path, home: Path) -> PublishedSource:
    source = classify_root_argument("file://" + quote(str(origin.resolve()), safe="/&"))
    assert isinstance(source, GitSource), source
    return asyncio.run(acquire_source(source, home=home))


def _served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    user = tmp_path / "user"
    folder = user / "wrk" / "squares"
    (folder / "docs").mkdir(parents=True)
    (folder / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    # Two origins of one history, written by fast-import so the commit is the same
    # everywhere, each under the name its mirror is called by.
    origins = user / "git"
    origins.mkdir()
    build_origin(origins).rename(origins / "squares.git")
    build_origin(origins).rename(origins / _HOSTILE)

    monkeypatch.setenv("HOME", str(user))
    _allow_installed_git(monkeypatch)

    served: dict[str, Any] = {}
    server._set_root_dir(folder)
    with TestClient(server.app) as client:
        served["folder"] = _page(client, "filesystem")
    keys: list[str] = []
    for subject, name, home in (
        ("mirror", "squares.git", user / ".metabrowser"),
        ("hostile", _HOSTILE, user / _HOSTILE_HOME),
    ):
        monkeypatch.setenv("METABROWSER_HOME", str(home))
        published = _acquire(origins / name, home)
        keys.append(published.store_key)
        serve_published(published)
        with TestClient(server.app) as client:
            served[subject] = _page(client, "git_revision")

    recorded: dict[str, Any] = stand_in_sandbox(served, tmp_path, *keys)
    for page in recorded.values():
        (page["title"],) = page["title"]
        (page["heading"],) = page["heading"]
    return recorded


def test_fixture_is_what_the_server_serves_for_a_folder_and_for_a_mirror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    served = _served(tmp_path, monkeypatch)

    folder, mirror, hostile = served["folder"], served["mirror"], served["hostile"]
    # A folder's root is its path, and a status has nothing to say of a mirror.
    assert folder["dataset"] == {"servedRoot": "~/wrk/squares"}
    assert folder["status"] == dict.fromkeys(("name", "origin", "location", "pin", "ref_name"))
    for page, home, key in (
        (mirror, ".metabrowser", STORE_KEY_STAND_INS[0]),
        (hostile, _HOSTILE_HOME, STORE_KEY_STAND_INS[1]),
    ):
        status = page["status"]
        # The page and the status say the same thing: one is rendered from the other.
        assert page["dataset"]["servedRoot"] == status["name"]
        assert page["dataset"]["mirrorLocation"] == status["location"]
        assert status["location"] == f"~/{home}/cache/repository-stores/{key}/repository.git"
        assert page["dataset"]["mirrorTip"] == (
            f"Mirror of {status['origin']} at {status['pin']}, stored in {status['location']}: "
            "a bare Git repository, with no checked-out files."
        )
    assert mirror["status"]["name"] == "squares"
    assert mirror["status"]["origin"] == f"file://{SANDBOX_STAND_IN}/user/git/squares.git"
    # The override is shown as U+FFFD in the name, and stays an escape in the address.
    assert hostile["status"]["name"] == "a<b>&\ufffdx"
    assert hostile["status"]["origin"].endswith("/a%3Cb%3E&%E2%80%AEx.git")
    assert "a&lt;b&gt;&amp;\ufffdx" in hostile["heading"]
    check_recording(RECORDING, served, transcript=TRANSCRIPT)


def test_the_session_names_a_mirror_and_says_where_it_is_kept() -> None:
    folder, mirror, hostile = run_session("mirror-heading-session.js")

    assert folder["mainHeading"]["file"]["text"] == "~/wrk/squares / docs / guide.md"
    location = f"~/.metabrowser/cache/repository-stores/{STORE_KEY_STAND_INS[0]}/repository.git"
    assert mirror["navigationHeading"]["text"] == f"squares topic {mirror['status']['pin'][:12]}"
    assert (
        mirror["mainHeading"]["file"]["text"] == f"squares / docs / guide.md mirror in {location}"
    )
    assert mirror["mainHeading"]["root"] == f"squares / mirror in {location}"
    assert mirror["navigationTooltip"]["afterTreeLoad"] == (
        f"squares 3 files 140 bytes Mirror of file://{SANDBOX_STAND_IN}/user/git/squares.git at "
        f"{mirror['status']['pin']}, stored in {location}: a bare Git repository, with no "
        "checked-out files. Jump to root"
    )
    assert hostile["mainHeading"]["file"]["text"].startswith("a<b>&\ufffdx / docs / guide.md ")
    assert {page["title"] for page in (folder, mirror, hostile)} == {"Metabrowser"}
