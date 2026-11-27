"""A served mirror of the GitHub stand-in, browsed in process, with its ``gh`` calls read back.

``browsing`` serves ``tests/github_pull_fixture.py``'s origin as a served mirror, as the Pulls
sessions do (``tests/test_github_pulls_readiness_session.py``), with its fake ``gh`` and an
event log of its own, and yields a :class:`Browsing`: the in-process application's client,
the session's clock, the coordinator's drain, every ``gh`` call the log holds, each named by
the key the stand-in answered it by, and the request report over the session
(``GET /api/plugin/github/gh-requests``). ``tests/test_github_gh_lanes.py`` reads each call's
lane.

**One clock.** The pull-request data's clock (``pulls.utc_now`` and ``pull_list.utc_now``)
stands still between a session's steps and moves only when the session says so
(:meth:`SessionClock.advance`), as the other sessions' clocks do. The event log's clock runs
with real time, so how long each gh call took and which ran at once are what they were, and
moves on with every advance as well, so calls a step's advance puts a minute apart are a
minute apart in the log too, as a duplicate's window counts them. It is
:data:`EVENT_LAG_S` behind real time, so no record is later than its segment's
modification time, which is what the report reads a segment by. The monotonic clock the
list's attending reads (``pull_list_route.monotonic``) moves with every advance as well.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections.abc import Generator, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Final

import pytest
from starlette.testclient import TestClient

from metabrowser import event_log, home
from metabrowser.builtin_plugins.github import gh, pull_list, pull_list_route, pulls
from metabrowser.builtin_plugins.github.served_pull import ServedPulls
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.git import repo as git_repo
from metabrowser.mirror_refresh import refresh_coordinator, serve_mirror
from metabrowser.server import app
from metabrowser.source import reset_source_session, serve_subject_opener
from tests.github_pull_fixture import (
    CANONICAL,
    DEFAULT_BRANCH,
    FETCHED_AT,
    Origin,
    install_fake_gh,
)
from tests.golden_harness import JSON_BODY
from tests.test_cache_acquire import _allow_installed_git

# How far the event log's clock is behind real time: more than any session advances its
# clock in all, so no record is stamped after its segment was last written.
EVENT_LAG_S: Final = 3600.0
# The longest a session waits for the jobs its asks started to end.
DRAIN_S: Final = 60.0
REPORT_ROUTE: Final = "/api/plugin/github/gh-requests"


@dataclass
class SessionClock:
    """The session's time: the data's, which steps move, and the event log's (module docstring)."""

    origin: datetime = FETCHED_AT
    shift_s: float = 0.0

    def now(self) -> datetime:
        return self.origin + timedelta(seconds=self.shift_s)

    def event_time(self) -> float:
        return time.time() - EVENT_LAG_S + self.shift_s

    def monotonic(self) -> float:
        return time.monotonic() + self.shift_s

    def advance(self, seconds: float) -> None:
        self.shift_s += seconds


