"""``.env`` / ``.env.local`` loader for the `metab` CLI.

Thin wrapper over ``python-dotenv`` that follows a conventional lookup:
walk up from the current working directory looking for both
``.env`` and ``.env.local``, and apply each into ``os.environ`` via
``setdefault`` so a shell-exported value always wins over a file value.

Trust model: files in the working tree are treated as trusted operator
configuration, with the exception of the keys in ``REFUSED_KEYS``.
Pointing metabrowser at an arbitrary served root does NOT pick up that
root's ``.env`` — the loader walks up from cwd, not from the served
root — but browsing a cloned repository from inside it does, so the
decisions about how far to trust browsed content are never read from a
file the browsed content can contain.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from metabrowser.capabilities import CAPABILITY_ENV_VARS

DOTENV_NAMES: tuple[str, ...] = (".env", ".env.local")
"""Files searched, in load order. ``.env.local`` is conventionally
gitignored for per-developer overrides; loaded after ``.env`` so its
keys win for any not-yet-set env var (we use ``override=False`` so a
shell-exported value still beats both)."""

REFUSED_KEYS: frozenset[str] = frozenset(
    {
        *CAPABILITY_ENV_VARS,
        # Every name here extends the set of domains whose pages a browser
        # will let read responses, which is the DNS-rebinding guard itself.
        "METABROWSER_ALLOWED_HOSTS",
    }
)
"""Keys a dotenv file may never contribute, in either direction.

The chain walks up from the working directory, so ``cd cloned-repo &&
metab --untrusted .`` reaches that repository's ``.env``. Honoring these
names from there would let the content being sandboxed choose its own
sandbox. They are read from the real process environment only, which is
what SECURITY.md documents."""


def load_dotenv_chain() -> list[Path]:
    """Apply ``.env`` then ``.env.local`` (whichever are found) into ``os.environ``.

    Uses ``python-dotenv``'s ``find_dotenv`` to walk up from cwd to the
    nearest ancestor that contains each filename. ``override=False``
    means existing env-var values are preserved (a shell-set value
    beats both files; ``.env.local`` only fills gaps left by ``.env``).
    ``REFUSED_KEYS`` are restored to their pre-load state afterwards, so
    no file value for them survives while every other key loads as before.

    Returns the list of files actually applied, in load order, for
    logging by callers that want to surface which files contributed.
    """
    preserved = {key: os.environ.get(key) for key in REFUSED_KEYS}
    applied: list[Path] = []
    try:
        for name in DOTENV_NAMES:
            found = find_dotenv(filename=name, usecwd=True)
            if found:
                load_dotenv(found, override=False)
                applied.append(Path(found))
    finally:
        for key, value in preserved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return applied


__all__ = ["DOTENV_NAMES", "REFUSED_KEYS", "load_dotenv_chain"]
