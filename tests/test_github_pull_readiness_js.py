"""The browser's status marks draw what the server decided, one glyph for each meaning.

``builtin_plugins/github/pull-readiness.js`` holds the status vocabulary: a glyph for each
verdict ``pull_readiness.py`` can decide, for each requirement it can report, and for each
bucket ``pull_status.py`` sorts a check into, and nothing else of them: the label and the tone
come with each readiness and each requirement (docs/design-system.md, "Pull Request Status
Vocabulary"). ``tests/dom/github-pull-readiness-behavior.js`` runs the production module in
Node over every verdict, tone, requirement, and bucket this test hands it from the server's
own types, and holds that a chip's glyph is its compact glyph and that no glyph means two
things. It reports the vocabulary's verdicts, so a verdict added to the server and not drawn
fails here, and the module's copies of the server's vocabulary (the labels the header's slot
is sized by, the statuses worst first, the tones, the verdict each requirement heads, and a
check's tone by its bucket), so each is held to the server's here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, get_args

from metabrowser.builtin_plugins.github.pull_readiness import (
    HEADLINES,
    LABELS,
    STATUS_ORDER,
    RequirementKind,
    RequirementStatus,
    Tone,
    Verdict,
    requirement_tone,
)
from metabrowser.builtin_plugins.github.pull_status import BUCKETS
from tests.required_tools import require_node

SESSION = Path(__file__).resolve().parent / "dom" / "github-pull-readiness-behavior.js"

# The checks requirement's status each bucket of a check stands for: a check that passed,
# failed, or is pending is drawn and colored as the checks met, unmet, or waiting. A skipped or
# a cancelled check is neither, and `gh pr checks` mutes it.
CHECKS_AT: dict[str, RequirementStatus] = {"pass": "met", "fail": "unmet", "pending": "waiting"}


def _session() -> dict[str, Any]:
    given = {
        "verdicts": list(get_args(Verdict.__value__)),
        "tones": list(get_args(Tone.__value__)),
        "statuses": list(get_args(RequirementStatus.__value__)),
        "kinds": list(get_args(RequirementKind.__value__)),
        "headlines": [[kind, status, verdict] for (kind, status), verdict in HEADLINES.items()],
        "buckets": list(BUCKETS),
    }
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


def test_each_meaning_the_server_decides_has_one_glyph_in_every_form() -> None:
    verdicts = get_args(Verdict.__value__)
    session = _session()
    assert sorted(session.pop("vocabulary")) == sorted(verdicts), (
        "pull-readiness.js draws exactly the verdicts pull_readiness.py decides"
    )
    assert session.pop("cases") == len(verdicts) * len(get_args(Tone.__value__))
    assert session.pop("requirementChips") > 0
    assert session.pop("meanings") > len(verdicts) - 1, "every verdict, met row, and bucket"
    assert sorted(session.pop("slotLabels")) == sorted(LABELS.values()), (
        "the header's slot is sized by exactly the labels the server gives a verdict"
    )
    assert session.pop("statusOrder") == list(STATUS_ORDER), "the statuses, worst first"
    assert session.pop("tones") == list(get_args(Tone.__value__)), "the tones the server gives"
    assert sorted(map(tuple, session.pop("requirementVerdicts"))) == sorted(
        (kind, status, verdict) for (kind, status), verdict in HEADLINES.items()
    ), "a requirement's row draws the glyph of the verdict the server says it heads"
    check_tones = session.pop("checkTones")
    assert sorted(check_tones) == sorted(BUCKETS), "every bucket has its tone"
    for bucket, status in CHECKS_AT.items():
        assert check_tones[bucket] == requirement_tone("checks", status), (
            f"a check in {bucket} takes the checks' tone when they are {status}"
        )
    assert {check_tones[bucket] for bucket in BUCKETS if bucket not in CHECKS_AT} == {"neutral"}
    assert session == {
        "noReadinessDrawsNothing": True,
        "toneAndLabelAreTheGivens": True,
        "namedByDefaultOrHidden": True,
        "chipGlyphIsTheCompactGlyph": True,
        "oneGlyphPerMeaning": True,
        "eachGlyphParsedOnce": True,
        "sizersAreHiddenChips": True,
    }
