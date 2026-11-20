"""The "Block remote images" preference: the page's wiring and the server's reading agree."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from metabrowser.settings import BLOCK_REMOTE_IMAGES_COOKIE, blocks_remote_images
from tests.required_tools import require_node

SESSION_JS = Path(__file__).resolve().parent / "dom" / "remote-images-session.js"


def test_the_page_writes_the_cookie_the_server_reads() -> None:
    """``static/remote-images.js`` writes the key and values ``settings.blocks_remote_images`` reads.

    The server's reading is the page's policy, the box's state, and its
    ``METABROWSER_SETTINGS``; the page only writes it. So what the page writes for each
    choice, read back by the server, has to be that choice, or the box would show one
    thing and the policy follow another.
    """

    require_node()
    result = subprocess.run(
        ["node", str(SESSION_JS)], capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    payload = json.loads(result.stdout)
    assert payload["authority"]["key"] == BLOCK_REMOTE_IMAGES_COOKIE
    assert payload["authority"]["serverKey"] == BLOCK_REMOTE_IMAGES_COOKIE
    assert payload["authority"]["inputId"] == "block-remote-images-input"
    for name, blocked in (("off, turned on", True), ("on, turned off", False)):
        (write,) = payload["choices"][name]["writes"]
        assert write["key"] == BLOCK_REMOTE_IMAGES_COOKIE
        assert blocks_remote_images({write["key"]: write["value"]}) is blocked, name
    wiring = payload["checkbox"]["served off, before and after wiring"]
    assert (wiring["disabledBefore"], wiring["disabledAfter"]) == (True, False)


@pytest.mark.parametrize(
    ("cookies", "blocked"),
    [
        ({}, False),
        ({BLOCK_REMOTE_IMAGES_COOKIE: "1"}, True),
        ({BLOCK_REMOTE_IMAGES_COOKIE: "0"}, False),
        ({BLOCK_REMOTE_IMAGES_COOKIE: ""}, False),
        ({BLOCK_REMOTE_IMAGES_COOKIE: "true"}, False),
        ({BLOCK_REMOTE_IMAGES_COOKIE: "yes"}, False),
        ({BLOCK_REMOTE_IMAGES_COOKIE: "11"}, False),
        ({BLOCK_REMOTE_IMAGES_COOKIE: " 1"}, False),
        ({"metabrowser.themeMode": "1"}, False),
    ],
)
def test_only_the_exact_cookie_value_blocks(cookies: dict[str, str], blocked: bool) -> None:
    assert blocks_remote_images(cookies) is blocked
