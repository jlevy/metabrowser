"""The GitHub status check: each state, what it keeps, the route, and what it never reads.

``tests/fixtures/github-status/gh`` answers ``gh --version`` and ``gh auth status --json
hosts`` as ``FAKE_GH_STATUS`` names, the same stand-in
``tests/golden/cli-github-status.tryscript.md`` runs; a second stand-in here logs each
call, so the tests can count them. Neither reaches a gh anyone has signed in.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from metabrowser.builtin_plugins.github import gh_status
from metabrowser.builtin_plugins.github.gh import ENVIRONMENT_TOKENS
from metabrowser.builtin_plugins.github.gh_status import (
    GithubStatus,
    github_status,
    kept_github_status,
)
from metabrowser.builtin_plugins.github.sidekick import status_handler
from tests.golden_harness import run_metab

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the stand-in gh is a shell script")

FIXTURE = Path(__file__).parent / "fixtures" / "github-status"

# An auth call reads its answer before it logs, so a logged call has its answer.
_LOGGING_GH = """#!/bin/sh
if [ "$1" = auth ]; then answer=$(cat "$STATUS_GH_ANSWER"); fi
printf '%s\\n' "$*" >> "$STATUS_GH_LOG"
if [ "$1" = --version ]; then echo 'gh version 2.98.0 (2026-08-20)'; exit 0; fi
if [ "$1" = auth ]; then
  if [ -n "$STATUS_GH_DELAY" ]; then sleep "$STATUS_GH_DELAY"; fi
  printf '%s\\n' "$answer"
  exit 0
fi
exit 2
"""


@pytest.fixture
def fixture_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", f"{FIXTURE}{os.pathsep}{os.environ.get('PATH', '')}")


@pytest.fixture
def logging_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A gh that logs every call and answers ``auth status`` from a file; the log."""

    directory = tmp_path / "bin"
    directory.mkdir()
    gh = directory / "gh"
    gh.write_text(_LOGGING_GH, encoding="utf-8")
    gh.chmod(0o755)
    answer = tmp_path / "answer.json"
    host = {
        "state": "success",
        "active": True,
        "host": "github.com",
        "login": "octo-reader",
        "tokenSource": "keyring",
        "scopes": "repo",
        # gh prints a token only with --show-token, which nothing passes; were it here,
        # nothing would read it.
        "token": "gho_never_read_by_metabrowser",
    }
    answer.write_text(json.dumps({"hosts": {"github.com": [host]}}), encoding="utf-8")
    log = tmp_path / "calls.log"
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("STATUS_GH_LOG", str(log))
    monkeypatch.setenv("STATUS_GH_ANSWER", str(answer))
    return log


