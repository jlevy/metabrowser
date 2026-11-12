"""The Pulls panel session runs production browser code on what a server answers.

``tests/dom/github-pulls-panel-session.js`` drives the GitHub plugin's
``builtin_plugins/github/pulls-panel.js`` -- what the panel shows, its filters, its windows
of rows, Load more, each way a refresh can end, polling only while shown, and walking the
rows with a held key -- through a scripted conversation, and
``tests/golden/cli-ui-github-pulls-panel.tryscript.md`` pins its transcript. So that the
conversation is the real server's and not envelopes a test wrote by hand, its responses come
from the lifecycle, cached-window, and changed-prefix recordings in
``tests/fixtures/github-pulls-*-responses.json``: what the in-process application
answered while it served ``tests/github_pull_fixture.py``'s stand-in, with a fake ``gh``
replaying full-size pages built on a scrubbed real item. The first test here replays that
story and fails when the recording no longer matches.

The clock is fixed, so fetch times are literal. Entity tags are the session's own, since the
server's are scoped to the build; which answers share one is kept. Every list answer carries
its window of rows, and the story reads one list many times, so the recording holds each
distinct window once: an answer whose rows an earlier answer carried names that answer,
``{"same_as": "current"}``, and the session reads it back as those rows. A row is one line of
JSON in a string, so a full page is a hundred lines to review. ``make golden-update`` rewrites
the recording and then the transcript.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.github import gh, pull_list, pull_list_refresh, pulls
from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
from metabrowser.builtin_plugins.github.pull_list import ListedRepository, write_list_refresh
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
from metabrowser.builtin_plugins.github.served_pull import ServedPulls
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.git import repo as git_repo
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.server import app
from metabrowser.source import reset_source_session, serve_subject_opener
from metabrowser.source_routes import PIN_HEADER
from tests.github_pull_fixture import (
    ANOTHER_READER,
    CANONICAL,
    DEFAULT_BRANCH,
    FETCHED_AT,
    Origin,
    generated_item,
    install_fake_gh,
    logged_gh_calls,
    scenario,
    seed_catalog,
)
from tests.golden_harness import JSON_BODY, check_recording, read_recording, run_session
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git

RECORDING = "github-pulls-panel-responses.json"
WINDOW_RECORDING = "github-pulls-catalog-window-responses.json"
PREFIX_RECORDING = "github-pulls-catalog-prefix-responses.json"
TRANSCRIPT = "cli-ui-github-pulls-panel.tryscript.md"
_PULLS = "/api/plugin/github/pulls"
_REFRESH = "/api/plugin/github/pulls-refresh"
pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]


def _answer(response: Any) -> dict[str, Any]:
    """One response as the panel sees it: status, entity tag, and body."""

    body = None if response.status_code == 304 else response.json()
    return {"status": response.status_code, "etag": response.headers.get("etag"), "body": body}


def _session_tags(recorded: dict[str, Any]) -> dict[str, Any]:
    """Alias opaque build tags and catalog generations, preserving every equality relation."""

    own: dict[str, str] = {}
    generations: dict[str, str] = {}
    for answer in recorded.values():
        body = answer["body"]
        envelopes = [body]
        if isinstance(body, dict) and isinstance(body.get("pulls"), dict):
            envelopes.append(body["pulls"])
        for envelope in envelopes:
            if isinstance(envelope, dict) and isinstance(envelope.get("generation"), str):
                envelope["generation"] = generations.setdefault(
                    envelope["generation"], f"catalog-{len(generations) + 1}"
                )
        if answer["etag"] is not None:
            answer["etag"] = own.setdefault(answer["etag"], f'"pulls-{len(own) + 1}"')
    return recorded


def _stored_once(recorded: dict[str, Any]) -> dict[str, Any]:
    """*recorded* with each distinct window of rows written once; see the module docstring."""

    holder: dict[str, str] = {}
    for name, answer in recorded.items():
        body = answer["body"]
        if not isinstance(body, dict) or not isinstance(body.get("rows"), list) or not body["rows"]:
            continue
        key = json.dumps(body["rows"])
        if key in holder:
            body["rows"] = {"same_as": holder[key]}
        else:
            holder[key] = name
            body["rows"] = [json.dumps(row, ensure_ascii=False) for row in body["rows"]]
    return recorded


def _large_items(numbers: range) -> list[dict[str, Any]]:
    return [
        {**generated_item(number), "state": "closed", "closed_at": "2026-09-17T12:00:00Z"}
        for number in numbers
    ]


def _record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
    _allow_installed_git(monkeypatch)
    monkeypatch.setattr(
        "metabrowser.cache.acquire.remote_url_for",
        lambda source: origin.url if source.normalized == CANONICAL else source.normalized,  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
    )
    clock = [FETCHED_AT]
    monkeypatch.setattr(pull_list, "utc_now", lambda: clock[0])
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    online = scenario(origin)

    def answering(answers: dict[str, Any]) -> None:
        for name, value in install_fake_gh(tmp_path, answers).items():
            monkeypatch.setenv(name, value)

    answering(online)
    source = GitSource(
        transport="https",
        form="url",
        normalized=CANONICAL,
        selection=RepositorySelection(kind="repository"),
    )
    published = asyncio.run(acquire_source(source, home=home))
    provider_calls = {"source acquisition": logged_gh_calls(tmp_path)}

    async def _pin() -> Any:
        subject = await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=origin["topic"],
            store_identity=published.store_id,
            ref=f"refs/remotes/origin/{DEFAULT_BRANCH}",
        )
        return subject

    # The serving lifespan owns the pin and any subjects a pin switch replaces it with.
    serve_subject_opener(_pin)
    serve_mirror(
        StoreMirror.from_published(replace(published, source=source)),
        pull_requests=ServedPulls(published),
    )
    git_repo.clear_repo_cache()
    recorded: dict[str, Any] = {}
    gate = threading.Event()
    gate.set()
    original: Callable[..., Awaitable[Any]] = pull_list_refresh.refresh_pull_list

    async def held(*args: Any, **kwargs: Any) -> Any:
        # The test thread sets it; a worker thread waits, so the job runs until then.
        await asyncio.to_thread(gate.wait, 30)
        return await original(*args, **kwargs)

    monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", held)
    try:
        with TestClient(app) as client:

            def read(**params: str) -> dict[str, Any]:
                return _answer(
                    client.get(_PULLS, params={"state": "all", "limit": "100", **params})
                )

            def ask(**body: Any) -> dict[str, Any]:
                return _answer(client.post(_REFRESH, json=body, headers=JSON_BODY))

            def settled() -> None:
                deadline = time.monotonic() + 50
                while client.get(_PULLS, params={"limit": "0"}).json()["refreshing"]:
                    assert time.monotonic() < deadline, "the catalog job did not finish"
                    time.sleep(0.01)

            repository = ListedRepository(home, published.slug, "octo", "demo")
            recorded["absent"] = read()
            recorded["landing_absent"] = read(limit="0")
            provider_calls["cold cache reads"] = logged_gh_calls(tmp_path)
            gate.clear()
            recorded["refresh_started"] = ask(state="all", target=500)
            recorded["pending"] = read()
            recorded["landing_pending"] = read(limit="0")
            gate.set()
            settled()
            recorded["current"] = read()
            provider_calls["catalog backfill"] = logged_gh_calls(tmp_path)
            recorded["more_done"] = read()
            recorded["more_window"] = read(after=str(recorded["current"]["body"]["next_after"]))
            recorded["open_current"] = read(state="open")
            recorded["closed_current"] = read(state="closed")
            tag = {"if-none-match": recorded["current"]["etag"]}
            assert (
                client.get(_PULLS, params={"state": "all", "limit": "100"}, headers=tag).status_code
                == 304
            )
            recorded["not_due"] = ask(state="all", target=500)
            assert ask(state="all", target=1000)["body"]["refresh"] == "not_due"
            assert read() == recorded["current"]
            provider_calls["cached windows, filters, Fetch more and reopen"] = logged_gh_calls(
                tmp_path
            )
            recorded["pin_changed"] = _answer(
                client.get(_PULLS, params={"state": "all"}, headers={PIN_HEADER: "0" * 40})
            )
            clock[0] = FETCHED_AT + timedelta(seconds=61)
            recorded["stale"] = read()
            gate.clear()
            recorded["refresh_again"] = ask(state="all", target=500)
            recorded["stale_refreshing"] = read()
            gate.set()
            settled()
            recorded["refreshed"] = read()
            provider_calls["due metadata refresh"] = logged_gh_calls(tmp_path)
            assert read() == recorded["refreshed"]
            provider_calls["fresh cached revisit"] = logged_gh_calls(tmp_path)

            # Actual persisted failure stamps, read through the production cache-only route.
            # Worker/network classification is covered by the catalog backend's own cases.
            for name in (
                "not_logged_in",
                "gh_too_old",
                "not_found_or_private",
                "network_error",
                "gh_failed",
                "account_changed",
                "gh_missing",
                "cache_unwritable",
                "rate_limited",
            ):
                message = "the saved catalog refresh failed"
                if name in {"gh_missing", "gh_too_old", "not_logged_in"}:
                    with monkeypatch.context() as setup:
                        if name == "gh_missing":
                            setup.setattr(gh, "gh_executable", lambda: None)
                        else:
                            auth = (
                                {"stdout": '{"hosts":{}}\n', "exit": 0}
                                if name == "not_logged_in"
                                else {"stderr": "unknown flag: --json\n", "exit": 1}
                            )
                            answering({**online, "auth": auth})
                        with pytest.raises(gh.GhError) as failure:
                            asyncio.run(gh.gh_account())
                        assert failure.value.state == name
                        message = str(failure.value)
                    answering(online)
                stamp = PullRefreshStamp(
                    outcome=name,
                    message=message,
                    at=utc_stamp(clock[0]),
                    reader="gh:octo-reader",
                    reset_at="2026-09-18T00:00:00Z" if name == "rate_limited" else None,
                )
                write_list_refresh(home, published.slug, "all", stamp)
                recorded[f"failed {name}"] = read()
            recorded["rate_limit_holds"] = ask(state="all", target=500, retry=True)

            # The following account story is independent of the saved network hold.
            clock[0] = FETCHED_AT + timedelta(days=2)
            items = [
                *online["api"][
                    "repos/octo/demo/pulls?state=all&sort=created&direction=desc&per_page=100&page=1"
                ]["body"],
                *online["api"][
                    "repos/octo/demo/pulls?state=all&sort=created&direction=desc&per_page=100&page=2"
                ]["body"],
            ]
            seed_catalog(repository, items, reader=ANOTHER_READER, fetched_at=utc_stamp(clock[0]))
            write_list_refresh(
                home,
                published.slug,
                "all",
                PullRefreshStamp(
                    outcome="network_error", at=utc_stamp(clock[0]), reader="gh:octo-reader"
                ),
            )
            recorded["another_reader"] = read(state="open")

            clock[0] = FETCHED_AT + timedelta(days=14)
            seed_catalog(
                repository,
                _large_items(range(6000, 5000, -1)),
                repository_id="R_large",
                fetched_at=utc_stamp(clock[0]),
                complete=False,
            )
            write_list_refresh(
                home,
                published.slug,
                "all",
                PullRefreshStamp(outcome="succeeded", at=utc_stamp(clock[0])),
            )
            for index in range(10):
                recorded[f"large_{index}"] = read(
                    state="closed", **({"after": str(6001 - index * 100)} if index else {})
                )
            # Opening a fresh partial catalog resumes durable work even after500 matching
            # rows are cached. Hold the real worker while committed cache pages progress.
            gate.clear()
            recorded["large_resume_started"] = ask(state="closed", target=500)
            # Growing only the older suffix changes progress/counts, not prefix generation.
            seed_catalog(
                repository,
                _large_items(range(6000, 0, -1)),
                repository_id="R_large",
                fetched_at=utc_stamp(clock[0]),
                complete=True,
            )
            recorded["large_progress"] = read(state="closed")
            for index in range(5, 10):
                recorded[f"large_progress_{index}"] = read(
                    state="closed", after=str(6001 - index * 100)
                )
            seed_catalog(
                repository,
                _large_items(range(6001, 0, -1)),
                repository_id="R_large",
                fetched_at=utc_stamp(clock[0] + timedelta(minutes=1)),
            )
            for index in range(10):
                recorded[f"moved_{index}"] = read(
                    state="closed", **({"after": str(6002 - index * 100)} if index else {})
                )

            gate.set()
            settled()
            seed_catalog(repository, [], repository_id="R_empty", fetched_at=utc_stamp(clock[0]))
            write_list_refresh(
                home,
                published.slug,
                "all",
                PullRefreshStamp(outcome="gh_missing", at=utc_stamp(clock[0])),
            )
            recorded["open_gh_missing"] = read(state="open", limit="0")
            recorded["landing_gh_missing"] = read(limit="0")
            write_list_refresh(
                home,
                published.slug,
                "all",
                PullRefreshStamp(outcome="succeeded", at=utc_stamp(clock[0])),
            )
            gate.clear()
            recorded["empty_refresh_started"] = ask(state="all", target=500, retry=True)
            recorded["landing_empty_refreshing"] = read(limit="0")
            gate.set()
            settled()
            recorded["landing_found_rows"] = read(limit="0")
    finally:
        gate.set()
        serve_mirror(None)
        git_repo.clear_repo_cache()
    reset_source_session()
    plain = tmp_path / "no-repository"
    plain.mkdir()
    server._set_root_dir(plain)
    with TestClient(app) as client:
        recorded["not_github"] = _answer(client.get(_PULLS, params={"limit": "100"}))
        recorded["not_github_refresh"] = _answer(
            client.post(_REFRESH, json={"state": "all", "target": 500}, headers=JSON_BODY)
        )
    return _session_tags(recorded), provider_calls


def test_recording_is_what_a_served_mirror_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    recorded, provider_calls = _record(tmp_path, monkeypatch, pull_origin)
    assert recorded["absent"]["body"]["reason"] == "not_cached"
    assert recorded["absent"]["body"]["filter_totals"] is None
    assert recorded["refresh_started"]["status"] == 202
    assert recorded["pending"]["body"]["state"] == "pending"
    assert recorded["pending"]["body"]["filter_totals"] is None
    current = recorded["current"]["body"]
    assert (
        current["repository_total"],
        current["total"],
        current["fetched"],
        current["complete"],
    ) == (102, 102, 102, True)
    assert len(current["rows"]) == 100
    assert len(recorded["more_window"]["body"]["rows"]) == 2
    assert recorded["open_current"]["body"]["total"] == 100
    assert recorded["closed_current"]["body"]["total"] == 2
    for label in ("current", "open_current", "closed_current", "more_window"):
        assert recorded[label]["body"]["filter_totals"] == {"all": 102, "open": 100, "closed": 2}
    assert recorded["stale"]["body"]["state"] == "stale"
    assert recorded["not_due"]["body"]["refresh"] == "not_due"
    assert recorded["rate_limit_holds"]["body"]["refresh"] == "not_due"
    for name in (
        "not_logged_in",
        "gh_too_old",
        "not_found_or_private",
        "network_error",
        "gh_failed",
        "account_changed",
        "gh_missing",
        "rate_limited",
        "cache_unwritable",
    ):
        envelope = recorded[f"failed {name}"]["body"]
        assert envelope["last_refresh"]["outcome"] == name and envelope["fetched"] == 102
    assert recorded["another_reader"]["body"]["reader"] == f"gh:{ANOTHER_READER}"
    assert recorded["another_reader"]["body"]["state"] == "stale"
    assert (
        recorded["large_0"]["body"]["generation"]
        == recorded["large_progress"]["body"]["generation"]
    )
    assert recorded["large_resume_started"]["status"] == 202
    assert recorded["large_progress"]["body"]["fetched"] == 6000
    assert (
        recorded["large_progress"]["body"]["generation"]
        != recorded["moved_0"]["body"]["generation"]
    )
    assert recorded["moved_0"]["body"]["rows"][0]["number"] == 6001
    assert recorded["not_github"]["body"]["reason"] == "not_github"
    assert recorded["not_github_refresh"]["status"] == 409
    assert recorded["pin_changed"]["body"]["code"] == "pin_changed"
    assert recorded["landing_gh_missing"]["body"]["last_refresh"]["outcome"] == "gh_missing"
    assert recorded["landing_empty_refreshing"]["body"]["fetched"] == 0
    assert recorded["landing_empty_refreshing"]["body"]["filter_totals"] == {
        "all": 0,
        "open": 0,
        "closed": 0,
    }
    assert recorded["landing_empty_refreshing"]["body"]["refreshing"] is True
    assert recorded["landing_found_rows"]["body"]["fetched"] == 102
    # Keep complete route answers, split by scenario so each recording is reviewable.
    stored = _stored_once(recorded)
    windows = {name: answer for name, answer in stored.items() if name.startswith("large_")}
    prefix = {name: answer for name, answer in stored.items() if name.startswith("moved_")}
    lifecycle = {
        name: answer
        for name, answer in stored.items()
        if name not in windows and name not in prefix
    }
    assert len(lifecycle) + len(windows) + len(prefix) == len(stored)
    # Fixture metadata: provider work observed during the real server session, not API fields.
    lifecycle["provider_calls"] = provider_calls
    check_recording(RECORDING, lifecycle, transcript=TRANSCRIPT, indent=1)
    check_recording(WINDOW_RECORDING, windows, transcript=TRANSCRIPT, indent=1)
    check_recording(PREFIX_RECORDING, prefix, transcript=TRANSCRIPT, indent=1)


def test_a_held_key_asks_for_no_row_it_passes() -> None:
    """The cost the golden shows as lists of requests, held as one relation.

    However far a key walks, the walk's requests are the one stop's, and the only rows it
    touches are the two at each step: a held key costs nothing per row but those two marks.
    """

    steps = {step["step"]: step for step in run_session("github-pulls-panel-session.js")["steps"]}
    walking = steps["a key held for 40 rows"]
    assert walking["requests"] == [], "a row walked past read something"
    assert "opened" not in walking, "a row walked past opened"
    assert walking["painted"] == 0, "a step repainted the list"
    assert walking["marks"] == 80, "a step touched more than the two rows that changed"
    # The one read of the row it stopped on, and then the one opening.
    assert len(steps["the key is let go"]["requests"]) == 1
    assert len(steps["the row it stopped on opens"]["opened"]) == 1


def test_the_recording_holds_every_failure_the_plan_names() -> None:
    """Each typed state of the plan's table has a recorded answer the session plays."""

    recording = read_recording(RECORDING)
    for name in (
        "gh_missing",
        "gh_too_old",
        "not_logged_in",
        "rate_limited",
        "network_error",
        "not_found_or_private",
        "account_changed",
        "gh_failed",
        "cache_unwritable",
    ):
        assert f"failed {name}" in recording, name


