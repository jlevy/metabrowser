"""One failure vocabulary for bounded content reads.

A data hook reads content without knowing whether the active subject is an
attached folder or an immutable Git-revision pin. The two kinds fail for
different underlying reasons -- a malformed gzip trailer, a ``cat-file``
deadline -- and a hook forced to name both families would have two error paths
and would get one of them wrong on the kind its author did not test.

So the typed errors those layers already raise keep their names, meanings, and
detail fields and gain one shared supertype plus the two facts a hook acts on: a
stable ``code`` and the ``http_status`` the server already answers with. Nothing
here replaces an existing exception, and there is no second taxonomy to keep in
step; this is the supertype over the existing one.

The statuses are the ones ``git.content_routes.git_content_failure_response``
already returns for the Git family, so a plugin hook and a pinned route cannot
disagree about what one failure means.
"""

from __future__ import annotations


class ContentReadError(Exception):
    """Base for every failure a bounded content read reports.

    ``code`` is the stable token a response envelope carries; ``http_status``
    is what a route answers when it has no more specific shape of its own.

    ``reader_message`` is the sentence a page shows a reader for the failure
    (docs/design-system-messages.md). ``str()`` is the failure's own account, for an
    agent and the log: it may name an object ID, a limit, or a command, so a route
    answers it as ``detail`` (:func:`content_error_wire`), never as ``error``.
    """

    code: str = "content_failed"
    http_status: int = 500
    reader_message: str = "This file could not be read."


class ContentUnavailableError(ContentReadError):
    """The content a reference named is gone, unreadable, or never existed.

    Resolution answers a missing identity with ``None``; this is the narrower
    case of content that resolved and then could not be read, which a
    filesystem race and a store missing an object both produce.
    """

    code = "content_unavailable"
    http_status = 404
    reader_message = "This file is no longer available."


def content_error_wire(exc: ContentReadError) -> dict[str, str]:
    """A failed read as a route answers it: the reader's sentence, the failure's own
    account as ``detail``, and its code."""
    return {"error": exc.reader_message, "detail": str(exc), "code": exc.code}


__all__ = ["ContentReadError", "ContentUnavailableError", "content_error_wire"]
