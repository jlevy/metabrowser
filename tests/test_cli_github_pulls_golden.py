"""Golden CLI transcript: a repository's lists of pull requests fetched, extended, and refused.

Each command runs the production CLI in-process, as ``tests/test_cli_github_pull_golden.py``
does, with these substitutions and nothing else:

- ``metabrowser.cache.acquire.remote_url_for`` clones ``https://github.com/octo/demo`` from
  the local origin in ``tests/github_pull_fixture.py``;
- a fake ``gh`` first on ``PATH`` replays list pages built on a scrubbed real item, and logs
  every call, which the transcript lists after each command;
- the clock is fixed, and a block says where it moves, so ``fetched_at``, the window, and a
  list's state are the same every run.

Reading a list from a prebuilt home, with no ``gh`` at all, runs as a subprocess in
``tests/golden/cli-github-pulls.tryscript.md``. This transcript is what that one cannot
show: a refresh that completes, the requests it made, and a list that is ``current``.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import gh, pull_list, pulls
from metabrowser.builtin_plugins.github.pull_catalog import read_catalog
from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    ANOTHER_READER,
    CANONICAL,
    FETCHED_AT,
    Origin,
    account,
    catalog_entries,
    generated_item,
    graph_core_data,
    install_fake_gh,
    list_item,
    logged_gh_calls,
    ok,
    pull_bodies,
    scenario,
)
from tests.golden_harness import (
    Invocation,
    Labels,
    check_golden,
    isolate_cli,
    label_home,
    origin_identity,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

PULLS = "/api/plugin/github/pulls"
REFRESH = "/api/plugin/github/pulls-refresh"
PREPARE = "/api/plugin/github/pull-cores-prepare"


class _Session:
    """The stand-in origin, the fake gh, the clock, and a transcript of each command."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.home = isolate_cli(tmp_path, monkeypatch).home
        self.origin = origin
        self.now = FETCHED_AT
        local = origin.url

        def remote_url_for(source: GitSource) -> str:
            return local if source.normalized == CANONICAL else source.normalized

        monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote_url_for)
        monkeypatch.setattr(pull_list, "utc_now", lambda: self.now)
        self.blocks: list[str] = []
        self.labels = Labels()
        self.epochs: set[str] = set()
        self.answer(scenario(origin))

    def answer(self, answers: dict[str, Any]) -> None:
        for name, value in install_fake_gh(self.tmp_path, answers).items():
            self.monkeypatch.setenv(name, value)

    def say(self, text: str) -> None:
        self.blocks.append(f"## {text}\n")

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)
        self.say(f"The clock moves on {seconds:g} s, to {self.now:%Y-%m-%dT%H:%M:%SZ}.")

    def _run(self, *args: str, **sections: list[str]) -> Invocation:
        result = run_metab(args)
        catalog = read_catalog(self.home, origin_identity(CANONICAL).slug)
        if catalog is not None and catalog.epoch not in self.epochs:
            self.epochs.add(catalog.epoch)
            self.labels.add(catalog.epoch, f"<CATALOG_EPOCH_{len(self.epochs)}>")
        shown = [arg.removeprefix(f"{self.tmp_path}/") for arg in args]
        self.blocks.append(
            result.block(
                " ".join(quoted(arg) for arg in shown),
                **sections,
                gh=logged_gh_calls(self.tmp_path),
            )
        )
        return result

    def get(self, query: str = "") -> Invocation:
        return self._run(CANONICAL, "--api", f"{PULLS}{query}")

    def post(self, body: dict[str, Any], *, route: str = REFRESH) -> Invocation:
        path = self.tmp_path / "request.json"
        text = json.dumps(body)
        path.write_text(text + "\n", encoding="utf-8")
        return self._run(CANONICAL, "--api", route, "--data", str(path), body=[text])

    def local(self, route: str) -> Invocation:
        """A route read from a local root, which opens no source and asks gh nothing."""

        root = self.tmp_path / "root"
        root.mkdir(exist_ok=True)
        return self._run(str(root), "--api", route)


def _after(result: Invocation) -> dict[str, Any]:
    """The envelope a one-shot refresh printed after the job ended."""

    return json.loads(
        result.stdout[result.stdout.rindex("status: 200\n{") + len("status: 200\n") :]
    )


