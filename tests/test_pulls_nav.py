"""What the server decides about the Pulls tab, and what its paint is wired to.

``tests/dom/pulls-nav-session.js`` runs the tab's host and ``tests/dom/github-pulls-panel-session.js``
its list, and their goldens pin every decision they make. These add what no browserless session
can see: the shell the server writes for each kind of source, which is where the tab is decided,
and that a folder's shell carries nothing of it.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.git import repo as git_repo
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.server import app
from metabrowser.source import attach_subject, reset_source_session
from tests.github_pull_fixture import (
    CANONICAL,
    DEFAULT_BRANCH,
    Origin,
    clone_checkout,
    install_fake_gh,
    scenario,
)
from tests.golden_harness import run_session
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git

REPO_ROOT = Path(__file__).resolve().parent.parent
PANEL = REPO_ROOT / "src/metabrowser/builtin_plugins/github/pulls-panel.js"
pytestmark = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")


def _tabs(html: str) -> dict[str, bool]:
    """Each navigation tab in *html*, and whether it is in front."""

    bar = html[html.index('class="tab-bar nav-tab-bar"') :]
    bar = bar[: bar.index("</div>")]
    tabs: dict[str, bool] = {}
    for button in re.findall(r"<button[^>]*>", bar):
        name = re.search(r'data-tab="([a-z]+)"', button)
        assert name is not None
        active = 'class="tab-btn active"' in button
        assert f'aria-selected="{"true" if active else "false"}"' in button, button
        tabs[name.group(1)] = active
    return tabs


def _toolbars(html: str) -> dict[str, bool]:
    """Each toolbar in the navigation's slot, and whether it is shown; one per tab, never empty."""

    toolbars: dict[str, bool] = {}
    for opening, body in re.findall(
        r'(<div [^>]*data-nav-toolbar="[a-z]+"[^>]*>)(.*?)</div>', html
    ):
        name = re.search(r'data-nav-toolbar="([a-z]+)"', opening)
        assert name is not None
        toolbars[name.group(1)] = " hidden" not in opening
        # Each ships the pending tally until its script fills it.
        assert "tally-pending" in body, opening
    assert list(toolbars.values()).count(True) == 1, toolbars
    assert set(toolbars) == set(_tabs(html)), (toolbars, _tabs(html))
    return toolbars


def _shell_tools(html: str) -> list[str]:
    bundles = re.search(r"window\.METABROWSER_ASSET_BUNDLES=(\{.*?\});</script>", html)
    assert bundles is not None
    return [entry["src"].split("?")[0] for entry in json.loads(bundles.group(1))["shell-tools"]]


def _startup_scripts(html: str) -> list[str]:
    return [src.split("?")[0] for src in re.findall(r'<script src="([^"]+)"', html)]


def test_a_folder_draws_no_tab_and_lists_no_script(tmp_path: Path) -> None:
    """A plain folder's shell is the mutation check on all of it: nothing of the tab reaches it."""

    reset_source_session()
    from metabrowser import server

    (tmp_path / "README.md").write_text("# Local\n")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        for route in ("/view/", "/pull/7", "/pulls"):
            html = client.get(route).text
            assert _tabs(html) == {"files": True}, route
            assert 'id="tab-pulls"' not in html, route
            assert "pulls-nav.js" not in html, route
            assert "/static/pulls-nav.js" not in _shell_tools(html), route
            assert "/static/pulls-nav.js" not in _startup_scripts(html), route
    reset_source_session()


