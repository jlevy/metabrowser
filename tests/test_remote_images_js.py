"""The "Block remote images" preference reads the same in the browser and on the server."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from metabrowser.settings import BLOCK_REMOTE_IMAGES_COOKIE, blocks_remote_images
from tests.required_tools import require_node

SESSION_JS = Path(__file__).resolve().parent / "dom" / "remote-images-session.js"


def test_the_page_and_the_server_read_the_cookie_alike() -> None:
    """``static/remote-images.js`` reads each value as ``settings.blocks_remote_images``.

    The server's reading is the page's policy and its ``METABROWSER_SETTINGS``; the page's
    is the checkbox's state when it changes the cookie. They must agree for every value a
    browser can hold, or the box would show a choice the policy did not follow.
    """

    require_node()
    result = subprocess.run(
        ["node", str(SESSION_JS)], capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    payload = json.loads(result.stdout)
    assert payload["authority"]["key"] == BLOCK_REMOTE_IMAGES_COOKIE
    assert payload["authority"]["inputId"] == "block-remote-images-input"
    assert payload["authority"]["serverKey"] == BLOCK_REMOTE_IMAGES_COOKIE
    for written, blocked in payload["stored"].items():
        value = json.loads(written)
        cookies = {} if value is None else {BLOCK_REMOTE_IMAGES_COOKIE: value}
        assert blocks_remote_images(cookies) is blocked, written
    assert payload["stored"]['"1"'] is True
    assert payload["choices"]["off, turned on"]["writes"] == [
        {"key": BLOCK_REMOTE_IMAGES_COOKIE, "value": "1"}
    ]