def test_pulls_landing_leaves_connection_status_to_the_sidebar() -> None:
    paint = run_session("github-pulls-panel-session.js", "--part", "all")["paint"]
    assert paint["landing"] == "Select a pull request."
    assert paint["ready action"] == "Reload"


def test_catalog_windows_and_late_request_ownership() -> None:
    assert run_session("github-pulls-catalog-behavior.js") == {
        "defaultFilter": "open",
        "initialRows": 500,
        "explicitRows": 1000,
        "scrollRows": 600,
        "terminalRows": 645,
        "repeatedScrollSharesRequest": True,
        "keepsSelection": True,
        "cachedGrowthKeepsEveryRow": True,
        "failedProviderUsesCacheOnly": True,
        "hiddenTailIsIdle": True,
        "staleTailCannotChangeFilter": True,
        "progressOnlyReads": 1,
        "generationPages": 10,
        "detailReads": 0,
        "priorityTarget": 1000,
        "lateWindowRejected": True,
        "ownerTransferred": True,
        "mixedGenerationRejected": True,
        "lateFilterRejected": True,
        "failedWindowDoesNotSpin": True,
        "newerRefreshKeepsOwnership": True,
        "freshPartialCatalogResumes": True,
        "offlineKeepsCache": True,
        "reconnectUsesBackgroundHint": True,
        "interactiveFilterKeepsPriority": True,
        "directAndHistoryFiltersKeepPriority": True,
        "hiddenWarmupYieldsToVisibleDemand": True,
        "acceptedTopArrivalsAreOneShot": True,
        "transientRetriesAutomatically": True,
        "retryKeepsPriorFailure": True,
        "localReadFailureDoesNotPost": True,
        "setupUsesQuietProbe": True,
        "focusCoalesces": True,
        "parkAndResume": True,
        "rateResetWake": True,
        "reloadCoalesces": True,
        "abortedTailKeepsWake": True,
    }


