"""Serving an acquired ``file://`` pin: lifecycle, routes, and trust isolation over HTTP.

``metab file://… --no-open`` runs here in-process with only the uvicorn server and the
port search patched, the boundary ``tests/test_cli_golden.py`` uses for the filesystem
banner. The command leaves the server's subject opener installed, so a ``TestClient``
then drives the same application lifespan uvicorn would: it opens the pin in its own
event loop, serves real requests through the full middleware stack, and closes the pin
at shutdown. No port is bound and no network is used.

Acquisition needs a Git at or above the floor; like every other acquiring test, these
patch that floor through ``_allow_installed_git`` and run unpatched in the admitted-Git
CI job.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from starlette.routing import Route
from starlette.testclient import TestClient
from typer.testing import CliRunner

from metabrowser import server
from metabrowser.cache.acquire import PublishedSource, acquire_file_source
from metabrowser.cache.repository_store import open_revision
from metabrowser.capabilities import get_capabilities
from metabrowser.cli.main import _app
from metabrowser.errors import CLIError
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitPath,
    GitRevisionSubject,
    store_batch_reader_count,
)
from metabrowser.source import (
    get_source_session,
    reset_source_session,
    serve_subject_opener,
)
from tests.test_cache_acquire import _allow_installed_git, _file_source, _git
from tests.test_cli_golden import _normalize, check_golden

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = [
    posix_only,
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]

runner = CliRunner()

# The forced untrusted profile: /raw keeps its sandbox and loses allow-scripts.
_RAW_CSP_NO_SCRIPTS = "sandbox allow-popups allow-forms allow-downloads"

# A real one-pixel PNG, so the image blob is served from stored bytes.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001"
    "08060000001f15c4890000000a49444154789c630001000005"
    "00010d0a2db40000000049454e44ae426082"
)

_OTHER_SOURCE_CANARY = "canary-from-another-cached-source"
_WORKING_DIRECTORY_CANARY = "canary-from-the-working-directory"


def _wire(display: str) -> str:
    return GitPath.from_display(display).to_wire()


@dataclass(frozen=True, slots=True)
class _Origin:
    path: Path
    first: str
    second: str

    @property
    def url(self) -> str:
        return f"file://{self.path.resolve()}"


def _origin(root: Path) -> _Origin:
    """A bare origin whose ``topic`` has two commits and a small browsable tree."""

    work = root / "work"
    work.mkdir(parents=True)
    _git(work, "init", "-q", "-b", "topic")
    (work / "README.md").write_text("# Pinned\n\n![logo](images/logo.png)\n", encoding="utf-8")
    (work / "images").mkdir()
    (work / "images" / "logo.png").write_bytes(_PNG)
    (work / "page.html").write_text(
        '<!doctype html><link rel="stylesheet" href="style.css"><p>page</p>\n',
        encoding="utf-8",
    )
    (work / "style.css").write_text("p { color: black; }\n", encoding="utf-8")
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "first")
    first = _rev(work)
    (work / "data.json").write_text('{"k": 1}\n', encoding="utf-8")
    (work / "README.md").write_text(
        "# Pinned\n\nSecond revision.\n\n![logo](images/logo.png)\n", encoding="utf-8"
    )
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "second")
    second = _rev(work)
    origin = root / "origin.git"
    _git(work, "clone", "--bare", "--template=", "--", str(work), str(origin))
    return _Origin(path=origin, first=first, second=second)


def _rev(work: Path) -> str:
    head = (work / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    ref = head.removeprefix("ref: ")
    return (work / ".git" / ref).read_text(encoding="utf-8").strip()


@pytest.fixture(autouse=True)
def _isolated_session(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Keep the served subject, its opener, and the interrupt handler inside one test."""

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)
    yield
    reset_source_session()


def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    _allow_installed_git(monkeypatch)
    return home


