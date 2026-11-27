"""What a link preview says of each object, from the reads the app already makes for it.

``static/link-preview-providers.js`` answers the link card's title, state, and detail for
each kind of in-app link, and starts loading what the link opens. The browserless session
(``tests/dom/link-preview-providers-session.js``, pinned whole by
``cli-ui-link-preview-providers.tryscript.md``) runs the exact module, and the exact Git
panel whose commit summary it reads, against the server's own answers: a recording of the
catalog's search, the record read, a commit's detail and comparison
(``link-preview-providers-responses.json``, recorded here), and the stacks snapshot the
Pulls tab's session replays (``github-stacks-responses.json``). These tests hold its
answers to those recordings and to the rules of a link rest: every read is one the app
already makes for that object, none asks GitHub or counts a view, none is aborted, and a
card claims nothing its data does not give.
"""

from __future__ import annotations

import functools
import os
import re
import subprocess
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from metabrowser import paths_safe
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.git import repo as git_repo
from metabrowser.git.process import _REPO_PINNING_GIT_VARS  # pyright: ignore[reportPrivateUsage]
from metabrowser.server import app
from tests.github_pull_fixture import CANONICAL, generated_item, seed_catalog
from tests.golden_harness import check_recording, read_recording, run_session
from tests.required_tools import needs_git

RECORDING = "link-preview-providers-responses.json"
STACKS_RECORDING = "github-stacks-responses.json"
TRANSCRIPT = "cli-ui-link-preview-providers.tryscript.md"
SESSION = "link-preview-providers-session.js"
ROOT = Path(__file__).resolve().parents[1]
GITHUB_MANIFEST = ROOT / "src/metabrowser/builtin_plugins/github/manifest.toml"
# The pull requests the recording's catalog holds, one in each state a row can have.
PULLS = {
    12: ("open", "feat(links): preview what a link opens"),
    13: ("draft", "Draft: a tooltip for every in-app link"),
    14: ("closed", "Retire the native link title"),
    15: ("merged", "docs: the rule for tooltips on links"),
}
UNKNOWN_PULL = 99
# A commit the recording's repository lacks, as the source freshness session names one.
ABSENT_COMMIT = "0123456789abcdef0123456789abcdef01234567"
# The one commit date of the recording's repository, so its commit IDs are the same on
# every run; the session reads ages as of a fixed time after it.
COMMIT_DATE = "2026-11-20T12:00:00Z"


def _git(root: Path, *args: str) -> str:
    """Run Git in *root* with no configuration but these names and this date.

    Repository-pinning variables are scrubbed as tests/test_git_e2e.py scrubs them: under
    the pre-push gate, Git's exported GIT_DIR outranks -C.
    """

    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Ada Author",
            "GIT_AUTHOR_EMAIL": "ada@example.invalid",
            "GIT_AUTHOR_DATE": COMMIT_DATE,
            "GIT_COMMITTER_NAME": "Ada Author",
            "GIT_COMMITTER_EMAIL": "ada@example.invalid",
            "GIT_COMMITTER_DATE": COMMIT_DATE,
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True, env=env
    )
    return result.stdout.strip()