def test_variable_height_catalog_window_keeps_protected_anchors() -> None:
    assert run_session("github-pulls-window-behavior.js") == {
        "catalogRows": 5000,
        "mountedRowsBound": 101,
        "expandedHeight": 1200,
        "protectedAnchors": True,
        "prefixAnchorPreserved": True,
    }


def test_viewport_resize_and_distant_focus_keep_the_mounted_window_complete() -> None:
    result = run_session("github-pulls-viewport-behavior.js")
    assert result == {
        "case": "viewport-height-increase",
        "before": 43,
        "after": 113,
        "observedRoot": 1,
        "gapStartsAt": None,
        "viewportHeight": 3000,
        "oneVisibleFlash": True,
        "retainedReadingPlace": True,
        # The titles of an admitted core batch breathe, with no row busy, until a settled
        # receipt, a new window, or going offline ends it; `beat` is alignRefreshing's one
        # start time ("Refreshing Content" in docs/design-system.md; review A on #354).
        "titleBreathing": {
            "admitted": {"asked": [407, 406, 405], "breathing": [407, 406, 405], "busyRows": 0},
            "settled": [],
            "moved": {"asked": [311, 310, 309, 308], "breathing": [311, 310, 309, 308]},
            "offline": [],
            "beat": [100, 100, 50, 100],
        },
    }


