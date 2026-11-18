"""The rendered YAML and JSON session runs production browser code on the server's trees.

``tests/dom/diff-structured-session.js`` loads ``builtin_plugins/diff/diff-structured.js``
and the structured plugin's ``preview.js`` and ``tree.js`` whole, and draws each merged
tree as a pull request's Changes does: which rows it has, which open first, what a click
opens and closes, and how each row is marked. ``tests/golden/cli-ui-diff-structured.tryscript.md``
pins its transcript. So that the trees are the server's and not ones a test wrote by hand,
they come from ``tests/fixtures/diff-structured-responses.json``: what
:func:`metabrowser.diff.structured_projection.project_structured_diff` answers for these
files. The route itself, admission and refusals included, is pinned by
``tests/golden/cli-github-pull-rendered.txt``. The first test fails when the recording no
longer matches; ``make golden-update`` rewrites it and then the transcript.
"""

from __future__ import annotations

from typing import Any

from metabrowser.diff.structured_projection import Format, project_structured_diff
from tests.golden_harness import check_recording, run_session

_RECORDING = "diff-structured-responses.json"

_CONFIG_OLD = b"""\
name: demo
version: 3
services:
  web:
    image: nginx
    ports: [80]
  db:
    image: postgres
    port: 5432
flags:
  - fast
  - safe
"""
_CONFIG_NEW = b"""\
name: demo
version: 4
services:
  web:
    image: nginx
    ports: [80, 443]
flags:
  - fast
  - safe
"""


def _answer(old: bytes | None, new: bytes | None, fmt: Format) -> dict[str, Any]:
    return dict(project_structured_diff(old=old, new=new, fmt=fmt))


def _recording() -> dict[str, Any]:
    return {
        "config/app.yaml": _answer(_CONFIG_OLD, _CONFIG_NEW, "yaml"),
        "package.json": _answer(None, b'{"name": "demo", "scripts": {"test": "make"}}\n', "json"),
        "data/swap.json": _answer(b"[1, 2]\n", b'"text"\n', "json"),
    }


def test_recording_matches_the_production_projection() -> None:
    recording = _recording()
    assert {path: answer["status"] for path, answer in recording.items()} == dict.fromkeys(
        recording, "ready"
    )
    check_recording(_RECORDING, recording, transcript="cli-ui-diff-structured.tryscript.md")


def test_session_replays_the_recording() -> None:
    transcript = run_session("diff-structured-session.js")
    config = transcript["config/app.yaml"]
    assert config["opens"] == [
        "$",
        "$.services",
        "$.services.db",
        "$.services.web",
        "$.services.web.ports",
    ]
    assert "  removed kv version: 3" in config["first draw"]
    assert "  added kv version: 4" in config["first draw"]
    assert '  context open flags: ["fast", "safe"]' in config["first draw"]
    assert transcript["data/swap.json"]["first draw"][0].startswith("removed open")