def stamp(moment: float) -> str:
    """*moment*, seconds since the epoch, as the report's ``since`` and ``until`` take it."""

    return datetime.fromtimestamp(moment, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class GhCall:
    """One ``gh`` call the event log holds: its end record, the key the stand-in answered
    it by (``None`` for a command it answers by no key, as ``gh --version``), and the job
    or request it ran in."""

    record: dict[str, Any]
    key: str | None
    owner: str | None

    @property
    def lane(self) -> str | None:
        return self.record.get("attrs", {}).get("lane")


@dataclass
class Browsing:
    """The served stand-in as a session drives it (module docstring)."""

    client: TestClient
    clock: SessionClock
    log: event_log.EventLog
    directory: Path
    answered: Path
    started_at: float
    _seen: int = field(default=0)

    def answer(self, answers: Mapping[str, Any]) -> None:
        """Have the stand-in answer *answers* from now on, as GitHub does after a change."""

        install_fake_gh(self.directory, answers)

    def post(self, route: str, body: Mapping[str, Any]) -> Any:
        return self.client.post(route, json=dict(body), headers=JSON_BODY)

    def get(self, route: str, **params: str) -> Any:
        return self.client.get(route, params=params)

    def settle(self) -> None:
        """Wait until the coordinator holds no job: every job an ask started, and every job
        those started, has ended."""

        coordinator = refresh_coordinator(app)
        assert coordinator is not None and self.client.portal is not None
        self.client.portal.call(partial(coordinator.drain, timeout_s=DRAIN_S))
        assert not coordinator._jobs, "a job did not end within the drain"  # pyright: ignore[reportPrivateUsage]

    def _records(self) -> list[dict[str, Any]]:
        assert self.log.path is not None
        return [json.loads(line) for line in self.log.path.read_text("utf-8").splitlines()]

    def calls(self) -> list[GhCall]:
        """The ``gh`` calls that ended since the last time this was asked, in the order
        they ended."""

        keys: dict[str, str] = {}
        if self.answered.exists():
            for line in self.answered.read_text("utf-8").splitlines():
                read = json.loads(line)
                keys[gh.fingerprint(read["args"])] = read["key"]
        records = self._records()
        owners = {
            record["span"]: record["name"]
            for record in records
            if record.get("kind") in ("job", "request") and "span" in record
        }
        ended = [
            record
            for record in records
            if record.get("kind") == "subprocess"
            and record.get("event") == "end"
            and (record.get("name") == "gh" or str(record.get("name")).startswith("gh "))
        ]
        fresh, self._seen = ended[self._seen :], len(ended)
        return [
            GhCall(
                record,
                keys.get(record.get("attrs", {}).get("fingerprint", "")),
                owners.get(record.get("parent")),
            )
            for record in fresh
        ]

    def report(self, *, since: float | None = None, buckets: int = 1) -> dict[str, Any]:
        """The request report over the session so far, or from *since*, as the route answers."""

        until = self.clock.event_time() + 1
        response = self.get(
            REPORT_ROUTE,
            since=stamp(self.started_at if since is None else since),
            until=stamp(until),
            buckets=str(buckets),
        )
        assert response.status_code == 200, response.text
        return response.json()


@contextlib.contextmanager
def browsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    origin: Origin,
    answers: Mapping[str, Any],
    *,
    attend: int | None = None,
) -> Generator[Browsing]:
    """Serve the stand-in's mirror answering *answers*, attending pull request *attend*."""

    cache = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(cache))
    state = tmp_path / "state"
    monkeypatch.setenv("METABROWSER_STATE_DIR", str(state))
    _allow_installed_git(monkeypatch)
    monkeypatch.setattr(
        "metabrowser.cache.acquire.remote_url_for",
        lambda source: origin.url if source.normalized == CANONICAL else source.normalized,  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
    )
    clock = SessionClock()
    monkeypatch.setattr(pull_list, "utc_now", clock.now)
    monkeypatch.setattr(pulls, "utc_now", clock.now)
    monkeypatch.setattr(pull_list_route, "monotonic", clock.monotonic)
    for name, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(name, value)
    answered = tmp_path / "fake-gh-answered.jsonl"
    monkeypatch.setenv("FAKE_GH_ANSWERED", str(answered))
    source = GitSource(
        transport="https",
        form="url",
        normalized=CANONICAL,
        selection=RepositorySelection(kind="repository"),
    )
    published = asyncio.run(acquire_source(source, home=cache))
    answered.unlink(missing_ok=True)

    async def pin() -> Any:
        return await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=origin["topic"],
            store_identity=published.store_id,
            ref=f"refs/remotes/origin/{DEFAULT_BRANCH}",
        )

    serve_subject_opener(pin)
    serve_mirror(
        StoreMirror.from_published(replace(published, source=source)),
        pull_request=attend,
        pull_requests=ServedPulls(published),
    )
    git_repo.clear_repo_cache()
    home.ensure_storage_root(state)
    home.ensure_private_directory(state, event_log.EVENTS_DIRECTORY)
    log = event_log.EventLog(state / event_log.EVENTS_DIRECTORY, state, clock=clock.event_time)
    try:
        with event_log.installed(log), TestClient(app) as client:
            yield Browsing(client, clock, log, tmp_path, answered, clock.event_time())
    finally:
        log.close()
        serve_mirror(None)
        git_repo.clear_repo_cache()
        reset_source_session()


__all__ = ["DRAIN_S", "EVENT_LAG_S", "Browsing", "GhCall", "SessionClock", "browsing", "stamp"]