def test_setup_guidance_retains_cached_content_and_failure_distinctions() -> None:
    assert run_session("github-setup-guidance-behavior.js") == {
        "setupStates": 3,
        "views": 3,
        "nullMessageFallbacks": True,
        "backendTextPreserved": True,
        "cachedRecordPreserved": True,
        "authUsesNormalizedGuidance": True,
        "otherFailureKindsPreserved": True,
    }


def test_optional_native_stack_state_is_shared_and_owned() -> None:
    assert run_session("github-pull-stacks-behavior.js") == {
        "rowCaptions": {
            "single": {"text": "2/3", "hint": "Stack #286, position 2 of 3"},
            "shared": {
                "text": "3/3 · 1/2",
                "hint": "Stack #286, position 3 of 3; Stack #900, position 1 of 2",
            },
            "foreign": None,
        },
        "authoritativeMembership": True,
        "multipleStacks": True,
        "identityGuard": True,
        "tabAndReaderIntent": True,
        "sharedRead": True,
        "failureRetention": True,
        "retryWindow": True,
        "disposal": True,
        "lateOwnerGuard": True,
        "initialFailureRetry": True,
    }


def test_native_stack_navigation_and_cold_page_skeleton_preserve_cached_content() -> None:
    assert run_session("github-pull-stack-mount-behavior.js") == {
        "coldSkeleton": True,
        "pendingSkeleton": True,
        "cachedRefreshRetained": True,
        "authoritativeStack": True,
        "orderedNeighbors": True,
        "stackActivationFocus": True,
        "tabPreserved": True,
        "fileCleared": True,
        "explicitReaderIntent": True,
        "disposedWorkReleased": True,
    }


