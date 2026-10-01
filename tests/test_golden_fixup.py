"""``devtools/golden_fixup.py`` restores each pattern, and nothing a fixture pins.

``tryscript run --update`` rewrites a changed block with literal output, so the step
after it in ``make golden-update`` has to put every elision back and must not touch a
value a fixture controls. Both directions are checked on text shaped like the output
each rule is for, and the last test holds the committed transcripts to the same rules.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools import golden_fixup

FRONTMATTER = "---\nsandbox: true\npatterns:\n  COUNT: '\\d+'\n---\n"


def _fixed(body: str) -> str:
    fixed = golden_fixup.fix_text(FRONTMATTER + body)
    assert fixed.startswith(FRONTMATTER)
    return fixed.removeprefix(FRONTMATTER)


@pytest.mark.parametrize(
    ("captured", "restored"),
    [
        ("Usage: metab [OPTIONS] [ROOT]\n", "Usage: metab [OPTIONS] [ROOT_ARG]\n"),
        (
            '  "root": "/private/var/folders/x/T/tryscript-AbC123/shellroot",\n',
            '  "root": "[CWD]/shellroot",\n',
        ),
        (
            "path: /opt/checkout/src/metabrowser/builtin_plugins/markdown\n",
            "path: [BUILTIN]/markdown\n",
        ),
        ("metab 0.12.0a1 (3 commits past v0.11.0, dirty)\n", "metab [VERSION]\n"),
        (
            '  "html": "<svg xmlns=\\"http://www.w3.org/2000/svg\\" style=\\"display: none\\">'
            '\\n  <symbol id=\\"kpress-icon-x\\"></symbol>\\n</svg>\\n<article class=\\"kpress\\">'
            '<h1 id=\\"sample\\">Sample</h1></article>",\n',
            '  "html": "<svg xmlns=\\"http://www.w3.org/2000/svg\\" style=\\"display: none\\">'
            '[..]</svg>\\n<article class=\\"kpress\\"><h1 id=\\"sample\\">Sample</h1></article>",\n',
        ),
        (
            '12:34:56 metabrowser.events_route | pending folder tallies diagnostic id=x server={"version":8,"walker_task":"done"}\n',
            '[CLOCK] metabrowser.events_route | pending folder tallies diagnostic id=x server={"version":[COUNT],"walker_task":"done"}\n',
        ),
        (
            '    "contract": "inventory-provider-v1",\n    "version": 8,\n',
            '    "contract": "inventory-provider-v1",\n    "version": [COUNT],\n',
        ),
        (
            '    "mode": "native",\n    "reason": "fs=apfs",\n    "state": "active"\n',
            '    "mode": "[..]",\n    "reason": "[..]",\n    "state": "[..]"\n',
        ),
        (
            '    "outcome": "refreshing_elsewhere",\n    "at": "2026-10-01T05:32:00Z"\n',
            '    "outcome": "refreshing_elsewhere",\n    "at": "[TIMESTAMP]"\n',
        ),
        (
            '    "reset_at": null,\n    "at": "2026-10-01T05:32:00Z"\n',
            '    "reset_at": null,\n    "at": "[TIMESTAMP]"\n',
        ),
        (
            '  "last_fetch_at": "2026-10-01T05:32:00Z",\n  "last_outcome": {\n'
            '    "operation": "acquire",\n    "outcome": "succeeded",\n'
            '    "at": "2026-10-01T05:32:00Z"\n',
            '  "last_fetch_at": "[TIMESTAMP]",\n  "last_outcome": {\n'
            '    "operation": "acquire",\n    "outcome": "succeeded",\n    "at": "[TIMESTAMP]"\n',
        ),
        ("padded   \t\nkept\n", "padded\nkept\n"),
    ],
    ids=[
        "usage-metavar",
        "sandbox-path",
        "builtin-path",
        "version",
        "icon-sprite",
        "diagnostic-line",
        "change-batch-counter",
        "watcher",
        "refreshing-elsewhere",
        "failed-pull-refresh",
        "fixture-fetch",
        "trailing-whitespace",
    ],
)
def test_captured_output_gets_its_pattern_back(captured: str, restored: str) -> None:
    assert _fixed(captured) == restored
    # Restoring is idempotent: a second `make golden-update` changes nothing.
    assert _fixed(restored) == restored


@pytest.mark.parametrize(
    "pinned",
    [
        # A time a fixture fixed stays literal beside the same keys.
        '  "last_fetch_at": "2026-09-17T12:00:05Z",\n',
        '    "reset_at": null,\n    "at": "2026-09-17T12:00:00Z"\n',
        '    "operation": "acquire",\n    "outcome": "succeeded",\n    "at": "2026-09-17T12:00:05Z"\n',
        # A commit time, a record's fetch time, and a schema version are not wall clocks.
        '  "committed_at": "2026-01-01T00:00:00Z",\n  "fetched_at": "2026-09-17T12:00:00Z",\n',
        '  "schema_version": 2,\n  "version": 1,\n',
        # Rendered HTML with no sprite is the document itself.
        '  "html": "\\n<div><div><p>This teaches it <strong>two</strong>.</p></div></div>"\n',
        # A watcher-shaped key outside the watcher's trio, and prose.
        '  "mode": "100644",\n  "state": "current",\n',
        "The diagnostic is reported in `version`.\n",
    ],
    ids=[
        "fixture-fetch",
        "fixture-refresh",
        "fixture-acquire",
        "other-times",
        "other-versions",
        "plain-html",
        "other-modes",
        "prose",
    ],
)
def test_a_value_a_fixture_pins_is_left_alone(pinned: str) -> None:
    assert _fixed(pinned) == pinned


def test_the_frontmatter_is_never_rewritten() -> None:
    frontmatter = "---\nbefore: >-\n  metab /tmp/tryscript-AbC123/root --version   \n---\n"
    assert golden_fixup.fix_text(frontmatter + "body\n") == frontmatter + "body\n"


def test_the_repeated_asset_manifest_is_collapsed_once() -> None:
    literal = (
        "$ metab shellroot --api /api/kpress/render --data shellroot/render.json\n"
        "{\n"
        '  "assets": {\n'
        '    "schema_version": "kpress-asset-manifest-v2",\n'
        '    "assets": []\n'
        "  },\n"
        '  "diagnostics": [],\n'
    )
    collapsed = (
        "$ metab shellroot --api /api/kpress/render --data shellroot/render.json\n"
        '{\n  "assets": {\n...\n  },\n  "diagnostics": [],\n'
    )
    assert _fixed(literal) == collapsed
    assert _fixed(collapsed) == collapsed
    # The GET case above it keeps the manifest it pins.
    get = literal.replace(" --data shellroot/render.json", "?path=README.md")
    assert _fixed(get) == get


def test_main_rewrites_only_transcripts_that_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "changed.tryscript.md").write_text(FRONTMATTER + "metab 0.12.0\n", "utf-8")
    (tmp_path / "same.tryscript.md").write_text(FRONTMATTER + "metab [VERSION]\n", "utf-8")
    (tmp_path / "notes.txt").write_text("metab 0.12.0\n", "utf-8")
    golden_fixup.main(tmp_path)
    assert capsys.readouterr().out == "patterns restored: changed.tryscript.md\n"
    assert (tmp_path / "changed.tryscript.md").read_text("utf-8") == (
        FRONTMATTER + "metab [VERSION]\n"
    )
    assert (tmp_path / "notes.txt").read_text("utf-8") == "metab 0.12.0\n"


def test_every_committed_transcript_is_already_fixed() -> None:
    """A hand edit the next ``make golden-update`` would revert is caught here instead."""

    for path in sorted(golden_fixup.GOLDEN_DIR.glob("*.tryscript.md")):
        text = path.read_text(encoding="utf-8")
        assert golden_fixup.fix_text(text) == text, path.name
