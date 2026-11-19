"""A commit message's body rendered as Markdown, as a pull request's description is.

``GET /api/git/commit-markdown/{revision}`` reads the commit's message and renders its body,
everything after the subject line, through the path a pull request's description takes
(:mod:`metabrowser.builtin_plugins.github.pull_markdown`): KPress in its sanitized mode in
the server's Markdown child under its deadline, with fenced code plain, and
:func:`metabrowser.inert_html.harden` reducing the HTML to its allowlist of plain markup
(:mod:`metabrowser.diff.markdown_projection_worker`, ``InertRender``). The answer carries
the same manifest of KPress's stylesheets, and the page sets the HTML as the pull request
page sets a description: through ``static/inert-html.js`` into a KPress article of its
own. The subject is not rendered; ``/api/git/commit/{revision}`` keeps the message as
written for the hover card and for a body this route will not render.

What a commit body is, and how it differs from a description:

- **Line breaks.** KPress reads Markdown as CommonMark does, a pull request's description
  included: a single newline inside a paragraph is a soft break, so a body hard-wrapped at
  72 columns reflows into paragraphs at the page's width, a blank line ends a paragraph,
  and a line ending in two spaces or a backslash breaks where it ends. github.com shows a
  commit body as preformatted text instead, and breaks a comment's line at every
  newline; neither suits a hard-wrapped body set at another width.
- **Trailers.** Git's trailers (``Signed-off-by:``, ``Co-Authored-By:``) are lines a
  paragraph would join into one run of text, so the trailer block is split off before the
  render and answered as written, for the page to show as a block of its own lines
  (:func:`split_trailers`).
- **Links.** A description's links resolve against its pull request's github.com page. A
  commit message has no page whose relative references it could mean, so its links
  resolve against :data:`COMMIT_MESSAGE_LINK_BASE`: an absolute ``http`` or ``https`` link
  is kept, opening in a new tab, and every relative reference, fragment, and
  protocol-relative address loses its address and keeps its text. An image becomes a link
  to its absolute address. ``#123`` and a bare URL stay text, as they do in a
  description: KPress links neither.
- **Size.** A description is cut to its bound when its record is written. A commit's
  message is in the repository whole, so a body past
  :data:`~metabrowser.settings.GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES` is not cut: the route
  refuses it with ``body_too_large``, and the page shows the message as written.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any, Final

from metabrowser import kpress_adapter
from metabrowser.diff.markdown_projection_worker import (
    InertRender,
    InertRenderRefused,
    shared_worker,
    text_identity,
)
from metabrowser.git.detail import _UNKNOWN_REVISION_MARKERS, _split_message
from metabrowser.git.process import GitCommandError, GitLocation, run_git_at
from metabrowser.settings import GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES

# The base a commit body's links resolve against, on the server (``inert_html.harden``)
# and in the page (``static/inert-html.js``, which the route's answer hands it). Nothing
# relative resolves against ``about:blank`` in either: Python's ``urljoin`` returns a
# reference unchanged for a base whose scheme takes no relative references, and a
# browser's URL parser refuses one against an opaque base. Both then drop the address as
# not ``http`` or ``https``, while an absolute ``http`` or ``https`` address is unchanged.
COMMIT_MESSAGE_LINK_BASE: Final = "about:blank"

# A trailer line, as git reads one: a token of letters, digits, and hyphens, a colon, and
# a value. Git also takes a value with no space after the colon, which would make a line
# that is only a URL a trailer (``https://...``); one space or tab is required here.
_TRAILER_LINE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*:[ \t]+\S.*")
# A trailer's value folded onto the next line, which git reads as part of it.
_CONTINUATION_LINE: Final = re.compile(r"[ \t]+\S.*")
# The note ``git cherry-pick -x`` appends, which git counts as a trailer.
_CHERRY_PICK_LINE: Final = re.compile(r"\(cherry picked from commit [0-9a-f]{4,64}\)")

# ``%H`` first, so an object ID that is not a commit's, whose ``show`` is not this format,
# is told apart from a commit; ``%B`` is the message as git writes it, the field
# ``detail.py`` reads.
_MESSAGE_FORMAT: Final = "--format=%H%x00%B"


def split_trailers(body: str) -> tuple[str, str]:
    """Split *body* into ``(prose, trailers)``: the text to render, and the trailer block.

    The trailer block is the body's last paragraph when every line of it is a trailer
    (``Token: value``), a value folded onto an indented line under one, or git's
    cherry-pick note. That is git's own rule when every line is a trailer; git also takes
    a block where a quarter of the lines are trailers, one of them ``Signed-off-by``, which
    would show prose as trailers, so that one is not followed. A body that is only a
    trailer block has no prose. The block is returned as written, its lines joined by
    newlines; *prose* is what comes before it, without the blank lines between.
    """

    lines = body.split("\n")
    start = len(lines)
    while start > 0 and lines[start - 1].strip() != "":
        start -= 1
    block = lines[start:]
    if not block:
        return body, ""
    folded = False
    for line in block:
        if _TRAILER_LINE.fullmatch(line) or _CHERRY_PICK_LINE.fullmatch(line.rstrip()):
            folded = True
        elif not (folded and _CONTINUATION_LINE.fullmatch(line)):
            return body, ""
    return "\n".join(lines[:start]).rstrip(), "\n".join(block)


async def read_commit_message(location: GitLocation, revision: str) -> str | None:
    """The full message of the commit *revision* at *location*, or ``None`` when it has none.

    One ``git show`` with no diff (``-s``): a message is read without the changed files the
    commit route lists. ``None`` names a revision the repository lacks or one that is not a
    commit's.
    """

    try:
        raw = await run_git_at(
            ["show", *location.diff_driver_args, "-s", _MESSAGE_FORMAT, revision], location
        )
    except GitCommandError as exc:
        if any(marker in exc.stderr_summary.lower() for marker in _UNKNOWN_REVISION_MARKERS):
            return None
        raise
    text = raw.decode("utf-8", errors="replace")
    named, separator, message = text.partition("\0")
    if separator == "" or named != revision:
        return None
    return message


async def render_commit_body(message: str, revision: str) -> tuple[int, dict[str, Any]]:
    """The status and answer for the body of *message*, the message of commit *revision*.

    ``html`` is the body's prose rendered and hardened, or empty when the body is only
    trailers or empty; ``trailers`` is the trailer block as written, or empty.
    """

    _subject, body = _split_message(message)
    prose, trailers = split_trailers(body)
    size = len(prose.encode("utf-8", "surrogatepass"))
    if size > GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES:
        return 422, {
            "error": (
                f"the message is {size} bytes, more than the "
                f"{GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES} rendered as Markdown"
            ),
            "code": "body_too_large",
            "max_bytes": GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES,
            "revision": revision,
        }
    html = ""
    if prose:
        # KPress caches a render by this key, and the Markdown child joins a request to one
        # in flight with the same key (`InertRender.flight_key`). A commit's message never
        # changes, so the key is its revision and the text alone, as a description's is
        # its part and text (`pull_markdown.render_part`).
        key = hashlib.sha256(f"commit\0{revision}\0{prose}".encode()).hexdigest()[:16]
        try:
            rendered = await shared_worker().render_inert(
                InertRender(
                    source_text=prose,
                    source_path=f"commit-{revision}.md",
                    identity=text_identity(prose),
                    kind="markdown",
                    view="document",
                    ext=".md",
                    mtime_hash=key,
                    size=size,
                    include_toc="off",
                    link_base=COMMIT_MESSAGE_LINK_BASE,
                )
            )
        except InertRenderRefused as refused:
            return refused.http_status, {**refused.payload(), "revision": revision}
        except (
            kpress_adapter.KPressInvalidRequestError,
            kpress_adapter.KPressRenderError,
        ) as exc:
            return 422, {
                "error": f"the message could not be rendered: {exc}",
                "code": "render_failed",
                "revision": revision,
            }
        html = str(rendered["html"])
    return 200, {
        "is_repo": True,
        "revision": revision,
        "html": html,
        "trailers": trailers,
        "link_base": COMMIT_MESSAGE_LINK_BASE,
        "assets": await asyncio.to_thread(kpress_adapter.document_stylesheets),
    }


__all__ = [
    "COMMIT_MESSAGE_LINK_BASE",
    "read_commit_message",
    "render_commit_body",
    "split_trailers",
]
