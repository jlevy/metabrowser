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

import json
import os
import stat
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_list, pull_markdown, pulls
from metabrowser.builtin_plugins.github.pull_record import write_refresh_stamp
from metabrowser.cache.paths import source_pull_refresh
from metabrowser.capabilities import Capabilities, set_capabilities
from tests.checkout_replica import fingerprint
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    HOSTILE_COMMENT,
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
def read_only_checkout(tmp_path: Path, pull_origin: Origin) -> Iterator[Path]:
    """A checkout whose every directory and file is read-only, put back for cleanup."""

    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    entries = [checkout, *checkout.rglob("*")]
    modes = {path: stat.S_IMODE(os.lstat(path).st_mode) for path in entries}
    for path in sorted(entries, key=lambda entry: len(entry.parts), reverse=True):
        if not path.is_symlink():
            path.chmod(modes[path] & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    try:
        yield checkout
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
        ("the next page", "/api/plugin/github/pulls-refresh", {"more": True}),
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