@pytest.fixture
def served_repository(tmp_path: Path) -> Iterator[Path]:
    """A checkout of two commits whose origin is the fixture's GitHub repository."""

    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "remote", "add", "origin", f"{CANONICAL}.git")
    (root / "README.md").write_text("# Demo\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "Start the demo")
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("# Guide\n\nRest on a link to see what it opens.\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "docs: write the guide")
    paths_safe._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
    git_repo.clear_repo_cache()
    try:
        yield root
    finally:
        git_repo.clear_repo_cache()


def _answer(response: Any) -> dict[str, Any]:
    return {"status": response.status_code, "body": response.json()}


@needs_git
@pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
def test_recording_link_preview_answers_real_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, served_repository: Path
) -> None:
    """The answers the session replays come from the real routes, each cache-only."""

    from tests.cache_home_fixture import FixtureSource, _stage_and_publish_source, build_empty_home

    home = tmp_path / "home"
    build_empty_home(home)
    source = FixtureSource("https", CANONICAL)
    _stage_and_publish_source(home, source, opened=False)  # pyright: ignore[reportPrivateUsage]
    repository = ListedRepository(home, source.slug, "octo", "demo")
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_list_route.served_repository",
        lambda _app: repository,  # pyright: ignore[reportUnknownLambdaType]
    )
    items: list[dict[str, Any]] = []
    for number, (state, title) in PULLS.items():
        item = generated_item(number) | {"title": title}
        if state == "draft":
            item["draft"] = True
        elif state in {"closed", "merged"}:
            item |= {"state": "closed", "closed_at": "2026-11-21T12:00:00Z"}
            if state == "merged":
                item |= {"merged_at": "2026-11-21T12:00:00Z", "merge_commit_sha": "1" * 40}
        items.append(item)
    seed_catalog(repository, items)
    head = _git(served_repository, "rev-parse", "HEAD")
    first = _git(served_repository, "rev-parse", "HEAD~1")
    recorded: dict[str, Any] = {}
    with TestClient(app) as client:
        for number in [*PULLS, UNKNOWN_PULL]:
            response = client.get("/api/plugin/github/pulls", params={"q": str(number)})
            recorded[f"pulls?q={number}"] = _answer(response)
        warm = client.get("/api/plugin/github/pull", params={"number": "12", "warm": "1"})
        recorded["pull?number=12&warm=1"] = _answer(warm)
        for name, revision in (("commit", head), ("first commit", first)):
            detail = client.get(f"/api/git/commit/{revision}")
            comparison = client.get("/api/plugin/diff/comparison", params={"revision": revision})
            recorded[name] = {"revision": revision, **_answer(detail)}
            recorded[f"{name} comparison"] = {"revision": revision, **_answer(comparison)}
        absent: dict[str, Any] = {
            "revision": ABSENT_COMMIT,
            **_answer(client.get(f"/api/git/commit/{ABSENT_COMMIT}")),
        }
        recorded["commit absent"] = absent
    for number, (state, title) in PULLS.items():
        rows = recorded[f"pulls?q={number}"]["body"]["rows"]
        assert rows == [{"number": number, "title": title, "state": state}], number
    assert recorded[f"pulls?q={UNKNOWN_PULL}"]["body"]["rows"] == []
    assert recorded["commit"]["body"]["commit"]["subject"] == "docs: write the guide"
    assert recorded["first commit"]["body"]["commit"]["subject"] == "Start the demo"
    assert recorded["commit absent"]["status"] == 404
    assert recorded["commit absent"]["body"]["code"] == "commit_not_found"
    for name in ("commit", "first commit", "commit comparison", "first commit comparison"):
        assert recorded[name]["status"] == 200, name
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)


@functools.cache
def _session() -> dict[str, Any]:
    return run_session(SESSION)


def _manifest(plugin: str) -> dict[str, Any]:
    path = GITHUB_MANIFEST.parent.parent / plugin / "manifest.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _rests() -> list[dict[str, Any]]:
    return list(_session()["summaries"].values())


def test_every_kind_of_in_app_link_has_one_provider() -> None:
    """Each kind of page the card names has exactly one provider, so no link goes without."""

    provided = _session()["provided"]
    assert sorted(provided) == ["commit", "file", "folder", "pull", "pulls", "stack"]
    assert len(provided) == len(set(provided))


