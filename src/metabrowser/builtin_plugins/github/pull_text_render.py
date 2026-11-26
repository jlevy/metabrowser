"""A text of a pull request rendered as inert HTML, in the server's Markdown child.

The pull-markdown route (:mod:`.pull_markdown`) renders the description and each comment
through :func:`render_text`, and the guided-review route (:mod:`.guided_review`) renders a
guide's notes, which are texts of the description, through it too. It imports neither
route's module, so each imports it at the top: the description's route imports the guide's
module for the description's introduction, and the guide's would otherwise import the
description's back.
"""

from __future__ import annotations

import hashlib

from metabrowser.diff.markdown_projection_worker import InertRender, shared_worker, text_identity


async def render_text(text: str, *, number: int, part: str, link_base: str) -> str:
    """*text*, a text of pull request *number*, as inert HTML: KPress in its sanitized mode,
    then :func:`~metabrowser.inert_html.harden` against *link_base*, the pull request's page,
    in the Markdown child under its deadline.

    *part* names the text: a part ``PART_PATTERN`` in pull_markdown.py matches, or a guide's
    note, which renders as the description does (``guided_review.py``). Raises
    :class:`~metabrowser.diff.markdown_projection_worker.InertRenderRefused`, and KPress's
    ``KPressInvalidRequestError`` and ``KPressRenderError``.
    """
    # KPress caches a render by this key, and the Markdown child joins a request to one in
    # flight with the same key (`InertRender.flight_key`). A render is of the part's text
    # and the page its links resolve against alone, so the key is those and not when the
    # text was read: a page that asks again, a reload, a refresh that left the text as it
    # was, and the record that follows a core preview with its description unchanged all
    # reuse one render (mb-d59o).
    key = hashlib.sha256(f"{part}\0{link_base}\0{text}".encode()).hexdigest()[:16]
    # KPress's sanitized mode keeps what a document may load; in the page it must not, so
    # the child reduces the HTML to the allowlist against the pull request's page.
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
            mark_path_relative=True,
        )
    )
    return str(rendered["html"])


__all__ = ["render_text"]
