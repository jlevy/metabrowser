"""Optional public GitHub avatars, restricted to one image origin and size."""

from __future__ import annotations

import re
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import BeforeValidator

_PATH = re.compile(r"/(?:u|in)/[0-9]{1,20}")


def avatar_url(value: object) -> str | None:
    """Normalize a provider/cache URL, or leave an unsupported avatar absent."""
    if not isinstance(value, str) or len(value) > 512:
        return None
    if any(ord(char) < 33 or ord(char) == 127 or char == "\\" for char in value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.netloc != "avatars.githubusercontent.com"
        or parsed.fragment
        or _PATH.fullmatch(parsed.path) is None
    ):
        return None
    return f"https://avatars.githubusercontent.com{parsed.path}?s=40"


def avatar_of(actor: object) -> str | None:
    """Read an optional actor without making a deleted account an unreadable item."""
    return avatar_url(actor.get("avatar_url")) if isinstance(actor, dict) else None


type AvatarUrl = Annotated[str | None, BeforeValidator(avatar_url)]
