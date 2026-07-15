"""``.env`` / ``.env.local`` loader for the `metab` CLI.

Thin wrapper over ``python-dotenv`` that follows a conventional lookup:
walk up from the current working directory looking for both
``.env`` and ``.env.local``, and apply each into ``os.environ`` via
``setdefault`` so a shell-exported value always wins over a file value.

Trust model: files in the working tree are treated as trusted operator
configuration. Pointing metabrowser at an arbitrary served root does
NOT pick up that root's ``.env`` — the loader walks up from cwd, not
from the served root.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import find_dotenv, load_dotenv

DOTENV_NAMES: tuple[str, ...] = (".env", ".env.local")
"""Files searched, in load order. ``.env.local`` is conventionally
gitignored for per-developer overrides; loaded after ``.env`` so its
keys win for any not-yet-set env var (we use ``override=False`` so a
shell-exported value still beats both)."""


def load_dotenv_chain() -> list[Path]:
    """Apply ``.env`` then ``.env.local`` (whichever are found) into ``os.environ``.

    Uses ``python-dotenv``'s ``find_dotenv`` to walk up from cwd to the
    nearest ancestor that contains each filename. ``override=False``
    means existing env-var values are preserved (a shell-set value
    beats both files; ``.env.local`` only fills gaps left by ``.env``).

    Returns the list of files actually applied, in load order, for
    logging by callers that want to surface which files contributed.
    """
    applied: list[Path] = []
    for name in DOTENV_NAMES:
        found = find_dotenv(filename=name, usecwd=True)
        if found:
            load_dotenv(found, override=False)
            applied.append(Path(found))
    return applied


__all__ = ["DOTENV_NAMES", "load_dotenv_chain"]
