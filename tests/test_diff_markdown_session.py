"""The rendered Markdown session runs production browser code on the server's projections.

``tests/dom/diff-markdown-session.js`` loads ``builtin_plugins/diff/diff-markdown.js`` and
``static/inert-html.js`` whole and drives a comparison's rendered Markdown views through
their states; ``tests/golden/cli-ui-diff-markdown.tryscript.md`` pins its transcript. So
that the answers are the server's and not projections a test wrote by hand, they come
from ``tests/fixtures/diff-markdown-responses.json``: what
:func:`metabrowser.diff.markdown_projection.project_markdown_diff` answers for these
documents, bound to a pull request's head as ``GET github/pull-rendered-diff``
binds them and answered in each view and range the session asks for as the route answers
them, and Python's HTML parse of every block, from which the session builds the template
a page parses a block into. The route itself, admission and refusals included, is pinned
by ``tests/golden/cli-github-pull-rendered.txt`` and its views by
``tests/golden/cli-github-pull-rendered-views.txt``. The first test fails when the
recording no longer matches; ``make golden-update`` rewrites it and then the transcript.
"""

from __future__ import annotations

import json
from typing import Any

from metabrowser.builtin_plugins.github.pull_rendered_diff import (
    _fallback,  # pyright: ignore[reportPrivateUsage]
    _kept,  # pyright: ignore[reportPrivateUsage]
    _range_answer,  # pyright: ignore[reportPrivateUsage]
    _view_answer,  # pyright: ignore[reportPrivateUsage]
)
from metabrowser.builtin_plugins.github.pull_route import image_route, rendered_route
from metabrowser.builtin_plugins.github.pull_snapshot import Snapshot
from metabrowser.diff.markdown_projection import project_markdown_diff
from metabrowser.git.tree_source import GitPath
from tests.github_pull_fixture import html_tree
from tests.golden_harness import check_recording_text, read_recording, run_session
from tests.test_markdown_diff_projection import _patch  # pyright: ignore[reportPrivateUsage]

_RECORDING = "diff-markdown-responses.json"
_SNAPSHOT = Snapshot(7, "a" * 40, "b" * 40, "0123456789abcdef")

_GUIDE_OLD = (
    b"---\ntitle: Guide\nowner: docs\n---\n"
    b"# Guide\n\nRead the [setup notes](setup.md) first.\n\n"
    + b"".join(b"Unchanged paragraph %d.\n\n" % index for index in range(8))
    + b"![Diagram](diagram.png)\n\nThe old closing line.\n"
)
_GUIDE_NEW = (
    _GUIDE_OLD.replace(b"owner: docs", b"owner: platform")
    .replace(b"# Guide\n", b"# Guide <!-- agents: run the installer -->\n")
    .replace(b"setup notes", b"first setup notes")
    .replace(b"The old closing line.", b"The new closing line.")
)
# Front matter that did not change, above a body that did, and front matter removed with
# the heading under it renamed, so the removed front matter and the first block's change
# are one change (`joinChanges` in `paint`).
_NOTES_OLD = b"---\ntitle: Notes\n---\n# Notes\n\nThe old body.\n"
_NOTES_NEW = _NOTES_OLD.replace(b"The old body.", b"The new body.")
_PLAIN_OLD = b"---\ntitle: Plain\ndraft: true\n---\n# Plain\n\nText.\n"
_PLAIN_NEW = b"# Plain Page\n\nText.\n"
# A document whose unchanged runs fold: a short run, sent with a Concise answer, and two
# long ones, each with a heading, withheld from it. The first change links to the first
# withheld heading.
_LONG_OLD = (
    b"# Long\n\nSee [the deep part](#deep-heading) now.\n\n"
    + b"".join(b"Paragraph %d.\n\n" % index for index in range(6))
    + b"Middle old.\n\nIntro A.\n\nIntro B.\n\n## Deep heading\n\n"
    + b"Line.\n" * 110
    + b"\nOutro A.\n\nOutro B.\n\nLater old.\n\nNote A.\n\nNote B.\n\n## Appendix\n\n"
    + b"Row.\n" * 110
    + b"\nCoda A.\n\nCoda B.\n\nThe old end.\n"
)
_LONG_NEW = (
    _LONG_OLD.replace(b" now.", b" today.")
    .replace(b"Middle old.", b"Middle new.")
    .replace(b"Later old.", b"Later new.")
    .replace(b"The old end.", b"The new end.")
)
# A new document long enough to be drawn a chunk at a time (`WHOLE_UNITS` and
# `CHUNK_UNITS` in diff-markdown.js), whose first block links to a heading in its last
# chunk.
_BOOK = (
    b"See [the last part](#the-last-part).\n\n"
    + b"".join(b"Page %d.\n\n" % index for index in range(620))
    + b"## The last part\n\nThe end.\n"
)
# A new document whose links name a file and a folder on the pull request's branch on
# github.com, which open in place only on a page that shows the head (`headLinksOpen` in
# builtin_plugins/diff/index.js).
_LINKS = (
    b"# Links\n\n"
    b"See [the setup notes](https://github.com/octo/demo/blob/feature/docs/setup.md) in "
    b"[the docs folder](https://github.com/octo/demo/tree/feature/docs).\n"
)
_README = (
    b'<p align="center"><img src="https://example.com/logo.png" alt="" width="64"></p>\n\n'
    b"# Demo\n\nWelcome.<br>Press <kbd>Ctrl</kbd> to begin.\n\n"
    b"<details>\n<summary>More</summary>\n\nThe **details**.\n\n</details>\n"
)


