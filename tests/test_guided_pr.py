from __future__ import annotations

import pytest
from softschema.compile import compile_model

from metabrowser.builtin_plugins.github.guided_pr import (
    CONTRACT_ID,
    SCHEMA_PATH,
    GuidedPR,
    GuideError,
    parse_guide,
)

_GUIDE = """```guided-pr
softschema:
  contract: metabrowser.github:GuidedPR/v1
  envelope: guide
  status: enforced
guide:
  comparison:
    merge_base: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    head: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  feature: Explain the feature.
  architecture: Trace the request through the worker.
  steps:
    - title: Read the request first
      commentary: Does the request wait for the worker?
      references:
        - {path: read.py, side: new, start_line: 2, end_line: 5}
    - title: Follow the worker
      commentary: Check the publication boundary.
      references:
        - {path: worker.py}
```"""


def test_parses_an_ordered_guide_from_the_description() -> None:
    guide = parse_guide(f"An ordinary PR description.\r\n\r\n{_GUIDE}")
    assert guide is not None
    assert [step.title for step in guide.steps] == ["Read the request first", "Follow the worker"]
    assert guide.steps[0].references[0].end_line == 5


def test_ignores_the_marker_inside_an_example_of_markdown() -> None:
    assert parse_guide(f"````markdown\n{_GUIDE}\n````") is None


def test_packaged_schema_matches_the_model() -> None:
    compiled = compile_model(GuidedPR, SCHEMA_PATH, contract_id=CONTRACT_ID, check_only=True)
    assert not compiled.drift, compiled.drift_diff


@pytest.mark.parametrize(
    "body",
    [
        _GUIDE.removesuffix("```"),
        f"{_GUIDE}\n\n{_GUIDE}",
        _GUIDE.replace("end_line: 5", "end_line: 1"),
        _GUIDE.replace("path: read.py", "path: ../read.py"),
        _GUIDE.replace("start_line: 2", "start_line: true"),
        _GUIDE.replace("start_line: 2", "start_line: 2, extra: 3"),
        _GUIDE.replace("feature: Explain the feature.", "feature: [one, two]"),
        _GUIDE.replace("status: enforced", "status: soft"),
        _GUIDE.replace("GuidedPR/v1", "GuidedPR/v2"),
    ],
)
def test_rejects_malformed_guide_blocks(body: str) -> None:
    with pytest.raises(GuideError):
        parse_guide(body)