def test_recording_optional_stack_metadata_answers_real_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The UI's optional snapshot comes from the actual cache-only route and worker."""
    from metabrowser import paths_safe
    from tests.cache_home_fixture import FixtureSource, _stage_and_publish_source, build_empty_home
    from tests.github_pull_fixture import account, ok

    paths_safe._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    home = tmp_path / "home"
    build_empty_home(home)
    source = FixtureSource("https", CANONICAL)
    _stage_and_publish_source(home, source, opened=False)
    repository = ListedRepository(home, source.slug, "octo", "demo")
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_stacks_route.served_repository",
        lambda _app: repository,
    )
    clock = [FETCHED_AT]
    monkeypatch.setattr(pull_list, "utc_now", lambda: clock[0])
    answers: dict[str, Any] = {"auth": account(), "api": {}}
    endpoint = "repos/octo/demo/stacks?per_page=100&page=1"

    def install() -> None:
        for name, value in install_fake_gh(tmp_path, answers).items():
            monkeypatch.setenv(name, value)

    install()
    recorded: dict[str, Any] = {}
    with TestClient(app) as client:

        def read(name: str) -> dict[str, Any]:
            logged_gh_calls(tmp_path)  # Drain the completed explicit worker's calls.
            response = client.get("/api/plugin/github/stacks")
            assert logged_gh_calls(tmp_path) == [], "stack GET must stay cache-only"
            recorded[name] = _answer(response)
            return recorded[name]["body"]

        def refresh() -> None:
            response = client.post(
                "/api/plugin/github/stacks-refresh", json={"retry": True}, headers=JSON_BODY
            )
            assert response.status_code == 202
            deadline = time.monotonic() + 20
            while client.get("/api/plugin/github/stacks").json()["refreshing"]:
                assert time.monotonic() < deadline, "optional stack job did not finish"
                time.sleep(0.01)

        assert read("absent")["reason"] == "not_cached"
        refresh()
        assert read("missing")["reason"] == "gh_stack_missing"
        clock[0] += timedelta(seconds=301)
        answers["stack_version"] = "0.1.0"
        answers["api"][endpoint] = ok(
            endpoint,
            [
                {
                    "number": 286,
                    "url": "https://api.github.com/repos/octo/demo/stacks/286",
                    "base": {"ref": "main"},
                    "open": True,
                    "pull_requests": [{"number": n} for n in (6, 7, 8)],
                }
            ],
        )
        # Native membership has no titles; the cache-only projection reads the
        # already-discovered repository catalog without additional provider calls.
        seed_catalog(
            repository,
            [generated_item(n) | {"title": f"Stack change {n}"} for n in (6, 7, 8)],
            fetched_at=utc_stamp(clock[0]),
        )
        install()
        refresh()
        present = read("current")
        assert present["stacks"][0]["pulls"] == [6, 7, 8]
        response = client.get(
            "/api/plugin/github/stacks",
            headers={
                "if-none-match": recorded["current"]["etag"],
            },
        )
        recorded["unchanged"] = _answer(response)
        assert response.status_code == 304
        clock[0] += timedelta(seconds=301)
        answers.pop("stack_version")
        install()
        refresh()
        failed = read("failed_retained")
        assert failed["state"] == "stale" and failed["stacks"] == present["stacks"]
        clock[0] += timedelta(seconds=301)
        answers["stack_version"] = "0.1.0"
        answers["api"][endpoint] = ok(endpoint, [])
        install()
        refresh()
        empty = read("empty")
        assert empty["complete"] and empty["stacks"] == [] and empty["state"] == "current"
    check_recording(
        "github-stacks-responses.json",
        _session_tags(recorded),
        transcript="cli-ui-github-pulls-panel.tryscript.md",
    )