def test_a_folders_page_at_the_lists_address_says_so_and_starts_no_gh(tmp_path: Path) -> None:
    """The page's own request answers `not_github`, from a folder's route table alone."""

    root = tmp_path / "browse"
    root.mkdir()
    program = textwrap.dedent(
        """
        import asyncio, json, sys
        from pathlib import Path
        from metabrowser import server
        from metabrowser.cli.asgi_client import InProcessClient

        async def answer():
            async with InProcessClient(server.app, label="shell") as client:
                page = await client.get("/pulls")
                listing = await client.get("/api/plugin/github/pulls?limit=0")
                return page.status_code, listing.json()

        server._set_root_dir(Path(sys.argv[1]))
        status, listing = asyncio.run(answer())
        print(json.dumps({"status": status, "reason": listing["reason"]}))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", program, str(root)],
        check=False,
        capture_output=True,
        text=True,
        timeout=50,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"status": 200, "reason": "not_github"}


def _serve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin, url: str) -> Any:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
    _allow_installed_git(monkeypatch)
    for name, value in install_fake_gh(tmp_path, scenario(origin)).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        "metabrowser.cache.acquire.remote_url_for",
        lambda source: origin.url if source.normalized == CANONICAL else source.normalized,  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
    )
    source = GitSource(
        transport="https" if url.startswith("https") else "file",
        form="url",
        normalized=url,
        selection=RepositorySelection(kind="repository"),
    )
    published = asyncio.run(acquire_source(source, home=home))

    async def _pin() -> Any:
        subject = await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=origin["topic"],
            store_identity=published.store_id,
            ref=f"refs/remotes/origin/{DEFAULT_BRANCH}",
        )
        await subject.aclose()
        return subject

    attach_subject(asyncio.run(_pin()))
    serve_mirror(StoreMirror.from_published(published))
    git_repo.clear_repo_cache()


@needs_git
def test_a_mirror_of_github_draws_the_tab_and_puts_it_in_front_at_its_addresses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    _serve(tmp_path, monkeypatch, pull_origin, CANONICAL)
    try:
        with TestClient(app) as client:
            elsewhere = client.get("/view/").text
            # A pin is a repository, so Commits is drawn at first paint, after Pulls.
            assert _tabs(elsewhere) == {"files": True, "git": False, "pulls": False}
            assert list(_tabs(elsewhere)) == ["files", "pulls", "git"]
            # Fetched with the shell's tools, after the first tree: no startup script.
            assert "/static/pulls-nav.js" in _shell_tools(elsewhere)
            assert "/static/pulls-nav.js" not in _startup_scripts(elsewhere)
            assert '<div id="tab-pulls" data-tab-content="pulls" style="display: none"></div>' in (
                elsewhere
            )
            assert _toolbars(elsewhere) == {"files": True, "git": False, "pulls": False}

            for route in (
                "/pull/7",
                "/pull/7/files",
                "/pull/7/checks",
                "/pulls",
                "/pulls?state=closed",
            ):
                html = client.get(route).text
                assert _tabs(html) == {"files": False, "git": False, "pulls": True}, route
                # The Files tree is behind the Pulls tab from first paint, and the toolbar
                # slot holds the Pulls toolbar in its filters' place, never empty.
                assert 'id="tab-files" data-tab-content="files" style="display: none"' in html
                assert _toolbars(html) == {"files": False, "git": False, "pulls": True}, route
                sidebar = html.split('id="tab-pulls"', 1)[1].split('id="preview-pane"', 1)[0]
                assert sidebar.count('class="spinner spinner-sm"') == 1
                assert sidebar.count("Fetching pull requests…") == 1
                if route.startswith("/pulls"):
                    preview = html.split('id="preview-pane"', 1)[1].split("</main>", 1)[0]
                    assert "Select a pull request." in preview
                    assert 'class="spinner"' not in preview
            # The list's address adds no startup script a page elsewhere does not have.
            assert _startup_scripts(client.get("/pulls").text) == _startup_scripts(elsewhere)
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()
        reset_source_session()


@needs_git
def test_a_mirror_of_anything_else_draws_no_tab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """Core holds no provider grammar: a `file://` mirror has no repository context."""

    _serve(tmp_path, monkeypatch, pull_origin, pull_origin.url)
    try:
        with TestClient(app) as client:
            for route in ("/view/", "/pull/7", "/pulls"):
                html = client.get(route).text
                assert _tabs(html) == {"files": True, "git": False}, route
                assert "/static/pulls-nav.js" not in _shell_tools(html), route
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()
        reset_source_session()


@needs_git
@pytest.mark.parametrize(
    ("remote", "served"),
    [
        (CANONICAL + ".git", ""),
        ("git@github.com:octo/demo.git", ""),
        (CANONICAL + ".git", "src"),
        # The plugin's grammar refuses it, and the tab then says so: discovery admits it.
        ("https://github.com/under_score/demo.git", ""),
    ],
    ids=["https", "ssh", "subdirectory", "a remote the plugin refuses"],
)
def test_a_github_checkout_draws_the_tab_and_puts_it_in_front_at_its_addresses(
    tmp_path: Path, pull_origin: Origin, remote: str, served: str
) -> None:
    """The tab is decided from the repository context the shell already has, for a folder too.

    A subdirectory of the checkout is still its repository's, unlike the Git tab's root
    rule. Mutation check: decide the tab from a served pin alone, as it was before
    checkouts, and every case here fails.
    """

    reset_source_session()
    from metabrowser import server

    checkout = clone_checkout(pull_origin, tmp_path / "checkout", remote=remote)
    server._set_root_dir(checkout / served)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        elsewhere = client.get("/view/").text
        assert _tabs(elsewhere)["pulls"] is False
        # Commits is drawn at first paint at the repository's root only, the one root Git
        # discovery accepts, and always after Pulls.
        assert ("git" in _tabs(elsewhere)) is (served == "")
        assert list(_tabs(elsewhere))[1] == "pulls"
        assert "/static/pulls-nav.js" in _shell_tools(elsewhere)
        assert "/static/pulls-nav.js" not in _startup_scripts(elsewhere)
        for route in ("/pull/7", "/pulls"):
            assert _tabs(client.get(route).text)["pulls"] is True, route
        # A cold page shows its own loading state, header rows and tab bar over a body
        # skeleton, at once: the shell's placeholder is nothing to keep on screen while
        # the page is staged, so the page is not staged behind it.
        placeholder = re.search(
            r'<div class="pull-request-placeholder[^>]*>', client.get("/pull/7").text
        )
        assert placeholder is not None and "data-preview-empty" in placeholder.group(0)
    reset_source_session()


@needs_git
def test_a_checkout_of_anything_else_draws_no_tab(tmp_path: Path, pull_origin: Origin) -> None:
    """A checkout whose ``origin`` is not on github.com is a plain folder to the tab."""

    reset_source_session()
    from metabrowser import server

    checkout = clone_checkout(
        pull_origin, tmp_path / "checkout", remote="https://gitlab.example/octo/demo.git"
    )
    server._set_root_dir(checkout)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        for route in ("/view/", "/pull/7", "/pulls"):
            html = client.get(route).text
            assert "pulls" not in _tabs(html), route
            # Any repository at the root has Commits from first paint, GitHub or not.
            assert _tabs(html)["git"] is False, route
            assert "/static/pulls-nav.js" not in _shell_tools(html), route
    reset_source_session()


@needs_git
def test_a_commits_address_lands_on_commits_from_first_paint(
    tmp_path: Path, pull_origin: Origin
) -> None:
    """A commit's address draws Commits in front: its tab, its toolbar, and its panel's
    container, so the landing never shows the Files tree and toolbar and then swaps them."""

    reset_source_session()
    from metabrowser import server

    checkout = clone_checkout(
        pull_origin, tmp_path / "checkout", remote="https://gitlab.example/octo/demo.git"
    )
    server._set_root_dir(checkout)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        html = client.get("/commit/" + "a" * 40).text
        assert _tabs(html) == {"files": False, "git": True}
        assert _toolbars(html) == {"files": False, "git": True}
        assert 'id="tab-files" data-tab-content="files" style="display: none"' in html
        assert '<div id="tab-git" data-tab-content="git"><div class="loading' in html
        # Elsewhere Files is in front, and the Commits panel's container is the page's to make.
        elsewhere = client.get("/view/").text
        assert _tabs(elsewhere) == {"files": True, "git": False}
        assert _toolbars(elsewhere) == {"files": True, "git": False}
        assert 'id="tab-git"' not in elsewhere
    reset_source_session()


def test_a_commits_address_in_a_folder_draws_no_commits(tmp_path: Path) -> None:
    """With no repository there is no Commits tab to put in front: Files stays."""

    reset_source_session()
    from metabrowser import server

    (tmp_path / "README.md").write_text("# Local\n")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        html = client.get("/commit/" + "a" * 40).text
        assert _tabs(html) == {"files": True}
        assert _toolbars(html) == {"files": True}
    reset_source_session()


def test_a_rows_text_is_only_ever_text() -> None:
    """The one markup the panel parses is the shell's own chip group.

    The panel session's `paint` is the evidence: it builds the rows and reads a title written
    as markup back as one text node. This is the second line, for code the session's rows do
    not reach: nothing else in the module parses markup at all. Mutation check: assign a row's
    title to `innerHTML` and both fail.
    """

    source = PANEL.read_text(encoding="utf-8")
    assert source.count("innerHTML") == 1
    assert "filters.innerHTML = controls.groupHtml(" in source
    assert "insertAdjacentHTML" not in source
    assert "outerHTML" not in source
    # The window's internally measured numeric gap is the sole inline style. Values from
    # GitHub remain text; neither titles nor refs reach a style or class assignment.
    style_lines = re.findall(r"^.*\.style\..*$", source, re.MULTILINE)
    assert [line.strip() for line in style_lines] == ["gap.style.height = `${part.height}px`;"]
    assert "cssText" not in source


def test_stack_shortcuts_follow_active_pr_and_preserve_registry_guards() -> None:
    """Public page capability owns stack direction; shared scopes retain native input."""

    result = run_session("pulls-nav-session.js")["stack keys"]
    # P toward the base and N toward the top, and Shift changes neither.
    assert result["directions"] == [-1, 1]
    assert result["shiftedDirections"] == [-1, 1]
    assert [entry["keys"] for entry in result["help"]] == ["N", "P"]
    assert result["endpointConsumed"] is True
    assert result["plainJRemainsRowNavigation"] is True
    # A focused row keeps J and K with Shift held; they never reach the stack.
    assert result["shiftedRowKeysMoveTheRow"]["handled"] == [True, True]
    assert result["shiftedFileKeysMoveTheFile"]["handled"] == [True, True]
    assert result["cleanup"] is True
