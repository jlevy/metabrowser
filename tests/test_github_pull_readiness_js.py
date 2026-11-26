"""The browser's readiness marks draw what the server decided, and only that.

``builtin_plugins/github/pull-readiness.js`` holds one glyph for each verdict
``pull_readiness.py`` can decide, and nothing else of it: the label and the tone come with
each readiness (docs/design-system.md, "A Pull Request’s Readiness").
``tests/dom/github-pull-readiness-behavior.js`` runs the production module in Node over
every verdict and tone this test hands it from the server's own types, and reports the
vocabulary's verdicts, so a verdict added to the server and not drawn fails here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, get_args

from metabrowser.builtin_plugins.github.pull_readiness import Tone, Verdict
from tests.required_tools import require_node

SESSION = Path(__file__).resolve().parent / "dom" / "github-pull-readiness-behavior.js"


def _session() -> dict[str, Any]:
    given = {"verdicts": list(get_args(Verdict.__value__)), "tones": list(get_args(Tone.__value__))}
    result = subprocess.run(
        [require_node(), str(SESSION), json.dumps(given)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"{SESSION.name} failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    return json.loads(result.stdout)


def test_each_verdict_the_server_decides_has_one_glyph_and_takes_its_tone_and_label() -> None:
    verdicts = get_args(Verdict.__value__)
    session = _session()
    assert sorted(session.pop("vocabulary")) == sorted(verdicts), (
        "pull-readiness.js draws exactly the verdicts pull_readiness.py decides"
    )
    assert session.pop("cases") == len(verdicts) * len(get_args(Tone.__value__))
    assert session == {
        "noReadinessDrawsNothing": True,
        "toneAndLabelAreTheReadinesss": True,
        "namedByDefaultOrHidden": True,
        "oneShapePerVerdict": True,
        "sharedShapesAreSharedGlyphs": True,
        "eachGlyphParsedOnce": True,
    }