def test_a_card_says_what_its_records_say_and_nothing_more() -> None:
    """A summary is plain text taken from the server's own answer, and claims no more.

    A pull request's title and state are its catalog row's, and one the catalog does not
    hold has no summary; only a pull request has a state; a commit's title is its subject
    and its detail starts with its author; a stack's title is one of its members' and its
    detail counts them all.
    """

    recording = read_recording(RECORDING)
    rows = {
        row["number"]: row
        for name, answer in recording.items()
        if name.startswith("pulls?q=")
        for row in answer["body"]["rows"]
    }
    commits = {
        answer["revision"]: answer["body"]["commit"]
        for answer in recording.values()
        if isinstance(answer.get("body"), dict) and "commit" in answer["body"]
    }
    stacks = {
        stack["number"]: stack
        for stack in read_recording(STACKS_RECORDING)["shared"]["body"]["stacks"]
    }
    for rest in _rests():
        subject, summary = rest["subject"], rest["summary"]
        if subject["kind"] == "pull" and subject["number"] not in rows:
            assert summary is None, rest
        if summary is None or "rejected" in summary:
            continue
        assert set(summary) <= {"title", "state", "detail", "missing"}, rest
        assert all(isinstance(value, str) and value for value in summary.values()), rest
        assert ("state" in summary) == (subject["kind"] == "pull"), rest
        if subject["kind"] == "pull":
            row = rows[subject["number"]]
            assert (summary["title"], summary["state"]) == (row["title"], row["state"]), rest
        elif subject["kind"] == "commit" and "missing" not in summary:
            commit = commits[subject["revision"]]
            assert summary["title"] == commit["subject"], rest
            assert summary["detail"].startswith(f"{commit['author']['name']} · "), rest
        elif subject["kind"] == "stack":
            stack = stacks[subject["number"]]
            assert summary["title"] in stack["titles"], rest
            assert summary["detail"].startswith(f"{len(stack['pulls'])} "), rest


def test_no_file_or_folder_is_called_missing() -> None:
    """No list the page holds is every file a link can open: a served folder's whole Quick
    File catalog leaves out its hidden, gitignored, and symlinked files, and a pin's lists no
    folder. So a file's card says nothing a catalog's not listing it would give, whether the
    catalog lists the file or not, and a folder's never says it is missing."""

    held = [rest for rest in _rests() if rest["subject"]["kind"] in {"file", "folder"}]
    files = [rest for rest in held if rest["subject"]["kind"] == "file"]
    listed = [rest for rest in files if rest["listed"]]
    unlisted = [rest for rest in files if not rest["listed"]]
    assert listed and len(unlisted) >= 4, files
    for rest in held:
        assert "missing" not in (rest["known"] or {}), rest
        assert "missing" not in (rest["summary"] or {}), rest
    for rest in unlisted:
        same_kind = [
            other for other in listed if other["subject"]["opens"] == rest["subject"]["opens"]
        ]
        assert all(rest["summary"] == other["summary"] for other in same_kind), rest


def test_every_read_is_one_the_app_makes_from_the_cache() -> None:
    """No rest writes, asks GitHub, counts a view, or aborts a request.

    Every request is a GET of a commit's detail or of a data hook its plugin's manifest
    declares for GET alone, never a refresh; the record read is marked `warm=1`, which the
    server leaves out of what a reader viewed; and no request is aborted before its answer.
    """

    session = _session()
    readable = {
        f"/api/plugin/{plugin}/{hook['route']}"
        for plugin in ("github", "diff")
        for hook in _manifest(plugin)["data_hook"]
        if hook.get("methods", ["GET"]) == ["GET"]
    }
    assert session["requests"]
    for line in session["requests"]:
        method, url = line.split(" ", 1)
        address = urlsplit(url)
        assert method == "GET", line
        assert address.path in readable or address.path.startswith("/api/git/commit/"), line
        assert "refresh" not in address.path, line
        if address.path == "/api/plugin/github/pull":
            assert parse_qs(address.query).get("warm") == ["1"], line
    assert session["aborted"] == []


def test_what_a_provider_holds_it_says_at_once_and_reads_nothing() -> None:
    """A provider that holds a fresh answer says it as the pointer arrives (`known`), and its
    summary is that answer, with no read; one that holds nothing reads."""

    for rest in _rests():
        if rest["known"] is not None:
            assert rest["summary"] == rest["known"] and rest["asked"] == [], rest
    assert any(rest["known"] is not None for rest in _rests())


