"""``.env`` / ``.env.local`` loader for the `metab` CLI.

Thin wrapper over ``python-dotenv`` that follows a conventional lookup:
walk up from the current working directory looking for both ``.env`` and
``.env.local``, and apply each with ``setdefault`` so a shell-exported
value always wins over a file value.

Trust model: a dotenv file may contribute only the names in
``ALLOWED_KEYS``. The chain walks up from the working directory, so
``cd cloned-repo && metab .`` reaches that repository's own ``.env``, and
the loader cannot tell that file apart from one the operator wrote. An
allowlist is therefore the only shape that holds: a denylist secures the
names somebody thought of, and the environment is full of names that
decide which program runs — ``BROWSER``, which the standard library's
browser launcher honors, the ``GIT_*`` variables that select an external
diff or ssh command, and ``PATH``.

The file is parsed rather than loaded: ``dotenv_values`` reads it without
touching ``os.environ``, so a value outside the allowlist is never
written to the process environment even transiently.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import dotenv_values, find_dotenv

from metabrowser.capabilities import CAPABILITY_ENV_VARS

log = logging.getLogger(__name__)

DOTENV_NAMES: tuple[str, ...] = (".env", ".env.local")
"""Files searched, in load order. ``.env.local`` is conventionally
gitignored for per-developer overrides; loaded after ``.env``, and
``setdefault`` means it only fills gaps ``.env`` left."""

ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        # Log verbosity. Read once through ``VALID_LOG_LEVELS``, so an
        # unknown value falls back to INFO rather than raising.
        "METABROWSER_LOG_LEVEL",
        # Verbose request log. Read as an equality test against one
        # literal, so no value can fail to parse.
        "METABROWSER_REQUEST_LOG",
    }
)
"""The only keys a dotenv file may contribute.

Membership has one test, and it is narrower than it looks: the name must
be consumed by a *total* parser, so that no value a hostile repository
writes can change what the program does beyond the knob's own meaning.
Both names here are read that way — one through ``VALID_LOG_LEVELS``,
one as an equality test — so the worst a browsed repository buys by
setting them is a noisier terminal.

The rendering budgets (``METABROWSER_*_MAX_BYTES``, ``STRUCTURED_*``, and
``METABROWSER_SLOW_SERVER_MS``) are deliberately **not** here. Each is
parsed with ``int()`` at import and is the upper bound on a request-path
read, so a file value could crash the process before anything renders or
lift a cap that exists to keep a large document from exhausting memory.
They are operator knobs: export them.

Also outside, for the reason each name carries: what executes
(``BROWSER``, ``GIT_EXTERNAL_DIFF``, ``PATH``), how far content is
trusted (``METAB_UNTRUSTED`` and its siblings), which JavaScript loads
into the application page (``METABROWSER_PLUGINS_DIRS``), which origins
may read responses (``METABROWSER_ALLOWED_HOSTS``), where a remote
session connects (``METABROWSER_GCP_PROJECT``), which routes exist
(``METABROWSER_DEBUG``), which engine walks the tree
(``METABROWSER_INVENTORY_PROVIDER``), and where the toolchain looks for
configuration and credentials (``HOME``).

Adding a name here is a trust decision. Ask what a hostile repository
gains by setting it, and check its parser is total, before adding one."""

# Names whose refusal is worth reporting: a dotenv file carrying one was
# almost certainly written by the operator, so silence would look like a
# bug. An unrelated project's own variables are not reported, because
# every repository has those and the noise would train the warning away.
_REPORTED_PREFIXES: tuple[str, ...] = ("METABROWSER_", "METAB_", "STRUCTURED_")

# The chain is loaded at several bootstrap points in one process -- the CLI
# mode, the server module, one-shot plugin discovery -- and each would
# otherwise repeat the same warning. Report each file once per process, so
# the message stays a signal.
_reported: set[Path] = set()

# The capability variables decide how far content is trusted, so a file
# the content controls must never supply them. Checked at import rather
# than asserted: ``python -O`` strips ``assert``, and this invariant
# should hold in an optimized process too.
if ALLOWED_KEYS & set(CAPABILITY_ENV_VARS):
    raise RuntimeError("capability variables must never be loadable from a dotenv file")


def load_dotenv_chain() -> list[Path]:
    """Apply the allowlisted names from ``.env`` then ``.env.local``.

    Uses ``python-dotenv``'s ``find_dotenv`` to walk up from cwd to the
    nearest ancestor containing each filename, and ``dotenv_values`` to
    parse it without touching ``os.environ``. Allowlisted names are
    applied with ``setdefault``, so a shell-set value beats both files
    and ``.env`` beats ``.env.local``. Every other name is ignored, and
    those carrying one of this package's prefixes are reported at
    WARNING so an operator is not left guessing.

    Returns the files found and parsed, in load order, for callers that
    want to surface which files were consulted. A file every one of
    whose names was ignored still appears.
    """

    parsed: list[Path] = []
    for name in DOTENV_NAMES:
        found = find_dotenv(filename=name, usecwd=True)
        if not found:
            continue
        path = Path(found)
        parsed.append(path)
        ignored: list[str] = []
        for key, value in dotenv_values(found).items():
            if value is None:
                continue
            if key in ALLOWED_KEYS:
                os.environ.setdefault(key, value)
            elif key.startswith(_REPORTED_PREFIXES):
                ignored.append(key)
        if ignored and path not in _reported:
            _reported.add(path)
            # Names only, never values: a refused name is often a secret's.
            log.warning(
                "%s: ignored %s — a dotenv file may only set %s. "
                "Export the others in the environment instead; see SECURITY.md.",
                path,
                ", ".join(sorted(ignored)),
                ", ".join(sorted(ALLOWED_KEYS)),
            )
    return parsed


__all__ = ["ALLOWED_KEYS", "DOTENV_NAMES", "load_dotenv_chain"]