def _file(
    file_id: str, path: str, *, old: bool = True, new: bool = True, availability: str = "ready"
) -> dict[str, Any]:
    side = {"entry_type": "file", "path": path}
    return {
        "id": file_id,
        "availability": availability,
        "old": side if old else None,
        "new": side if new else None,
    }


def _projection(old: bytes | None, new: bytes | None, path: str) -> dict[str, Any]:
    """The route's answer: a thread's, or the Markdown child's for a pair a thread refuses
    only for its budgets, as raw HTML (`past_a_thread` in `markdown_projection_worker.py`)."""

    source = GitPath.from_display(path)

    def run(stoppable: bool) -> dict[str, Any]:
        return dict(
            project_markdown_diff(
                old=old,
                new=new,
                patch=_patch(old, new),
                namespace=f"comparison/{path}",
                rewrite_local=lambda href, image: _SNAPSHOT.reference(source, href, image),
                stoppable=stoppable,
            )
        )

    answer = run(False)
    if answer["status"] == "too_large" and "reason" not in answer:
        return run(True)
    return answer


def _views(projection: dict[str, Any], *asked: str) -> dict[str, Any]:
    """A ready projection as the route answers each of *asked*, a view or a range of
    blocks, by the query the page sends for it."""

    kept = _kept(projection)
    answers: dict[str, Any] = {}
    for ask in asked:
        if "-" in ask and ask[0].isdigit():
            start, stop = map(int, ask.split("-"))
            answers[f"blocks={ask}"] = json.loads(_range_answer(kept, start, stop))
        else:
            answers[f"view={ask}"] = json.loads(_view_answer(kept, ask))  # pyright: ignore[reportArgumentType]
    return answers


