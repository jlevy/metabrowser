"""The render bound for Markdown an untrusted author wrote, and the pinned viewer that holds it.

``metabrowser.markdown_render_bound`` estimates a document's render work from the
constructs a renderer was measured to spend on; ``git/content_routes.py`` opens a document
past it as Source on a pin, which runs under the untrusted profile, and renders one within
it with its fenced code plain. The estimate's shapes and their measured costs are recorded
beside its constants.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from metabrowser import kpress_adapter
from metabrowser.capabilities import Capabilities, set_capabilities
from metabrowser.git.tree_source import GitPath
from metabrowser.markdown_render_bound import (
    DOCUMENT_BYTES,
    DOCUMENT_WORK_MS,
    document_work_ms,
    within_render_bound,
)
from tests.git_pin_harness import fast_import_store, pinned_client

_CAP = DOCUMENT_BYTES


def _repeat(unit: bytes, head: bytes = b"") -> bytes:
    return (head + unit * (_CAP // len(unit) + 1))[:_CAP]


@pytest.mark.parametrize(
    "separator", [b"\n\x0b\n", b"\n\x0c\n", b"\n\n", b"\n \t\n"], ids=["vt", "ff", "blank", "ws"]
)
def test_the_render_bound_counts_the_whole_document(separator: bytes) -> None:
    """Review C1 on #348: no line, blank or not, resets the count.

    The old per-block rule reset on any line ``bytes.strip`` emptied, which ``\\x0b`` and
    ``\\x0c`` lines are, though CommonMark keeps them inside the paragraph.
    """
    body = separator.join([b"[" * 200] * 40) + b"x"
    assert document_work_ms(body) > DOCUMENT_WORK_MS


_COSTLY = [
    _repeat(b"["),
    _repeat(b"$a$ "),
    _repeat(b"|a|b|\n", b"|a|b|\n|-|-|\n"),
    _repeat(b"- [ ] a\n"),
    _repeat(b"# h\n"),
    _repeat(b"- a\n"),
    _repeat(b"*a"),
    _repeat(b"$a$"),
    (b"[" * 16384 + b"$a$" * _CAP)[:_CAP],
    _repeat(b"a\n\n"),
    _repeat(b"a\\\n"),
    (b"$a$ " * 2200 + b"a\n\n" * _CAP)[:_CAP],
    _repeat(b"> - [ ] a\n"),
    _repeat(b"- - [ ] a\n"),
]
_COSTLY_IDS = [
    "brackets",
    "math",
    "table",
    "tasks",
    "headings",
    "list",
    "emphasis",
    "math-run",
    "brackets-then-math",
    "paragraphs",
    "backslash-breaks",
    "math-then-paragraphs",
    "quoted-tasks",
    "nested-tasks",
]


@pytest.mark.parametrize("body", _COSTLY, ids=_COSTLY_IDS)
def test_each_measured_costly_shape_at_the_cap_opens_as_source(body: bytes) -> None:
    """Reviews A4, F1, and F2: what took 0.5 to 6.4 s at 64 KiB is refused before it renders."""
    assert len(body) == _CAP
    assert document_work_ms(body) > DOCUMENT_WORK_MS
    assert not within_render_bound(body)


@pytest.mark.parametrize(
    "body",
    [b"- [ ] a\r" * 1025, b"-\n  [ ] a\n" * 1025, b"> - > - [ ] a\n" * 1025],
    ids=["cr-tasks", "blank-first-tasks", "quote-in-list-tasks"],
)
def test_task_items_past_the_count_open_as_source_however_written(body: bytes) -> None:
    """Review F2: a task is one behind any container, on its own line, or after a `\\r`."""
    assert document_work_ms(body) > DOCUMENT_WORK_MS
    assert not within_render_bound(body)


def test_ordinary_documents_are_within_the_render_bound() -> None:
    root = Path(__file__).resolve().parent.parent
    prose = b"Ordinary prose line with words, `code`, and a [link](a.md).\n" * 2000
    for body in (
        prose[:_CAP],
        (root / "README.md").read_bytes()[:_CAP],
        (root / "CHANGELOG.md").read_bytes()[:_CAP],
        (root / "docs" / "reviewing-pull-requests.md").read_bytes()[:_CAP],
        # Console transcripts, which render in 43 to 73 ms; review F3 found them refused.
        (root / "tests" / "golden" / "cli-ui-github-pull-page.tryscript.md").read_bytes()[:_CAP],
        (root / "tests" / "golden" / "cli-api-cache.tryscript.md").read_bytes()[:_CAP],
    ):
        assert within_render_bound(body)
    assert not within_render_bound(prose[: _CAP + 1] + b"x")


def _fence(language: bytes, code: bytes) -> bytes:
    return b"```" + language + b"\n" + code + b"\n```\n"


_FENCES = {
    "console-prompt-after-venv": _fence(b"console", b"(x)(a)" + b"b" * 800 + b"@" * 800),
    "console-prompt-brackets": _fence(b"console", b"[a@]" * 1000),
    "devicetree": _fence(b"devicetree", b"aaaaaaa," * 6058),
    "systemd": _fence(b"systemd", b"aaaaaaa," * 6058),
    "registry": _fence(b"registry", b"aaaaaaa," * 6058),
    "make": _fence(b"make", (b"a" * 63 + b",") * 1020),
    "spaced-ruby": _fence(b"ruby", b"a " * 12700),
    "quoted-ruby": b"> ```ruby\n" + (b"> " + b"a," * 32 + b"\n") * 300,
}


def _wire(name: str) -> str:
    return GitPath.from_display(name).to_wire()


def _untrusted() -> None:
    set_capabilities(Capabilities(active_content=False, mutations=False))


def test_a_pinned_document_past_the_bound_opens_as_source_and_renders_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q3 of the View on branch plan: the bound moved from the revision page to the pin.

    A pin runs under the untrusted profile. Its file envelope offers no Document for a
    Markdown file past the bound, so the page opens it in Source; a request to render it
    anyway is refused before KPress is asked, at once. A file within it renders, and a
    trusting profile renders either.
    """

    costly = _repeat(b"[*a*a")
    store, commit = fast_import_store(
        tmp_path,
        {b"costly.md": costly, b"large.md": b"Prose.\n" * (_CAP // 7 + 1), b"fine.md": b"# Fine\n"},
    )
    rendered: list[str] = []
    real = kpress_adapter.render_kpress_view

    def counted(**kwargs: object) -> dict[str, object]:
        rendered.append(str(kwargs["source_path"]))
        return real(**kwargs)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(kpress_adapter, "render_kpress_view", counted)

    async def run() -> dict[str, object]:
        seen: dict[str, object] = {}
        async with pinned_client(store, commit) as (client, _subject):
            _untrusted()
            for name in ("costly.md", "large.md", "fine.md"):
                envelope = (await client.get("/api/file", params={"path": _wire(name)})).json()
                seen[f"{name} views"] = [view["id"] for view in envelope["views"]]
                seen[f"{name} default"] = next(
                    view["id"] for view in envelope["views"] if view.get("default")
                )
                started = time.monotonic()
                answer = await client.get(
                    "/api/kpress/render", params={"path": _wire(name), "view": "rendered"}
                )
                seen[f"{name} render"] = answer.status_code
                seen[f"{name} seconds"] = time.monotonic() - started
                if answer.status_code == 413:
                    seen[f"{name} error"] = answer.json()["error"]
            set_capabilities(Capabilities(active_content=True, mutations=False))
            trusted = await client.get("/api/file", params={"path": _wire("costly.md")})
            seen["trusted views"] = [view["id"] for view in trusted.json()["views"]]
        return seen

    seen = asyncio.run(run())
    for name in ("costly.md", "large.md"):
        assert seen[f"{name} views"] == ["source"], seen
        assert seen[f"{name} default"] == "source"
        assert seen[f"{name} render"] == 413
        assert seen[f"{name} error"] == (
            "This document is too costly to render from an untrusted source"
        )
        # Refused by the estimate, not by a render: the shape took 1.8 s to render.
        assert float(str(seen[f"{name} seconds"])) < 1.0, seen
    assert seen["fine.md views"] == ["rendered", "source"]
    assert seen["fine.md render"] == 200
    assert rendered == [_wire("fine.md")]
    assert seen["trusted views"] == ["rendered", "source"]


@pytest.mark.parametrize("body", list(_FENCES.values()), ids=list(_FENCES))
def test_a_pinned_document_renders_its_fenced_code_plain_whatever_language_it_names(
    body: bytes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review G1 to G3: an untrusted author's fence never reaches a lexer.

    Each took 12 to 79 s to highlight within the estimate, and some held the interpreter
    throughout. Shown as escaped plain code, each is admitted by the text's own charges and
    renders like any text; under a trusting profile the same render highlights.
    """

    from kpress.format import markdown as kpress_markdown

    def refuse(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("the pinned viewer highlighted an untrusted author's fence")

    monkeypatch.setattr(kpress_markdown, "highlight", refuse)
    kpress_adapter.clear_render_cache()
    assert within_render_bound(body)
    store, commit = fast_import_store(tmp_path, {b"README.md": body})

    async def run() -> tuple[int, str]:
        async with pinned_client(store, commit) as (client, _subject):
            _untrusted()
            answer = await client.get(
                "/api/kpress/render", params={"path": _wire("README.md"), "view": "rendered"}
            )
            return answer.status_code, str(answer.json().get("html", ""))

    status, html = asyncio.run(run())
    assert status == 200, html
    assert '<pre class="kpress-code">' in html or "<pre><code>" in html, html[:400]
    code = html.split("<pre", 1)[1]
    # Highlighted code came through the inert render as a classless span a token.
    assert "<span" not in code.split("</pre>", 1)[0]
