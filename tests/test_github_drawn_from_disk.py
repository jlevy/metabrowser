"""Every element the pull-request page, the stack page, and the Pulls tab draw answers from
disk (mb-g8oe).

What Metabrowser draws is cached on disk and painted from it first. This module holds
that true route by route. A module fixture writes one cache home through the production
writers, with the stand-in origin of ``tests/github_pull_fixture.py`` and a fake ``gh``
replaying its scrubbed responses: pull requests 7's and 10's records, with their heads
fetched and their comparison manifests prepared; the catalog; 7's and 106's changed-files
lists; two native stacks, one of 7 and 106 and one of 10 alone, whose page was read once,
which kept its combined comparison's manifest; the label set; 7's Conversation timeline;
and 8's lightweight core, with no record. Then every test takes the network away: a
``gh`` that fails every command is first on ``PATH``, the mirror's remote is an address
nothing answers, every process is recorded, a Git transport command
(:data:`NETWORK_VERBS`) refused on the spot, and every socket that would leave the machine
is refused and recorded. Each test reads that warm disk with the process caches
``tests/conftest.py`` drops between tests dropped, and the comparison cache and the stack
page's ancestry answers, which :func:`offline` drops; the plugin's own memos of parsed
files stay, which a route that reads again only answers faster. The pages are a mirror's: a
checkout's server reaches the same routes through ``checkout.py``.

:data:`ELEMENTS` is the inventory: what a reader sees, the route that answers it through
``metab --api``, what the answer must hold, and the Git commands the route runs in the
local store (computation, never the network). :data:`JOBS` names every other route and
why it draws nothing, so a new route fails
:func:`test_every_route_is_drawn_from_disk_or_a_job` until it is classified.
:data:`GAPS` lists what a surface draws that does not answer from disk, each a strict
expected failure that raises :class:`StillAGap` only for its own reason: a fixed gap
passes, which fails this module until its row moves to :data:`ELEMENTS`.
"Drawn From Disk" in ``docs/project/architecture/arch-github-pull-requests.md`` names
this module.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tomllib
from collections import Counter, OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import pytest

from metabrowser import http_caching
from metabrowser.builtin_plugins.diff import sidekick as diff_sidekick
from metabrowser.builtin_plugins.diff.comparison_cache import ComparisonCache
from metabrowser.builtin_plugins.github import pull_list, pull_stack, pulls
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_list_refresh import refresh_pull_list
from metabrowser.cache.urls import GitSource
from metabrowser.git.tree_source import GitPath
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    TREE_PULL,
    Origin,
    build_origin,
    files_scenario,
    graph_core_data,
    guide_body,
    install_fake_gh,
    ok,
    pull_bodies,
)
from tests.golden_harness import FIXTURES_DIR, Invocation, origin_identity, run_metab
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git  # pyright: ignore[reportPrivateUsage]

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

ROUTES: Final = "/api/plugin/github"
MANIFEST: Final = Path(__file__).resolve().parents[1] / (
    "src/metabrowser/builtin_plugins/github/manifest.toml"
)
# Git's commands that reach a remote. Anything else a route runs reads the local store.
NETWORK_VERBS: Final = frozenset(
    {"clone", "fetch", "fetch-pack", "ls-remote", "pull", "push", "remote"}
)
# The hosts a socket may reach: this machine.
LOOPBACK: Final = frozenset({None, "", "localhost", "127.0.0.1", "::1"})
_REFUSED: Final = (
    "import sys; sys.stderr.write('fatal: the network is refused here\\n'); sys.exit(128)"
)
# The avatar 7's record names, as GitHub's REST answer gives it, and as a record keeps it.
AVATAR: Final = "https://avatars.githubusercontent.com/u/9919?v=4"
KEPT_AVATAR: Final = "https://avatars.githubusercontent.com/u/9919?s=40"
STACK: Final = 70
# A stack of 10 alone: every member has a record, so its page shows its combined comparison,
# where 70 waits for 106, which has none.
LONE_STACK: Final = 71
LONE_PULL: Final = 10
CORE_PULL: Final = 8
# What the comparison of 7 holds: Files changed, and its Diff summary's totals.
CHANGED: Final = ("docs/new.md", "src/app.txt")
TOTALS: Final = (2, 2, 0)


class StillAGap(Exception):
    """Raised by a gap's check, and only for the reason that gap is listed."""


def git_verb(argv: Sequence[str]) -> str | None:
    """The Git command *argv* runs, past Git's own options and the store it names."""

    rest = iter(argv[1:])
    for arg in rest:
        if arg in ("-c", "-C", "--git-dir", "--work-tree", "--namespace"):
            next(rest, None)
        elif not arg.startswith("-"):
            return arg
    return None


