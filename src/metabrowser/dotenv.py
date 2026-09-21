"""``.env`` / ``.env.local`` loader for the `metab` CLI.

Thin wrapper over ``python-dotenv`` that follows a conventional lookup:
walk up from the current working directory looking for both
``.env`` and ``.env.local``, and apply each into ``os.environ`` via
``setdefault`` so a shell-exported value always wins over a file value.

Trust model: a dotenv file may contribute only the names in
``ALLOWED_KEYS``. The loader walks up from the working directory, so
``cd cloned-repo && metab .`` reaches that repository's own ``.env``,
and the loader cannot tell that file apart from one the operator wrote.
An allowlist is therefore the only shape that holds: a denylist secures
the names somebody thought of, and the environment is full of names that
decide which program runs — ``BROWSER``, which the standard library's
browser launcher honors, and the ``GIT_*`` variables that select an
external diff or ssh command, to say nothing of ``PATH``.
Everything outside the allowlist is read from the real process
environment or not at all.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from metabrowser.capabilities import CAPABILITY_ENV_VARS

DOTENV_NAMES: tuple[str, ...] = (".env", ".env.local")
"""Files searched, in load order. ``.env.local`` is conventionally
gitignored for per-developer overrides; loaded after ``.env`` so its
keys win for any not-yet-set env var (we use ``override=False`` so a
shell-exported value still beats both)."""

ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        # Log verbosity and request-log detail. Neither reaches a
        # decision about content; the worst a browsed repository buys by
        # setting them is a noisier terminal.
        "METABROWSER_LOG_LEVEL",
        "METABROWSER_REQUEST_LOG",
        "METABROWSER_SLOW_SERVER_MS",
        # Rendering budgets. These bound how much of a file is read or
        # highlighted, so the worst case is a larger or smaller preview
        # of content the operator already asked to see.
        "METABROWSER_HIGHLIGHT_MAX_BYTES",
        "METABROWSER_TEXT_PREVIEW_BYTES",
        "METABROWSER_TEXT_PREVIEW_MAX_BYTES",
        "METABROWSER_BINARY_PREVIEW_BYTES",
        "METABROWSER_BINARY_PREVIEW_MAX_BYTES",
        "METABROWSER_BINARY_PREVIEW_MAX_CHUNK_BYTES",
        "STRUCTURED_CACHE_SIZE",
        "STRUCTURED_PARSE_MAX_BYTES",
    }
)
"""The only keys a dotenv file may contribute.

The test for membership is what the name's worst case costs when the
file belongs to the repository being browsed rather than to the
operator. A rendering budget changes how much of a document is shown.
The names kept out change something else: what executes
(``BROWSER``, ``GIT_EXTERNAL_DIFF``, ``PATH``), how far content is
trusted (``METAB_UNTRUSTED`` and its siblings), which JavaScript loads
into the application page (``METABROWSER_PLUGINS_DIRS``), which origins
may read responses (``METABROWSER_ALLOWED_HOSTS``), where the server
binds or connects (``METABROWSER_HOST``, ``METABROWSER_PORT``,
``METABROWSER_GCP_PROJECT``), which routes exist
(``METABROWSER_DEBUG``), and which engine walks the tree
(``METABROWSER_INVENTORY_PROVIDER``).

Adding a name here is a trust decision. Ask what a hostile repository
gains by setting it before adding one."""

# The capability variables decide how far content is trusted, so a file
# the content controls must never supply them. Asserted rather than
# assumed: the allowlist and ``capabilities`` are edited by different
# hands, and this is the invariant that would otherwise fail silently.
assert not (ALLOWED_KEYS & set(CAPABILITY_ENV_VARS)), (
    "capability variables must never be loadable from a dotenv file"
)


def _restore_outside_allowlist(before: Mapping[str, str]) -> None:
    """Undo every environment change the files made outside the allowlist.

    ``load_dotenv(override=False)`` only adds names today, but restoring
    against a full snapshot keeps the guarantee from depending on that.
    """

    for key in [name for name in os.environ if name not in ALLOWED_KEYS]:
        original = before.get(key)
        if original is None:
            del os.environ[key]
        elif os.environ[key] != original:
            os.environ[key] = original
    for key, value in before.items():
        if key not in ALLOWED_KEYS and key not in os.environ:
            os.environ[key] = value


def load_dotenv_chain() -> list[Path]:
    """Apply ``.env`` then ``.env.local`` (whichever are found) into ``os.environ``.

    Uses ``python-dotenv``'s ``find_dotenv`` to walk up from cwd to the
    nearest ancestor that contains each filename. ``override=False``
    means existing env-var values are preserved (a shell-set value
    beats both files; ``.env.local`` only fills gaps left by ``.env``).
    Every name outside ``ALLOWED_KEYS`` is restored to its pre-load
    state afterwards, so no file value for it survives.

    Returns the list of files actually applied, in load order, for
    logging by callers that want to surface which files contributed.
    """

    before = dict(os.environ)
    applied: list[Path] = []
    try:
        for name in DOTENV_NAMES:
            found = find_dotenv(filename=name, usecwd=True)
            if found:
                load_dotenv(found, override=False)
                applied.append(Path(found))
    finally:
        _restore_outside_allowlist(before)
    return applied


__all__ = ["ALLOWED_KEYS", "DOTENV_NAMES", "load_dotenv_chain"]
