"""The guided-review route on a cached pull request: its staleness, its refusals, and the
description rendered beside the guide.

Each route test caches pull request 7 of the GitHub stand-in (``tests/github_pull_fixture.py``)
with a guide in its description, through the production refresh, and asks the route as its
handler does. The stand-in's pull request 7 is ``base`` → ``fork_earlier`` ("extra") →
``fork_head`` ("count to two"), and its record's comparison is ``base``..``fork_head``.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import subprocess
from collections.abc import Coroutine, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from metabrowser import kpress_adapter
from metabrowser.builtin_plugins.github import (
    guided_review,
    pull_manifest,
    pull_markdown,
    pull_rendered_diff,
    pull_text_render,
)
from metabrowser.builtin_plugins.github.guided_review import parse_guide
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_record import (
    MAX_BODY_BYTES,
    PullRecord,
    PullRefreshStamp,
)
from metabrowser.builtin_plugins.github.pull_route import PullHost, PullView
from metabrowser.builtin_plugins.github.pull_stacks import (
    NativeStack,
    StackPage,
    StackSnapshot,
    publish_stacks,
)
from metabrowser.builtin_plugins.github.served_pull import ServedPulls
from metabrowser.diff import markdown_projection_worker as worker_module
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.markdown_projection_worker import InertRenderRefused, RefusalCode
from metabrowser.git.process import (
    GitCommandError,
    GitError,
    GitLocation,
    GitOutputCutError,
    RepositoryStoreTarget,
)
from tests.diff_fixture_repo import git
from tests.github_pull_fixture import (
    _DOCUMENT_FILES,  # pyright: ignore[reportPrivateUsage]
    DEFAULT_BRANCH,
    FETCHED_AT,
    READER,
    commits_guide_body,
    grouped_guide_body,
    guide_body,
    kinds_guide_body,
    markdown_guide_body,
    scenario,
)
from tests.required_tools import needs_git
from tests.test_github_pulls import _Stand
from tests.test_github_pulls import stand as stand
from tests.test_guided_review import PUBLISHED_GUIDE

_MISSING = "e" * 40


@dataclass
class _NoteChild:
    """The Markdown child's stand-in for a step's notes: each render asked of it, and its
    answer, the note's text in a paragraph, or the refusal it was told to give."""

    asked: list[Any] = field(default_factory=list[Any])
    refusal: InertRenderRefused | None = None

    async def render_inert(self, request: Any) -> dict[str, Any]:
        self.asked.append(request)
        if self.refusal is not None:
            raise self.refusal
        return {"html": f"<p>{html.escape(request.source_text)}</p>"}


@pytest.fixture(autouse=True)
def notes(monkeypatch: pytest.MonkeyPatch) -> _NoteChild:
    """Every answer with a step renders its note through the Markdown child, which a test
    of something else need not start: those notes are a stand-in's. The tests of the render
    itself put the real child back (`_real_child`)."""
    child = _NoteChild()
    monkeypatch.setattr(pull_text_render, "shared_worker", lambda: child)
    return child


def _real_child(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_text_render, "shared_worker", worker_module.shared_worker)


def _closing[T](work: Coroutine[Any, Any, T]) -> T:
    """*work* on an event loop that ends as the server's lifespan ends one, with the real
    Markdown child's work on it closed (``ProjectionWorker.aclose``).

    A note refused at its deadline starts the child's replacement as the route answers.
    Without the close, ``asyncio.run`` cancels that start while it spawns, which on CPython
    3.12 and 3.13 never finishes (mb-4g7f), and ``fresh_markdown_child`` fails a test whose
    loop ended while that start ran.
    """

    async def closing() -> T:
        try:
            return await work
        finally:
            await worker_module.shared_worker().aclose()

    return asyncio.run(closing())


def _cache(stand: _Stand, body: str) -> PullRecord:
    """Pull request 7 cached with *body* as its description."""
    answers = scenario(stand.origin)
    answers["api"]["repos/octo/demo/pulls/7"]["body"]["body"] = body
    stand.answer(answers)
    record = stand.refresh(7)
    assert record.comparison is not None
    assert (record.comparison.base, record.comparison.head) == (
        stand.origin["base"],
        stand.origin["fork_head"],
    )
    return record


def _pinned(stand: _Stand, *, merge_base: str | None = None, head: str | None = None) -> str:
    """The stand-in's guide with its pins replaced."""
    body = guide_body(stand.origin)
    if head is not None:
        body = body.replace(f'head: "{stand.origin["fork_head"]}"', f'head: "{head}"')
    if merge_base is not None:
        body = body.replace(f'merge_base: "{stand.origin["base"]}"', f'merge_base: "{merge_base}"')
    return body


def _ask(
    stand: _Stand, step: int = 1, number: int = 7, repository: ListedRepository | None = None
) -> dict[str, Any]:
    host = PullHost(ServedPulls(stand.published), lambda _n: False, lambda _n, _a: "started")
    return _closing(guided_review.guided_review(host, number, step, repository))


def _rows(answer: dict[str, Any], at: int = 0) -> list[str]:
    return [
        f"{line['op']}:{line['text']}"
        for hunk in answer["references"][at]["hunks"]
        for line in hunk["lines"]
    ]


def test_a_guide_one_push_behind_is_ahead_and_read_at_the_current_head(stand: _Stand) -> None:
    """The ordinary stale guide: its author pushed after writing it. The answer carries
    every detail an agent needs to bring it up to date, and its steps are read at the pull
    request's current head, which the reviewer is reviewing."""
    origin = stand.origin
    _cache(stand, _pinned(stand, head=origin["fork_earlier"]))
    answer = _ask(stand)
    assert answer["state"] == "stale"
    assert answer["stale"] == {
        "guide": {"merge_base": origin["base"], "head": origin["fork_earlier"]},
        "current": {"merge_base": origin["base"], "head": origin["fork_head"]},
        "github_newer": False,
        "history": "ahead",
        "commit_count": 1,
        "commits": [{"sha": origin["fork_head"], "subject": "count to two"}],
        "changed_paths": ["docs/new.md", "src/app.txt"],
        "changed_steps": [1, 2],
    }
    # The excerpt is the current head's, where the file says "two", not the guide's "extra".
    assert answer["comparison"] == {"merge_base": origin["base"], "head": origin["fork_head"]}
    assert _rows(answer) == ["context:one", "add:two"]
    # A reference that no longer resolves says so in its place; the others still draw.
    assert [(ref["path"], ref["state"]) for ref in _ask(stand, step=2)["references"]] == [
        ("docs/new.md", "ready"),
        ("src/app.txt", "ready"),
        ("missing.txt", "path_not_changed"),
        ("src/app.txt", "range_unavailable"),
    ]