def test_real_page_history_owns_file_selection_separately_from_retained_cursor() -> None:
    result = run_session("github-pulls-file-selection-session.js")["selection"]
    assert result == {
        "observations": {
            "initial": ["/pull/105/files/src/app.txt"],
            "repeat": ["/pull/105/files/src/app.txt"],
            "leaving": [],
            "ignoredOld": [],
            "arriving": ["/pull/106/files/src/app.txt"],
            "sameHandle": ["/pull/106/files/src/app.txt"],
            "explicit": ["/pull/106/files/docs/new.md"],
            "unavailable": ["/pull/106/files/docs/new.md"],
            "reported": ["/pull/106/files/docs/new.md"],
            "history": ["/pull/105/files/src/app.txt"],
            "lateAfterHistory": [],
        },
        "back": "mount",
        "readerExpansionRetained": True,
        "rovingAnchorRetained": True,
        "disposed": 0,
    }


def test_a_selection_reads_its_record_once() -> None:
    """A click reads the record once: the page joins the peek's read or takes its answer.

    The mousedown's peek starts the read before the click, and the open waits only so long
    for it. A read still on its way is the page's first read; one that answered within a fast
    poll counts as it; the pointer resting on the clicked row reads nothing more. Only a
    record read ahead long before the click is asked again, with its tag. Before the page
    joined, the same stories read two and three times.
    """

    assert run_session("github-pull-selection-read-behavior.js") == {
        "slowRead": ["panel"],
        "fastRead": ["panel"],
        "oldReadAhead": ["panel", "page revalidates"],
        # The second read is the other row's own peek; the page's read is the first.
        "hoverAway": ["panel", "panel"],
    }


