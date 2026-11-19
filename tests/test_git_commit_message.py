"""A commit message's body as Markdown: ``GET /api/git/commit-markdown/{revision}``.

The route renders a body through the path a pull request's description takes, KPress in
the Markdown child and the inert allowlist (``src/metabrowser/git/message.py``). These
tests serve real repositories through the mounted application and check what a commit
body is: hard-wrapped prose reflowing, lists, indented and fenced code, Git's trailers
split off as written, ``#123`` and bare URLs left as text, HTML as safe as in a
description, links kept only when absolute, and the size bound a description has.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import kpress_adapter, paths_safe
from metabrowser.builtin_plugins.github.pull_record import MAX_BODY_BYTES
from metabrowser.diff.markdown_projection_worker import InertRenderRefused
from metabrowser.git import repo as git_repo
from metabrowser.git.message import COMMIT_MESSAGE_LINK_BASE, split_trailers
from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from metabrowser.inert_html import harden
from metabrowser.server import app
from metabrowser.settings import GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES
from tests.github_pull_fixture import allowlist_violations
from tests.required_tools import needs_git

pytestmark = needs_git

ROUTE = "/api/git/commit-markdown/"

# A body as people write them: prose hard-wrapped at 72 columns, lists of both markers, an
# issue reference and a bare URL, inline HTML and a script, indented and fenced code, links
# absolute and relative, an image, and Git's trailers.
BODY = """\
The app counted to one. This change wraps its prose at seventy-two
columns, as a commit body does, and the page reflows it into one
paragraph.

- a bullet that wraps onto
  a second line
- another, which fixes #12; see https://example.com/issue

* a star bullet with <b>bold</b> and <span onclick="alert(1)">a handler</span>
<script>alert(1)</script>

An indented example follows:

    indented code stays code

```python
def fenced():
    return "code stays code"
```