def test_reading_a_stale_guide_keeps_the_pull_requests_manifest(stand: _Stand) -> None:
    """A guide's own pins are another comparison, which never replaces the record's kept
    manifest (B8 of review B on #677): Changes reads that one on its next cold start."""
    origin = stand.origin
    _cache(stand, _pinned(stand, head=origin["fork_earlier"]))
    asyncio.run(
        pull_manifest.shared_pull_manifest(stand.published, 7, origin["base"], origin["fork_head"])
    )
    kept = stand.published.home / pull_manifest._path(stand.published, 7)
    before = kept.read_bytes()
    document = json.loads(before)["document"]
    assert document["resolved"]["right"]["id"] == origin["fork_head"]
    assert _ask(stand)["state"] == "stale"
    assert kept.read_bytes() == before


def test_a_moved_merge_base_marks_what_moved_with_it(stand: _Stand) -> None:
    """Pinned at the same head on a later merge base, the guide's comparison is narrower:
    the paths between the two merge bases changed, whatever the head did."""
    origin = stand.origin
    _cache(stand, _pinned(stand, merge_base=origin["fork_earlier"]))
    answer = _ask(stand)
    stale = answer["stale"]
    assert (stale["history"], stale["commit_count"], stale["commits"]) == ("ahead", 0, [])
    assert (stale["changed_paths"], stale["changed_steps"]) == (["src/app.txt"], [1, 2])
    # Read at the current comparison, not the guide's narrower one from fork_earlier.
    assert _rows(answer) == ["context:one", "add:two"]


def test_a_rebased_branch_is_rewritten(stand: _Stand) -> None:
    origin = stand.origin
    _cache(stand, _pinned(stand, head=origin["merged_head"]))
    answer = _ask(stand)
    stale = answer["stale"]
    assert (stale["history"], stale["commit_count"]) == ("rewritten", 2)
    assert [commit["subject"] for commit in stale["commits"]] == ["count to two", "extra"]
    assert stale["changed_paths"] == ["docs/new.md", "src/app.txt"]
    assert (answer["step"], _rows(answer)) == (1, ["context:one", "add:two"])


def test_a_guide_whose_head_this_copy_lacks_still_reads(stand: _Stand) -> None:
    """The store lacks the guide's head, as after a force push it never fetched: its
    commits and what changed are unknown, and its steps are read at the current head all
    the same, so the guide stays readable."""
    origin = stand.origin
    _cache(stand, _pinned(stand, head=_MISSING))
    answer = _ask(stand)
    assert answer["state"] == "stale"
    stale = answer["stale"]
    assert (stale["history"], stale["commit_count"], stale["changed_paths"]) == (
        "unavailable",
        None,
        None,
    )
    assert answer["comparison"] == {"merge_base": origin["base"], "head": origin["fork_head"]}
    assert (answer["step"], _rows(answer)) == (1, ["context:one", "add:two"])