def _calls(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _status(variant: str, monkeypatch: pytest.MonkeyPatch) -> GithubStatus:
    monkeypatch.setenv("FAKE_GH_STATUS", variant)
    gh_status.forget_github_status()
    return asyncio.run(github_status())


@pytest.mark.parametrize(
    ("variant", "state", "account", "scopes", "fix"),
    [
        ("signed-in", "ok", "octo-reader", ("gist", "read:org", "repo", "workflow"), None),
        (
            "no-repo-scope",
            "missing_scope",
            "octo-reader",
            ("gist", "read:org"),
            "gh auth refresh --hostname github.com --scopes repo",
        ),
        ("fine-grained-token", "ok", "octo-reader", None, None),
        ("signed-out", "not_logged_in", None, None, "gh auth login --hostname github.com"),
        (
            "token-refused",
            "not_logged_in",
            "octo-reader",
            None,
            "gh auth login --hostname github.com",
        ),
        (
            "env-token-refused",
            "not_logged_in",
            None,
            None,
            "replace the token in GH_TOKEN, or unset it and run gh auth login --hostname github.com",
        ),
        ("offline", "network_error", "octo-reader", None, None),
        ("too-old", "gh_too_old", None, None, "https://cli.github.com/"),
        ("broken", "gh_failed", None, None, "gh auth status --hostname github.com"),
    ],
)
@pytest.mark.usefixtures("fixture_gh")
def test_each_answer_gh_gives_has_one_state_and_its_fix(
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
    state: str,
    account: str | None,
    scopes: tuple[str, ...] | None,
    fix: str | None,
) -> None:
    status = _status(variant, monkeypatch)
    assert (status.state, status.account, status.scopes, status.fix) == (
        state,
        account,
        scopes,
        fix,
    )
    assert status.gh_path == str(FIXTURE / "gh")
    assert status.gh_version == (
        "2.20.2" if variant == "too-old" else None if variant == "broken" else "2.98.0"
    )
    assert status.stops_github_work == (state in {"gh_missing", "gh_too_old", "not_logged_in"})
    # gh's own diagnostics are matched, never repeated.
    assert "dial tcp" not in status.message and "Bad credentials" not in status.message
    assert status.message.endswith(".")
    assert status.to_json()["state"] == state


@pytest.mark.parametrize("variable", ["GH_TOKEN", "GITHUB_TOKEN"])
def test_an_environment_token_that_is_refused_names_the_variable(
    logging_gh: Path, variable: str
) -> None:
    # The shape gh 2.98.0 printed for a refused GH_TOKEN (2026-11-18): no login, the
    # variable as tokenSource, and the 401 body as the error. gh refuses
    # `gh auth login` while the variable is set, so the fix names it.
    answer = Path(os.environ["STATUS_GH_ANSWER"])
    refusal = '{\r\n  "message": "Bad credentials",\r\n  "status": "401"\r\n}'
    host = {
        "state": "error",
        "error": f'non-200 OK status code: 401 Unauthorized body: "{refusal}"',
        "active": True,
        "host": "github.com",
        "login": "",
        "tokenSource": variable,
        "gitProtocol": "https",
    }
    answer.write_text(json.dumps({"hosts": {"github.com": [host]}}), encoding="utf-8")
    status = asyncio.run(github_status())
    fix = (
        f"replace the token in {variable}, or unset it and run gh auth login --hostname github.com"
    )
    assert (status.state, status.account, status.token_source, status.fix) == (
        "not_logged_in",
        None,
        variable,
        fix,
    )
    assert status.message == f"GitHub refused the token in {variable}. To sign in again: {fix}."
    assert "gh auth login" not in status.message.replace(fix, "")


def test_no_gh_on_path_is_gh_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    status = asyncio.run(github_status())
    assert (status.state, status.gh_path, status.fix) == (
        "gh_missing",
        None,
        "https://cli.github.com/",
    )
    assert status.lines()[1] == "  gh: not found on PATH"


def test_the_token_is_never_read(logging_gh: Path) -> None:
    status = asyncio.run(github_status())
    assert status.state == "ok"
    shown = json.dumps(status.to_json()) + "\n".join(status.lines())
    assert "gho_never_read_by_metabrowser" not in shown


def test_an_answer_is_kept_and_one_check_in_flight_is_shared(logging_gh: Path) -> None:
    async def three_at_once() -> list[GithubStatus]:
        return list(await asyncio.gather(*(github_status() for _ in range(3))))

    statuses = asyncio.run(three_at_once())
    assert {status.state for status in statuses} == {"ok"}
    assert _calls(logging_gh).count("auth status --active --hostname github.com --json hosts") == 1
    # Kept: a second check, and the version, run no gh while the answer is fresh.
    again = asyncio.run(github_status())
    assert again == statuses[0]
    assert len([call for call in _calls(logging_gh) if call.startswith("auth")]) == 1
    assert len([call for call in _calls(logging_gh) if call == "--version"]) == 1


def test_the_checks_before_work_leave_the_version_out(logging_gh: Path) -> None:
    status = asyncio.run(github_status(version=False))
    assert status.gh_version is None
    assert _calls(logging_gh) == ["auth status --active --hostname github.com --json hosts"]


def test_a_kept_answer_is_dropped_when_gh_or_its_configuration_changes(
    logging_gh: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The key says only whether a token variable is set, so one the caller already set,
    # as a cloud container sets GH_TOKEN, would hide the token this test sets below.
    for variable in ENVIRONMENT_TOKENS:
        monkeypatch.delenv(variable, raising=False)
    asyncio.run(github_status(version=False))
    assert kept_github_status() is not None
    monkeypatch.setenv("GH_CONFIG_DIR", str(tmp_path / "other-config"))
    assert kept_github_status() is None
    asyncio.run(github_status(version=False))
    monkeypatch.setenv("GH_TOKEN", "set-by-the-test")
    assert kept_github_status() is None
    # Past its time, an answer is not kept either.
    monkeypatch.setattr(gh_status, "GH_STATUS_TTL_S", 0.0)
    assert kept_github_status() is None
    assert len(_calls(logging_gh)) == 2


def test_a_fresh_check_neither_joins_nor_keeps_one_that_started_before(
    logging_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Retry after signing in sends `fresh` while an earlier check may still be
    running: that check started before the sign-in, so its answer is not the Retry's,
    and it is not kept when it ends after the Retry's."""

    answer = Path(os.environ["STATUS_GH_ANSWER"])
    auth = "auth status --active --hostname github.com --json hosts"

    async def retry_during_a_check() -> tuple[GithubStatus, GithubStatus]:
        monkeypatch.setenv("STATUS_GH_DELAY", "1.5")
        earlier = asyncio.ensure_future(github_status(version=False))
        for _ in range(500):
            if auth in _calls(logging_gh):
                break
            await asyncio.sleep(0.01)
        # The earlier gh has read its answer, signed in; now the reader signs out, and
        # the Retry's gh answers at once.
        answer.write_text('{"hosts":{}}', encoding="utf-8")
        monkeypatch.delenv("STATUS_GH_DELAY")
        gh_status.forget_github_status()
        retried = await github_status(version=False)
        return await earlier, retried

    earlier, retried = asyncio.run(retry_during_a_check())
    assert (earlier.state, retried.state) == ("ok", "not_logged_in")
    assert _calls(logging_gh).count(auth) == 2
    kept = kept_github_status()
    assert kept is not None and kept.state == "not_logged_in"


def test_a_gh_that_does_not_answer_in_time_is_a_network_error(
    logging_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STATUS_GH_DELAY", "10")
    monkeypatch.setattr(gh_status, "GH_STATUS_TIMEOUT_S", 0.5)
    status = asyncio.run(github_status(version=False))
    assert status.state == "network_error"
    assert status.message == "gh did not answer within 0.5 s."


@pytest.mark.usefixtures("fixture_gh")
def test_the_route_serves_the_doctors_section_and_refuses_another_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "ERROR")
    root = tmp_path / "root"
    root.mkdir()
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    route = ["--api", "/api/plugin/github/status", "--data"]

    monkeypatch.setenv("FAKE_GH_STATUS", "signed-out")
    served = run_metab([str(root), *route, str(empty)])
    assert served.exit_code == 0, served.stderr
    assert served.payload() == _status("signed-out", monkeypatch).to_json()
    doctor = run_metab(["--doctor", "--json"])
    assert json.loads(doctor.stdout)["github"] == served.payload()

    other = tmp_path / "other.json"
    other.write_text('{"fresh": "yes"}', encoding="utf-8")
    refused = run_metab([str(root), *route, str(other)])
    assert refused.payload() == {
        "error": "a status request names only fresh, true or false",
        "code": "invalid_request",
    }


@pytest.mark.usefixtures("fixture_gh")
def test_a_server_keeps_an_answer_until_a_fresh_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each `metab` command is a process of its own; a server is one process for many
    requests, so after signing in, a kept answer says signed out for a few seconds
    more, and `fresh` asks gh again, as the app's Retry does."""

    app = Starlette(routes=[Route("/status", status_handler, methods=["POST"])])
    client = TestClient(app)
    monkeypatch.setenv("FAKE_GH_STATUS", "signed-out")
    assert client.post("/status", json={}).json()["state"] == "not_logged_in"
    monkeypatch.setenv("FAKE_GH_STATUS", "signed-in")
    assert client.post("/status", json={}).json()["state"] == "not_logged_in"
    assert client.post("/status", json={"fresh": True}).json()["state"] == "ok"
    assert client.post("/status", json={}).json()["state"] == "ok"


@pytest.mark.usefixtures("fixture_gh")
def test_the_doctors_github_section_never_changes_its_exit_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_GH_STATUS", "signed-out")
    monkeypatch.setenv("METABROWSER_OPEN_IN", "browser")
    doctor = run_metab(["--doctor"])
    assert doctor.exit_code == 0, doctor.stderr
    assert doctor.stderr == ""
    lines = doctor.stdout.splitlines()
    assert re.fullmatch(r"metab --doctor: [1-9][0-9]* plugin\(s\) OK", lines[1])
    # The plugin requirements follow the verdict, then the GitHub section.
    start = lines.index(next(line for line in lines if line.startswith("github: ")))
    assert lines[start] == (
        "github: not_logged_in: GitHub CLI is not signed in to github.com. "
        "Run gh auth login --hostname github.com, then retry."
    )
    # The GitHub section ends at the first setup check (`cli/doctor.py`), which follows it.
    section = lines[start : lines.index(next(line for line in lines if line.startswith("metab: ")))]
    assert section[-1] == "  fix: gh auth login --hostname github.com"