A [link](https://example.com/doc), a [relative one](docs/x.md), a
[fragment](#top), a [protocol-relative one](//evil.test/x), and an
![image](https://example.com/i.png).

Signed-off-by: Test Author <test@example.com>
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
"""


def _git(root: Path, *args: str, stdin: str | None = None) -> str:
    """Run git in *root* with a pinned identity and none of the host's configuration."""

    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture Committer",
            "GIT_COMMITTER_EMAIL": "committer@example.invalid",
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        env=env,
        text=True,
        input=stdin,
    ).stdout.strip()


def _commit(root: Path, message: str) -> str:
    """Commit *message* as written (no cleanup), and return the commit's ID."""

    _git(root, "commit", "-q", "--allow-empty", "--cleanup=verbatim", "-F", "-", stdin=message)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def served(tmp_path: Path) -> Iterator[Path]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "a.txt").write_text("a\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "first commit")
    paths_safe._set_root_dir(root)
    git_repo.clear_repo_cache()
    try:
        yield root
    finally:
        git_repo.clear_repo_cache()


def _answer(revision: str) -> tuple[int, dict[str, Any]]:
    with TestClient(app) as client:
        response = client.get(ROUTE + revision)
    return response.status_code, response.json()


# ── Trailers ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("body", "prose", "trailers"),
    [
        pytest.param(
            "Prose.\n\nSigned-off-by: A <a@example.com>\nCo-Authored-By: B <b@example.com>",
            "Prose.",
            "Signed-off-by: A <a@example.com>\nCo-Authored-By: B <b@example.com>",
            id="a trailer block",
        ),
        pytest.param(
            "Prose.\n\nReviewed-by: A <a@example.com>\n  and a value folded under it",
            "Prose.",
            "Reviewed-by: A <a@example.com>\n  and a value folded under it",
            id="a folded value",
        ),
        pytest.param(
            "Prose.\n\nSigned-off-by: A <a@example.com>\n(cherry picked from commit 0123abcd)",
            "Prose.",
            "Signed-off-by: A <a@example.com>\n(cherry picked from commit 0123abcd)",
            id="git's cherry-pick note",
        ),
        pytest.param(
            "Signed-off-by: A <a@example.com>", "", "Signed-off-by: A <a@example.com>", id="only"
        ),
        pytest.param(
            "Prose.\n\nSigned-off-by: A <a@example.com>\nand a line of prose",
            "Prose.\n\nSigned-off-by: A <a@example.com>\nand a line of prose",
            "",
            id="a last paragraph with prose in it",
        ),
        pytest.param(
            "Prose.\n\nhttps://example.com/x", "Prose.\n\nhttps://example.com/x", "", id="a URL"
        ),
        pytest.param(
            "Prose.\n\n- Fixes: a bullet", "Prose.\n\n- Fixes: a bullet", "", id="a list item"
        ),
        pytest.param(
            "Prose.\n\n  indented: not a trailer",
            "Prose.\n\n  indented: not a trailer",
            "",
            id="a continuation with no trailer",
        ),
        pytest.param("Just prose.", "Just prose.", "", id="no trailers"),
        pytest.param("", "", "", id="empty"),
    ],
)
def test_split_trailers_takes_the_last_paragraph_only_when_every_line_is_a_trailer(
    body: str, prose: str, trailers: str
) -> None:
    assert split_trailers(body) == (prose, trailers)


# ── The route ────────────────────────────────────────────────


def test_a_commit_body_renders_as_a_pull_request_description_does(served: Path) -> None:
    revision = _commit(served, "feat: teach the app to count\n\n" + BODY)
    status, answer = _answer(revision)
    assert status == 200, answer
    html = answer["html"]
    assert answer["revision"] == revision and answer["is_repo"] is True

    # The path a description takes: KPress's sanitized render, plain code, and the allowlist
    # against the commit's base, as the Markdown child makes it.
    prose, trailers = split_trailers(BODY.strip())
    rendered = kpress_adapter.render_kpress_view(
        source_text=prose,
        source_path="commit.md",
        kind="markdown",
        view="document",
        ext=".md",
        mtime_hash="test-commit-message",
        size=len(prose.encode()),
        include_toc="off",
        plain_code=True,
    )
    assert html == harden(str(rendered["html"]), COMMIT_MESSAGE_LINK_BASE)
    assert answer["link_base"] == COMMIT_MESSAGE_LINK_BASE
    assert answer["assets"] == kpress_adapter.document_stylesheets()

    # Wrapped prose is one paragraph: its newlines are soft breaks, not <br>.
    assert (
        "<p>The app counted to one. This change wraps its prose at seventy-two\n"
        "columns, as a commit body does, and the page reflows it into one\n"
        "paragraph.</p>"
    ) in html
    assert "<br" not in html
    # Both list markers make lists, and a wrapped item stays one item.
    assert "<li>a bullet that wraps onto\na second line</li>" in html
    assert html.count("<ul>") == 2
    # #123 and a bare URL stay text, as in a description: KPress links neither.
    assert "fixes #12; see https://example.com/issue</li>" in html
    # Indented and fenced code stay code, plain.
    assert "<pre><code>indented code stays code\n</code></pre>" in html
    assert '<pre><code>def fenced():\n    return "code stays code"\n</code></pre>' in html
    # HTML is as safe as in a description: allowed markup kept, its attributes and scripts
    # gone.
    assert "<b>bold</b>" in html
    assert allowlist_violations(html) == []
    for gone in ("<script", "alert(1)", "onclick", "<img"):
        assert gone not in html, gone
    # Only an absolute http(s) link keeps its address; a relative one, a fragment, and a
    # protocol-relative one keep their text. An image becomes a link to its address.
    assert (
        '<a href="https://example.com/doc" target="_blank" rel="noopener noreferrer">link</a>'
    ) in html
    for text in ("relative one", "fragment", "protocol-relative one"):
        assert f"<a>{text}</a>" in html, text
    assert (
        '<a href="https://example.com/i.png" target="_blank" rel="noopener noreferrer">image</a>'
    ) in html
    # The trailers are answered as written and are not in the prose.
    assert (
        answer["trailers"]
        == trailers
        == (
            "Signed-off-by: Test Author <test@example.com>\n"
            "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
        )
    )
    assert "Signed-off-by" not in html and "Co-Authored-By" not in html
    # The subject is the page's heading, never part of the body.
    assert "teach the app" not in html


def test_a_body_of_only_trailers_renders_nothing(served: Path) -> None:
    revision = _commit(served, "chore: sign\n\nSigned-off-by: A <a@example.com>\n")
    status, answer = _answer(revision)
    assert status == 200
    assert (answer["html"], answer["trailers"]) == ("", "Signed-off-by: A <a@example.com>")


def test_a_commit_with_no_body_answers_an_empty_one(served: Path) -> None:
    status, answer = _answer(_commit(served, "just a subject\n"))
    assert status == 200
    assert (answer["html"], answer["trailers"]) == ("", "")


def test_the_bound_is_a_pull_request_descriptions(served: Path) -> None:
    """Past it a body is refused whole, and the page shows the message as written."""

    assert GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES == MAX_BODY_BYTES
    line = "a hard-wrapped line of a very long commit body, seventy-odd columns\n"
    at_bound = line * (GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES // len(line))
    status, _answer_at = _answer(_commit(served, "at the bound\n\n" + at_bound))
    assert status == 200
    past = at_bound + line
    status, answer = _answer(revision := _commit(served, "past the bound\n\n" + past))
    assert status == 422
    assert answer == {
        "error": (
            f"the message is {len(past.strip().encode())} bytes, more than the "
            f"{GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES} rendered as Markdown"
        ),
        "code": "body_too_large",
        "max_bytes": GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES,
        "revision": revision,
    }


def test_trailers_do_not_count_toward_the_bound(served: Path) -> None:
    line = "x" * 71 + "\n"
    prose = line * (GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES // len(line))
    trailers = "".join(f"Signed-off-by: Person {n} <p{n}@example.com>\n" for n in range(200))
    status, answer = _answer(_commit(served, "subject\n\n" + prose + "\n" + trailers))
    assert status == 200
    assert answer["trailers"] == trailers.strip()


def test_a_refused_render_answers_why_with_the_revision(
    served: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.diff import markdown_projection_worker

    async def refuse(_self: object, _request: object) -> dict[str, Any]:
        raise InertRenderRefused("render_deadline")

    monkeypatch.setattr(markdown_projection_worker.ProjectionWorker, "render_inert", refuse)
    revision = _commit(served, "subject\n\nsome prose\n")
    status, answer = _answer(revision)
    assert status == 422
    assert answer["code"] == "render_deadline"
    assert answer["revision"] == revision


@pytest.mark.parametrize("revision", ["HEAD", "abc1234", "0" * 39, "--upload-pack=x"])
def test_anything_but_a_full_commit_id_is_refused(served: Path, revision: str) -> None:
    status, answer = _answer(revision)
    assert (status, answer["code"]) == (400, "revision_not_full")


def test_an_unknown_commit_and_an_object_that_is_not_one_are_not_found(served: Path) -> None:
    blob = _git(served, "rev-parse", "HEAD:a.txt")
    for revision in ("0" * 40, blob):
        status, answer = _answer(revision)
        assert (status, answer) == (404, {"error": "unknown revision", "code": "commit_not_found"})


def test_a_folder_that_is_not_a_repository_answers_the_negative_envelope(tmp_path: Path) -> None:
    paths_safe._set_root_dir(tmp_path)
    git_repo.clear_repo_cache()
    try:
        status, answer = _answer("0" * 40)
    finally:
        git_repo.clear_repo_cache()
    assert status == 200
    assert answer["is_repo"] is False
