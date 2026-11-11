"""The rules a checkout served as a folder keeps, as tests a transcript cannot be.

``tests/test_cli_github_checkout_golden.py`` pins what the routes answer on a checkout. These
add the evidence no transcript gives, each with what breaks it:

- a page whose Pulls tab is never opened runs no ``gh`` and loads nothing of the cache or
  the GitHub plugin past their route tables;
- the whole flow leaves the checkout's ``.git`` byte for byte as it was, runs no Git at
  all, and works with the checkout read-only;
- nothing is written under a slug no source holds;
- a pull request's text is inert under both trust profiles, the trusted one with no
  Content-Security-Policy behind it, with the hardener removed as the mutation check.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_list, pull_markdown, pulls
from metabrowser.builtin_plugins.github.pull_record import write_refresh_stamp
from metabrowser.cache.paths import source_pull_refresh
from metabrowser.capabilities import Capabilities, set_capabilities
from tests.checkout_replica import fingerprint
from tests.github_pull_fixture import (
    ANOTHER_READER,
    CANONICAL,
    FETCHED_AT,
    HOSTILE_COMMENT,
    READER,
    Origin,
    allowlist_violations,
    clone_checkout,
    files_scenario,
    install_fake_gh,
    ok,
    page,
)
from tests.golden_harness import Invocation, origin_identity, run_metab
from tests.required_tools import needs_git
from tests.test_plugin_public_api import (
    _CHILD_TIMEOUT_S,  # pyright: ignore[reportPrivateUsage]
    _git_source_modules_in,  # pyright: ignore[reportPrivateUsage]
)

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

REPO_ROOT = Path(__file__).resolve().parent.parent
HOSTILE_LINKS = json.loads(
    (REPO_ROOT / "tests" / "fixtures" / "inert-html-hostile-links.json").read_text(encoding="utf-8")
)


def _logging_tool(directory: Path, name: str, *, then: str | None) -> Path:
    """A *name* first on ``PATH`` that logs each call and its directory, then runs *then*.

    With *then* ``None`` it fails, as a ``gh`` that must never be asked does.
    """

    directory.mkdir(parents=True, exist_ok=True)
    log = directory / f"{name}-calls.log"
    tail = f'exec {then} "$@"' if then is not None else "exit 1"
    tool = directory / name
    tool.write_text(
        f'#!/bin/sh\nprintf "%s\\t%s\\t%s\\n" "$PWD" "${{GIT_DIR:-}}" "$*" >> {log}\n{tail}\n',
        encoding="utf-8",
    )
    tool.chmod(0o755)
    return log


def _calls(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


# ── An unopened tab ─────────────────────────────────────────────

# The routes a checkout's page asks for while its Pulls tab is never opened: the shell, the
# tree, and the Git tab's question, which the shell asks of every folder.
_UNOPENED = (
    "/view/",
    "/view/README.md",
    "/api/tree?depth=1",
    "/api/git/repo",
    "/api/source/status",
)

_REPORT = textwrap.dedent(
    """
    import asyncio, json, sys
    from pathlib import Path
    from metabrowser import server
    from metabrowser.cli.asgi_client import InProcessClient

    async def answer(routes):
        async with InProcessClient(server.app, label="shell") as client:
            return [(await client.get(route)) for route in routes]

    server._set_root_dir(Path(sys.argv[1]))
    answers = asyncio.run(answer(sys.argv[2:]))
    loaded = sorted(name for name in sys.modules if name.startswith("metabrowser."))
    sys.stdout.write(json.dumps({
        "status": [response.status_code for response in answers],
        "tab": 'data-tab="pulls"' in answers[0].text(),
        "loaded": loaded,
    }))
    """
)


def test_an_unopened_tab_runs_no_gh_and_loads_nothing_past_the_route_tables(
    tmp_path: Path, pull_origin: Origin
) -> None:
    """The page has the tab, and nothing behind it ran: the network rule's evidence.

    A fresh interpreter, so what is loaded is what serving the page loaded. Mutation check:
    a shell that reads the cached list ahead of the tab on a checkout, or a route table that
    resolves the checkout at import, loads ``checkout`` and fails here; one that asks ``gh``
    fills its log.
    """

    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    gh_log = _logging_tool(tmp_path / "bin", "gh", then=None)
    environment = {
        **os.environ,
        "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}",
        "METABROWSER_CACHE_DIR": str(tmp_path / "home"),
    }
    result = subprocess.run(
        [sys.executable, "-c", _REPORT, str(checkout), *_UNOPENED],
        check=False,
        capture_output=True,
        text=True,
        timeout=_CHILD_TIMEOUT_S,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    answer = json.loads(result.stdout)

    assert answer["status"] == [200] * len(_UNOPENED)
    assert answer["tab"] is True
    assert _git_source_modules_in(set(answer["loaded"])) == []
    assert "metabrowser.builtin_plugins.github.checkout" not in answer["loaded"]
    assert _calls(gh_log) == []
    assert not (tmp_path / "home").exists()


# ── The whole flow, read-only ───────────────────────────────────


@pytest.fixture
def read_only_checkout(
    tmp_path: Path, pull_origin: Origin, request: pytest.FixtureRequest
) -> Iterator[Path]:
    """A checkout whose every directory and file is read-only, put back for cleanup."""

    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    roots = [checkout]
    if getattr(request, "param", "main") == "linked":
        linked = tmp_path / "linked-checkout"
        subprocess.run(
            ["git", "-C", str(checkout), "worktree", "add", "--detach", str(linked)],
            check=True,
            capture_output=True,
        )
        roots.append(linked)
    entries = [entry for root in roots for entry in (root, *root.rglob("*"))]
    modes = {path: stat.S_IMODE(os.lstat(path).st_mode) for path in entries}
    for path in sorted(entries, key=lambda entry: len(entry.parts), reverse=True):
        if not path.is_symlink():
            path.chmod(modes[path] & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    try:
        yield roots[-1]
    finally:
        for path in sorted(entries, key=lambda entry: len(entry.parts)):
            if not path.is_symlink():
                path.chmod(modes[path])


def _api(root: Path, route: str, body: dict[str, Any] | None, request: Path) -> Invocation:
    if body is None:
        return run_metab([str(root), "--api", route])
    request.write_text(json.dumps(body) + "\n", encoding="utf-8")
    return run_metab([str(root), "--api", route, "--data", str(request)])


def test_the_whole_flow_writes_nothing_to_the_checkout_and_runs_no_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, read_only_checkout: Path, pull_origin: Origin
) -> None:
    """Every pull route a reader's page reaches, on a checkout nobody may write.

    ``.git`` is compared byte for byte, inode and time included, so a rewrite to the same
    bytes shows. A ``git`` that logs every call, and then runs the real one, is first on
    ``PATH``: the routes run none, so nothing can have read the checkout's configuration
    either. Mutation check: a record job that fetches the head into the checkout, or reads
    a comparison from it, fails on the read-only tree and fills the log.
    """

    checkout = read_only_checkout
    before = fingerprint(checkout)
    real_git = subprocess.run(
        ["sh", "-c", "command -v git"], check=True, capture_output=True, text=True
    ).stdout.strip()
    git_log = _logging_tool(tmp_path / "git-bin", "git", then=real_git)
    for name, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("PATH", f"{tmp_path / 'git-bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(tmp_path / "home"))
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "ERROR")
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
    request = tmp_path / "request.json"

    flow: list[tuple[str, str, dict[str, Any] | None]] = [
        ("list", "/api/plugin/github/pulls?limit=1", None),
        ("refresh the list", "/api/plugin/github/pulls-refresh", {}),
        ("a larger display window", "/api/plugin/github/pulls-refresh", {"target": 1000}),
        ("a record", "/api/plugin/github/pull-refresh", {"number": 10, "retry": True}),
        ("one it lacks", "/api/plugin/github/pull-refresh", {"number": 7, "retry": True}),
        ("its text", "/api/plugin/github/pull-markdown?number=7&part=body", None),
        ("its files", "/api/plugin/github/pull-files-refresh", {"number": 7}),
        ("read back", "/api/plugin/github/pull?number=7", None),
    ]
    for step, route, body in flow:
        answered = _api(checkout, route, body, request)
        assert answered.exit_code == 0, (step, answered.stdout, answered.stderr)
    for shown in ("/pull/10", "/pulls", "/pull/7"):
        assert run_metab([str(checkout), "--show", shown]).exit_code == 0, shown

    assert _calls(git_log) == []
    assert fingerprint(checkout) == before
    slug = origin_identity(CANONICAL).slug
    written = tmp_path / "home" / "sources" / slug / "pulls" / "7.json"
    record = json.loads(written.read_text(encoding="utf-8"))
    assert record["comparison"] is None
    assert record["unavailable"]["comparison"] == "no_store"


def test_comparison_on_a_recognized_checkout_without_a_store_is_no_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
    before = fingerprint(checkout)
    route = (
        "/api/plugin/github/pull-comparison?number=7"
        f"&left={'a' * 40}&right={'b' * 40}&base_policy=merge_base"
    )
    response = _api(checkout, route, None, tmp_path / "request.json")
    assert response.exit_code == 1, response.stderr
    assert "status: 409\n" in response.stdout
    assert response.payload() == {
        "error": "this comparison has no available repository store",
        "code": "no_store",
    }
    assert not home.exists(), "a comparison GET acquired a store"
    assert fingerprint(checkout) == before


def test_nothing_is_written_under_a_slug_no_source_holds(tmp_path: Path) -> None:
    """A write ahead of the claim creates nothing: no home and no orphaned source directory.

    Mutation check: create the ``pulls`` directory with ``ensure_private_directory`` alone,
    as the writes did before a checkout could reach them, and the home appears.
    """

    from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp

    home = tmp_path / "home"
    stamp = PullRefreshStamp(outcome="gh_missing", at="2026-09-17T12:00:00Z")
    with pytest.raises(FileNotFoundError):
        write_refresh_stamp(
            home,
            "github-com--octo--demo--0123456789ab",
            source_pull_refresh("github-com--octo--demo--0123456789ab", 7),
            stamp,
        )
    assert not home.exists()


# ── Untrusted text on a trusted page ────────────────────────────


def _hostile_scenario(origin: Origin) -> dict[str, Any]:
    """Pull request 10, every text of it hostile: title, body, branch names, labels, and a
    comment, a review, and a review comment, each carrying the comment and the link corpus."""

    answers = files_scenario(origin)
    # Each link in its own paragraph, so Markdown reads the second spelling as a link too.
    corpus = (
        HOSTILE_COMMENT
        + "\n\n"
        + "\n\n".join(
            f'<a href="{href}">{name}</a> [{name}]({href})'
            for name, href in {**HOSTILE_LINKS["refused"], **HOSTILE_LINKS["kept"]}.items()
        )
    )
    api = dict(answers["api"])
    base = "repos/octo/demo"
    pull = json.loads(json.dumps(api[f"{base}/pulls/10"]["body"]))
    pull["title"] = '<img src=x onerror="alert(1)"> <script>alert(2)</script>'
    pull["body"] = corpus
    pull["head"]["ref"] = '"><svg onload=alert(3)>'
    pull["labels"] = [{"name": "<b onmouseover=alert(4)>label</b>", "color": "ff0000"}]
    api[f"{base}/pulls/10"] = ok(f"{base}/pulls/10", pull)
    who = {"login": "<i>someone</i>"}
    comment = {
        "id": 1,
        "user": who,
        "body": corpus,
        "created_at": pull["created_at"],
        "updated_at": pull["updated_at"],
    }
    review = {
        "id": 2,
        "user": who,
        "body": corpus,
        "state": "COMMENTED",
        "submitted_at": pull["updated_at"],
        "commit_id": pull["head"]["sha"],
    }
    for path, body in (
        (page(f"{base}/issues/10/comments"), [comment]),
        (page(f"{base}/pulls/10/reviews"), [review]),
    ):
        api[path] = ok(path, body)
    return {**answers, "api": api}


def test_pull_request_text_is_inert_under_both_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """The same inert markup under the profile a checkout has and the one a mirror has.

    A checkout is served trusted, and its page has no Content-Security-Policy, which is
    asserted here; so the server's allowlist is its only line, and the page's rebuild is
    ``tests/test_inert_html.py``'s. Every text renders through it, every link left is
    http(s), and no other text reaches markup: the record is JSON, which the page paints as
    text. Neither layer reads the profile, so both servers answer the same markup. Mutation
    check: render without ``harden`` and every text has violations, under both profiles.
    """

    from starlette.testclient import TestClient

    from metabrowser import server

    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    for name, value in install_fake_gh(tmp_path, _hostile_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(tmp_path / "home"))
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "ERROR")
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
    body = {"number": 10, "retry": True}
    fetched = _api(checkout, "/api/plugin/github/pull-refresh", body, tmp_path / "request.json")
    assert fetched.exit_code == 0, fetched.stderr

    by_profile: dict[str, dict[str, str]] = {}
    for profile, active in (("trusted", True), ("untrusted", False)):
        set_capabilities(Capabilities(active_content=active, mutations=False))
        server._set_root_dir(checkout)  # pyright: ignore[reportPrivateUsage]
        with TestClient(server.app) as client:
            shell = client.get("/pull/10")
            assert ("content-security-policy" in shell.headers) is not active, profile
            record = client.get("/api/plugin/github/pull?number=10").json()["record"]
            # What the page paints as text comes as it was written, as JSON strings.
            assert record["pull"]["title"].startswith("<img src=x")
            assert record["pull"]["labels"] == ["<b onmouseover=alert(4)>label</b>"]
            assert record["pull"]["head"]["ref"] == '"><svg onload=alert(3)>'
            rendered = by_profile[profile] = _rendered(client)
            with monkeypatch.context() as broken:
                broken.setattr(pull_markdown, "harden", lambda html, _base: html)  # pyright: ignore[reportUnknownLambdaType]
                unhardened = _rendered(client)
        for part, html in rendered.items():
            assert allowlist_violations(html) == [], (profile, part)
            # Raw markup survives only as text: the corpus's script is escaped, never a tag.
            assert "<script" not in html and "onerror=" not in html, (profile, part)
            for name in HOSTILE_LINKS["refused"]:
                assert f"<a>{name}</a>" in html, (profile, part, name)
        for part, html in unhardened.items():
            assert allowlist_violations(html) != [], (profile, part)
    assert by_profile["trusted"] == by_profile["untrusted"]


def _rendered(client: Any) -> dict[str, str]:
    parts = ("body", "issue_comment/1", "review/2")
    answers = {
        part: client.get(f"/api/plugin/github/pull-markdown?number=10&part={part}")
        for part in parts
    }
    for part, answer in answers.items():
        assert answer.status_code == 200, (part, answer.text)
    return {part: answer.json()["html"] for part, answer in answers.items()}


@pytest.mark.parametrize("read_only_checkout", ["main", "linked"], indirect=True)
@pytest.mark.parametrize("serve_subdirectory", [False, True])
def test_checkout_comparison_fetch_uses_only_the_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    read_only_checkout: Path,
    pull_origin: Origin,
    serve_subdirectory: bool,
) -> None:
    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.cache.urls import GitSource
    from tests.golden_harness import isolate_cli
    from tests.test_cli_github_checkout_golden import _after  # pyright: ignore[reportPrivateUsage]

    home = isolate_cli(tmp_path, monkeypatch).home
    checkout_module._RESOLVED.clear()  # pyright: ignore[reportPrivateUsage]
    checkout_module._PULLS.clear()  # pyright: ignore[reportPrivateUsage]
    for name, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)

    def remote_url_for(source: GitSource) -> str:
        return pull_origin.url if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote_url_for)
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
    before = fingerprint(read_only_checkout)
    common_before = fingerprint(tmp_path / "checkout")
    root = read_only_checkout / "src" if serve_subdirectory else read_only_checkout
    real_git = subprocess.run(
        ["sh", "-c", "command -v git"], check=True, capture_output=True, text=True
    ).stdout.strip()
    git_log = _logging_tool(tmp_path / "git-bin", "git", then=real_git)
    monkeypatch.setattr(
        "metabrowser.git.process.git_executable", lambda: str(git_log.parent / "git")
    )
    request = tmp_path / "request.json"
    route = "/api/plugin/github/pull-refresh"
    record = _api(root, route, {"number": 10, "retry": True}, request)
    assert record.exit_code == 0, record.stderr
    assert _after(record)["record"]["unavailable"]["comparison"] == "no_store"
    assert not list((home / "repository-stores").iterdir())

    fetched = _api(
        root,
        route,
        {"number": 10, "retry": True, "comparison": True},
        request,
    )
    assert fetched.exit_code == 0, fetched.stderr
    after = _after(fetched)
    assert after["record"]["comparison"] is not None, after
    assert after["pin"] is None
    assert after["comparison_route"].startswith("/api/plugin/github/pull-comparison?")
    compared = _api(root, after["comparison_route"], None, request)
    assert compared.exit_code == 0, compared.stderr
    assert compared.payload()["manifest"]["files"]
    assert fingerprint(read_only_checkout) == before
    # A revision file opens from the store beside the checkout and leaves it as it was.
    from metabrowser.git.tree_source import GitPath

    revision = _api(
        root,
        after["snapshot_route"]
        + "&side=head&mode=download&path="
        + GitPath.from_display("docs/draft.md").to_wire(),
        None,
        request,
    )
    assert revision.exit_code == 0, revision.stderr
    assert revision.stdout.endswith("# Draft\n\n"), revision.stdout
    assert fingerprint(read_only_checkout) == before

    # A fresh server adopts the persisted store without acquisition or a timestamp write.
    checkout_module._RESOLVED.clear()  # pyright: ignore[reportPrivateUsage]
    checkout_module._PULLS.clear()  # pyright: ignore[reportPrivateUsage]
    calls: list[str] = []

    async def forbidden(*args: Any, **kwargs: Any) -> Any:
        calls.append("acquire")
        raise AssertionError("a cached comparison must not acquire")

    monkeypatch.setattr("metabrowser.cache.acquire.acquire_source", forbidden)
    record_files = {
        path: (path.stat().st_mtime_ns, path.read_bytes()) for path in home.rglob("*.yml")
    }
    git_before_read = _calls(git_log)
    cached = _api(root, "/api/plugin/github/pull?number=10", None, request)
    assert cached.payload()["record"]["comparison"] == after["record"]["comparison"]
    assert cached.payload()["comparison_route"] == after["comparison_route"]
    assert calls == []
    assert _calls(git_log) == git_before_read
    assert {
        path: (path.stat().st_mtime_ns, path.read_bytes()) for path in home.rglob("*.yml")
    } == record_files
    assert fingerprint(read_only_checkout) == before

    assert fingerprint(tmp_path / "checkout") == common_before
    assert _calls(git_log), "the comparison exercises real Git"
    assert all(str(read_only_checkout) not in call for call in _calls(git_log))
    assert all(str(tmp_path / "checkout") not in call for call in _calls(git_log))


def _idle_job_stand(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin, events: list[str]
) -> tuple[Any, asyncio.Event, asyncio.Event]:
    """A checkout with a store, whose job phases only note that they ran.

    The idle phase sets the first event and waits for the second, so a test can act
    while it runs.
    """
    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.builtin_plugins.github.served_pull import ServedPull, ServedPulls

    checkout = clone_checkout(origin, tmp_path / "checkout")
    repository = checkout_module._resolve(checkout, tmp_path / "home")  # pyright: ignore[reportPrivateUsage]
    assert repository is not None
    monkeypatch.setattr(ServedPulls, "git_dir", property(lambda _self: tmp_path / "store.git"))
    started, release = asyncio.Event(), asyncio.Event()

    async def prepare_idle(_state: Any, companion: ServedPull, _eager: Any) -> None:
        events.append(f"idle {companion.number} starts")
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            events.append(f"idle {companion.number} cancelled")
            raise
        events.append(f"idle {companion.number} ends")

    async def prepare_foreground(_state: Any, _repository: Any, companion: ServedPull) -> str:
        events.append(f"comparison {companion.number}")
        return "done"

    async def refresh(companion: ServedPull) -> None:
        events.append(f"refresh {companion.number}")
        await asyncio.sleep(0.01)

    monkeypatch.setattr(checkout_module, "_prepare_idle", prepare_idle)
    monkeypatch.setattr(checkout_module, "_prepare_foreground", prepare_foreground)
    monkeypatch.setattr(ServedPull, "refresh", refresh)
    return repository, started, release


@pytest.mark.usefixtures("fresh_checkout_state")
@pytest.mark.parametrize("reader", ["another_pull", "refresh", "changes"])
def test_a_readers_request_never_waits_for_idle_comparison_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin, reader: str
) -> None:
    """Review B1: idle work holds no slot, and any reader's request ends it.

    Before, the idle job held the store turn and one of two network slots through a whole
    acquisition, and the reader's job waited for it: 2.1 to 4.3 s in review D's runs.
    """
    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.mirror_refresh import MAX_CONCURRENT_REFRESHES, RefreshCoordinator

    events: list[str] = []
    repository, started, release = _idle_job_stand(tmp_path, monkeypatch, pull_origin, events)

    def start(number: int, **kwargs: Any) -> str:
        return checkout_module.start_pull_refresh(coordinator, repository, number, **kwargs)

    async def run() -> None:
        try:
            assert start(10, comparison=True, eager_revision="a" * 64) == "started"
            await asyncio.wait_for(started.wait(), 5)
            assert checkout_module.comparison_preparing(coordinator, repository, 10)
            free = coordinator.slot()._value  # pyright: ignore[reportPrivateUsage]
            assert free == MAX_CONCURRENT_REFRESHES, "an idle job holds no network slot"
            if reader == "another_pull":
                assert start(12) == "started"
            elif reader == "refresh":
                held = checkout_module.checkout_pulls(repository)
                assert (await held.companion(10)).request_recovery(None)
                assert start(10) == "joined"
            else:
                assert start(10, comparison=True) == "joined"
                assert not checkout_module.comparison_preparing(coordinator, repository, 10)
                release.set()
            await coordinator.drain(timeout_s=5)
        finally:
            release.set()
            await coordinator.aclose()

    coordinator = RefreshCoordinator()
    asyncio.run(run())
    assert (
        events
        == {
            "another_pull": ["idle 10 starts", "idle 10 cancelled", "refresh 12"],
            "refresh": ["idle 10 starts", "idle 10 cancelled", "refresh 10"],
            # Changes asks for the very work the idle job is doing, which goes on as the reader's.
            "changes": ["idle 10 starts", "idle 10 ends", "comparison 10"],
        }[reader]
    )


@pytest.mark.usefixtures("fresh_checkout_state")
def test_idle_comparison_is_never_queued_with_or_ahead_of_a_readers_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """Review D2: optional work starts only on a quiet checkout.

    Before, an idle job queued behind a running job took the turn ahead of the third
    waiting reader's job, through the turn's rule that keeps a mirror refresh from
    starving: ``foreground 12, foreground 13, idle 10, foreground 14, foreground 15``.
    """
    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.mirror_refresh import RefreshCoordinator

    events: list[str] = []
    repository, _started, release = _idle_job_stand(tmp_path, monkeypatch, pull_origin, events)

    def start(number: int, **kwargs: Any) -> str:
        return checkout_module.start_pull_refresh(coordinator, repository, number, **kwargs)

    async def run() -> None:
        turn = checkout_module._checkout_state(repository).turn  # pyright: ignore[reportPrivateUsage]
        try:
            assert start(12) == "started"
            assert start(10, comparison=True, eager_revision="a" * 64) == "not_due"
            await coordinator.drain(timeout_s=5)
            # Even an idle job that is waiting when the readers come is ended by them.
            async with turn(lambda: True):
                assert start(10, comparison=True, eager_revision="a" * 64) == "started"
                await asyncio.sleep(0)
                assert start(11, comparison=True, eager_revision="b" * 64) == "not_due"
                for number in (12, 13, 14, 15):
                    assert start(number) == "started"
                    await asyncio.sleep(0)
            await coordinator.drain(timeout_s=5)
        finally:
            release.set()
            await coordinator.aclose()

    coordinator = RefreshCoordinator(limit=8)
    asyncio.run(run())
    assert events == ["refresh 12", "refresh 12", "refresh 13", "refresh 14", "refresh 15"]


@pytest.mark.usefixtures("fresh_checkout_state")
def test_idle_comparison_never_starts_without_a_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.mirror_refresh import RefreshCoordinator

    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    repository = checkout_module._resolve(checkout, tmp_path / "home")  # pyright: ignore[reportPrivateUsage]
    assert repository is not None

    async def run() -> str:
        coordinator = RefreshCoordinator()
        try:
            return checkout_module.start_pull_refresh(
                coordinator, repository, 10, comparison=True, eager_revision="a" * 64
            )
        finally:
            await coordinator.aclose()

    assert asyncio.run(run()) == "not_due"


def test_comparison_fetch_joining_metadata_refresh_is_not_lost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.builtin_plugins.github.gh_lists import PullDataError
    from metabrowser.builtin_plugins.github.served_pull import ServedPull
    from metabrowser.mirror_refresh import RefreshCoordinator

    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    repository = checkout_module._resolve(checkout, tmp_path / "home")  # pyright: ignore[reportPrivateUsage]
    assert repository is not None
    acquisitions: list[Path] = []

    async def run() -> None:
        coordinator = RefreshCoordinator(limit=1)
        entered, release = asyncio.Event(), asyncio.Event()

        async def held_refresh(self: ServedPull) -> None:
            entered.set()
            await release.wait()

        async def refused(repository: checkout_module.CheckoutRepository) -> Any:
            acquisitions.append(repository.checkout_root)
            raise PullDataError("network_error", "the repository could not be read from its origin")

        monkeypatch.setattr(ServedPull, "refresh", held_refresh)
        monkeypatch.setattr(checkout_module, "_acquire_comparison", refused)
        try:
            assert checkout_module.start_pull_refresh(coordinator, repository, 10) == "started"
            await asyncio.wait_for(entered.wait(), timeout=5)
            assert (
                checkout_module.start_pull_refresh(coordinator, repository, 10, comparison=True)
                == "joined"
            )
            release.set()
            await coordinator.drain(timeout_s=5)
            assert not coordinator.running(checkout_module.checkout_job_key(repository, 10))
            held = checkout_module.checkout_pulls(repository).held(10)
            assert held is not None and held.last is not None
            assert held.last["outcome"] == "network_error"
        finally:
            await coordinator.aclose()

    asyncio.run(run())
    assert acquisitions == [checkout]


def test_failed_comparison_fetch_preserves_cached_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    from metabrowser.cache.acquire import RemoteAccessError
    from tests.golden_harness import isolate_cli
    from tests.test_cli_github_checkout_golden import _after  # pyright: ignore[reportPrivateUsage]

    isolate_cli(tmp_path, monkeypatch)
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    for name, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
    request = tmp_path / "request.json"
    route = "/api/plugin/github/pull-refresh"
    before = _after(_api(checkout, route, {"number": 10, "retry": True}, request))

    async def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise RemoteAccessError(
            "network_unreachable", "private filesystem detail must stay internal"
        )

    monkeypatch.setattr("metabrowser.cache.acquire.acquire_source", unavailable)
    fetched = _api(checkout, route, {"number": 10, "retry": True, "comparison": True}, request)
    assert fetched.exit_code == 1
    after = _after(fetched)
    assert after["record"] == before["record"]
    assert after["last_refresh"]["outcome"] == "network_error"
    assert "private filesystem detail" not in fetched.stdout
    assert after["pin"] is None and after["comparison_route"] is None


@pytest.mark.parametrize("damage", ["partial", "alternates"])
def test_checkout_comparison_fetch_refuses_to_clone_when_borrowing_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin, damage: str
) -> None:
    from metabrowser.cache import acquire
    from tests.golden_harness import isolate_cli, pinned_git
    from tests.test_cli_github_checkout_golden import _after  # pyright: ignore[reportPrivateUsage]

    home = isolate_cli(tmp_path, monkeypatch).home
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    if damage == "partial":
        pinned_git(checkout, "config", "remote.origin.promisor", "true")
    else:
        (checkout / ".git/objects/info/alternates").write_text("/unavailable\n")
    before = fingerprint(checkout)
    for name, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
    monkeypatch.setattr(acquire, "remote_url_for", lambda _source: pull_origin.url)
    request = tmp_path / "request.json"
    route = "/api/plugin/github/pull-refresh"
    initial = _after(_api(checkout, route, {"number": 10, "retry": True}, request))
    fetched = _api(checkout, route, {"number": 10, "retry": True, "comparison": True}, request)
    assert fetched.exit_code == 1, fetched.stdout
    after = _after(fetched)
    assert after["last_refresh"]["outcome"] == "lender_missing"
    assert after["record"] == initial["record"]
    assert str(checkout) not in fetched.stdout
    assert not list((home / "repository-stores").iterdir())
    assert fingerprint(checkout) == before


@pytest.mark.parametrize(
    "damage", ["future", "missing", "corrupt", "unknown", "config_future", "config_corrupt"]
)
@pytest.mark.parametrize("rate_hold", [False, True])
def test_existing_checkout_source_refuses_unknown_cache_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pull_origin: Origin,
    damage: str,
    rate_hold: bool,
) -> None:
    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.builtin_plugins.github.gh_lists import PullDataError
    from tests.golden_harness import isolate_cli

    isolated = isolate_cli(tmp_path, monkeypatch)
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    repository = checkout_module._resolve(checkout, isolated.home)  # pyright: ignore[reportPrivateUsage]
    assert repository is not None
    asyncio.run(checkout_module.claim_source(repository))
    from datetime import timedelta

    from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp

    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    reset_at = "2026-09-17T12:05:00Z" if rate_hold else None
    if rate_hold:
        pull_list.write_files_refresh(
            isolated.home,
            repository.slug,
            7,
            PullRefreshStamp(outcome="rate_limited", at="2026-09-17T12:00:00Z", reset_at=reset_at),
        )
    layout = isolated.home / "layout.yml"
    config = Path(os.environ["METABROWSER_CONFIG_DIR"]) / "config.yml"
    if damage == "missing":
        layout.unlink()
    elif damage == "corrupt":
        layout.write_text("not: [valid\n")
    elif damage == "config_corrupt":
        config.write_text("not: [valid\n")
    else:
        path = config if damage == "config_future" else layout
        replacement = "f00" if damage == "unknown" else "f02"
        path.write_text(path.read_text().replace("format: f01", f"format: {replacement}", 1))

    def snapshot(root: Path) -> dict[str, tuple[int, int, int, bytes | str | None]]:
        entries = {}
        for path in root.rglob("*"):
            status = path.lstat()
            payload = (
                path.readlink().as_posix()
                if path.is_symlink()
                else path.read_bytes()
                if path.is_file()
                else None
            )
            entries[path.relative_to(root).as_posix()] = (
                status.st_ino,
                status.st_mtime_ns,
                status.st_mode,
                payload,
            )
        return entries

    before = snapshot(isolated.home)
    config_before = snapshot(config.parent)
    assert before and config_before
    with pytest.raises(PullDataError) as refused:
        asyncio.run(checkout_module.claim_source(repository))
    assert refused.value.state == "cache_unwritable"
    assert str(refused.value) == "the repository could not be recorded in the cache"

    from metabrowser.builtin_plugins.github import pull_list_refresh, pull_list_route

    async def no_account() -> str:
        raise AssertionError("a refused source must not contact gh")

    monkeypatch.setattr(pull_list_refresh, "active_account", no_account)
    with pytest.raises(PullDataError) as list_refused:
        asyncio.run(pull_list_refresh.refresh_pull_list(repository, "all"))
    assert list_refused.value.state == "cache_unwritable"
    view = pull_list_route.ListView(repository, None, False)
    envelope = pull_list_route.pull_list_envelope(view, pull_list_route.ListWindow("all"))
    assert envelope["last_refresh"] is not None
    assert envelope["last_refresh"]["outcome"] == "cache_unwritable"
    assert not pull_list_route.refresh_wanted(view, pull_list_route.RefreshRequest("all"))
    assert snapshot(isolated.home) == before
    assert snapshot(config.parent) == config_before

    # The real file-list worker reports failed admission in memory without touching
    # the refused cache, so a visible tree does not retry on every automatic poll.
    from metabrowser.builtin_plugins.github import pull_files_refresh, pull_files_route
    from metabrowser.mirror_refresh import RefreshCoordinator

    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)

    async def no_provider() -> str:
        raise AssertionError("a refused cache must not contact gh")

    monkeypatch.setattr(pull_files_refresh, "active_account", no_provider)

    async def attempt() -> None:
        coordinator = RefreshCoordinator()
        try:
            await pull_files_route._run_files_refresh(  # pyright: ignore[reportPrivateUsage]
                repository, 7, None, coordinator
            )
        finally:
            await coordinator.aclose()

    asyncio.run(attempt())
    view = pull_files_route.FilesView(7, repository, None, False, None)
    envelope = pull_files_route.pull_files_envelope(view, pull_files_route.FilesWindow(7))
    assert envelope["last_refresh"] is not None
    assert envelope["last_refresh"]["outcome"] == "cache_unwritable"
    assert envelope["last_refresh"]["message"] == str(refused.value)
    assert envelope["last_refresh"]["reset_at"] == reset_at
    assert (
        pull_files_route.files_refresh_wanted(view, pull_files_route.FilesRefreshRequest(7, False))[
            0
        ]
        is False
    )
    assert snapshot(isolated.home) == before
    assert snapshot(config.parent) == config_before
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(seconds=61))
    due, _ = pull_files_route.files_refresh_wanted(
        view, pull_files_route.FilesRefreshRequest(7, False)
    )
    assert due is (not rate_hold)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(seconds=301))
    due, _ = pull_files_route.files_refresh_wanted(
        view, pull_files_route.FilesRefreshRequest(7, False)
    )
    assert due is True


def test_other_pull_read_crossing_attachment_uses_store_for_every_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    from threading import Event

    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.builtin_plugins.github import served_pull as served_module
    from metabrowser.builtin_plugins.github.pull_record import PullRecord, read_pull_record
    from metabrowser.mirror_refresh import RefreshCoordinator
    from tests.golden_harness import isolate_cli

    home = isolate_cli(tmp_path, monkeypatch).home
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    repository = checkout_module._resolve(checkout, home)  # pyright: ignore[reportPrivateUsage]
    assert repository is not None
    for name, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", lambda _source: pull_origin.url)
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
    entered, release = Event(), Event()
    read = served_module.served_pull

    def delayed_read(published: Any, number: int) -> served_module.ServedPull:
        held = read(published, number)
        if number == 7:
            entered.set()
            assert release.wait(10)
        return held

    monkeypatch.setattr(served_module, "served_pull", delayed_read)

    async def run() -> None:
        coordinator = RefreshCoordinator(limit=2)
        group = checkout_module.checkout_pulls(repository)
        reading = asyncio.create_task(group.companion(7))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            assert (
                checkout_module.start_pull_refresh(coordinator, repository, 10, comparison=True)
                == "started"
            )
            await coordinator.drain(timeout_s=10)
            assert group.git_dir is not None
            release.set()
            held = await reading
            assert held.published is group.published
            assert await group.companion(7) is held
            for comparison in (False, True):
                assert (
                    checkout_module.start_pull_refresh(
                        coordinator, repository, 7, comparison=comparison
                    )
                    == "started"
                )
                await coordinator.drain(timeout_s=10)
                record = read_pull_record(home, repository.slug, 7)
                assert isinstance(record, PullRecord)
                assert record.comparison is not None, record.unavailable
                assert held.published is group.published
        finally:
            release.set()
            await reading
            await coordinator.aclose()

    asyncio.run(run())


@pytest.fixture
def fresh_checkout_state(monkeypatch: pytest.MonkeyPatch) -> None:
    from metabrowser.builtin_plugins.github import checkout as checkout_module

    # Successful pytest temporary directories may be removed and their names reused.
    monkeypatch.setattr(checkout_module, "_RESOLVED", {})
    monkeypatch.setattr(checkout_module, "_PULLS", {})


@pytest.mark.usefixtures("fresh_checkout_state")
def test_visible_core_preparation_leaves_checkout_git_and_full_records_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    from tests.github_pull_fixture import catalog_entries, graph_core_data, pull_bodies, scenario
    from tests.golden_harness import isolate_cli
    from tests.test_cli_github_checkout_golden import _after  # pyright: ignore[reportPrivateUsage]

    home = isolate_cli(tmp_path, monkeypatch).home
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    entry = pull_bodies(pull_origin)[7]["pull"]
    data = graph_core_data(entry)
    data["repository"]["p0"] = data["repository"].pop("pull")
    key = "graphql:visible-cores:7"
    answers = scenario(pull_origin)
    answers["api"].update(catalog_entries([entry]))
    answers["api"][key] = ok(key, {"data": data})
    for name, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(name, value)
    request = tmp_path / "request.json"
    listing = _api(checkout, "/api/plugin/github/pulls-refresh", {"retry": True}, request)
    assert listing.exit_code == 0, listing.stdout
    catalog = _after(listing)
    before = fingerprint(checkout)
    git_log = _logging_tool(tmp_path / "no-git", "git", then=None)
    monkeypatch.setenv("PATH", f"{git_log.parent}{os.pathsep}{os.environ['PATH']}")

    result = _api(
        checkout,
        "/api/plugin/github/pull-cores-prepare",
        {
            "state": catalog["list"],
            "window": {"id": "checkout-7", "generation": catalog["generation"]},
            "numbers": [7],
        },
        request,
    )
    assert result.exit_code == 0, result.stdout
    answer = _after(result)
    assert answer["record"] is None and answer["refreshing"] is False
    assert answer["core_preview"]["comparison_state"] == "not_started"
    assert answer["core_preview"]["pull"]["body"] == entry["body"]
    assert _calls(git_log) == [] and fingerprint(checkout) == before
    assert not list(home.glob("sources/*/pulls/7.json"))


@pytest.mark.usefixtures("fresh_checkout_state")
def test_publication_rebinds_checkout_records_to_the_claimed_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    from metabrowser.cache import acquire
    from tests.golden_harness import isolate_cli
    from tests.test_cli_github_checkout_golden import _after  # pyright: ignore[reportPrivateUsage]

    home = isolate_cli(tmp_path, monkeypatch).home
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    for name, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)
    request = tmp_path / "request.json"
    route = "/api/plugin/github/pull?number=10"
    assert _api(checkout, route, None, request).payload()["state"] == "absent"
    other = clone_checkout(pull_origin, tmp_path / "other-checkout")
    assert _api(other, route, None, request).payload()["state"] == "absent"
    choose = acquire.cache_slug

    def longer_slug(transport: Any, address: str, source_id: str, **kwargs: Any) -> str:
        # Inject the admitted collision chooser; publication and route reads remain real.
        short = choose(transport, address, source_id, **kwargs)
        return short.rsplit("--", 1)[0] + "--" + source_id.removeprefix("sha256:")[:16]

    monkeypatch.setattr(acquire, "cache_slug", longer_slug)
    refreshed = _api(
        checkout, "/api/plugin/github/pull-refresh", {"number": 10, "retry": True}, request
    )
    assert refreshed.exit_code == 0, refreshed.stdout
    after = _after(refreshed)
    assert after["record"] is not None, after
    assert after["record"]["pull"]["number"] == 10
    assert _api(checkout, route, None, request).payload()["record"] == after["record"]
    assert _api(other, route, None, request).payload()["record"] == after["record"]
    written = list(home.glob("sources/*/pulls/10.json"))
    assert len(written) == 1 and len(written[0].parents[1].name.rsplit("--", 1)[1]) == 16


@pytest.mark.usefixtures("fresh_checkout_state")
def test_metadata_refresh_preserves_only_the_same_readers_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.builtin_plugins.github.pull_record import (
        PullRecord,
        read_pull_record,
        write_pull_record,
    )
    from tests.golden_harness import isolate_cli

    home = isolate_cli(tmp_path, monkeypatch).home
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    repository = checkout_module._resolve(checkout, home)  # pyright: ignore[reportPrivateUsage]
    assert repository is not None and repository.cached is None
    for name, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", lambda _source: pull_origin.url)

    async def run() -> None:
        published = await checkout_module._acquire_comparison(repository)  # pyright: ignore[reportPrivateUsage]
        original = await pulls.refresh_pull_request(published, 10)
        assert original.comparison is not None
        for change in ("none", "head", "base", "branch", "state", "reader", "comparison_head"):
            cached = original
            if change == "comparison_head":
                cached = original.model_copy(
                    update={"comparison": original.comparison.model_copy(update={"head": "f" * 40})}
                )
            await asyncio.to_thread(write_pull_record, home, published.slug, cached)
            pull = original.pull
            if change in ("head", "base"):
                side = getattr(pull, change).model_copy(update={"sha": "f" * 40})
                pull = pull.model_copy(update={change: side})
            elif change == "branch":
                pull = pull.model_copy(
                    update={"base": pull.base.model_copy(update={"ref": "other"})}
                )
            elif change == "state":
                pull = pull.model_copy(
                    update={"state": "closed" if pull.state == "open" else "open"}
                )
            reader = "gh:other" if change == "reader" else original.reader
            incoming = original.model_copy(
                update={"pull": pull, "reader": reader, "comparison": None}
            )

            async def account(reader: str = reader) -> str:
                return reader.removeprefix("gh:")

            async def api(
                *args: Any, change: str = change, incoming: PullRecord = incoming, **kwargs: Any
            ) -> PullRecord:
                assert (kwargs["previous"] is None) == (change == "reader")
                return incoming

            monkeypatch.setattr(pulls, "active_account", account)
            monkeypatch.setattr(pulls, "_read_api", api)
            refreshed = await pulls.refresh_pull_request(repository, 10)
            assert read_pull_record(home, published.slug, 10) == refreshed
            assert refreshed.comparison == (original.comparison if change == "none" else None), (
                change
            )
            assert refreshed.unavailable.get("comparison") == (
                None if change == "none" else "no_store"
            ), change

    asyncio.run(run())


@pytest.mark.usefixtures("fresh_checkout_state")
@pytest.mark.parametrize("outcome", ["success", "cancel", "failure"])
def test_acquisition_keeps_its_active_companion_bound_after_eviction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin, outcome: str
) -> None:
    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.builtin_plugins.github.pull_record import PullRecord, read_pull_record
    from metabrowser.builtin_plugins.github.served_pull import MAX_KEPT_PULLS
    from metabrowser.mirror_refresh import RefreshCoordinator
    from tests.golden_harness import isolate_cli

    home = isolate_cli(tmp_path, monkeypatch).home
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    repository = checkout_module._resolve(checkout, home)  # pyright: ignore[reportPrivateUsage]
    assert repository is not None
    for name, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", lambda _source: pull_origin.url)
    acquire = checkout_module._acquire_comparison  # pyright: ignore[reportPrivateUsage]

    async def run() -> None:
        coordinator = RefreshCoordinator(limit=1)
        entered, release = asyncio.Event(), asyncio.Event()
        state = checkout_module._checkout_state(repository)  # pyright: ignore[reportPrivateUsage]

        async def delayed(repository: checkout_module.CheckoutRepository) -> Any:
            entered.set()
            await release.wait()
            if outcome == "failure":
                raise pulls.PullDataError("network_error", "the origin is unavailable")
            return await acquire(repository)

        monkeypatch.setattr(checkout_module, "_acquire_comparison", delayed)
        try:
            assert (
                checkout_module.start_pull_refresh(coordinator, repository, 10, comparison=True)
                == "started"
            )
            await asyncio.wait_for(entered.wait(), 5)
            active = state.pulls.held(10)
            assert active is not None
            for number in range(100, 100 + MAX_KEPT_PULLS):
                await state.pulls.companion(number)
            assert state.pulls.held(10) is active
            if outcome == "cancel":
                await coordinator.aclose()
            elif outcome == "failure":
                release.set()
                await coordinator.drain(timeout_s=10)
                assert active.last is not None and active.last["outcome"] == "network_error"
                assert state.pulls.git_dir is None
            else:
                release.set()
                await coordinator.drain(timeout_s=10)
                record = read_pull_record(home, repository.slug, 10)
                assert isinstance(record, PullRecord)
                assert record.comparison is not None, record.unavailable
                assert active.published is state.pulls.published
                assert (await state.pulls.companion(10)).published is state.pulls.published
            assert state.pulls.active is None
        finally:
            release.set()
            await coordinator.aclose()

    asyncio.run(run())


@pytest.mark.usefixtures("fresh_checkout_state")
def test_metadata_refresh_keeps_comparison_published_during_its_api_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    from metabrowser.builtin_plugins.github import checkout as checkout_module
    from metabrowser.builtin_plugins.github.pull_record import read_pull_record
    from tests.golden_harness import isolate_cli

    home = isolate_cli(tmp_path, monkeypatch).home
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    repository = checkout_module._resolve(checkout, home)  # pyright: ignore[reportPrivateUsage]
    assert repository is not None and repository.cached is None
    for name, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", lambda _source: pull_origin.url)
    api = pulls._read_api  # pyright: ignore[reportPrivateUsage]

    async def run() -> None:
        published = await checkout_module._acquire_comparison(repository)  # pyright: ignore[reportPrivateUsage]
        entered, release = asyncio.Event(), asyncio.Event()
        first = True

        async def delayed(*args: Any, **kwargs: Any) -> Any:
            nonlocal first
            if first:
                first = False
                assert kwargs["previous"] is None
                entered.set()
                await release.wait()
            return await api(*args, **kwargs)

        monkeypatch.setattr(pulls, "_read_api", delayed)
        metadata = asyncio.create_task(pulls.refresh_pull_request(repository, 10))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            shared = await pulls.refresh_pull_request(published, 10)
            assert shared.comparison is not None
            release.set()
            refreshed = await metadata
            assert refreshed.comparison == shared.comparison
            assert "comparison" not in refreshed.unavailable
            assert read_pull_record(home, published.slug, 10) == refreshed
        finally:
            release.set()
            await metadata

    asyncio.run(run())


# ── Comparison preparation ─────────────────────────────────────────

_REFRESH: str = "/api/plugin/github/pull-refresh"


class _Session:
    """One checkout served by one-shot ``--api`` commands, with every Git and gh call logged."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin) -> None:
        from tests.golden_harness import isolate_cli

        self.home = isolate_cli(tmp_path, monkeypatch).home
        self.origin = origin
        self.tmp_path = tmp_path
        self.checkout = clone_checkout(origin, tmp_path / "checkout")
        for name, value in install_fake_gh(tmp_path, files_scenario(origin)).items():
            monkeypatch.setenv(name, value)
        monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", lambda _source: origin.url)
        self.monkeypatch = monkeypatch
        self.now(FETCHED_AT)
        real_git = subprocess.run(
            ["sh", "-c", "command -v git"], check=True, capture_output=True, text=True
        ).stdout.strip()
        self.git_log = _logging_tool(tmp_path / "git-bin", "git", then=real_git)
        monkeypatch.setattr(
            "metabrowser.git.process.git_executable", lambda: str(self.git_log.parent / "git")
        )
        self.request = tmp_path / "request.json"
        self.before = fingerprint(self.checkout)

    def now(self, moment: datetime) -> None:
        self.monkeypatch.setattr(pulls, "utc_now", lambda: moment)

    def post(self, body: dict[str, Any]) -> Invocation:
        answer = _api(self.checkout, _REFRESH, body, self.request)
        assert answer.exit_code == 0, answer.stderr
        return answer

    def after(self, body: dict[str, Any]) -> dict[str, Any]:
        from tests.test_cli_github_checkout_golden import (
            _after,  # pyright: ignore[reportPrivateUsage]
        )

        return _after(self.post(body))

    def get(self, route: str) -> Invocation:
        return _api(self.checkout, route, None, self.request)

    def gh(self) -> list[str]:
        from tests.github_pull_fixture import logged_gh_calls

        return logged_gh_calls(self.tmp_path)

    def git(self) -> list[str]:
        """Each Git call since the last ask, as its arguments."""
        calls = [line.split("\t", 2)[2] for line in _calls(self.git_log)]
        self.git_log.unlink(missing_ok=True)
        return calls

    def stamp(self, number: int) -> bytes:
        slug = self.state().pulls.slug
        return (self.home / source_pull_refresh(slug, number)).read_bytes()

    def state(self) -> Any:
        from metabrowser.builtin_plugins.github import checkout as checkout_module

        (held,) = checkout_module._PULLS.values()  # pyright: ignore[reportPrivateUsage]
        return held

    def store_refs(self) -> list[str]:
        git_dir = self.state().pulls.git_dir
        assert git_dir is not None
        return subprocess.run(
            ["git", "--git-dir", str(git_dir), "for-each-ref", "--format=%(refname)"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()

    def attach_store(self) -> dict[str, Any]:
        """Records for 9 and 10 without a store, then the reader's Changes on 10 attaches one."""
        first = self.after({"number": 9, "retry": True})
        assert first["record"]["unavailable"]["comparison"] == "no_store"
        assert self.after({"number": 10, "retry": True})["last_refresh"]["outcome"] == "succeeded"
        assert self.gh()
        changes = self.after({"number": 10, "retry": True, "comparison": True})
        assert changes["comparison_route"] is not None, changes
        # The record is current, so the comparison is prepared from it without reading
        # GitHub a second time.
        assert self.gh() == []
        self.git()
        return first


def _subcommand(argv: str) -> str:
    words = argv.split()
    while words and (words[0].startswith("-") or words[0] in {"--git-dir"}):
        words = words[2:] if words[0] in {"-c", "-C", "--git-dir"} else words[1:]
    return words[0] if words else ""


def _push_unfetched_branches(origin: Origin, count: int) -> None:
    """Branches pushed after the checkout and its store fetched: one 64 KiB blob each."""
    from tests.github_pull_fixture import DEFAULT_BRANCH, git_env

    env = git_env(origin.path.parent)
    tip = subprocess.run(
        ["git", "--git-dir", str(origin.path), "rev-parse", f"refs/heads/{DEFAULT_BRANCH}"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()
    chunks: list[bytes] = []
    for index in range(count):
        data = os.urandom(64 * 1024)
        chunks.append(
            f"commit refs/heads/later-{index:04d}\n"
            f"committer Dev <dev@example.com> {1758110400 + index} +0000\n"
            f"data 6\nlater\nfrom {tip}\n"
            f"M 100644 inline later/{index:04d}.bin\ndata {len(data)}\n".encode()
            + data
            + b"\n"
        )
    subprocess.run(
        ["git", "--git-dir", str(origin.path), "fast-import", "--quiet"],
        input=b"".join(chunks),
        check=True,
        capture_output=True,
        env=env,
    )


@pytest.mark.usefixtures("fresh_checkout_state")
def test_conversation_alone_never_creates_a_store_or_runs_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """Idle preparation needs a store a reader's Changes attached (Review D1).

    Before, an idle request acquired an overlay store, fetching every branch and tag the
    checkout lacked, and every later Conversation refresh then fetched into it: 21 Git
    calls for the idle request and 22 and 18 with 2 and 1 origin fetches for the two
    refreshes below, in review D's measurement. Mutation check: drop the store condition
    from ``start_pull_refresh`` and the route, and the idle request starts that acquisition.
    """

    session = _Session(tmp_path, monkeypatch, pull_origin)
    record = session.after({"number": 10, "retry": True})
    assert record["record"]["unavailable"]["comparison"] == "no_store"
    idle = session.post({"number": 10, "prepare_comparison": record["record_revision"]})
    assert idle.payload()["refresh"] == "not_due"
    for number in (9, 10):
        assert session.after({"number": number, "retry": True})["comparison_route"] is None
    assert session.git() == []
    assert not list((session.home / "repository-stores").iterdir())
    assert fingerprint(session.checkout) == session.before


@pytest.mark.usefixtures("fresh_checkout_state")
def test_idle_comparison_fetches_only_its_pull_request_into_the_attached_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """Optional work costs what its comparison needs, not what the origin has since gained."""

    session = _Session(tmp_path, monkeypatch, pull_origin)
    record = session.attach_store()
    stamp = session.stamp(9)
    _push_unfetched_branches(pull_origin, 25)
    refs = session.store_refs()

    stale = session.post({"number": 9, "prepare_comparison": "a" * 64})
    assert stale.payload()["refresh"] == "not_due"
    after = session.after({"number": 9, "prepare_comparison": record["record_revision"]})
    assert after["comparison_route"] is not None, after
    assert after["fetched_at"] == record["fetched_at"]
    assert after["last_refresh"] == record["last_refresh"]
    assert session.stamp(9) == stamp
    calls = session.git()
    # The head by its pull-request ref and the observed base by its commit: nothing else.
    fetches = [call.split() for call in calls if _subcommand(call) == "fetch"]
    base = record["record"]["pull"]["base"]["sha"]
    wanted = [words[-1].split(":")[0].removeprefix("+") for words in fetches]
    assert wanted == ["refs/pull/9/head", base], fetches
    assert not any(_subcommand(call) == "ls-remote" for call in calls), calls
    assert not any("later-" in ref for ref in session.store_refs())
    assert len(session.store_refs()) <= len(refs) + 1
    assert session.gh() == []

    again = session.post({"number": 9, "prepare_comparison": record["record_revision"]})
    assert again.payload()["refresh"] == "not_due"
    clicked = session.after({"number": 9, "retry": True, "comparison": True})
    assert clicked["comparison_route"] == after["comparison_route"]
    assert session.gh() == []
    assert fingerprint(session.checkout) == session.before


@pytest.mark.usefixtures("fresh_checkout_state")
def test_a_failed_idle_comparison_reports_nothing_and_is_not_repeated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """Idle work never writes the refresh stamp (Review A1).

    Before, the failure became ``last_refresh``, and Conversation said the last refresh
    failed for work the reader never asked for.
    """

    session = _Session(tmp_path, monkeypatch, pull_origin)
    record = session.attach_store()
    stamp = session.stamp(9)
    moved = pull_origin.path.with_name("moved-origin.git")
    pull_origin.path.rename(moved)
    try:
        idle = session.after({"number": 9, "prepare_comparison": record["record_revision"]})
        assert idle["last_refresh"] == record["last_refresh"]
        assert idle["record_revision"] == record["record_revision"]
        assert session.stamp(9) == stamp
        assert [_subcommand(call) for call in session.git()].count("fetch") == 1
        again = session.post({"number": 9, "prepare_comparison": record["record_revision"]})
        assert again.payload()["refresh"] == "not_due"
        assert session.git() == []
    finally:
        moved.rename(pull_origin.path)
    assert session.gh() == []


@pytest.mark.usefixtures("fresh_checkout_state")
def test_a_comparison_from_the_cached_record_keeps_the_metadata_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """Only a metadata read writes a success stamp (Review A1).

    Before, a comparison prepared from the cached record stamped success at the time of
    the click, though nothing was read from GitHub.
    """

    session = _Session(tmp_path, monkeypatch, pull_origin)
    session.after({"number": 10, "retry": True})
    stamp = session.stamp(10)
    session.gh()
    session.now(FETCHED_AT + timedelta(seconds=30))
    changes = session.after({"number": 10, "retry": True, "comparison": True})
    assert changes["comparison_route"] is not None
    assert session.gh() == []
    assert session.stamp(10) == stamp
    assert changes["last_refresh"]["at"] == "2026-09-17T12:00:00Z"


@pytest.mark.usefixtures("fresh_checkout_state")
@pytest.mark.parametrize("why", ["stale", "rate_limited", "another_reader"])
def test_changes_reads_github_first_unless_the_cached_record_is_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin, why: str
) -> None:
    """A stale record, a failure since it, or another reader's record is refreshed first.

    Review A2: before, Changes prepared any cached record of the same source with
    no GitHub read, and a rate limit's stamp was replaced by a success nothing read.
    """
    from metabrowser.builtin_plugins.github.pull_record import (
        PullRefreshStamp,
        read_pull_record,
        write_pull_record,
    )

    session = _Session(tmp_path, monkeypatch, pull_origin)
    session.after({"number": 10, "retry": True})
    session.gh()
    clicked_at = FETCHED_AT + timedelta(seconds=40)
    held = session.state().pulls
    if why == "stale":
        clicked_at = FETCHED_AT + timedelta(days=2)
    elif why == "rate_limited":
        write_refresh_stamp(
            held.home,
            held.slug,
            source_pull_refresh(held.slug, 10),
            PullRefreshStamp(
                outcome="rate_limited",
                message="GitHub's API rate limit was reached",
                reset_at="2026-09-17T13:00:00Z",
                at="2026-09-17T12:00:30Z",
            ),
        )
    else:
        cached = read_pull_record(held.home, held.slug, 10)
        assert not isinstance(cached, str)
        write_pull_record(
            held.home, held.slug, cached.model_copy(update={"reader": f"gh:{ANOTHER_READER}"})
        )
    session.now(clicked_at)
    changes = session.after({"number": 10, "retry": True, "comparison": True})
    assert changes["comparison_route"] is not None, changes
    assert session.gh(), "the comparison request read GitHub"
    assert changes["fetched_at"] == clicked_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert changes["last_refresh"] == {
        "outcome": "succeeded",
        "message": None,
        "reset_at": None,
        "at": changes["fetched_at"],
    }
    assert changes["record"]["reader"] == f"gh:{READER}"


@pytest.mark.usefixtures("fresh_checkout_state")
def test_attaching_a_store_keeps_the_observed_reader_for_reader_scoped_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """Review B2: the bind no longer forgets the reader, and no refresh follows it.

    Each check below admits data of any reader when the observed reader is ``None``, as it
    was after the bind before; the last assertions show that for the two that read cores.
    """
    from metabrowser.builtin_plugins.github.pull_catalog import catalog_members
    from metabrowser.builtin_plugins.github.pull_core_cache import (
        read_cached_core,
        write_cached_cores,
    )
    from metabrowser.builtin_plugins.github.pull_cores import CoreRequest, cached_batch
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from metabrowser.builtin_plugins.github.pull_record import read_pull_record, write_pull_record
    from metabrowser.builtin_plugins.github.served_pull import cached_comparison_record
    from tests.github_pull_fixture import list_entries, list_page, seed_catalog

    session = _Session(tmp_path, monkeypatch, pull_origin)
    session.attach_store()
    held = session.state().pulls
    assert held.git_dir is not None
    assert held.observed_reader == f"gh:{READER}"
    published = held.published

    # The comparison and the idle job admit only the observed reader's record.
    mine = read_pull_record(held.home, held.slug, 10)
    assert not isinstance(mine, str)
    theirs = mine.model_copy(update={"reader": f"gh:{ANOTHER_READER}"})
    write_pull_record(held.home, held.slug, theirs, store_id=published.store_id)
    assert cached_comparison_record(published, held.observed_reader, 10) is None
    # A snapshot of that record's comparison is refused.
    envelope = session.get("/api/plugin/github/pull?number=10").payload()
    query = envelope["comparison_route"].split("?", 1)[1]
    snapshot = session.get(f"/api/plugin/github/pull-snapshot?{query}&side=head&path=README.md")
    assert snapshot.exit_code != 0, snapshot.stdout

    # Core admission and cached cores refuse another reader's catalog.
    lists = list_entries(pull_origin)
    items = [*lists[list_page("all")]["body"], *lists[list_page("all", 2)]["body"]]
    repository = ListedRepository(held.home, held.slug, "octo", "demo")
    catalog = seed_catalog(repository, items, reader=ANOTHER_READER)
    ask = CoreRequest("all", "octo", catalog.generation("all"), (10,))
    _, members = catalog_members(held.home, held.slug, "all", (10,))
    write_cached_cores(held.home, held.slug, catalog, members, {10: mine.pull}, FETCHED_AT)
    held.observe_catalog(catalog)
    assert held.observed_reader == f"gh:{READER}"
    assert cached_batch(held, ask) is None
    assert read_cached_core(held.home, held.slug, 10, reader=held.observed_reader) is None
    # The mutation: the reader the bind used to forget.
    held.observed_reader = None
    assert cached_batch(held, ask) is not None
    assert read_cached_core(held.home, held.slug, 10, reader=held.observed_reader) is not None


@pytest.mark.usefixtures("fresh_checkout_state")
@pytest.mark.parametrize("winner_compared", [True, False])
def test_a_comparison_that_loses_publication_adopts_the_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin, winner_compared: bool
) -> None:
    """Review A6: the checkout job adopts a record another writer published first.

    A winner with a comparison ends the request; one without it is read from GitHub again.
    """
    from metabrowser.builtin_plugins.github.pull_record import PullRecord

    session = _Session(tmp_path, monkeypatch, pull_origin)
    session.attach_store()
    stamp = session.stamp(9)
    real = pulls.write_pull_record
    winners: list[PullRecord] = []

    def first_writer_wins(home: Any, slug: str, record: PullRecord, **kwargs: Any) -> Any:
        if record.number == 9 and not winners:
            update: dict[str, Any] = {"fetched_at": "2026-09-17T12:00:05Z"}
            if not winner_compared:
                update["comparison"] = None
            winners.append(record.model_copy(update=update))
            real(home, slug, winners[0], store_id=kwargs.get("store_id"))
        return real(home, slug, record, **kwargs)

    monkeypatch.setattr(pulls, "write_pull_record", first_writer_wins)
    changes = session.after({"number": 9, "retry": True, "comparison": True})
    assert winners
    if winner_compared:
        assert changes["fetched_at"] == "2026-09-17T12:00:05Z"
        assert changes["comparison_route"] is not None
        assert session.gh() == []
        assert session.stamp(9) == stamp
    else:
        assert session.gh(), "a winner without a comparison is read again"
        assert changes["comparison_route"] is not None