def _serve(url: str, *extra: str) -> Any:
    """Run serve mode to the point where uvicorn would take over, and return the result."""

    with (
        patch("metabrowser.cli.serve._QuietForceExitServer") as server_class,
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = runner.invoke(_app, [url, "--no-open", *extra])
    if result.exit_code == 0:
        config = server_class.call_args.args[0]
        assert config.app is server.app
        assert config.port == 8411
    return result


# ── The command ─────────────────────────────────────────────────────


def test_golden_serve_pin_banner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The banner names the source, the pinned commit, and the ref it was resolved from."""

    _home(tmp_path, monkeypatch)
    origin = _origin(tmp_path)
    result = _serve(origin.url)
    assert result.exit_code == 0, result.output
    stdout = _normalize(result.stdout, tmp_path).replace(origin.second, "<REVISION>")
    stderr = _normalize(result.stderr, tmp_path)
    rendered = (
        "# metab file://<ROOT>/origin.git --no-open\n"
        f"exit: {result.exit_code}\n"
        f"--- stdout ---\n{stdout}"
        f"--- stderr ---\n{stderr}"
    )
    check_golden("serve-pin-banner.txt", rendered)


@pytest.mark.parametrize(
    "env",
    [{}, {"METAB_ACTIVE_CONTENT": "1", "METAB_ALLOW_EDITS": "1", "METAB_UNTRUSTED": "0"}],
    ids=["default", "env-enables"],
)
def test_serve_pin_forces_the_untrusted_profile(
    env: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home(tmp_path, monkeypatch)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    result = _serve(_origin(tmp_path).url)
    assert result.exit_code == 0, result.output
    assert get_capabilities().active_content is False
    assert get_capabilities().mutations is False
    with TestClient(server.app) as client:
        wire = client.get("/api/capabilities").json()["capabilities"]
    assert wire == {"active_content": False, "mutations": False}


def test_serve_pin_refuses_allow_edits_before_acquiring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _home(tmp_path, monkeypatch)
    result = _serve(_origin(tmp_path).url, "--allow-edits")
    assert isinstance(result.exception, CLIError)
    assert "--allow-edits is not available on an acquired Git source" in str(result.exception)
    assert not home.exists()


def test_serve_pin_path_deep_links_a_wire_and_refuses_a_missing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home(tmp_path, monkeypatch)
    origin = _origin(tmp_path)
    found = _serve(origin.url, "--path", "images/logo.png")
    assert found.exit_code == 0, found.output
    assert f"/view/{_wire('images/logo.png')}" in found.stdout
    directory = _serve(origin.url, "--path", "images")
    assert f"/view/{_wire('images')} " in directory.stdout
    missing = _serve(origin.url, "--path", "nope.txt")
    assert isinstance(missing.exception, CLIError)
    assert "--path target is not in the pinned revision: nope.txt" in str(missing.exception)


def test_a_pin_that_cannot_open_is_refused_before_the_banner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same path-free message as ``--show`` and ``--api``, and nothing served."""

    home = _home(tmp_path, monkeypatch)

    async def fail_open(**_kwargs: object) -> GitRevisionSubject:
        raise GitObjectUnavailableError("0" * 40)

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.open_revision", fail_open)
    result = _serve(_origin(tmp_path).url)
    assert isinstance(result.exception, CLIError)
    assert "Serving" not in result.output
    assert str(home) not in str(result.exception)


# ── The lifespan ─────────────────────────────────────────────────────


def _published(tmp_path: Path, origin: _Origin) -> PublishedSource:
    return asyncio.run(acquire_file_source(_file_source(origin.path), home=tmp_path / "home"))


def _counting_opener(
    published: PublishedSource,
) -> tuple[Callable[[], Awaitable[GitRevisionSubject]], list[GitRevisionSubject]]:
    opened: list[GitRevisionSubject] = []

    async def opener() -> GitRevisionSubject:
        subject = await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=published.default_revision,
            store_identity=published.store_id,
            ref=published.default_remote_ref,
        )
        opened.append(subject)
        return subject

    return opener, opened