def _is(argv: Sequence[str], program: str) -> bool:
    return Path(argv[0]).name == program


@dataclass
class Spawns:
    """Every process a test's commands started, a Git transport command refused."""

    seen: list[tuple[str, ...]] = field(default_factory=list[tuple[str, ...]])
    refused: int = 0
    # The hosts a socket was refused for.
    sockets: list[str] = field(default_factory=list[str])

    def take(self) -> list[tuple[str, ...]]:
        seen, self.seen = self.seen, []
        return seen


def _refusing(spawns: Spawns) -> type[subprocess.Popen[Any]]:
    """A ``Popen`` that records each process and runs a refusal for Git's transport.

    asyncio starts its children through ``subprocess.Popen`` too, so every ``gh`` and Git
    process Metabrowser starts, on the event loop or off it, passes through here.
    """

    class Refusing(subprocess.Popen[Any]):
        def __init__(
            self, args: str | Sequence[str | os.PathLike[str]], *rest: Any, **kwargs: Any
        ) -> None:
            argv = (args,) if isinstance(args, str) else tuple(os.fspath(arg) for arg in args)
            spawns.seen.append(argv)
            if _is(argv, "git") and git_verb(argv) in NETWORK_VERBS:
                spawns.refused += 1
                args = [sys.executable, "-I", "-c", _REFUSED]
            super().__init__(args, *rest, **kwargs)

    return Refusing


