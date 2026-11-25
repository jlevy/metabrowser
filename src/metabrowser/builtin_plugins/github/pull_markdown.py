"""Text of a pull request rendered as Markdown, from the cached record alone.

``GET /api/plugin/github/pull-markdown?number=<n>&part=<part>`` renders one text of the record
through the KPress adapter, the renderer every Markdown file goes through, in its
sanitized trust mode: raw HTML in the text is cleaned, never trusted, and GitHub's own
``body_html`` is never read. KPress keeps what a document of its own may use, so
:func:`~metabrowser.inert_html.harden` then reduces the HTML to a small allowlist of plain markup. A
part is ``body``, the description, or ``issue_comment/<id>``, ``review/<id>``, or
``review_comment/<id>``. The answer carries the same parsed record's ``record_revision``
and its ``fetched_at`` timestamp and ``part``, so a page can drop superseded content even
when two records share a timestamp. It also carries the manifest of
KPress's stylesheets, which set the text as they set a Markdown file. That manifest is the
same for every text, and it is the only part of KPress's render envelope that reaches
the page: the render's own asset list names scripts KPress adds for what a text contains,
and a comment must not choose what the page loads.

A text's author is untrusted, and what KPress spends on a text depends on what it
contains, so the render and the hardening run in the server's Markdown child under its
deadline (:mod:`metabrowser.diff.markdown_projection_worker`), with fenced code plain:
the allowlist drops every class highlighting would add. A text that runs past the
deadline is refused with ``422`` and the code ``render_deadline``, and refused again at
once while the server runs; the page then shows it as plain text and says why.

It reads the record the pull route reads and never runs gh or Git. One part is one
render of at most one body, which the record bounds, so a page with many comments asks
for the ones a reader sees rather than the server rendering them all at once.

With no record cached, the description is the core preview's, the one the pull route
serves (``core_preview`` in its envelope, "Lightweight Cores" in
docs/project/architecture/arch-github-pull-requests.md), so a page that shows a preview
shows its description rendered rather than as Markdown source while the full record is
fetched. That answer carries the preview's ``revision`` as ``core_revision``, with
``record_revision`` and ``fetched_at`` null, and every other part is refused as the record's
absence. Measured 2026-11-18 in headless Chrome 152 on jlevy/metabrowser through the Pulls
tab, load average 14 to 19: a preview's description showed as source for 1.0 and 2.0 s
before this, the full record's fetch through gh and the page's next poll, and the owner saw
3 to 4 s (mb-d59o).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Final

from metabrowser import kpress_adapter
from metabrowser.builtin_plugins.github.guided_review import guide_introduction
from metabrowser.builtin_plugins.github.pull_record import PullRecord
from metabrowser.builtin_plugins.github.pull_route import PullView, cached_pull_record
from metabrowser.diff.markdown_projection_worker import (
    InertRender,
    InertRenderRefused,
    shared_worker,
    text_identity,
)

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.served_pull import PullCorePreview

PART_PATTERN: Final = re.compile(r"^(?:body|(?:issue_comment|review|review_comment)/[0-9]{1,20})$")


def part_text(record: PullRecord, part: str) -> str | None:
    """The text *part* names in *record*, as the record has it, or ``None`` when it names none.

    :func:`render_part` renders the description without its guide (:func:`_description`).
    """

    if part == "body":
        return record.pull.body
    kind, _, ident = part.partition("/")
    wanted = int(ident)
    items = {
        "issue_comment": record.issue_comments,
        "review": record.reviews,
        "review_comment": record.review_comments,
    }[kind]
    return next((item.body for item in items if item.id == wanted), None)


async def _description(key: tuple[str, str, int], revision: str, body: str) -> str:
    """The description as Conversation and Guided Review render it.

    The guide's block is the Guided Review tab's, so the description renders as its
    introduction, without the block, once the block reads as a guide; a block that does
    not stays, so its author sees what they wrote. The parse is the guide route's, kept
    for the revision (`read_guide` in guided_review.py), off the event loop.
    """
    if "guided-review" not in body:
        return body
    return await asyncio.to_thread(guide_introduction, key, revision, body)


async def render_part(
    view: PullView,
    part: str,
    *,
    current_core: Callable[[], Awaitable[PullCorePreview | None]] | None = None,
) -> tuple[int, dict[str, Any]]:
    """The status and body for one part.

    *current_core* answers the core preview the pull route would serve now, or ``None``; it
    is asked only for the description of a pull request with no record cached.
    """

    if PART_PATTERN.fullmatch(part) is None:
        return 400, {"error": "name a part of the pull request", "code": "invalid_part"}
    if view.host is None:
        return 409, {"error": "this server serves no GitHub repository", "code": "not_github"}
    served = view.host.pulls
    number = view.number
    record, _dumped, revision = await asyncio.to_thread(
        cached_pull_record, served.home, served.slug, number
    )
    preview = (
        await current_core()
        if not isinstance(record, PullRecord) and part == "body" and current_core is not None
        else None
    )
    key = (str(served.home), served.slug, number)
    if preview is not None:
        # A preview's description is drawn as the record's will be, so a guided pull
        # request's front page opens on its guide with the same introduction.
        text = await _description(
            key, f"core:{preview['revision']}", str(preview["pull"].get("body") or "")
        )
        link_base = str(preview["pull"].get("html_url") or "")
        answered = {
            "fetched_at": None,
            "record_revision": None,
            "core_revision": preview["revision"],
        }
    elif not isinstance(record, PullRecord):
        return 404, {"error": "This pull request has not been loaded.", "code": record}
    else:
        found = part_text(record, part)
        if found is None:
            return 404, {"error": "the record has no such part", "code": "unknown_part"}
        text = (
            await _description(key, revision, found)
            if part == "body" and revision is not None
            else found
        )
        link_base = record.pull.html_url
        answered = {"fetched_at": record.fetched_at, "record_revision": revision}
    # KPress caches a render by this key, and the Markdown child joins a request to one in
    # flight with the same key (`InertRender.flight_key`). A render is of the part's text
    # and the page its links resolve against alone, so the key is those and not when the
    # text was read: a page that asks again, a reload, a refresh that left the text as it
    # was, and the record that follows a core preview with its description unchanged all
    # reuse one render (mb-d59o).
    key = hashlib.sha256(f"{part}\0{link_base}\0{text}".encode()).hexdigest()[:16]
    try:
        # KPress's sanitized mode keeps what a document may load; in the page it must not,
        # so the child reduces the HTML to the allowlist against the pull request's page.
        rendered = await shared_worker().render_inert(
            InertRender(
                source_text=text,
                source_path=f"pull-{number}-{part.replace('/', '-')}.md",
                identity=text_identity(text),
                kind="markdown",
                view="document",
                ext=".md",
                mtime_hash=key,
                size=len(text.encode()),
                include_toc="off",
                link_base=link_base,
            )
        )
    except InertRenderRefused as refused:
        return refused.http_status, {**refused.payload(), "number": number, "part": part}
    except (kpress_adapter.KPressInvalidRequestError, kpress_adapter.KPressRenderError) as exc:
        return 422, {"error": f"the text could not be rendered: {exc}", "code": "render_failed"}
    return 200, {
        "number": number,
        **answered,
        "part": part,
        "html": str(rendered["html"]),
        "assets": await asyncio.to_thread(kpress_adapter.document_stylesheets),
    }


__all__ = ["PART_PATTERN", "part_text", "render_part"]