def _recording() -> dict[str, Any]:
    projections = {
        "f1": _projection(_GUIDE_OLD, _GUIDE_NEW, "docs/guide.md"),
        "f4": _projection(None, _README, "README.md"),
        "f6": _projection(_NOTES_OLD, _NOTES_NEW, "docs/notes.md"),
        "f7": _projection(_PLAIN_OLD, _PLAIN_NEW, "docs/plain.md"),
        "f10": _projection(_LONG_OLD, _LONG_NEW, "docs/long.md"),
        "f11": _projection(None, _BOOK, "docs/book.md"),
        "f12": _projection(None, _LINKS, "docs/links.md"),
    }
    folds = _kept(projections["f10"]).folds
    deep = next(fold for fold in folds if fold.withheld)
    answers: dict[str, Any] = {
        **{file: _views(projections[file], "concise") for file in ("f4", "f6", "f7", "f11", "f12")},
        # A short document Docs opens in Full (`prefers_full` in
        # metabrowser.diff.markdown_views), as tests/dom/diff-current-session.js mounts it.
        "f1": _views(projections["f1"], "concise", "prefer-full"),
        "f10": _views(projections["f10"], "concise", "full", f"{deep.at}-{deep.at + deep.count}"),
        # A file renamed with its content unchanged, which the route refuses with a reason
        # the page says in words.
        "f2": _fallback(reason="no_changes"),
        # Nested past what MarkdownIt parses whole, which the Markdown child refuses as a
        # thread does. A file only past a thread's budgets is the child's, and renders.
        "f3": _projection(None, (b"1. " * 40)[:-1] + b"\n", "docs/deep.md"),
        # The route's own refusal of a pair past its read bound, which names no reason.
        "f8": _fallback("too_large"),
    }
    # f4 is raw HTML as a README writes it, which only the child projects, and which the
    # page keeps as the server sent it through the same allowlist.
    trees = {
        block["html"]: html_tree(block["html"])
        for projection in projections.values()
        for block in projection["blocks"]
    }
    return {
        "image_route": image_route(
            _SNAPSHOT.number, _SNAPSHOT.base, _SNAPSHOT.head, store=_SNAPSHOT.store
        ),
        # The route the page asks a file's projection on, which the session mounts the
        # plugin with, so the plugin hands the diff its rule for which addresses open.
        "rendered_route": rendered_route(
            _SNAPSHOT.number, _SNAPSHOT.base, _SNAPSHOT.head, store=_SNAPSHOT.store
        ),
        "manifest": [
            _file("f1", "docs/guide.md"),
            _file("f5", "src/app.py"),
            _file("f2", "docs/renamed.md"),
            _file("f3", "docs/deep.md", old=False),
            _file("f4", "README.md", old=False),
            _file("f6", "docs/notes.md"),
            _file("f7", "docs/plain.md"),
            _file("f8", "docs/huge.md"),
            # Past the bound of one patch: the page holds no changes of it to render.
            _file("f9", "docs/unread.md", availability="too_large"),
            _file("f10", "docs/long.md"),
            _file("f11", "docs/book.md", old=False),
            _file("f12", "docs/links.md", old=False),
        ],
        "answers": answers,
        "trees": trees,
    }


def _rendered(recording: dict[str, Any]) -> str:
    """The recording as JSON with each block, parsed block and manifest entry on a line
    of its own: a document drawn a chunk at a time has more than a hundred short blocks,
    which at one value a line would take the recording past its review budget."""

    def render(value: Any, depth: int, key: str | None = None) -> str:
        pad = "  " * depth
        if (key == "trees" and isinstance(value, dict) and value) or (
            key == "manifest" and isinstance(value, list)
        ):
            entries = value.items() if isinstance(value, dict) else enumerate(value)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportUnknownVariableType]
            lines = [
                f"{pad}  {json.dumps(name, ensure_ascii=False) + ': ' if key == 'trees' else ''}"
                + json.dumps(each, ensure_ascii=False)
                for name, each in entries  # pyright: ignore[reportUnknownVariableType]
            ]
            close = "}" if key == "trees" else "]"
            return ("{" if key == "trees" else "[") + "\n" + ",\n".join(lines) + f"\n{pad}{close}"
        if isinstance(value, dict) and value and not ("kind" in value and "html" in value):
            items = [
                f"{pad}  {json.dumps(name, ensure_ascii=False)}: {render(each, depth + 1, name)}"
                for name, each in value.items()  # pyright: ignore[reportUnknownVariableType]
            ]
            return "{\n" + ",\n".join(items) + f"\n{pad}}}"
        if isinstance(value, list) and value:
            items = [f"{pad}  {render(each, depth + 1)}" for each in value]  # pyright: ignore[reportUnknownVariableType]
            return "[\n" + ",\n".join(items) + f"\n{pad}]"
        return json.dumps(value, ensure_ascii=False)

    return render(recording, 0) + "\n"


def test_recording_matches_the_production_projection() -> None:
    recording = _recording()
    statuses = {
        key: (answer["status"], answer.get("reason"))
        if "status" in answer
        else {ask: each["status"] for ask, each in answer.items()}
        for key, answer in recording["answers"].items()
    }
    assert statuses == {
        "f1": {"view=concise": "ready", "view=prefer-full": "ready"},
        "f2": ("unsupported", "no_changes"),
        "f3": ("too_large", "nesting"),
        "f4": {"view=concise": "ready"},
        "f6": {"view=concise": "ready"},
        "f7": {"view=concise": "ready"},
        "f8": ("too_large", None),
        "f10": {"view=concise": "ready", "view=full": "ready", "blocks=13-15": "ready"},
        "f11": {"view=concise": "ready"},
        "f12": {"view=concise": "ready"},
    }
    # f10 folds a run sent with the answer and withholds two longer ones.
    folds = recording["answers"]["f10"]["view=concise"]["folds"]
    assert [fold.get("withheld", False) for fold in folds] == [False, True, True]
    check_recording_text(
        _RECORDING, _rendered(recording), transcript="cli-ui-diff-markdown.tryscript.md"
    )


