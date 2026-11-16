"""A GitHub label's color and description, from GitHub's answer to the chip's properties.

The record keeps each label's color as six lower-case hex digits, or ``None`` for anything
else (``pull_record.label_color``), and its description, or ``None`` for none
(``pull_record.label_description``); a list's row keeps its name alone, since no row draws
labels. The page turns a color into the custom properties github.com sets on a label
(``labelColorProperties`` in ``builtin_plugins/github/pull-page.js``), and
``tests/fixtures/github-label-colors.json``
holds the properties github.com set on 112 colors of six public repositories' labels, so
the hue, saturation, and lightness are held to github.com's own, rounding and all. What
the stylesheet paints from them is checked in Chrome, in
``tests/dom/github-pull-header-chrome.mjs`` (its ``labels`` part).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_list_refresh, pulls
from metabrowser.builtin_plugins.github.pull_record import (
    PullRequest,
    label_color,
    label_description,
)
from tests.github_pull_fixture import generated_item, recorded_responses
from tests.required_tools import needs_node

ROOT = Path(__file__).resolve().parent.parent
PULL_PAGE_JS = ROOT / "src/metabrowser/builtin_plugins/github/pull-page.js"
GITHUB = json.loads((ROOT / "tests/fixtures/github-label-colors.json").read_text(encoding="utf-8"))

_RUN = r"""
const [pageUrl, input] = process.argv.slice(1);
import(pageUrl).then(({ labelColorProperties }) => {
  process.stdout.write(JSON.stringify(JSON.parse(input).map((color) => labelColorProperties(color))));
});
"""


def _properties(colors: list[Any]) -> list[str | None]:
    completed = subprocess.run(
        ["node", "-e", _RUN, PULL_PAGE_JS.as_uri(), json.dumps(colors)],
        capture_output=True,
        text=True,
        timeout=50,
        check=True,
    )
    return json.loads(completed.stdout)


@needs_node
def test_each_color_gets_the_properties_github_com_gave_it() -> None:
    observed: dict[str, list[int]] = GITHUB["properties"]
    assert len(observed) == 112
    # Hues that fall on a half degree, as 9ce9f4's 187.5 does, round up, as github.com's do.
    assert observed["9ce9f4"] == [188, 80, 78]
    colors = sorted(observed)
    for color, properties in zip(colors, _properties(colors), strict=True):
        r, g, b = (int(color[at : at + 2], 16) for at in (0, 2, 4))
        hue, saturation, lightness = observed[color]
        assert properties == (
            f"--github-label-r:{r};--github-label-g:{g};--github-label-b:{b};"
            f"--github-label-h:{hue};--github-label-s:{saturation};--github-label-l:{lightness}"
        ), color


@needs_node
def test_the_page_paints_only_six_hex_digits() -> None:
    upper, lower, *refused = _properties(
        ["D73A4A", "d73a4a", "#d73a4a", "d73a4", "d73a4a0", "d73a4g", "", None, 123, ["d73a4a"]]
    )
    assert (
        upper
        == lower
        == (
            "--github-label-r:215;--github-label-g:58;--github-label-b:74;--github-label-h:354;--github-label-s:66;--github-label-l:54"
        )
    )
    assert refused == [None] * 8


@pytest.mark.parametrize(
    ("given", "kept"),
    [
        ("d73a4a", "d73a4a"),
        ("D73A4A", "d73a4a"),
        ("#d73a4a", None),
        ("d73a4", None),
        ("d73a4ag", None),
        ("", None),
        (None, None),
        (0xD73A4A, None),
    ],
)
def test_a_color_is_six_hex_digits_kept_lower_case_or_none(given: object, kept: str | None) -> None:
    assert label_color(given) == kept


@pytest.mark.parametrize(
    ("given", "kept"),
    [
        ("Something isn't working", "Something isn't working"),
        ("", None),
        ("  ", None),
        (None, None),
    ],
)
def test_a_description_is_its_text_or_none(given: object, kept: str | None) -> None:
    assert label_description(given) == kept


_LABELS: list[dict[str, Any]] = [
    {"name": "bug", "color": "D73A4A", "description": "Something isn't working"},
    {"name": "invalid", "color": "e4e669", "description": ""},
    {"name": "odd", "color": "#123456"},
    {"color": "ffffff", "description": "no name"},
]
_KEPT = [
    {"name": "bug", "color": "d73a4a", "description": "Something isn't working"},
    {"name": "invalid", "color": "e4e669", "description": None},
    {"name": "odd", "color": None, "description": None},
]


def test_a_record_keeps_each_labels_color_and_description() -> None:
    answer = recorded_responses()["pull"] | {"labels": _LABELS}
    answer["base"] = answer["base"] | {"sha": "1" * 40}
    answer["head"] = answer["head"] | {"sha": "2" * 40}
    pull = pulls._pull(answer, 7)  # pyright: ignore[reportPrivateUsage]
    assert [label.model_dump() for label in pull.labels] == _KEPT


def test_a_row_keeps_each_labels_name_alone() -> None:
    row, cut = pull_list_refresh._row(generated_item(1) | {"labels": _LABELS})  # pyright: ignore[reportPrivateUsage]
    assert row.labels == tuple(label["name"] for label in _KEPT)
    # A label without a name is left out, which the row says.
    assert cut
    # Neither a color nor a description is the row's, so neither cuts it.
    long = {"name": "long", "color": "#ffffff", "description": "\x00" * 1000}
    row, cut = pull_list_refresh._row(generated_item(1) | {"labels": [long]})  # pyright: ignore[reportPrivateUsage]
    assert not cut and row.labels == ("long",)


def test_a_label_an_earlier_projection_named_alone_reads_without_color_or_description() -> None:
    answer = recorded_responses()["pull"] | {"labels": []}
    answer["base"] = answer["base"] | {"sha": "1" * 40}
    answer["head"] = answer["head"] | {"sha": "2" * 40}
    pull = pulls._pull(answer, 7)  # pyright: ignore[reportPrivateUsage]
    read = PullRequest.model_validate(pull.model_dump() | {"labels": ["bug"]})
    assert [label.model_dump() for label in read.labels] == [
        {"name": "bug", "color": None, "description": None}
    ]
    # What is written is the label itself, never the bare name.
    assert json.loads(read.model_dump_json())["labels"] == [
        {"name": "bug", "color": None, "description": None}
    ]
