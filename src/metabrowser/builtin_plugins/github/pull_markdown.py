"""Text of the served pull request rendered as Markdown, from the cached record alone.

``GET /api/plugin/github/pull-markdown?part=<part>`` renders one text of the record
through the KPress adapter, the renderer every Markdown file goes through, in its
sanitized trust mode: raw HTML in the text is cleaned, never trusted, and GitHub's own
``body_html`` is never read. KPress keeps what a document of its own may use, so
:func:`~metabrowser.inert_html.harden` then reduces the HTML to a small allowlist of plain markup. A
part is ``body``, the description, or ``issue_comment/<id>``, ``review/<id>``, or
``review_comment/<id>``. The answer is that HTML with the record's ``fetched_at`` and the
``part``, so a page drops a render of a record it no longer shows. None of KPress's
render envelope reaches the page: its asset list names scripts KPress adds for what a
text contains, and a comment must not choose what the page loads.

It reads the record the pull route reads and never runs gh or Git. One part is one
render of at most one body, which the record bounds, so a page with many comments asks
for the ones a reader sees rather than the server rendering them all at once.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Final

from metabrowser import kpress_adapter
from metabrowser.builtin_plugins.github.pull_record import PullRecord
from metabrowser.builtin_plugins.github.pull_route import ServedPullView, cached_pull_record
from metabrowser.inert_html import harden

PART_PATTERN: Final = re.compile(r"^(?:body|(?:issue_comment|review|review_comment)/[0-9]{1,20})$")


def part_text(record: PullRecord, part: str) -> str | None:
    """The text *part* names in *record*, or ``None`` when it names none."""

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


def render_part(view: ServedPullView | None, part: str) -> tuple[int, dict[str, Any]]:
    """The status and body for one part. Blocking and bounded; run it off the loop."""

    if PART_PATTERN.fullmatch(part) is None:
        return 400, {"error": "name a part of the pull request", "code": "invalid_part"}
    if view is None:
        return 409, {"error": "this server serves no pull request", "code": "no_pull_request"}
    published = view.served.published
    number = view.served.number
    record, _dumped = cached_pull_record(published.home, published.slug, number)
    if not isinstance(record, PullRecord):
        return 404, {"error": "no record of this pull request is cached", "code": record}
    text = part_text(record, part)
    if text is None:
        return 404, {"error": "the record has no such part", "code": "unknown_part"}
    # KPress caches a render by this key, so a page that asks again, or a reload, costs
    # nothing until a refresh changes the text.
    key = hashlib.sha256(f"{record.fetched_at}\0{part}\0{text}".encode()).hexdigest()[:16]
    try:
        rendered = kpress_adapter.render_kpress_view(
            source_text=text,
            source_path=f"pull-{number}-{part.replace('/', '-')}.md",
            kind="markdown",
            view="document",
            ext=".md",
            mtime_hash=key,
            size=len(text.encode()),
            include_toc="off",
        )
    except (kpress_adapter.KPressInvalidRequestError, kpress_adapter.KPressRenderError) as exc:
        return 422, {"error": f"the text could not be rendered: {exc}", "code": "render_failed"}
    # KPress's sanitized mode keeps what a document may load; in the page it must not.
    html = harden(str(rendered["html"]), record.pull.html_url)
    return 200, {"number": number, "fetched_at": record.fetched_at, "part": part, "html": html}


__all__ = ["PART_PATTERN", "part_text", "render_part"]