def test_what_failed_or_was_not_yet_known_is_read_again() -> None:
    """The registry keeps no answer, so a provider's own rules decide each rest's reads: a
    read that failed is read again, a catalog not yet whole is asked again, a kept answer
    goes stale after the Pulls tab's interval, and a commit follows the Commits panel."""

    summaries = _session()["summaries"]
    failed = summaries["a closed one, whose read fails"]
    again = summaries["the closed one, rested on again"]
    assert failed["summary"] is None and failed["asked"], failed
    assert again["asked"] == failed["asked"] and again["summary"]["title"], again
    filling = summaries["the same, at the next rest"]
    assert filling["asked"] == summaries["one a catalog still filling does not hold"]["asked"]
    assert summaries["one the catalog does not hold"]["asked"]
    stale = summaries["the open one, once its summary is too old to reuse"]
    assert stale["known"] is None and stale["asked"] == summaries["a pull request, open"]["asked"]
    refreshing = summaries["the same stack, a second later"]
    assert refreshing["known"] is None and refreshing["asked"], refreshing
    let_go = summaries["the missing commit, once the panel let go of what it knew"]
    assert let_go["known"] is None and let_go["asked"] == summaries["a commit it lacks"]["asked"]


def _constant(path: Path, name: str) -> int:
    """The number *path* gives `const NAME`, with or without `export` and `_` separators."""

    match = re.search(rf"\bconst {name} = ([0-9_]+);", path.read_text(encoding="utf-8"))
    assert match is not None, f"{path.name} no longer declares {name}"
    return int(match[1].replace("_", ""))


def test_a_kept_answer_is_reused_as_long_as_the_pulls_tab_waits() -> None:
    """The providers reuse a pull request's summary and the stacks snapshot for as long as
    the Pulls tab's pollers wait between their reads, and a second while it is refreshing:
    the github plugin's own intervals, which a classic script cannot import."""

    providers = ROOT / "src/metabrowser/static/link-preview-providers.js"
    github = ROOT / "src/metabrowser/builtin_plugins/github"
    reuse = _constant(providers, "REUSE_MS")
    refreshing = _constant(providers, "REFRESHING_REUSE_MS")
    assert reuse == _constant(github / "pull-stacks.js", "STACKS_POLL_MS")
    assert reuse == _constant(github / "pull-page.js", "SLOW_POLL_MS")
    assert refreshing == _constant(github / "pull-stacks.js", "STACKS_REFRESHING_POLL_MS")
    assert refreshing == _constant(github / "pull-page.js", "FAST_POLL_MS")


def test_a_prefetch_loads_what_the_link_opens_and_nothing_for_a_missing_commit() -> None:
    """Each prefetch loads a page kind a built-in plugin declares a view for; a commit's
    shares the detail its card read; a commit the repository lacks starts nothing; and a
    pin's View on GitHub request names the page the server's GitPath codec reads back."""

    from metabrowser.git.tree_source import GitPath

    session = _session()
    views = {view["kind"] for plugin in ("github", "diff") for view in _manifest(plugin)["view"]}
    prefetches = session["prefetches"]
    for name, prefetch in prefetches.items():
        assert set(prefetch["assets"]) <= views, name
    missing = prefetches["a commit it lacks"]
    assert (missing["asked"], missing["assets"]) == ([], []), missing
    together = session["a commit's card and prefetch together"]
    assert sum("/api/git/commit/" in line for line in together["asked"]) == 1, together
    [page] = prefetches["a file of a pinned revision"]["counterparts"]
    wire = page.removeprefix("/view/")
    shown = prefetches["a file of a pinned revision"]["subject"]["path"]
    assert GitPath.from_wire(wire).segments == tuple(
        segment.encode() for segment in shown.split("/")
    )