def test_each_start_opens_a_fresh_pin_and_shutdown_closes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repeated starts share nothing: new processes, a new generation, and a clean close."""

    _home(tmp_path, monkeypatch)
    origin = _origin(tmp_path)
    published = _published(tmp_path, origin)
    opener, opened = _counting_opener(published)
    serve_subject_opener(opener)

    generations: list[int] = []
    for start in range(2):
        with TestClient(server.app) as client:
            assert len(opened) == start + 1
            subject = opened[-1]
            assert get_source_session().subject is subject
            status = client.get("/api/source/status").json()
            assert status["pin"] == origin.second
            assert status["ref"] == "refs/remotes/origin/topic"
            assert status["ref_name"] == "topic"
            generations.append(status["generation"])
            readme = client.get("/api/file", params={"path": _wire("README.md")})
            assert "Second revision." in readme.json()["content"]
            assert store_batch_reader_count(subject.command_target) >= 1
        # Shutdown closed the pin's readers and detached it.
        assert store_batch_reader_count(subject.command_target) == 0
    assert opened[0] is not opened[1]
    assert generations[1] > generations[0]


def test_a_pin_that_fails_to_open_fails_startup_and_attaches_nothing(
    tmp_path: Path,
) -> None:
    async def opener() -> GitRevisionSubject:
        raise GitObjectUnavailableError("0" * 40)

    serve_subject_opener(opener)
    with pytest.raises(GitObjectUnavailableError), TestClient(server.app):
        pass
    server._set_root_dir(tmp_path)
    assert get_source_session().subject.kind == "attached_filesystem"


def test_setting_a_filesystem_root_replaces_a_served_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home(tmp_path, monkeypatch)
    published = _published(tmp_path, _origin(tmp_path))
    opener, opened = _counting_opener(published)
    serve_subject_opener(opener)
    folder = tmp_path / "folder"
    folder.mkdir()
    server._set_root_dir(folder)
    with TestClient(server.app) as client:
        status = client.get("/api/source/status").json()
    assert status["subject"] == "attached_filesystem"
    assert status["pin"] is None
    assert opened == []


# ── Routes over HTTP ─────────────────────────────────────────────────


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, _Origin]]:
    _home(tmp_path, monkeypatch)
    origin = _origin(tmp_path)
    result = _serve(origin.url)
    assert result.exit_code == 0, result.output
    with TestClient(server.app) as client:
        yield client, origin


def test_the_shell_names_the_pinned_revision(served: tuple[TestClient, _Origin]) -> None:
    client, origin = served
    shell = client.get("/view/")
    assert shell.status_code == 200
    assert f'data-served-root="{origin.second}"' in shell.text
    assert '<span class="path-base">topic</span>' in shell.text
    assert f'<span class="header-revision">{origin.second[:12]}</span>' in shell.text
    assert 'window.METABROWSER_SOURCE_KIND="git_revision"' in shell.text
    assert "window.METABROWSER_REPOSITORY_CONTEXT=null" in shell.text
    # A pinned address is a GitPath wire, and a filesystem spelling is refused.
    assert client.get(f"/view/{_wire('README.md')}").status_code == 200
    assert client.get("/view/README.md").status_code == 400
    assert client.get(f"/commit/{origin.first}").status_code == 200


def test_tree_file_and_raw_answer_from_the_pinned_tree(
    served: tuple[TestClient, _Origin],
) -> None:
    client = served[0]
    tree = client.get("/api/tree", params={"depth": "1"}).json()
    assert tree["subject"] == "git_revision"
    assert sorted(node["name"] for node in tree["tree"]) == [
        "README.md",
        "data.json",
        "images",
        "page.html",
        "style.css",
    ]

    readme = client.get("/api/file", params={"path": _wire("README.md")}).json()
    assert readme["kind"] == "markdown"
    assert readme["content"].startswith("# Pinned")

    html = client.get("/api/file", params={"path": _wire("page.html")}).json()
    assert [view["id"] for view in html["views"]] == ["source"]

    image = client.get("/raw", params={"path": _wire("images/logo.png")})
    assert image.status_code == 200
    assert image.content == _PNG
    assert image.headers["content-type"] == "image/png"
    assert image.headers["content-security-policy"] == _RAW_CSP_NO_SCRIPTS
    assert image.headers["x-content-type-options"] == "nosniff"

    page = client.get("/raw", params={"path": _wire("page.html")})
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert page.headers["content-security-policy"] == _RAW_CSP_NO_SCRIPTS


@pytest.mark.parametrize(
    "path",
    ["style.css", "page.html", _wire("style.css"), "images/logo.png"],
)
def test_the_raw_path_form_is_an_honest_refusal_on_a_pin(
    path: str, served: tuple[TestClient, _Origin]
) -> None:
    """A relative reference inside a raw pinned document reaches a typed refusal (mb-g5je)."""

    client = served[0]
    response = client.get(f"/raw/{path}")
    assert response.status_code == 409
    assert response.json() == {
        "error": "source does not support raw_document_path",
        "code": "unsupported_for_subject",
        "capability": "raw_document_path",
    }
    assert response.headers["content-security-policy"] == _RAW_CSP_NO_SCRIPTS
    assert response.headers["x-content-type-options"] == "nosniff"


def test_history_commit_and_comparison_work_on_a_served_pin(
    served: tuple[TestClient, _Origin],
) -> None:
    client, origin = served
    repo = client.get("/api/git/repo").json()
    assert repo["head"]["revision"] == origin.second
    assert repo["head"]["detached"] is True

    log = client.get("/api/git/log", params={"limit": "10"}).json()
    assert [commit["id"] for commit in log["commits"]] == [origin.second, origin.first]

    detail = client.get(f"/api/git/commit/{origin.second}").json()
    assert detail["commit"]["subject"] == "second"
    changed = {entry["path"] for entry in detail["files"]}
    assert changed == {"README.md", "data.json"}

    comparison = client.get("/api/plugin/diff/comparison", params={"revision": origin.second})
    assert comparison.status_code == 200
    manifest = comparison.json()["manifest"]
    assert manifest["totals"]["files"] == 2
    assert {entry["new"]["path"] for entry in manifest["files"]} == {"README.md", "data.json"}


# ── Trust isolation ─────────────────────────────────────────────────


def _second_source(tmp_path: Path) -> _Origin:
    """Another cached source whose tree holds a canary the pin must never serve."""

    root = tmp_path / "other"
    work = root / "work"
    work.mkdir(parents=True)
    _git(work, "init", "-q", "-b", "topic")
    (work / "OTHER.md").write_text(f"{_OTHER_SOURCE_CANARY}\n", encoding="utf-8")
    (work / "README.md").write_text(f"{_OTHER_SOURCE_CANARY}\n", encoding="utf-8")
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "other")
    commit = _rev(work)
    origin = root / "origin.git"
    _git(work, "clone", "--bare", "--template=", "--", str(work), str(origin))
    return _Origin(path=origin, first=commit, second=commit)


def _probe_urls(route: Route, probes: tuple[str, ...], other_commit: str) -> list[str]:
    """Every GET route, with each probe identity in its path parameter or ``path`` query."""

    path = route.path
    urls: list[str] = []
    for probe in probes:
        if "{" not in path:
            urls.append(f"{path}?path={probe}")
            continue
        filled = re.sub(r"\{revision\}|\{rest:path\}", other_commit, path)
        filled = re.sub(r"\{[^}]+\}", probe, filled)
        urls.append(filled)
    return urls


def test_a_served_pin_reads_nothing_outside_its_own_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Populated-cache isolation over HTTP (mb-99ub).

    A second source is acquired into the same home and the working directory holds a
    file too. Every registered GET route is asked for both, by display name and by
    GitPath wire, and for the other source's commit; no answer carries either canary.
    The cache records that name the other source are refused outright, and a request
    from the sandboxed preview origin cannot read ``/api`` at all.
    """

    home = _home(tmp_path, monkeypatch)
    other = _second_source(tmp_path)
    asyncio.run(acquire_file_source(_file_source(other.path), home=home))
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "canary.md").write_text(f"{_WORKING_DIRECTORY_CANARY}\n", encoding="utf-8")
    (cwd / "OTHER.md").write_text(f"{_WORKING_DIRECTORY_CANARY}\n", encoding="utf-8")
    monkeypatch.chdir(cwd)

    origin = _origin(tmp_path / "mine")
    result = _serve(origin.url)
    assert result.exit_code == 0, result.output

    probes = ("canary.md", "OTHER.md", _wire("canary.md"), _wire("OTHER.md"))
    routes = [
        route
        for route in server.app.routes
        if isinstance(route, Route)
        and "GET" in (route.methods or set())
        and route.path.startswith(("/api/", "/raw", "/view", "/commit"))
    ]
    probed = [url for route in routes for url in _probe_urls(route, probes, other.first)]
    expected = {"/api/file", "/raw", "/raw/{path:path}", "/api/tree", "/api/git/commit/{revision}"}
    assert expected <= {route.path for route in routes}
    with TestClient(server.app) as client:
        # The probe can see a leak: the pin's own content does come back.
        own = client.get("/api/file", params={"path": _wire("README.md")})
        assert "Second revision." in own.json()["content"]
        assert client.get(f"/api/git/commit/{other.first}").status_code == 404
        for url in probed:
            response = client.get(url)
            assert _OTHER_SOURCE_CANARY not in response.text, url
            assert _WORKING_DIRECTORY_CANARY not in response.text, url
            assert str(home) not in response.text, url
            assert str(other.path) not in response.text, url

        for route in ("/api/cache/layout", "/api/cache/sources", "/api/cache/stores"):
            refused = client.get(route)
            assert refused.status_code == 409, route
            assert refused.json()["capability"] == "cache_inspection"
        assert client.get("/api/cache/source/anything").status_code == 409

        # The preview frame's origin is opaque; nothing under /api answers it.
        for headers in ({"origin": "null"}, {"sec-fetch-site": "cross-site"}):
            for route in ("/api/source/status", f"/api/file?path={_wire('README.md')}"):
                assert client.get(route, headers=headers).status_code == 403, (route, headers)