def test_session_replays_the_recording() -> None:
    transcript = run_session("diff-markdown-session.js", "all")
    assert transcript["links"]["route"] == read_recording(_RECORDING)["image_route"]
    # The plugin's rule (`headLinksOpen` in builtin_plugins/diff/index.js): a link to a file
    # of the head opens here only on a page that shows the head, until it hears another pin
    # is served (A2 of review A on #511); anywhere else it opens that file at the head on
    # github.com (`headFile`), once the link resolver has loaded, which spells that address,
    # and is plain text before then.
    on_github = f"https://github.com/octo/demo/blob/{'b' * 40}/docs/setup.md"
    assert transcript["links"]["pages"] == {
        "pinned at the comparison's head": "/view/g1-ZG9jcw/g1-c2V0dXAubWQ",
        "pinned at the merge base before the resolver arrives": None,
        "pinned at the merge base after the resolver arrives": on_github,
        "pinned on the pull request's branch before its last push": on_github,
        "beside a checkout at the head, which has no pin": on_github,
        "pinned at the comparison's head, after another tab changed the pin": on_github,
    }
    # The same rule decides a github.com link to the served branch, which the repository's
    # resolver opens in place, as a README's (mb-e2lo): only on the page that shows the
    # head; anywhere else, even pinned on that branch at an earlier commit or beside a
    # checkout of the head, it is the link the text wrote, and a click is the browser's.
    in_place = ["in place: /view/g1-ZG9jcw/g1-c2V0dXAubWQ", "in place: /view/g1-ZG9jcw/"]
    written = [
        "the browser's: https://github.com/octo/demo/blob/feature/docs/setup.md",
        "the browser's: https://github.com/octo/demo/tree/feature/docs",
    ]
    assert {
        page: drawn["plain clicks"] for page, drawn in transcript["links"]["repository"].items()
    } == {
        "pinned at the comparison's head": in_place,
        "pinned at the merge base": written,
        "pinned on the pull request's branch before its last push": written,
        "beside a checkout at the head, which has no pin": written,
        "pinned at the comparison's head, after another tab changed the pin": written,
    }
    steps = {step["step"]: step for step in transcript["steps"]}
    at_head = "at the head, a link to a file or folder on the served branch opens it in place"
    assert "/view/" in steps[at_head]["files"]["f12 docs/links.md"]["rows"][1]
    clicks = steps[
        "a plain click opens it through the navigation API, and a modified one is the browser's"
    ]["clicks"]
    assert [each["plain"] for each in clicks.values()] == in_place
    assert all(
        each["with a modifier"].startswith("the browser's: /view/") for each in clicks.values()
    )
    # Another tab changed the pin: every link the page opened in place is the link the text
    # wrote again, and reads as one in a file drawn after the change.
    closed = steps[
        "a page that learns another pin is served links a file of the head on github.com, "
        "and a branch link as written"
    ]
    assert not any("/view/" in row for each in closed["files"].values() for row in each["rows"])
    after = steps["every click on a link the page opened in place is the browser's"]["clicks"]
    assert [each["plain"] for each in after.values()] == written
    relinked = steps["a file drawn after the pin change links as the one the change closed"]
    assert relinked["files"]["f12 docs/links.md"] == closed["files"]["f12 docs/links.md"]
    first = steps["an answer within the loading delay paints Rendered first"]["files"]
    assert first["f1 docs/guide.md"]["shows"] == "rendered"
    # A file still waiting past the delay goes on showing nothing: Source shown then was
    # replaced when the answer came, which moved every file below it (mb-ne65).
    assert steps["past the loading delay a waiting file still waits, Source hidden"]["files"] == {}
    # Every file of a rendered format keeps its chooser, and a file its rendered views
    # cannot show says why (mb-rm40): the session itself fails on a chooser that is gone.
    mounted = steps[
        "mount: a Markdown file waits for Rendered with Source hidden; "
        "one whose changes did not load shows Source"
    ]["files"]
    assert len(mounted) == 11
    assert mounted["f1 docs/guide.md"]["chooser"] == "*Rendered | Source"
    unread = "This change is too large to show inline."
    assert mounted["f9 docs/unread.md"] == {
        "chooser": f"Rendered (unavailable: {unread}) | *Source",
        "shows": "source",
    }
    refused = steps["a file Rendered cannot show stays in Source, and its chooser says why"]
    same = "This file's content did not change."
    assert refused["files"]["f2 docs/renamed.md"] == {
        "chooser": f"Rendered (unavailable: {same}) | *Source",
        "shows": "source",
    }
    again = steps["choosing an unavailable view changes nothing and asks for nothing"]
    assert again == {"step": again["step"], "requests": [], "files": {}}
    assert steps["the wait is over"]["requests"] == ["f3 view=concise"]
    large = steps[
        "a file past the route's read bound says it is too large; "
        "no projection is asked for a file whose changes did not load"
    ]
    assert large["requests"] == ["f8 view=concise"]
    huge = "This file is too large to show rendered."
    assert large["files"]["f8 docs/huge.md"]["chooser"] == (
        f"Rendered (unavailable: {huge}) | *Source"
    )
    assert not any(
        "f9" in request for step in transcript["steps"] for request in step.get("requests", [])
    )
    kept = steps["choosing Rendered again shows the kept answer without asking"]
    assert kept["requests"] == [] and kept["files"]["f4 README.md"]["shows"] == "rendered"
    front = steps[
        "front matter that did not change is closed above the body's change, "
        "and front matter removed is one removed row"
    ]["files"]
    assert front["f6 docs/notes.md"]["rows"][0] == "[Frontmatter]"
    assert front["f7 docs/plain.md"]["rows"][0] == "[Frontmatter, open, removed]"
    # A fold the answer holds opens at once; a withheld one asks for its blocks, as a link
    # to a heading inside it does, which goes there once they are drawn (mb-3q2y).
    assert steps["opening the short run's fold asks for nothing"]["requests"] == []
    linked = steps["a link to a heading a withheld fold holds waits for it"]
    assert linked["prevented"] is True
    assert steps["its fold opens and asks for its blocks"]["requests"] == ["f10 blocks=13-15"]
    [went] = steps["scrolled into view"]["scrolled"]
    assert went["id"].endswith("-new-deep-heading")
    assert steps["expanding unchanged sections asks for the blocks still withheld"]["requests"] == [
        "f10 view=full"
    ]
    # A withheld fold's blocks are asked for under the file's progress mark, and blocks that
    # did not load close the fold again, its bar saying so; a press asks again (A3 of
    # review A on #811). Full that fails after the reader chose Source leaves Source chosen
    # (A7).
    asking = steps["a withheld fold asks for its blocks, the file's progress mark counting"]
    assert asking["requests"] == ["f10 blocks=21-23"]
    assert asking["files"]["f10 docs/long.md"]["progress"] == "counting"
    failed = steps["blocks that did not load close the fold again, and its bar says so"]
    assert "progress" not in failed["files"]["f10 docs/long.md"]
    assert failed["files"]["f10 docs/long.md"]["folds"][-1] == (
        "Could not load 2 unchanged blocks. Retry"
    )
    assert steps["a press on it asks again"]["requests"] == ["f10 blocks=21-23"]
    chose = steps["Full failing after Source was chosen leaves Source chosen"]["files"]
    assert chose["f10 docs/long.md"]["chooser"] == "Rendered | *Source"
    assert steps["expanding unchanged sections again retries the request"]["requests"] == [
        "f10 view=full"
    ]
    assert (
        steps["collapsing unchanged sections keeps the folds the reader opened"]["requests"] == []
    )
    # A long document draws a chunk and keeps the rest's place until the reader nears it.
    book = steps["a long document draws its first chunk and keeps the place of the rest"]
    assert book["files"]["f11 docs/book.md"]["rows"][-1].startswith("[blocks 600-623 not drawn:")
    near = steps["coming near a place draws the chunk there"]["files"]["f11 docs/book.md"]["rows"]
    # Its first two chunks' 200 blocks drawn, and the places of the other four.
    assert near[4] == "... 197 rows ..."
    assert near[-4].startswith("[blocks 300-400 not drawn:")
    # The link's own navigation goes to the heading, once its chunk is drawn.
    assert steps["a link into a chunk not drawn yet"]["prevented"] is False
    drawn = steps["draws every chunk through it, and the link goes there"]["files"]
    drawn = drawn["f11 docs/book.md"]["rows"]
    assert drawn[4] == "... 615 rows ..."
    assert drawn[-1] == "added: <p>The end.</p>"
    assert steps["after disposal"]["timers"] == 0