def test_background_core_warming_covers_viewport_and_catalog_without_stranding_reconnect() -> None:
    """Transport batches never cap coverage, and recovery keeps the settled cursor."""

    assert run_session("github-pr-prefetch-behavior.js") == {
        "catalogRows": 24,
        "settledOwnershipReleases": 3,
        "prefixOwnership": {"retained": 3, "revoked": 4},
        "latePassReceipts": ["ready", "partial", "failed", "busy", "not_owner", "invalid"],
        "hiddenBatches": [8, 8, 8],
        "busyAttemptsMs": [0, 1000, 3000, 7000],
        "allVisibleReadyMs": 12000,
        "recoveredAfterLongBusyMs": 91000,
        "cachedAfterColdStart": 24,
        "recoveredRaceAndRevision": [24, 25],
        "recoveredTransientAndPartial": [24, 24],
        "cachedPastPartialCohort": 24,
        "cachedAfterReconnect": 24,
        "completedBeforeDisconnect": 8,
        "backgroundRequestsAfterCompletion": 17,
    }


def test_background_freshness_asks_only_while_visible_and_says_how_old_each_part_is() -> None:
    """The prefetch policy and the page's catalog ask; the transcript shows the rest."""

    facts = run_session("github-pulls-prefetch-behavior.js")
    assert facts["afterScan"] == {
        "records": [119, 117, 120, 116],
        "files": [118, 119, 117],
        "changed": True,
    }
    assert facts["sameScanAsksOnce"] and facts["nextScanAsksAgain"]
    assert facts["afterLanding"]["files"] == [110, 111, 109]
    assert 110 not in facts["afterLanding"]["records"]
    assert facts["quiet"] == {"refreshing": 1, "failed": 0, "hidden": 0, "offline": 0}
    assert facts["lapsedRead"] == [
        "POST /api/plugin/github/pulls-refresh",
        "GET /api/plugin/github/pull?number=7",
    ]
    assert facts["withinWindow"] == ["GET /api/plugin/github/pull?number=7"]
    assert facts["checked"].startswith("Checked ") and " · fetched 3 h ago" in facts["checked"]
    assert facts["pendingChecks"][-1] == "POST /api/plugin/github/pull-refresh"
    assert facts["pendingFreshness"].startswith("Fetched ")
    assert facts["headMoved"] == "New commits were pushed; updating."
    assert facts["headStill"] is None
    assert facts["breathingWhileRead"] == [111] and facts["breathingAfter"] == []
    assert facts["breathingOffline"] == []