def _with(answers: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {**answers, **changes}


def _api(answers: dict[str, Any], path: str, entry: Any) -> dict[str, Any]:
    return {**answers, "api": {**answers["api"], path: entry}}


def _numbers(result: Invocation) -> list[int]:
    return [row["number"] for row in result.payload()["rows"]]


def test_golden_pull_lists_fetch_extend_refresh_and_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    online = scenario(session.origin)
    known = {
        number: list_item(parts["pull"]) for number, parts in pull_bodies(session.origin).items()
    }
    items = []
    for number in range(606, 10, -1):
        stamp = (FETCHED_AT - timedelta(days=1) + timedelta(seconds=number)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        items.append(dict(generated_item(number), created_at=stamp, updated_at=stamp))
    items.extend(known[number] for number in (10, 9, 8, 7))
    online = {**online, "api": {**online["api"], **catalog_entries(items)}}
    session.answer(online)

    # Cache-only reads neither create a catalog nor ask GitHub for one.
    empty = session.get()
    assert empty.exit_code == 0, empty.stderr
    assert (empty.payload()["list"], empty.payload()["reason"]) == ("open", "not_cached")
    assert not read_catalog(session.home, origin_identity(CANONICAL).slug)

    # The requested prefix goes first, then all metadata is backfilled in the same job.
    # No per-PR detail, Git comparison or patch request appears in its gh call log.
    started = session.post({"target": 500})
    assert started.exit_code == 0, started.stderr
    filled = _after(started)
    assert (filled["list"], filled["fetched"], filled["total"]) == ("open", 598, 598)
    assert (filled["repository_total"], filled["catalog_fetched"], filled["complete"]) == (
        600,
        600,
        True,
    )
    assert "repos/octo/demo/pulls/" not in session.blocks[-1]

    # Windows stay small even though the catalog has more than the first displayed 500.
    newest = session.get("?limit=2")
    assert _numbers(newest) == [606, 605]
    assert newest.payload()["next_after"] == 605
    assert _numbers(session.get("?limit=2&after=605")) == [604, 603]
    assert _numbers(session.get("?limit=2&after=10")) == [7]
    generation = newest.payload()["generation"]
    no_network = session.post({"target": 1000})
    assert no_network.exit_code == 0
    assert json.loads(no_network.stdout.split("status: 200\n")[1])["refresh"] == "not_due"
    assert session.get("?limit=0").payload()["generation"] == generation

    # Filters project one shared catalog, including merged PRs in Closed.
    assert [
        (row["number"], row["merged"]) for row in session.get("?state=closed").payload()["rows"]
    ] == [(9, False), (8, True)]
    assert session.get("?state=all&limit=0").payload()["total"] == 600

    # Search reaches the cached PRs beyond the first list window, without calling gh.
    for query, row in (
        ("%239", {"number": 9, "title": "spam", "state": "closed"}),
        ("GUIDE+say", {"number": 8, "title": "Say more in the guide", "state": "merged"}),
    ):
        assert session.get(f"?q={query}").payload() == {
            "rows": [row],
            "complete": True,
            "limited": False,
            "refreshing": False,
        }
        assert not session.blocks[-1].rsplit("--- gh ---\n", 1)[1].strip()

    # A changed PR is merged through UPDATED_AT without rescanning the old creation pages.
    session.advance(61)
    changed = dict(
        known[10],
        title="Retitled after catalog backfill",
        updated_at=f"{session.now:%Y-%m-%dT%H:%M:%SZ}",
    )
    added = dict(
        generated_item(607), updated_at=changed["updated_at"], created_at=changed["updated_at"]
    )
    moved_items = [added, *(changed if item["number"] == 10 else item for item in items)]
    moved = {**online, "api": {**online["api"], **catalog_entries(moved_items)}}
    session.answer(moved)
    refreshed = session.post({})
    assert refreshed.exit_code == 0, refreshed.stdout
    after = _after(refreshed)
    assert (after["total"], after["repository_total"], after["catalog_fetched"]) == (599, 601, 601)
    assert "catalog state=updated" in session.blocks[-1]
    assert "catalog state=all" not in session.blocks[-1]
    assert _numbers(session.get("?limit=2")) == [607, 606]
    assert session.get("?after=11&limit=1").payload()["rows"][0]["title"] == changed["title"]

    # A failed account switch preserves the old catalog and its reader label.
    session.answer(
        _with(
            moved,
            auth=account(ANOTHER_READER),
            api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1},
        )
    )
    assert session.post({"retry": True}).exit_code == 1
    labelled = session.get("?limit=0").payload()
    assert (labelled["state"], labelled["reader"]) == ("stale", "gh:octo-reader")

    # A successful switch starts with that account's own catalog and cursors.
    replacement = scenario(session.origin)
    base_items = [
        *(generated_item(number) for number in range(106, 10, -1)),
        *(known[number] for number in (10, 9, 8, 7)),
    ]
    replacement = {
        **replacement,
        "auth": account(ANOTHER_READER),
        "api": {**replacement["api"], **catalog_entries(base_items, reader=ANOTHER_READER)},
    }
    session.answer(replacement)
    replaced = _after(session.post({"retry": True}))
    assert (replaced["reader"], replaced["repository_total"], replaced["catalog_fetched"]) == (
        f"gh:{ANOTHER_READER}",
        100,
        100,
    )
    assert replaced["generation"].split(":")[0] != generation.split(":")[0]

    session.say("A visible pull request prepares its description from one GraphQL batch.")
    entry = pull_bodies(session.origin)[7]["pull"]
    data = graph_core_data(entry, reader=ANOTHER_READER)
    data["repository"]["p0"] = data["repository"].pop("pull")
    key = "graphql:visible-cores:7"
    session.answer(_api(replacement, key, ok(key, {"data": data})))
    monkeypatch.setattr(pulls, "utc_now", lambda: session.now)

    prepared = session.post(
        {
            "state": replaced["list"],
            "window": {"id": "visible-7", "generation": replaced["generation"]},
            "numbers": [7],
        },
        route=PREPARE,
    )
    assert prepared.exit_code == 0, prepared.stderr
    _, accepted, body = prepared.stdout.partition("status: 202\n")
    assert accepted
    ack, _ = json.JSONDecoder().raw_decode(body)
    assert ack == {"preparation": "started", "status_route": "/api/plugin/github/pull?number=7"}
    final = _after(prepared)
    preview = final["core_preview"]
    assert final["record"] is None and final["refreshing"] is False
    assert (preview["source"], preview["reader"], preview["number"]) == (
        replaced["source"],
        f"gh:{ANOTHER_READER}",
        7,
    )
    assert preview["observed_at"] == session.now.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert preview["comparison_state"] == "not_started"
    assert preview["pull"]["body"] == entry["body"]
    assert session.blocks[-1].rsplit("--- gh ---\n", 1)[1].splitlines() == [
        "gh api graphql visible-cores numbers=7"
    ]

    cached = session.local(f"/api/cache/source/{origin_identity(CANONICAL).slug}")
    assert cached.exit_code == 0, cached.stderr
    rendered = label_home(session.labels.apply("".join(session.blocks)), session.home)
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-pulls-refresh.txt", rendered)


def test_golden_pull_list_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    online = scenario(session.origin)
    first_path = "graphql:updated:start"
    assert session.post({}).exit_code == 0
    baseline = session.get("?limit=0").payload()

    # Every typed refusal keeps the last published catalog readable.
    failures: list[tuple[str, dict[str, Any]]] = [
        ("not_logged_in", _with(online, auth={"stdout": '{"hosts":{}}\n', "exit": 0})),
        ("gh_too_old", _with(online, auth={"stderr": "unknown flag: --json\n", "exit": 1})),
        (
            "not_found_or_private",
            _api(online, first_path, {"status": 404, "body": {"message": "Not Found"}}),
        ),
        (
            "network_error",
            _with(
                online, api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1}
            ),
        ),
        ("gh_failed", _api(online, first_path, {"status": 200, "raw": "not JSON"})),
    ]
    session.advance(61)
    for state, answers in failures:
        session.answer(answers)
        refused = session.post({"retry": True})
        assert refused.exit_code == 1, (state, refused.stdout)
        result = _after(refused)
        assert result["last_refresh"]["outcome"] == state
        assert result["fetched"] == baseline["fetched"]

    # The page itself identifies a different account from the one that started the job.
    switched_account = {
        **online,
        "api": {**online["api"], **catalog_entries([], reader=ANOTHER_READER)},
    }
    session.answer(switched_account)
    switched = session.post({"retry": True})
    assert switched.exit_code == 1
    assert _after(switched)["last_refresh"]["outcome"] == "account_changed"
    assert _after(switched)["state"] == "stale"
    with monkeypatch.context() as patched:
        patched.setattr(gh, "gh_executable", lambda: None)
        assert _after(session.post({"retry": True}))["last_refresh"]["outcome"] == "gh_missing"

    session.answer(
        _with(online, api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1})
    )
    offline = session.get("?limit=1")
    assert offline.exit_code == 0 and offline.payload()["fetched"] == baseline["fetched"]

    # Rate holds cover retries and a larger display demand, and expire at their boundary.
    slow_down = {"status": 429, "headers": {"Retry-After": "120"}, "body": {"message": "slow down"}}
    session.answer(_api(online, first_path, slow_down))
    limited = session.post({"retry": True})
    assert limited.exit_code == 1
    assert _after(limited)["last_refresh"]["outcome"] == "rate_limited"
    session.answer(online)
    for body in ({"retry": True}, {"target": 1000}):
        waited = session.post(body)
        assert waited.exit_code == 0
        assert json.loads(waited.stdout.split("status: 200\n")[1])["refresh"] == "not_due"
    session.advance(121)
    assert _after(session.post({"retry": True}))["last_refresh"]["outcome"] == "succeeded"

    slug = origin_identity(CANONICAL).slug
    pulls_directory = session.home / "sources" / slug / "pulls"
    pulls_directory.chmod(0o500)
    try:
        unwritable = session.post({"retry": True})
    finally:
        pulls_directory.chmod(0o700)
    assert unwritable.exit_code == 1
    assert _after(unwritable)["last_refresh"]["outcome"] == "cache_unwritable"
    session.answer(online)
    assert _after(session.post({"retry": True}))["last_refresh"]["outcome"] == "succeeded"

    rendered = label_home(session.labels.apply("".join(session.blocks)), session.home)
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-pulls-failures.txt", rendered)