def test_a_newer_head_on_github_leaves_what_changed_unknown(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHub reports a head this copy lacks. A guide that matches this copy is then stale,
    and since the store lacks the newer commits, neither list is answered, so the page
    never says that every step still matches (B1 of review B on #677)."""
    origin = stand.origin
    _cache(stand, guide_body(origin))
    assert _ask(stand)["state"] == "ready"
    monkeypatch.setattr(guided_review, "_head_moved", lambda _store, _record: True)
    answer = _ask(stand)
    assert answer["state"] == "stale"
    assert answer["stale"] == {
        "guide": {"merge_base": origin["base"], "head": origin["fork_head"]},
        "current": {"merge_base": origin["base"], "head": origin["fork_head"]},
        "github_newer": True,
        "history": "ahead",
        "commit_count": 0,
        "commits": [],
        "changed_paths": None,
        "changed_steps": None,
    }
    # Its steps are still read, at this copy's head.
    assert (answer["step"], _rows(answer)) == (1, ["context:one", "add:two"])


def test_pins_that_name_no_comparison_are_refused(stand: _Stand) -> None:
    """A merge_base that is not where the guide's head leaves the base names no comparison
    the guide could have been written for (B9 of review B on #677): an author's mistake,
    not an earlier version of the pull request."""
    origin = stand.origin
    _cache(stand, _pinned(stand, merge_base=origin["topic"]))
    answer = _ask(stand)
    assert (answer["state"], answer["message"]) == (
        "invalid",
        "The guided-review block's merge_base is not the merge base of its head.",
    )
    assert "step" not in answer


def test_a_file_too_large_for_a_step_is_not_read(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path alone whose changed lines charge past a step's whole files is refused from
    the manifest's counts, without reading its patch."""
    old = "        - {path: src/app.txt, side: old, start_line: 2, end_line: 4}\n"
    body = guide_body(stand.origin)
    assert old in body
    _cache(stand, body.replace(old, ""))
    # src/app.txt adds one line here, which charges at least 80 bytes.
    monkeypatch.setattr(guided_review, "MAX_STEP_PATCH_BYTES", 79)
    asked: list[tuple[str, ...]] = []
    real = guided_review.GitDiffSource.hydrate

    async def hydrate(self: Any, resolved: Any, ids: tuple[str, ...], **kwargs: Any) -> Any:
        asked.append(ids)
        return await real(self, resolved, ids, **kwargs)

    monkeypatch.setattr(guided_review.GitDiffSource, "hydrate", hydrate)
    answer = _ask(stand, step=2)
    assert [(ref["path"], ref["state"]) for ref in answer["references"]] == [
        ("docs/new.md", "ready"),
        ("src/app.txt", "patch_too_large"),
        ("missing.txt", "path_not_changed"),
    ]
    assert [len(ids) for ids in asked] == [1]


@pytest.mark.parametrize("budget", [guided_review.MAX_STEP_PATCH_BYTES, 79])
def test_a_document_cited_whole_is_drawn_from_its_own_reads(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, budget: int
) -> None:
    """A path alone of a file the rendered route renders answers that route's format and no
    hunks: the page draws the file whole from its own reads, so the step reads no patch for
    it and charges it nothing, and the step's other whole files keep the whole budget. With
    a budget of 79 bytes, less than any one row, the document still answers ready, and the
    other file is too large to show whole."""
    ranged = "        - {path: docs/new.md, side: new, start_line: 1, end_line: 1}\n"
    body = guide_body(stand.origin)
    assert ranged in body
    _cache(stand, body.replace(ranged, "        - {path: docs/new.md}\n"))
    monkeypatch.setattr(guided_review, "MAX_STEP_PATCH_BYTES", budget)
    asked: list[tuple[str, ...]] = []
    real = guided_review.GitDiffSource.hydrate

    async def hydrate(self: Any, resolved: Any, ids: tuple[str, ...], **kwargs: Any) -> Any:
        asked.append(ids)
        return await real(self, resolved, ids, **kwargs)

    monkeypatch.setattr(guided_review.GitDiffSource, "hydrate", hydrate)
    answer = _ask(stand, step=2)
    whole = "ready" if budget > 79 else "patch_too_large"
    assert [
        (ref["path"], ref["side"], ref["state"], ref["rendered"], len(ref["hunks"]))
        for ref in answer["references"]
    ] == [
        ("docs/new.md", None, "ready", "markdown", 0),
        ("src/app.txt", None, whole, None, 1 if budget > 79 else 0),
        ("missing.txt", None, "path_not_changed", None, 0),
        ("src/app.txt", "old", "range_unavailable", None, 0),
    ]
    # src/app.txt alone is read: its range needs its patch at either budget.
    manifest = asyncio.run(
        pull_manifest.shared_pull_manifest(
            stand.published, 7, stand.origin["base"], stand.origin["fork_head"]
        )
    ).manifest
    ids = {change.new.path: change.id for change in manifest.files if change.new is not None}
    assert asked == [(ids["src/app.txt"],)]


def test_the_large_document_build_is_past_the_step_budget_and_inside_the_rendered_bound() -> None:
    """The large document a documents build adds (``--guided-large-document``, which the
    guided-review golden reads) would be too large to show as a step's patch, and is not
    too large for the rendered route to read."""
    text = _DOCUMENT_FILES["docs/large.md"]
    charge = sum(80 + 6 * len(line) for line in text.split("\n")[:-1])
    assert charge > guided_review.MAX_STEP_PATCH_BYTES
    assert len(text.encode()) < pull_rendered_diff._MARKDOWN_PAIR_MAX_BYTES  # pyright: ignore[reportPrivateUsage]


def test_a_guide_in_groups_numbers_its_steps_through_them(stand: _Stand) -> None:
    """Each answer with a step carries the guide's outline, a tree of its groups and steps,
    and the index of the step's group in it. Steps are numbered through the groups, as
    ``step=<k>`` asks for them and a stale guide's ``changed_steps`` names them."""
    origin = stand.origin
    body = grouped_guide_body(origin).replace(
        f'head: "{origin["fork_head"]}"', f'head: "{origin["fork_earlier"]}"'
    )
    _cache(stand, body)
    first, second = _ask(stand, step=1), _ask(stand, step=2)
    assert (
        first["outline"]
        == second["outline"]
        == [
            {
                "kind": "group",
                "title": "The count",
                "note": "Read the value before its explanation.",
                "children": [{"kind": "step", "step": 1, "title": "Start with the count"}],
            },
            {
                "kind": "group",
                "title": "The docs",
                "note": None,
                "children": [{"kind": "step", "step": 2, "title": "Read the new guide"}],
            },
        ]
    )
    assert (first["group"], second["group"]) == (0, 1)
    assert first["titles"] == ["Start with the count", "Read the new guide"]
    assert first["stale"]["changed_steps"] == [1, 2]
    assert [ref["path"] for ref in second["references"]] == [
        "docs/new.md",
        "src/app.txt",
        "missing.txt",
        "src/app.txt",
    ]
    assert _ask(stand, step=3)["state"] == "step_not_found"


def test_a_guide_without_groups_is_an_outline_of_its_steps(stand: _Stand) -> None:
    _cache(stand, guide_body(stand.origin))
    plain = _ask(stand, step=2)
    assert plain["outline"] == [
        {"kind": "step", "step": 1, "title": "Start with the count"},
        {"kind": "step", "step": 2, "title": "Read the new guide"},
    ]
    assert plain["group"] is None


def test_a_published_guide_without_groups_answers_each_step_as_before(stand: _Stand) -> None:
    """The guide #785 published, its pins moved to the stand-in's comparison, answers each
    step ``ready`` with an outline of its steps alone and no group. It cites this
    repository's files, which the stand-in's pull request does not change."""
    published = PUBLISHED_GUIDE.read_text("utf-8")
    guide = parse_guide(published)
    assert guide is not None
    pinned = published.replace(guide.comparison.merge_base, stand.origin["base"]).replace(
        guide.comparison.head, stand.origin["fork_head"]
    )
    _cache(stand, pinned)
    titles = [step.title for step in guide.items]
    flat = [{"kind": "step", "step": k, "title": title} for k, title in enumerate(titles, 1)]
    for number, title in enumerate(titles, 1):
        answer = _ask(stand, step=number)
        assert (answer["state"], answer["step"], answer["title"]) == ("ready", number, title)
        assert (answer["outline"], answer["group"], answer["titles"]) == (flat, None, titles)
        assert {reference["state"] for reference in answer["references"]} == {"path_not_changed"}


def test_a_step_answers_its_note_rendered_beside_its_source(
    stand: _Stand, notes: _NoteChild
) -> None:
    """A step's note renders as the description does, from the pull request's page, and its
    group's note on the group's first step alone; a title is never rendered. The render is
    kept with the parse, so the step read again asks nothing more of the child."""
    record = _cache(stand, markdown_guide_body(stand.origin))
    first = _ask(stand, step=1)
    assert (first["state"], first["title"]) == ("ready", "Start with the <b>count</b>")
    assert first["note"].startswith("Check that the **original** value\n")
    assert first["note_html"] == f"<p>{html.escape(first['note'])}</p>"
    group_note = "Read the `count` before *its* explanation."
    assert first["outline"][0]["note"] == group_note
    assert first["group_note_html"] == f"<p>{html.escape(group_note)}</p>"
    assert [request.source_text for request in notes.asked] == [first["note"], group_note]
    request = notes.asked[0]
    assert (request.kind, request.view, request.ext, request.include_toc) == (
        "markdown",
        "document",
        ".md",
        "off",
    )
    assert (request.link_base, request.source_path) == (
        record.pull.html_url,
        "pull-7-guided-review-note.md",
    )
    # The group's second step opens nothing, and a step outside a group has no group.
    second, third = _ask(stand, step=2), _ask(stand, step=3)
    assert (second["group"], second["group_note_html"]) == (0, None)
    assert (third["group"], third["group_note_html"]) == (None, None)
    assert second["note_html"] == "<p>Check what the count replaced.</p>"
    asked = len(notes.asked)
    assert _ask(stand, step=1) == first
    assert len(notes.asked) == asked


def test_a_note_past_the_kept_renders_renders_again(
    stand: _Stand, notes: _NoteChild, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cache(stand, guide_body(stand.origin))
    monkeypatch.setattr(guided_review, "_MAX_KEPT_NOTE_CHARS", 0)
    assert _ask(stand)["note_html"] == _ask(stand)["note_html"] is not None
    assert len(notes.asked) == 2


@pytest.mark.parametrize(
    "code", ["render_deadline", "renderer_exited", "renderer_busy", "renderer_unavailable"]
)
def test_a_refused_render_answers_the_note_and_why(
    stand: _Stand, notes: _NoteChild, code: RefusalCode
) -> None:
    """A note whose render is refused is answered as written, with no HTML and the code the
    pull-markdown route answers the refusal with, and the step reads as before: the page
    shows the note as typed, with the line a description's refusal says. A refusal is not
    kept here, so the next read asks again, and the child answers from the refusal it keeps
    or, for a busy renderer or one that could not start, renders."""
    _cache(stand, markdown_guide_body(stand.origin))
    notes.refusal = InertRenderRefused(code)
    answer = _ask(stand)
    assert (
        answer["state"],
        answer["note_html"],
        answer["note_refusal"],
        answer["group_note_html"],
        answer["group_note_refusal"],
    ) == ("ready", None, code, None, code)
    assert answer["note"].startswith("Check that the **original** value")
    assert [ref["state"] for ref in answer["references"]] == ["ready"]
    _ask(stand)
    assert len(notes.asked) == 4
    notes.refusal = None
    again = _ask(stand)
    assert (again["note_refusal"], again["group_note_refusal"]) == (None, None)
    assert again["note_html"] == f"<p>{html.escape(again['note'])}</p>"


def test_a_note_kpress_cannot_render_answers_render_failed(
    stand: _Stand, notes: _NoteChild, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KPress's own failure is answered as the pull-markdown route answers it, ``render_failed``."""
    _cache(stand, guide_body(stand.origin))

    async def failing(_request: Any) -> dict[str, Any]:
        raise kpress_adapter.KPressRenderError("no")

    monkeypatch.setattr(notes, "render_inert", failing)
    answer = _ask(stand)
    assert (answer["note_html"], answer["note_refusal"]) == (None, "render_failed")
    assert (answer["group_note_html"], answer["group_note_refusal"]) == (None, None)


def test_the_published_guides_notes_render_inert(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every note of the guide #785 published renders in the real Markdown child, as its
    text: plain prose reads the same as Markdown, its flags included."""
    _real_child(monkeypatch)
    published = PUBLISHED_GUIDE.read_text("utf-8")
    guide = parse_guide(published)
    assert guide is not None
    _cache(
        stand,
        published.replace(guide.comparison.merge_base, stand.origin["base"]).replace(
            guide.comparison.head, stand.origin["fork_head"]
        ),
    )
    host = PullHost(ServedPulls(stand.published), lambda _n: False, lambda _n, _a: "started")
    steps = guide.flat_items()

    async def every_step() -> list[dict[str, object]]:
        # One event loop, so one child renders every note.
        return [await guided_review.guided_review(host, 7, k) for k in range(1, len(steps) + 1)]

    for answer, step in zip(_closing(every_step()), steps, strict=True):
        paragraph = html.escape(step.note, quote=False)
        assert answer["note_html"] == f"\n<div><div><p>{paragraph}</p></div></div>"


def test_a_note_past_the_render_deadline_shows_as_typed(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A note KPress takes seconds to render, 100 unpaired ``[`` before 60 KiB of ``%``
    (``tests/test_inert_render_deadline.py``), is stopped at the real child's deadline and
    answered as written."""
    _real_child(monkeypatch)
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 0.25)
    slow = "[" * 100 + "%" * (60 * 1024)
    body = guide_body(stand.origin).replace(
        "note: Check that the original value is preserved.", f"note: |-\n        {slow}"
    )
    assert slow in body
    _cache(stand, body)
    answer = _ask(stand)
    assert (answer["state"], answer["note"], answer["note_html"], answer["note_refusal"]) == (
        "ready",
        slow,
        None,
        "render_deadline",
    )


def test_a_step_past_the_guide_and_an_uncached_pull_request(stand: _Stand) -> None:
    _cache(stand, guide_body(stand.origin))
    assert _ask(stand, step=3)["state"] == "step_not_found"
    assert _ask(stand, number=11) == {"record_revision": None, "state": "not_cached"}


@pytest.mark.parametrize("stale", [False, True], ids=["current", "stale"])
def test_a_comparison_the_store_cannot_read_is_unavailable(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, stale: bool
) -> None:
    """A stale guide's refusal is a current one's, with its diagnostics beside it for an
    agent; the page says only why the step is unavailable."""
    _cache(
        stand,
        _pinned(stand, head=stand.origin["fork_earlier"]) if stale else guide_body(stand.origin),
    )

    async def unreadable(*_args: object, **_kwargs: object) -> object:
        raise DiffSourceError("the store cannot list it")

    monkeypatch.setattr(guided_review, "shared_pull_manifest", unreadable)
    answer = _ask(stand)
    assert answer["state"] == "comparison_unavailable"
    assert ("stale" in answer) is stale
    if stale:
        assert answer["stale"]["changed_steps"] == [1, 2]


def test_a_stale_guide_on_a_record_with_no_comparison_keeps_its_diagnostics(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record with no comparison, as when the store could not answer for it at fetch,
    refuses every step as unavailable, and a stale guide's diagnostics ride on that refusal
    too, with no current merge base (A4 of review A on #795)."""
    origin = stand.origin
    _cache(stand, _pinned(stand, head=origin["fork_earlier"]))
    real = guided_review.cached_pull_record

    def without_comparison(*args: Any) -> Any:
        found, other, revision = real(*args)
        assert isinstance(found, PullRecord)
        return found.model_copy(update={"comparison": None}), other, revision

    monkeypatch.setattr(guided_review, "cached_pull_record", without_comparison)
    answer = _ask(stand)
    assert answer["state"] == "comparison_unavailable"
    assert answer["stale"]["current"] == {"merge_base": None, "head": origin["fork_head"]}
    assert answer["stale"]["changed_steps"] == [1, 2]


def test_a_step_past_a_stale_guide_keeps_its_diagnostics(stand: _Stand) -> None:
    """Every answer for a stale guide carries its diagnostics, a step it lacks too (A2 of
    review A on #795)."""
    _cache(stand, _pinned(stand, head=stand.origin["fork_earlier"]))
    answer = _ask(stand, step=3)
    assert answer["state"] == "step_not_found"
    assert answer["stale"]["changed_steps"] == [1, 2]


def test_a_merge_base_this_copy_lacks_says_nothing_about_the_pins(stand: _Stand) -> None:
    """Only a merge_base the store has can name no comparison. One it lacks, as after the
    base branch was rewritten, leaves the guide stale with what changed unknown, and its
    steps are read at the current head (A3 of review A on #795)."""
    origin = stand.origin
    _cache(stand, _pinned(stand, merge_base=_MISSING))
    answer = _ask(stand)
    assert answer["state"] == "stale"
    stale = answer["stale"]
    assert (stale["history"], stale["changed_paths"], stale["changed_steps"]) == (
        "ahead",
        None,
        None,
    )
    assert answer["comparison"] == {"merge_base": origin["base"], "head": origin["fork_head"]}
    assert (answer["step"], _rows(answer)) == (1, ["context:one", "add:two"])


def test_a_description_cut_inside_its_block_is_truncated_not_invalid(stand: _Stand) -> None:
    """The record keeps MAX_BODY_BYTES of a description, so a block past that is cut, and
    reads as an unclosed fence the author closed on GitHub (B12 of review B on #677)."""
    record = _cache(stand, "x" * (MAX_BODY_BYTES - 200) + "\n\n" + guide_body(stand.origin))
    assert record.pull.body_truncated
    assert _ask(stand)["state"] == "description_truncated"


def _repository(stand: _Stand, *stacks: tuple[int, ...]) -> ListedRepository:
    """The stand-in's repository, as the server serves it, with a stack snapshot of each of
    *stacks*, numbered from 70, when any is given."""
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    if stacks:
        native = tuple(
            NativeStack(number=70 + at, base_ref=DEFAULT_BRANCH, open=True, pulls=pulls)
            for at, pulls in enumerate(stacks)
        )
        stamp = FETCHED_AT.strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot = StackSnapshot(
            source=repository.source,
            reader=f"gh:{READER}",
            fetched_at=stamp,
            complete=True,
            pages=(StackPage(etag=None, has_next=False, stacks=native),),
        )
        refresh = PullRefreshStamp(outcome="succeeded", at=stamp, reader=f"gh:{READER}")
        assert publish_stacks(repository, None, snapshot, refresh)
    return repository


def _cited(answer: dict[str, Any]) -> list[tuple[Any, ...]]:
    return [
        (ref["kind"], ref["pull"] or ref["commit"], ref["state"], ref["href"])
        for ref in answer["references"]
    ]


def test_a_step_cites_other_pull_requests_and_commits(stand: _Stand) -> None:
    """A `{pull}` is a row naming that pull request, a `{pull, path}` its file at its own
    current comparison, and a `{commit}` a row naming that commit, each read from this copy
    alone: a pull request it has not read is `not_cached` until it has."""
    origin = stand.origin
    _cache(stand, kinds_guide_body(origin))
    repository = _repository(stand, (8, 10), (8, 7, 10))
    before = _ask(stand, step=2, repository=repository)
    assert before["state"] == "ready"
    assert _cited(before) == [
        ("pull", 8, "not_cached", "/pull/8"),
        ("pull_file", 10, "not_cached", "/pull/10/files/docs/draft.md"),
        ("pull_file", 9, "not_cached", "/pull/9/files/src/app.txt"),
        ("pull", 50, "not_cached", "/pull/50"),
        ("pull", 2000, "not_cached", "/pull/2000"),
        ("commit", origin["fork_head"], "ready", f"/commit/{origin['fork_head']}"),
        ("commit", _MISSING, "commit_unavailable", None),
    ]
    for number in (8, 9, 10):
        stand.refresh(number)
    answer = _ask(stand, step=2, repository=repository)
    assert _cited(answer)[:3] == [
        ("pull", 8, "ready", "/pull/8"),
        ("pull_file", 10, "ready", "/pull/10/files/docs/draft.md"),
        ("pull_file", 9, "ready", "/pull/9/files/src/app.txt"),
    ]
    layer, document, patch, *_rest = answer["references"]
    # 8 is in both stacks; its place is in 71, the stack that holds 7, the guide's own.
    # Its author follows its number wherever it is named (docs/design-system.md, "Authors
    # Follow Pull Requests"): from its record, which names no avatar.
    assert layer["target"] == {
        "title": "Say more in the guide",
        "state": "merged",
        "stack": {"number": 71, "place": 1, "count": 3, "own": True},
        "author": "maintainer",
        "avatar": None,
    }
    assert (layer["path"], layer["comparison"], layer["hunks"]) == (None, None, [])
    # A document another pull request changes is drawn whole from that pull request's own
    # comparison, which its answer names, as a document of the guide's own is.
    assert (document["rendered"], document["hunks"]) == ("markdown", [])
    record = stand.record(10)
    assert isinstance(record, PullRecord) and record.comparison is not None
    comparison = document["comparison"]
    assert (comparison["merge_base"], comparison["head"]) == (
        record.comparison.base,
        record.comparison.head,
    )
    assert comparison["route"].startswith("/api/plugin/github/pull-comparison?number=10&")
    assert comparison["rendered_route"].startswith(
        "/api/plugin/github/pull-rendered-diff?number=10&"
    )
    assert comparison["image_route"].startswith("/api/plugin/github/pull-image?number=10&")
    # A file that is not a document is its whole patch, as a `{path}` without a range is.
    assert patch["rendered"] is None
    assert [
        f"{line['op']}:{line['text']}" for hunk in patch["hunks"] for line in hunk["lines"]
    ] == [
        "context:one",
        "add:spam",
    ]
    commit = answer["references"][5]
    assert commit["target"] == {"subject": "count to two", "committed_at": "2026-08-29T14:40:00Z"}
    assert answer["references"][6]["target"] is None


def test_a_pull_request_in_no_stack_or_with_no_snapshot_has_no_place(stand: _Stand) -> None:
    """Outside a stack, and on a server that lists no repository, a `{pull}` names no place;
    in stacks without the guide's pull request, its place is in the first that holds it,
    which is not the guide's own (A2 of review A on #853)."""
    _cache(stand, kinds_guide_body(stand.origin))
    stand.refresh(8)
    unlisted = _ask(stand, step=2)
    assert unlisted["references"][0]["target"]["stack"] is None
    elsewhere = _ask(stand, step=2, repository=_repository(stand, (9,), (10, 8)))
    assert elsewhere["references"][0]["target"]["stack"] == {
        "number": 71,
        "place": 2,
        "count": 2,
        "own": False,
    }


def test_a_reference_past_the_pull_request_is_never_stale(stand: _Stand) -> None:
    """What a push to the guide's own pull request changed is read from its `{path}`
    references alone: a `{pull, path}` to a file of the same name is another pull request's,
    and a `{pull}` or a `{commit}` names something no push to this one moves."""
    origin = stand.origin
    body = kinds_guide_body(origin).replace(
        f'head: "{origin["fork_head"]}"', f'head: "{origin["fork_earlier"]}"'
    )
    _cache(stand, body)
    answer = _ask(stand, step=2)
    assert answer["state"] == "stale"
    assert answer["stale"]["changed_paths"] == ["src/app.txt"]
    assert answer["stale"]["changed_steps"] == [1]


def test_the_guides_own_pull_request_cited_with_a_path_is_its_own_file(stand: _Stand) -> None:
    """A `{pull, path}` that names the guide's own pull request is that comparison's
    `{path}`: read at the guide's comparison, and marked when a push changes it (A4 of
    review A on #834)."""
    origin = stand.origin
    body = (
        kinds_guide_body(origin)
        .replace(f'head: "{origin["fork_head"]}"', f'head: "{origin["fork_earlier"]}"')
        .replace("{pull: 9, path: src/app.txt}", "{pull: 7, path: src/app.txt}")
    )
    _cache(stand, body)
    answer = _ask(stand, step=2)
    assert answer["stale"]["changed_paths"] == ["src/app.txt"]
    assert answer["stale"]["changed_steps"] == [1, 2]
    own = answer["references"][2]
    assert (own["kind"], own["pull"], own["href"], own["comparison"]) == (
        "file",
        None,
        "/pull/7/files/src/app.txt",
        None,
    )
    assert _rows(answer, 2) == ["context:one", "add:two"]


def test_another_pull_requests_comparison_the_store_cannot_read_says_so_in_its_place(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `{pull, path}` whose pull request's comparison this copy cannot read is
    unavailable in its place; the step's other references still draw."""
    _cache(stand, kinds_guide_body(stand.origin))
    for number in (8, 9, 10):
        stand.refresh(number)
    nine = stand.record(9)
    assert isinstance(nine, PullRecord) and nine.comparison is not None
    nines = nine.comparison.head
    real = guided_review._read_files  # pyright: ignore[reportPrivateUsage]

    async def unreadable(store: Any, compared: Any, head: str, refs: Any) -> Any:
        if head == nines:
            raise DiffSourceError("the store cannot read it")
        return await real(store, compared, head, refs)

    monkeypatch.setattr(guided_review, "_read_files", unreadable)
    answer = _ask(stand, step=2)
    assert [ref["state"] for ref in answer["references"][:3]] == [
        "ready",
        "ready",
        "comparison_unavailable",
    ]
    assert (answer["references"][2]["href"], answer["references"][2]["comparison"]) == (
        "/pull/9/files/src/app.txt",
        None,
    )


def test_a_commit_whose_line_passes_its_bound_names_no_subject(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git prints a subject whole, so commits whose lines pass the bound are read again for
    their IDs and times: each is still the commit, named by its SHA and when it was made."""
    _cache(stand, kinds_guide_body(stand.origin))
    monkeypatch.setattr(guided_review, "_MAX_COMMIT_ROW_BYTES", 8)
    commit, missing = _ask(stand, step=2)["references"][5:7]
    assert (commit["state"], commit["href"], commit["target"]) == (
        "ready",
        f"/commit/{stand.origin['fork_head']}",
        {"subject": None, "committed_at": "2026-08-29T14:40:00Z"},
    )
    assert (missing["state"], missing["target"]) == ("commit_unavailable", None)


@pytest.mark.parametrize("refused", [False, True], ids=["left out", "run refused"])
def test_an_id_that_names_no_commit_leaves_the_steps_other_commits_ready(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, refused: bool
) -> None:
    """A tree, a blob, an annotated tag, and a missing ID beside a commit are each
    `commit_unavailable`, and the commit stays ready: whether Git leaves them out of the
    step's one `git log`, or refuses that run, which is then read one ID a run."""
    origin = stand.origin
    head = origin["fork_head"]
    # An annotated tag of the head, which the store is given once it holds the head.
    tag = f"object {head}\ntype commit\ntag probe\ntagger A <a@example.invalid> 0 +0000\n\nA tag.\n"
    named = {
        "tree": git(origin.path, "rev-parse", f"{head}^{{tree}}").decode().strip(),
        "blob": git(origin.path, "rev-parse", f"{head}:src/app.txt").decode().strip(),
        "tag": hashlib.sha1(b"tag %d\0%s" % (len(tag), tag.encode())).hexdigest(),
        "missing": _MISSING,
    }
    commits = [named["tree"], head, named["blob"], named["tag"], named["missing"]]
    _cache(stand, commits_guide_body(origin, commits))
    written = subprocess.run(
        ["git", "-C", str(stand.published.git_dir), "hash-object", "-t", "tag", "-w", "--stdin"],
        input=tag.encode(),
        capture_output=True,
        check=True,
    )
    assert written.stdout.decode().strip() == named["tag"]
    batches: list[int] = []
    real = guided_review.run_git_at

    async def refusing(args: Sequence[str], location: GitLocation, **kwargs: Any) -> bytes:
        ids = [arg for arg in args if re.fullmatch(r"[0-9a-f]{40}", arg)]
        if args[0] == "log" and "--no-walk=unsorted" in args:
            batches.append(len(ids))
            if refused and len(ids) > 1:
                raise GitCommandError(args, 128, "fatal: not a commit")
        return await real(args, location, **kwargs)

    monkeypatch.setattr(guided_review, "run_git_at", refusing)
    answer = _ask(stand, step=2)
    assert answer["state"] == "ready"
    assert [(ref["commit"], ref["state"], ref["href"]) for ref in answer["references"]] == [
        (named["tree"], "commit_unavailable", None),
        (head, "ready", f"/commit/{head}"),
        (named["blob"], "commit_unavailable", None),
        (named["tag"], "commit_unavailable", None),
        (named["missing"], "commit_unavailable", None),
    ]
    assert answer["references"][1]["target"] == {
        "subject": "count to two",
        "committed_at": "2026-08-29T14:40:00Z",
    }
    # One run for the step's five IDs, or, once Git refuses it, one more for each.
    assert batches == ([5, 1, 1, 1, 1, 1] if refused else [5])


def test_a_pull_requests_file_with_no_kept_manifest_is_not_listed_here(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `{pull, path}` reads only the manifest its pull request's page kept: one with none
    is `not_cached`, opened from its Changes, and no whole comparison is listed on the
    guide's request (A1 of review A on #834)."""
    _cache(stand, kinds_guide_body(stand.origin))
    for number in (8, 9, 10):
        stand.refresh(number)
    real = guided_review.kept_pull_manifest
    listed: list[int] = []

    def kept(published: Any, number: int, base: str, head: str) -> Any:
        return None if number == 9 else real(published, number, base, head)

    async def listing(published: Any, number: int, *args: Any, **kwargs: Any) -> Any:
        listed.append(number)
        raise AssertionError("a cited pull request's comparison is listed on this request")

    monkeypatch.setattr(guided_review, "kept_pull_manifest", kept)
    monkeypatch.setattr(guided_review, "shared_pull_manifest", listing)
    answer = _ask(stand, step=2)
    assert _cited(answer)[1:3] == [
        ("pull_file", 10, "ready", "/pull/10/files/docs/draft.md"),
        ("pull_file", 9, "not_cached", "/pull/9/files/src/app.txt"),
    ]
    assert listed == []


def test_a_commit_the_served_checkout_lacks_is_answered_with_no_address(
    stand: _Stand, tmp_path: Path
) -> None:
    """A `{commit}`'s page reads Git where the session does: on a served checkout that
    lacks a commit the store fetched, the commit is named and dated with no address, and
    one the checkout has links its page (A3 of review A on #834)."""
    origin = stand.origin
    _cache(stand, kinds_guide_body(origin))
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    git(checkout, "init", "-q", "-b", "main")
    git(checkout, "commit", "-q", "--allow-empty", "-m", "the checkout's own")
    links = GitLocation.filesystem(checkout)
    host = PullHost(ServedPulls(stand.published), lambda _n: False, lambda _n, _a: "started")
    answer: Any = asyncio.run(guided_review.guided_review(host, 7, 2, None, links=links))
    commit = answer["references"][5]
    assert (commit["state"], commit["href"], commit["target"]) == (
        "ready",
        None,
        {"subject": "count to two", "committed_at": "2026-08-29T14:40:00Z"},
    )
    # A checkout that has the commit links it, as a mirror does.
    git(checkout, "fetch", "-q", str(stand.published.git_dir), origin["fork_head"])
    linked: Any = asyncio.run(guided_review.guided_review(host, 7, 2, None, links=links))
    assert linked["references"][5]["href"] == f"/commit/{origin['fork_head']}"


async def _commits_since(root: Path, subject: str) -> dict[str, object]:
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    git(root, "add", "a.txt")
    git(root, "commit", "-q", "-m", "first")
    old = git(root, "rev-parse", "HEAD").decode().strip()
    (root / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", subject)
    new = git(root, "rev-parse", "HEAD").decode().strip()
    target = RepositoryStoreTarget(root / ".git", "sha1")
    return await guided_review._commits_since(GitLocation.revision(target, new), old, new)


@needs_git
def test_a_long_subject_is_counted_not_listed(tmp_path: Path) -> None:
    """Git prints a subject whole, so one past the log's bound costs the list, not the
    count, nor the history and the changed paths read after it (B10 of review B on #677)."""
    short = asyncio.run(_commits_since(tmp_path / "short", "count to two"))
    assert (short["history"], short["commit_count"]) == ("ahead", 1)
    assert short["commits"] == [{"sha": short["commits"][0]["sha"], "subject": "count to two"}]  # type: ignore[index]
    long = asyncio.run(_commits_since(tmp_path / "long", "word " * 2400))
    assert long == {"history": "ahead", "commit_count": 1, "commits": []}


def _branch_moves(root: Path) -> dict[str, str]:
    """A pull request's branch, ``topic``, and the ways it moves after its guide is written.

    ``main`` is ``first``, then ``main_moves``, which changes ``notes.txt``. ``topic`` is
    ``first``, then ``guided``, which changes ``app.txt``, adds ``docs.md``, and is the
    guide's head. Then
    ``merged`` merges ``main`` into ``topic``; ``rebased`` is ``guided`` replayed onto
    ``main_moves``; and ``reworked`` is that rebase with ``app.txt`` changed again.
    """
    root.mkdir()
    git(root, "init", "-q", "-b", "main")

    def commit(message: str, **files: str) -> str:
        for name, text in files.items():
            (root / name).write_text(text, encoding="utf-8")
        git(root, "add", *files)
        git(root, "commit", "-q", "-m", message)
        return git(root, "rev-parse", "HEAD").decode().strip()

    shas = {"first": commit("first", **{"app.txt": "one\n", "notes.txt": "a\n"})}
    git(root, "checkout", "-q", "-b", "topic")
    shas["guided"] = commit("count to two", **{"app.txt": "one\ntwo\n", "docs.md": "# Two\n"})
    git(root, "checkout", "-q", "main")
    shas["main_moves"] = commit("notes", **{"notes.txt": "a\nb\n"})
    git(root, "checkout", "-q", "topic")
    git(root, "merge", "-q", "--no-edit", "main")
    shas["merged"] = git(root, "rev-parse", "HEAD").decode().strip()
    git(root, "checkout", "-q", "-b", "rebased", shas["main_moves"])
    shas["rebased"] = commit("count to two", **{"app.txt": "one\ntwo\n", "docs.md": "# Two\n"})
    shas["reworked"] = commit("count to three", **{"app.txt": "one\ntwo\nthree\n"})
    return shas


def _moved(root: Path, shas: dict[str, str], base: str, head: str) -> dict[str, object]:
    """The staleness of a guide pinned to ``first``..``guided``, the pull request now at
    *base*..*head*."""
    guide = guided_review.Collection.model_validate(
        {
            "comparison": {"merge_base": shas["first"], "head": shas["guided"]},
            "items": [
                {"title": "Count", "note": "Check it.", "references": [{"path": "app.txt"}]},
                {"title": "Docs", "note": "Read them.", "references": [{"path": "docs.md"}]},
            ],
        }
    )
    store = SimpleNamespace(git_dir=root / ".git", object_format="sha1")
    staleness = guided_review._staleness(  # pyright: ignore[reportPrivateUsage]
        cast(Any, store), (shas[base], shas[head]), guide, newer=False
    )
    return asyncio.run(staleness)


@needs_git
def test_merging_the_base_in_or_a_rebase_that_keeps_the_files_changes_no_step(
    tmp_path: Path,
) -> None:
    """The base branch merged in, or the branch replayed onto it with its files the same,
    moves both pins, and leaves every file the guide cites as it was in the guide's
    comparison: no step is marked, so the page says no more than a quiet line. A step whose
    file a rebase changed is marked."""
    root = tmp_path / "repo"
    shas = _branch_moves(root)
    merged = _moved(root, shas, "main_moves", "merged")
    assert (merged["history"], merged["commit_count"]) == ("ahead", 1)
    assert (merged["changed_paths"], merged["changed_steps"]) == ([], [])
    rebased = _moved(root, shas, "main_moves", "rebased")
    # The rebased head has main's commit and its own, and not the guide's head.
    assert (rebased["history"], rebased["commit_count"]) == ("rewritten", 2)
    assert (rebased["changed_paths"], rebased["changed_steps"]) == ([], [])
    reworked = _moved(root, shas, "main_moves", "reworked")
    assert (reworked["changed_paths"], reworked["changed_steps"]) == (["app.txt"], [1])


@needs_git
def test_paths_past_the_bound_stop_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A change past MAX_STALE_PATHS stops Git at the first path past it, rather than read
    the byte bound's worth and split it on the event loop (D3 of review D on #677)."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    git(root, "add", "a.txt")
    git(root, "commit", "-q", "-m", "first")
    old = git(root, "rev-parse", "HEAD").decode().strip()
    names = [f"f{n}.txt" for n in range(5)]
    for name in names:
        (root / name).write_text("x\n", encoding="utf-8")
    git(root, "add", *names)
    git(root, "commit", "-q", "-m", "five files")
    new = git(root, "rev-parse", "HEAD").decode().strip()
    location = GitLocation.revision(RepositoryStoreTarget(root / ".git", "sha1"), new)
    assert asyncio.run(guided_review._paths_between(location, old, new)) == set(names)
    refused: list[GitError] = []
    real = guided_review.run_git_at

    async def recording(*args: Any, **kwargs: Any) -> bytes:
        try:
            return await real(*args, **kwargs)
        except GitError as exc:
            refused.append(exc)
            raise

    monkeypatch.setattr(guided_review, "run_git_at", recording)
    monkeypatch.setattr(guided_review, "MAX_STALE_PATHS", 4)
    assert asyncio.run(guided_review._paths_between(location, old, new)) is None
    assert [type(exc) for exc in refused] == [GitOutputCutError]
    monkeypatch.setattr(guided_review, "MAX_STALE_PATHS", 5)
    assert asyncio.run(guided_review._paths_between(location, old, new)) == set(names)


@needs_git
def test_a_guide_pinned_past_a_kept_pair_is_one_written_for_a_later_comparison(
    tmp_path: Path,
) -> None:
    """A stack's guide read at a pair its page still draws is past it when it is pinned to
    the stack's current pair, or to a head that comes after the kept head, as when the member
    that carries it moved and its author pinned it again; otherwise its pins are the
    staleness read's to report (B1 of review B on #838)."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    line: list[str] = []
    for n in range(4):
        (root / "a.txt").write_text(f"{n}\n", encoding="utf-8")
        git(root, "add", "a.txt")
        git(root, "commit", "-q", "-m", f"commit {n}")
        line.append(git(root, "rev-parse", "HEAD").decode().strip())
    base, kept_head, later, newest = line
    git(root, "checkout", "-q", "-b", "side", base)
    (root / "b.txt").write_text("side\n", encoding="utf-8")
    git(root, "add", "b.txt")
    git(root, "commit", "-q", "-m", "side")
    side = git(root, "rev-parse", "HEAD").decode().strip()
    location = GitLocation.revision(RepositoryStoreTarget(root / ".git", "sha1"), kept_head)
    kept = (base, kept_head)
    current = (base, newest)

    def past(merge_base: str, head: str) -> bool:
        pinned = guided_review.CollectionComparison(merge_base=merge_base, head=head)
        return asyncio.run(guided_review._pinned_past(location, pinned, kept, current))

    assert past(base, kept_head) is False, "pinned to the kept pair itself"
    assert past(base, newest) is True, "pinned to the stack's current pair"
    assert past(base, later) is True, "pinned to a head after the kept head"
    assert past(kept_head, later) is True, "a head after the kept head, from another base"
    assert past(later, kept_head) is False, "the kept head, from another base"
    assert past(base, base) is False, "pinned before the kept head: out of date, as before"
    assert past(base, side) is False, "rewritten: the staleness read says so"
    assert past(base, _MISSING) is False, "a head the store lacks: the staleness read says so"


_VIEW = PullView(
    number=7,
    host=SimpleNamespace(pulls=SimpleNamespace(home=Path(), slug="octo/demo")),  # pyright: ignore[reportArgumentType]
    pin=None,
    pin_ref=None,
    refreshing=False,
    kept=None,
)
_KEY = (str(Path()), "octo/demo", 7)


@pytest.fixture
def rendered(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Each text the Markdown route asks the Markdown child to render."""
    texts: list[str] = []

    class Child:
        async def render_inert(self, request: Any) -> dict[str, Any]:
            texts.append(request.source_text)
            return {"html": "<p>rendered</p>"}

    monkeypatch.setattr(pull_text_render, "shared_worker", Child)
    monkeypatch.setattr(pull_markdown.kpress_adapter, "document_stylesheets", dict)
    guided_review._READS.clear()
    yield texts
    guided_review._READS.clear()


def _record(body: str) -> PullRecord:
    fixtures = Path(__file__).parent / "fixtures" / "github-pull-page-responses.json"
    recorded = json.loads(fixtures.read_text(encoding="utf-8"))
    record = PullRecord.model_validate(recorded["current"]["body"]["record"])
    return record.model_copy(
        update={"number": 7, "pull": record.pull.model_copy(update={"body": body})}
    )


_GUIDE = """Explain the change.

```guided-review
softschema:
  contract: metabrowser.collection:Collection/v1
  envelope: collection
  status: enforced
collection:
  comparison:
    merge_base: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    head: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  items:
    - title: Start here
      note: Check it.
      references:
        - {path: a.py}
```"""


@pytest.mark.parametrize(
    ("body", "shown"),
    [
        (_GUIDE, "Explain the change."),
        # A block the guide route refuses is the description's own text, shown as written:
        # the wrong contract, a field the contract lacks, and YAML that does not parse.
        (_GUIDE.replace("status: enforced", "status: soft"), None),
        (_GUIDE.replace("note: Check it.", "nope: Check it."), None),
        (_GUIDE.replace("  items:\n", "  items: [\n"), None),
    ],
)
def test_the_description_renders_without_only_a_readable_guide(
    rendered: list[str], monkeypatch: pytest.MonkeyPatch, body: str, shown: str | None
) -> None:
    record = _record(body)
    monkeypatch.setattr(pull_markdown, "cached_pull_record", lambda *_: (record, None, "f" * 64))
    status, _answer = asyncio.run(pull_markdown.render_part(_VIEW, "body"))
    assert status == 200
    assert rendered == [body if shown is None else shown]


def test_a_core_previews_description_renders_without_its_guide(
    rendered: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A preview's description is drawn as the record's will be, so a guided pull request's
    front page, its guide, opens on the same introduction (B3 of review B on #677)."""
    record = _record(_GUIDE)
    monkeypatch.setattr(pull_markdown, "cached_pull_record", lambda *_: ("not_cached", None, None))
    preview: Any = {"pull": record.pull.model_dump(mode="json"), "revision": "a" * 64}

    async def core() -> Any:
        return preview

    status, answer = asyncio.run(pull_markdown.render_part(_VIEW, "body", current_core=core))
    assert (status, answer["core_revision"]) == (200, "a" * 64)
    assert rendered == ["Explain the change."]


def test_the_guide_and_its_introduction_share_one_parse(
    rendered: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The route's parse, kept for the record revision, cuts the description too, off the
    event loop (B11 of review B on #677)."""
    record = _record(_GUIDE)
    parses: list[str] = []
    real = guided_review._read_description

    def counting(body: str) -> Any:
        parses.append(body)
        return real(body)

    monkeypatch.setattr(guided_review, "_read_description", counting)
    monkeypatch.setattr(pull_markdown, "cached_pull_record", lambda *_: (record, None, "f" * 64))
    assert guided_review.read_guide(_KEY, "f" * 64, _GUIDE) is not None
    for _ in range(2):
        asyncio.run(pull_markdown.render_part(_VIEW, "body"))
    assert rendered == ["Explain the change."] * 2
    assert len(parses) == 1