def _refuse_sockets(patch: pytest.MonkeyPatch, spawns: Spawns) -> None:
    """Name resolution and connections in this process reach only this machine."""

    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def refused(host: object) -> OSError:
        spawns.sockets.append(str(host))
        return OSError(f"the network is refused here: {host}")

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if host not in LOOPBACK:
            raise refused(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def leaves(sock: socket.socket, address: Any) -> bool:
        family = sock.family
        return family in (socket.AF_INET, socket.AF_INET6) and address[0] not in LOOPBACK

    def connect(sock: socket.socket, address: Any) -> None:
        if leaves(sock, address):
            raise refused(address[0])
        real_connect(sock, address)

    def connect_ex(sock: socket.socket, address: Any) -> int:
        if leaves(sock, address):
            raise refused(address[0])
        return real_connect_ex(sock, address)

    patch.setattr(socket, "getaddrinfo", getaddrinfo)
    patch.setattr(socket.socket, "connect", connect)
    patch.setattr(socket.socket, "connect_ex", connect_ex)


@dataclass(frozen=True)
class Built:
    """The home the module fixture wrote, and what its answers are checked against."""

    root: Path
    revision: str
    comparison_route: str
    image_route: str
    rendered_route: str
    size_route: str
    core_body: str | None
    # The combined comparison's address, as the lone stack's page answer names it.
    stack_comparison_route: str

    @property
    def timeline_request(self) -> Path:
        return self.root / "timeline-request.json"


def answer(result: Invocation) -> Any:
    """The last JSON envelope a command printed: a refresh's, after its job ended."""

    at = result.stdout.rfind("status: 200\n{")
    if at < 0:
        return result.payload()
    return json.loads(result.stdout[at + len("status: 200\n") :])


def _post(directory: Path, route: str, body: dict[str, Any]) -> Invocation:
    request = directory / "request.json"
    request.write_text(json.dumps(body) + "\n", encoding="utf-8")
    result = run_metab([CANONICAL, "--api", route, "--data", str(request)])
    assert result.exit_code == 0, (route, result.stdout[-2000:], result.stderr[-2000:])
    return result


def _stack_page(path: str, stacks: dict[int, list[int]]) -> dict[str, Any]:
    return ok(
        path,
        [
            {
                "number": number,
                "url": f"https://api.github.com/repos/octo/demo/stacks/{number}",
                "base": {"ref": "topic"},
                "open": True,
                "pull_requests": [{"number": member} for member in members],
            }
            for number, members in stacks.items()
        ],
    )


def _timeline_page(origin: Origin, record: dict[str, Any]) -> dict[str, Any]:
    """GitHub's timeline of 7: a commit, the comment, the head commit, the review."""

    head = record["pull"]["head"]["sha"]

    def commit(oid: str, subject: str, at: str) -> dict[str, Any]:
        return {
            "__typename": "PullRequestCommit",
            "commit": {"oid": oid, "messageHeadline": subject, "committedDate": at},
        }

    nodes = [
        commit(origin["fork_earlier"], "Prepare the fixture", "2026-08-29T00:00:00Z"),
        {"__typename": "IssueComment", "fullDatabaseId": str(record["issue_comments"][0]["id"])},
        commit(head, "Address the review", "2026-08-29T01:00:00Z"),
        {
            "__typename": "PullRequestReview",
            "fullDatabaseId": str(record["reviews"][0]["id"]),
            "state": "APPROVED",
        },
    ]
    pull = {
        "number": 7,
        "baseRefName": record["pull"]["base"]["ref"],
        "headRefOid": head,
        "timelineItems": {
            "nodes": nodes,
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        },
    }
    return {
        "viewer": {"login": record["reader"].removeprefix("gh:")},
        "repository": {"nameWithOwner": "octo/demo", "pullRequest": pull},
    }


def _console(patch: pytest.MonkeyPatch, root: Path) -> None:
    patch.setenv("METABROWSER_CACHE_DIR", str(root / "home"))
    patch.setenv("METABROWSER_CONFIG_DIR", str(root / "config"))
    patch.setenv("METABROWSER_LOG_LEVEL", "ERROR")
    patch.setenv("METABROWSER_PLUGINS_DIRS", "")
    patch.setenv("TERM", "dumb")
    patch.setenv("TZ", "UTC")
    patch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    patch.setattr(pulls, "utc_now", lambda: FETCHED_AT)


def _online(patch: pytest.MonkeyPatch, root: Path, origin: Origin, answers: dict[str, Any]) -> None:
    """The goldens' seams: the stand-in origin, the installed Git, and the fake ``gh``."""

    _console(patch, root)
    _allow_installed_git(patch)
    local = origin.url

    def remote(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    patch.setattr("metabrowser.cache.acquire.remote_url_for", remote)
    for key, value in install_fake_gh(root, answers).items():
        patch.setenv(key, value)


def _offline(patch: pytest.MonkeyPatch, root: Path) -> Spawns:
    """No ``gh`` that answers, no remote that answers, and no Git transport at all."""

    _console(patch, root)
    no_gh = FIXTURES_DIR / "github-pull" / "no-gh"
    patch.setenv("PATH", f"{no_gh}{os.pathsep}{os.environ.get('PATH', '')}")

    def nowhere(_source: GitSource) -> str:
        return "https://network.invalid/octo/demo"

    patch.setattr("metabrowser.cache.acquire.remote_url_for", nowhere)
    spawns = Spawns()
    patch.setattr(subprocess, "Popen", _refusing(spawns))
    _refuse_sockets(patch, spawns)
    # A fresh process holds no comparison; a manifest it reads comes from the bank on disk.
    patch.setattr(diff_sidekick, "_COMPARISONS", ComparisonCache())
    # Nor any ancestry answer: a stack's page asks the store again in a fresh process.
    patch.setattr(pull_stack, "_ANCESTRIES", OrderedDict())
    return spawns


def _build(root: Path, origin: Origin) -> Built:
    """Write the home through the production writers, as a reader's server would."""

    answers = files_scenario(origin)
    api = answers["api"]
    api["repos/octo/demo/pulls/7"]["body"]["user"]["avatar_url"] = AVATAR
    api["repos/octo/demo/pulls/7"]["body"]["body"] = guide_body(origin)
    answers["stack_version"] = "0.1.0"
    stacks = "repos/octo/demo/stacks?per_page=100&page=1"
    api[stacks] = _stack_page(stacks, {STACK: [7, TREE_PULL], LONE_STACK: [LONE_PULL]})
    entry = pull_bodies(origin)[CORE_PULL]["pull"]
    core = graph_core_data(entry)
    core["repository"]["p0"] = core["repository"].pop("pull")
    cores = f"graphql:visible-cores:{CORE_PULL}"
    api[cores] = ok(cores, {"data": core})
    with pytest.MonkeyPatch.context() as patch:
        _online(patch, root, origin, answers)
        for number in (7, LONE_PULL):
            fetched = run_metab([f"{CANONICAL}/pull/{number}", "--no-serve"])
            assert fetched.exit_code == 0, fetched.stderr
        repository = ListedRepository(
            root / "home", origin_identity(CANONICAL).slug, "octo", "demo"
        )
        asyncio.run(refresh_pull_list(repository, "open"))
        _post(root, f"{ROUTES}/pull-files-refresh", {"number": 7})
        _post(root, f"{ROUTES}/pull-files-refresh", {"number": TREE_PULL})
        _post(root, f"{ROUTES}/stacks-refresh", {})
        # The lone stack's page, read once as a reader opening it would, lists its combined
        # comparison and keeps that manifest beside the store.
        lone = run_metab([CANONICAL, "--api", f"{ROUTES}/stack?number={LONE_STACK}"]).payload()
        assert lone["state"] == "current", lone
        _post(root, f"{ROUTES}/labels-refresh", {})
        envelope = run_metab([CANONICAL, "--api", f"{ROUTES}/pull?number=7"]).payload()
        timeline = "graphql:timeline:7:start"
        api[timeline] = ok(timeline, {"data": _timeline_page(origin, envelope["record"])})
        for key, value in install_fake_gh(root, answers).items():
            patch.setenv(key, value)
        ask = {"number": 7, "record_revision": envelope["record_revision"]}
        assert answer(_post(root, f"{ROUTES}/pull-timeline", ask))["state"] == "complete"
        window = run_metab([CANONICAL, "--api", f"{ROUTES}/pulls?state=all&limit=0"]).payload()
        prepared = _post(
            root,
            f"{ROUTES}/pull-cores-prepare",
            {
                "state": "all",
                "window": {"id": "drawn", "generation": window["generation"]},
                "numbers": [CORE_PULL],
            },
        )
        assert "status: 202" in prepared.stdout, prepared.stdout[-2000:]
    built = Built(
        root=root,
        revision=envelope["record_revision"],
        comparison_route=envelope["comparison_route"],
        image_route=envelope["image_route"],
        rendered_route=envelope["rendered_route"],
        size_route=envelope["size_route"],
        core_body=entry.get("body"),
        stack_comparison_route=lone["comparison"]["route"],
    )
    built.timeline_request.write_text(json.dumps(ask), encoding="utf-8")
    return built


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Built:
    root = tmp_path_factory.mktemp("drawn-from-disk")
    return _build(root, build_origin(root / "origin"))


@pytest.fixture
def offline(built: Built, monkeypatch: pytest.MonkeyPatch) -> Spawns:
    return _offline(monkeypatch, built.root)


@dataclass(frozen=True)
class Run:
    """One command's answer, and what its route ran beyond opening the source."""

    result: Invocation
    git: frozenset[str]
    git_args: list[tuple[str, ...]]
    gh: list[tuple[str, ...]]
    network: list[tuple[str, ...]]
    sockets: list[str]


def run_offline(spawns: Spawns, args: Sequence[str]) -> Run:
    """*args* through ``metab``, and the processes its route started.

    ``/api/identity`` first is the baseline: what every command runs to open the cached
    mirror, which reads the local store and nothing else.
    """

    baseline = run_metab([CANONICAL, "--api", "/api/identity"])
    assert baseline.exit_code == 0, baseline.stderr
    opened = spawns.take()
    result = run_metab([CANONICAL, *args])
    seen = spawns.take()
    sockets, spawns.sockets = spawns.sockets, []
    every = [*opened, *seen]
    gits = [argv for argv in seen if _is(argv, "git")]
    own = Counter(git_verb(argv) for argv in gits) - Counter(
        git_verb(argv) for argv in opened if _is(argv, "git")
    )
    return Run(
        result,
        frozenset(verb for verb in own if verb is not None),
        gits,
        gh=[argv for argv in every if _is(argv, "gh")],
        network=[argv for argv in every if _is(argv, "git") and git_verb(argv) in NETWORK_VERBS],
        sockets=sockets,
    )


@dataclass(frozen=True)
class Drawn:
    """One element a surface draws, the route that answers it, and what it must hold."""

    element: str
    surface: str
    route: str
    query: Callable[[Built], str]
    check: Callable[[Built, Invocation], None]
    # The Git commands a route runs in the local store beyond opening it: computation.
    computes: frozenset[str] = frozenset()
    # The answer's status: `metab --api` exits 1 on any other than 200.
    status: int = 200

    def args(self, built: Built) -> list[str]:
        query = self.query(built)
        if self.route == "pull-timeline":
            return ["--api", f"{ROUTES}/{self.route}", "--data", str(built.timeline_request)]
        return ["--api", query if query.startswith("/") else f"{ROUTES}/{self.route}?{query}"]


def _fixed(query: str) -> Callable[[Built], str]:
    return lambda _built: query


def _rows(_built: Built, result: Invocation) -> None:
    listed = answer(result)
    assert listed["state"] in {"current", "stale"} and listed["complete"] is True
    numbers = [row["number"] for row in listed["rows"]]
    assert numbers[0] == 106 and 7 in numbers and CORE_PULL not in numbers
    seven = next(row for row in listed["rows"] if row["number"] == 7)
    assert seven["title"] and seven["author"] and seven["updated_at"] and seven["head_oid"]


def _search(_built: Built, result: Invocation) -> None:
    assert [row["number"] for row in answer(result)["rows"]][:1] == [7]


def _row_lines(_built: Built, result: Invocation) -> None:
    rows = {row["number"]: row for row in answer(result)["rows"]}
    assert (rows[7]["state"], rows[7]["listed_from"], rows[7]["files"]) == (
        "listed",
        "comparison",
        len(CHANGED),
    )
    assert (rows[TREE_PULL]["state"], rows[TREE_PULL]["listed_from"]) == ("listed", "github")
    assert rows[TREE_PULL]["files"] == 249


def _row_readiness(_built: Built, result: Invocation) -> None:
    # A row's verdict is the status kept for its head, the page's read's here, judged on
    # the lifecycle its catalog row names.
    rows = {row["number"]: row for row in answer(result)["rows"]}
    for number in (7, 10):
        row = rows[number]
        assert row["state"] == "status" and row["status"]["head"] == row["head"]
        assert row["lifecycle"] in {"open", "draft"} and row["readiness"]["head"] == row["head"]


def _file_tree(_built: Built, result: Invocation) -> None:
    listed = answer(result)
    assert (listed["state"], listed["complete"]) == ("current", True)
    assert tuple(row["path"] for row in listed["rows"]) == CHANGED


def _stacks(_built: Built, result: Invocation) -> None:
    snapshot = answer(result)
    assert snapshot["state"] in {"current", "stale"} and snapshot["complete"] is True
    assert [(stack["number"], stack["pulls"]) for stack in snapshot["stacks"]] == [
        (STACK, [7, TREE_PULL]),
        (LONE_STACK, [LONE_PULL]),
    ]


def _stack_line(_built: Built, result: Invocation) -> None:
    line = answer(result)
    assert (line["state"], line["pulls"], line["pending"]) == ("current", [7, TREE_PULL], [])
    assert line["files"] > len(CHANGED)


def _header(built: Built, result: Invocation) -> None:
    envelope = answer(result)
    assert envelope["record_revision"] == built.revision
    pull = envelope["record"]["pull"]
    assert pull["title"] and pull["author"] and pull["head"]["ref"] and pull["base"]["ref"]
    assert [(label["name"], label["color"]) for label in pull["labels"]] == [
        ("enhancement", "2700af")
    ]


def _checks(_built: Built, result: Invocation) -> None:
    # The checks are the status's, kept beside the record, and drawn from disk with it.
    envelope = answer(result)
    head = envelope["record"]["pull"]["head"]["sha"]
    assert envelope["checks"]["items"] and envelope["checks"]["head"] == head
    assert envelope["status"]["head"] == head and envelope["readiness"]["head"] == head
    assert "check_runs" not in envelope["record"]


def _reviews(_built: Built, result: Invocation) -> None:
    record = answer(result)["record"]
    assert len(record["reviews"]) == 2 and len(record["review_comments"]) == 2
    assert len(record["issue_comments"]) == 1


def _core(built: Built, result: Invocation) -> None:
    envelope = answer(result)
    preview = envelope["core_preview"]
    assert envelope["record"] is None and preview is not None
    assert (preview["number"], preview["pull"]["body"]) == (CORE_PULL, built.core_body)
    assert preview["pull"]["title"] and preview["pull"]["author"]


def _labels(_built: Built, result: Invocation) -> None:
    labels = answer(result)
    assert labels["state"] in {"current", "stale"} and labels["complete"] is True
    assert [label["name"] for label in labels["labels"]] == ["enhancement", "invalid", "bug"]


def _markdown(built: Built, result: Invocation) -> None:
    rendered = answer(result)
    assert (rendered["record_revision"], rendered["part"]) == (built.revision, "body")
    assert rendered["html"].strip()


def _guided(built: Built, result: Invocation) -> None:
    guide = answer(result)
    assert (guide["record_revision"], guide["state"], guide["step_count"]) == (
        built.revision,
        "ready",
        2,
    )
    reference = guide["references"][0]
    assert reference["path"] == "src/app.txt"
    (hunk,) = reference["hunks"]
    assert [(line["op"], line["text"]) for line in hunk["lines"]] == [
        ("context", "one"),
        ("add", "two"),
    ]


def _timeline(built: Built, result: Invocation) -> None:
    timeline = answer(result)
    assert (timeline["record_revision"], timeline["state"]) == (built.revision, "complete")
    kinds = [event["kind"] for event in timeline["events"]]
    assert kinds == ["commit", "comment", "commit", "review"]


def _summary(_built: Built, result: Invocation) -> None:
    totals = answer(result)["manifest"]["totals"]
    assert (totals["files"], totals["additions"], totals["deletions"]) == TOTALS


def _changes(_built: Built, result: Invocation) -> None:
    comparison = answer(result)
    paths = [change["new"]["path"] for change in comparison["manifest"]["files"]]
    assert tuple(paths) == CHANGED and sorted(comparison["patches"]) == ["f1", "f2"]


def _image(_built: Built, result: Invocation) -> None:
    # The fixture's head holds no image, so a text file is the path: the route resolves it
    # in the head's tree and sizes it, then refuses it as no image it shows.
    assert "status: 415\n" in result.stdout, result.stdout[-400:]
    assert '"code": "unsupported_image"' in result.stdout


def _size(_built: Built, result: Invocation) -> None:
    size = answer(result)["size"]
    assert size["state"] == "measured" and size["pushed_bytes"] > 0 and size["diff_bytes"] > 0


def _rendered(_built: Built, result: Invocation) -> None:
    rendered = answer(result)
    assert rendered["status"] == "ready" and rendered["blocks"]


def _stack_waiting(_built: Built, result: Invocation) -> None:
    page = answer(result)
    assert (page["state"], page["pending"], page["comparison"]) == ("pending", [TREE_PULL], None)
    seven, tree = page["members"]
    assert (seven["number"], seven["state"], seven["pending"]) == (7, "open", False)
    assert seven["title"] and seven["head"]
    assert (tree["number"], tree["head"], tree["pending"]) == (TREE_PULL, None, True)


def _stack_header(built: Built, result: Invocation) -> None:
    page = answer(result)
    assert (page["state"], page["pending"], page["lacking"]) == ("current", [], [])
    assert page["comparison"]["route"] == built.stack_comparison_route
    assert page["totals"]["files"] == len(page["files"]) > 0
    for file in page["files"]:
        assert file["layers"] == [{"number": LONE_PULL, "place": 1, "path": file["path"]}]


def _stack_changes(_built: Built, result: Invocation) -> None:
    comparison = answer(result)
    files = comparison["manifest"]["files"]
    assert files and len(comparison["patches"]) == len(files)


_APP: Final = GitPath.from_display("src/app.txt").to_wire()
# The comparison route reads the manifest from the bank, checks the store answers for both
# commits and their merge base, and prints the first files' hunks in one diff run.
_COMPARES: Final = frozenset({"rev-parse", "merge-base", "diff"})

ELEMENTS: Final[tuple[Drawn, ...]] = (
    Drawn("Rows: state, title, author, age", "Pulls tab", "pulls", _fixed("state=open"), _rows),
    Drawn("Quick Search completion", "shell", "pulls", _fixed("q=7"), _search),
    Drawn(
        "Row change line",
        "Pulls tab",
        "pull-files-summary",
        _fixed(f"numbers=7,{TREE_PULL}"),
        _row_lines,
    ),
    Drawn("Row changed files", "Pulls tab", "pull-files", _fixed("number=7"), _file_tree),
    Drawn("Row readiness", "Pulls tab", "pull-statuses", _fixed("numbers=7,10"), _row_readiness),
    Drawn("Stack rows and stack menu", "both", "stacks", _fixed(""), _stacks),
    Drawn("Stack change line", "Pulls tab", "stack-change", _fixed(f"number={STACK}"), _stack_line),
    Drawn(
        "Header: title, author, branches, labels", "PR page", "pull", _fixed("number=7"), _header
    ),
    Drawn("Checks", "PR page", "pull", _fixed("number=7"), _checks),
    Drawn("Reviews and comments", "PR page", "pull", _fixed("number=7"), _reviews),
    Drawn("Core before a record", "PR page", "pull", _fixed(f"number={CORE_PULL}"), _core),
    # The labels route is the CLI's read of the set. The page colors a chip from its record,
    # and a label a record names without a color from the envelope's `repository_labels`.
    Drawn("Label set", "CLI", "labels", _fixed(""), _labels),
    Drawn(
        "Description Markdown", "PR page", "pull-markdown", _fixed("number=7&part=body"), _markdown
    ),
    Drawn("Conversation timeline", "PR page", "pull-timeline", _fixed(""), _timeline),
    Drawn(
        "Guided Review excerpts", "PR page", "guided-review", _fixed("number=7"), _guided, _COMPARES
    ),
    Drawn(
        "Diff summary",
        "PR page",
        "pull-comparison",
        lambda built: built.comparison_route,
        _summary,
        _COMPARES,
    ),
    Drawn(
        "Changes: files and first hunks",
        "PR page",
        "pull-comparison",
        lambda built: built.comparison_route,
        _changes,
        _COMPARES,
    ),
    Drawn(
        "Image in a rendered Markdown file",
        "PR page",
        "pull-image",
        lambda built: f"{built.image_route}&path={_APP}",
        _image,
        # The pair is admitted from the record; the path is resolved in the head's tree.
        frozenset({"rev-parse", "cat-file"}),
        status=415,
    ),
    Drawn(
        "Rendered Markdown redline",
        "PR page",
        "pull-rendered-diff",
        lambda built: f"{built.rendered_route}&file=f1",
        _rendered,
        # The comparison's manifest from the bank, then both sides rendered off the loop.
        _COMPARES,
    ),
    Drawn(
        "Size line: what the comparison pushes",
        "PR page",
        "pull-size",
        lambda built: built.size_route,
        _size,
        # The pair's merge base alone: the refresh that listed the files from the store
        # measured the size and kept it beside the store, where this reads it.
        frozenset({"merge-base"}),
    ),
    Drawn(
        "Members while one is pending",
        "Stack page",
        "stack",
        _fixed(f"number={STACK}"),
        _stack_waiting,
    ),
    Drawn(
        "Members, totals, and each file's layers",
        "Stack page",
        "stack",
        _fixed(f"number={LONE_STACK}"),
        _stack_header,
        # Whether the top's history holds the bottom's merge base, and both commits checked
        # in the store before the kept manifest of the combined comparison is read.
        frozenset({"merge-base", "rev-parse"}),
    ),
    Drawn(
        "Diff summary, Docs, and Changes",
        "Stack page",
        "stack-comparison",
        lambda built: built.stack_comparison_route,
        _stack_changes,
        _COMPARES,
    ),
)

# Every other route, and why it draws nothing a reader sees: each starts or reports work.
JOBS: Final[dict[str, str]] = {
    "pull-refresh": "starts the record's refresh, which reads GitHub and fetches the head",
    "pull-cores-prepare": "starts a batch of cores, one GraphQL read",
    "pulls-refresh": "starts the catalog's scan, and the scan of every open pull request's status",
    "pull-files-refresh": "starts a changed-files list's refresh",
    "stacks-refresh": "starts the stack snapshot's read",
    "labels-refresh": "starts the label set's read",
    "pulls-prefetch": "reports or replaces the background lane's queue, from memory",
    "cache-clear": "removes the plugin's files for the repository",
    "status": "runs gh auth status, the GitHub status check, which reads no repository",
    "gh-requests": "reports what the event log says was asked of GitHub, which reads no repository",
}


@pytest.mark.parametrize("drawn", [pytest.param(d, id=d.element) for d in ELEMENTS])
def test_a_drawn_element_answers_from_disk_with_the_network_refused(
    drawn: Drawn, built: Built, offline: Spawns
) -> None:
    ran = run_offline(offline, drawn.args(built))
    expected = 0 if drawn.status == 200 else 1
    assert ran.result.exit_code == expected, (ran.result.stdout[-2000:], ran.result.stderr[-2000:])
    assert (ran.network, ran.gh, ran.sockets) == ([], [], []), "the route reached for the network"
    assert ran.git == drawn.computes, (drawn.element, sorted(ran.git))
    # A comparison's list of files is the manifest on disk, never Git's raw listing again.
    assert not any("--raw" in argv or "--numstat" in argv for argv in ran.git_args)
    drawn.check(built, ran.result)


def test_every_route_is_drawn_from_disk_or_a_job() -> None:
    """A route the manifest mounts is an element above, or starts or reports work."""

    hooks = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["data_hook"]
    routes = {hook["route"] for hook in hooks}
    drawn = {element.route for element in ELEMENTS}
    assert not drawn & JOBS.keys()
    assert routes == drawn | JOBS.keys(), (
        routes - drawn - JOBS.keys(),
        (drawn | JOBS.keys()) - routes,
    )


def test_a_diff_summary_answers_from_disk_after_the_build_changed(
    built: Built, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A kept manifest names its schema and its listing, not the build that wrote it.

    Another tag in every module that holds one is what an upgrade, or any edit of the
    source of an editable install, does to the build (``http_caching.py``): the record
    names a comparison route of the new build, and the manifest the old one kept answers.
    """

    tag = http_caching.BUILD_TAG
    for module in list(sys.modules.values()):
        if getattr(module, "BUILD_TAG", None) == tag:
            monkeypatch.setattr(module, "BUILD_TAG", "0" * 12)
    spawns = _offline(monkeypatch, built.root)
    envelope = answer(run_offline(spawns, ["--api", f"{ROUTES}/pull?number=7"]).result)
    route = envelope["comparison_route"]
    assert "build=000000000000" in route and route != built.comparison_route
    ran = run_offline(spawns, ["--api", route])
    assert (ran.result.exit_code, ran.network, ran.gh, ran.sockets) == (0, [], [], [])
    assert ran.git == _COMPARES, sorted(ran.git)
    assert not any("--raw" in argv for argv in ran.git_args), "the manifest was listed again"
    _summary(built, ran.result)


def test_every_pull_requests_diff_summary_answers_from_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Each pull request keeps its own manifest, so preparing one replaces no other's.

    The bank was sixteen direct-mapped slots, where a repository's next pull requests
    replaced each other's manifests, and one replaced was listed by Git again.
    """

    origin = build_origin(tmp_path / "origin")
    numbers = (7, 8, 10)
    with pytest.MonkeyPatch.context() as online:
        _online(online, tmp_path, origin, files_scenario(origin))
        for number in numbers:
            fetched = run_metab([f"{CANONICAL}/pull/{number}", "--no-serve"])
            assert fetched.exit_code == 0, fetched.stderr
        routes = {
            number: run_metab([CANONICAL, "--api", f"{ROUTES}/pull?number={number}"]).payload()[
                "comparison_route"
            ]
            for number in numbers
        }
    pairs = {route.partition("&left=")[2].partition("&store=")[0] for route in routes.values()}
    assert len(pairs) == len(numbers), routes
    spawns = _offline(monkeypatch, tmp_path)
    for number, route in routes.items():
        # A fresh process for each, so no comparison answers from another's memory.
        monkeypatch.setattr(diff_sidekick, "_COMPARISONS", ComparisonCache())
        ran = run_offline(spawns, ["--api", route])
        assert (ran.result.exit_code, ran.network, ran.gh, ran.sockets) == (0, [], [], []), number
        assert answer(ran.result)["manifest"]["files"], number
        assert not any("--raw" in argv for argv in ran.git_args), f"{number} was listed again"


# ── Gaps: what a surface draws that does not answer from disk ──────────────────────


def _avatar_gap(built: Built, patch: pytest.MonkeyPatch, _tmp: Path) -> None:
    spawns = _offline(patch, built.root)
    ran = run_offline(spawns, ["--api", f"{ROUTES}/pull?number=7"])
    url = answer(ran.result)["record"]["pull"]["author_avatar_url"]
    rows = answer(run_offline(spawns, ["--api", f"{ROUTES}/pulls?state=open"]).result)["rows"]
    urls = [url, *(row["author_avatar_url"] for row in rows if row["author_avatar_url"])]
    assert KEPT_AVATAR in urls
    if not all(each.startswith("/") for each in urls):
        raise StillAGap("the image is GitHub's, held only by the browser's HTTP cache")


@dataclass(frozen=True)
class Gap:
    """An element that does not answer from disk, and why."""

    element: str
    why: str
    check: Callable[[Built, pytest.MonkeyPatch, Path], None]


GAPS: Final[tuple[Gap, ...]] = (
    Gap(
        "Avatars on the page and in the rows",
        "Records and the catalog keep only the URL; the image is fetched from "
        "avatars.githubusercontent.com and only the browser's HTTP cache keeps it "
        "(the pull request's chrome in docs/design-system.md).",
        _avatar_gap,
    ),
)


@pytest.mark.parametrize(
    "gap",
    [
        pytest.param(
            gap,
            id=gap.element,
            marks=pytest.mark.xfail(strict=True, raises=StillAGap, reason=gap.why),
        )
        for gap in GAPS
    ],
)
def test_a_gap_still_does_not_answer_from_disk(
    gap: Gap, built: Built, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gap.check(built, monkeypatch, tmp_path)


def test_the_guard_sees_and_refuses_the_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The guard is not vacuous: an empty home's first command reaches for both."""

    spawns = _offline(monkeypatch, tmp_path)
    _allow_installed_git(monkeypatch)
    result = run_metab([CANONICAL, "--api", "/api/identity"])
    seen = spawns.take()
    assert result.exit_code != 0, result.stdout
    assert any(_is(argv, "gh") for argv in seen), seen
    assert any(_is(argv, "git") and git_verb(argv) in NETWORK_VERBS for argv in seen), seen
    assert spawns.refused > 0, "no Git transport command was refused"
    with pytest.raises(OSError, match="refused here"):
        socket.create_connection(("github.com", 443), timeout=1)
    with socket.socket(socket.AF_INET) as sock, pytest.raises(OSError, match="refused here"):
        sock.connect(("140.82.112.3", 443))
    assert spawns.sockets[-2:] == ["github.com", "140.82.112.3"]
