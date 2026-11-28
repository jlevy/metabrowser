"""The tooltip check's repeat rule: a literal tip that is its element's literal text.

``devtools/check_tooltips.py`` fails a tip that repeats its element's text, in the two
literal forms its docstring names, and leaves to the shell the forms it does not read.
The shipped tree has none, so without these a pattern that stopped matching would pass
lint silently. Each line below is one line of markup as a source file holds it.

It also fails a link card drawn outside its one renderer, ``static/link-previews.js``,
and the shell's stylesheet: a card's classes or its words for where a link opens.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools import check_tooltips as check

# Lines the rule finds: the tip is the element's own text.
REPEATS = (
    pytest.param('<button data-tip-text="Copy">Copy</button>', id="html"),
    pytest.param('<span data-tip-text="Copy"> Copy </span>', id="html-spaced-text"),
    pytest.param(
        '<button class="x" data-tip-text="Copy" type="button">Copy</button>',
        id="html-attributes-around",
    ),
    pytest.param('"<button data-tip-text=\\"Copy\\">Copy</button>"', id="html-escaped-quotes"),
    pytest.param('h("button", { "data-tip-text": "Copy" }, ["Copy"])', id="h"),
    pytest.param('h("button", { class: "x", "data-tip-text": "Copy" }, ["Copy"])', id="h-after"),
    pytest.param('h("button", { "data-tip-text": "Copy", class: "x" }, ["Copy"])', id="h-before"),
    pytest.param(
        'h("span", { "data-tip-text": "Copy", class: `chip ${kind}` }, ["Copy"])',
        id="h-before-a-substitution",
    ),
)

# Lines it does not find: the tip says something else, or is a form the shell holds.
NOT_REPEATS = (
    pytest.param('<button data-tip-text="Copy path" aria-label="Copy path">↑</button>', id="glyph"),
    pytest.param('h("button", { "data-tip-text": "Copy path" }, ["Copy"])', id="h-other-text"),
    pytest.param(
        'h("a", { "data-tip-text": "X" }, ["Y"]), h("b", {}, ["X"])', id="h-another-element"
    ),
    pytest.param('<button data-tip-text="${name}">${name}</button>', id="computed-at-run-time"),
    pytest.param("<button data-tip-text='Copy'>Copy</button>", id="single-quoted"),
    pytest.param('button.dataset.tipText = "Copy"; button.textContent = "Copy";', id="dataset"),
)


def _source(tmp_path: Path, line: str) -> Path:
    path = tmp_path / "markup.js"
    path.write_text(f"// before\n{line}\n// after\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("line", REPEATS)
def test_a_literal_tip_that_is_its_elements_text_is_found(tmp_path: Path, line: str) -> None:
    path = _source(tmp_path, line)
    assert check._repeats(path) == [check.Finding(path, 2, line)]


@pytest.mark.parametrize("line", NOT_REPEATS)
def test_a_tip_that_adds_or_a_form_the_shell_holds_is_not(tmp_path: Path, line: str) -> None:
    assert check._repeats(_source(tmp_path, line)) == []


def test_a_repeat_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _source(tmp_path, 'h("button", { "data-tip-text": "Refresh" }, ["Refresh"])')
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "_candidates", lambda: [path])
    monkeypatch.setattr(check, "_size_findings", list)
    assert check.main() == 1
    assert "markup.js:2:" in capsys.readouterr().err


def test_the_shipped_tree_repeats_no_tip() -> None:
    candidates = check._candidates()
    assert check.ROOT / "src" / "metabrowser" / "static" / "app.js" in candidates
    assert [finding for path in candidates for finding in check._repeats(path)] == []


# Lines that draw a link card of their own: its classes or its words for where it opens.
LINK_CARDS = (
    pytest.param('`<div class="tip-name link-card-name">${name}</div>`', id="class"),
    pytest.param('h("div", { class: "tip-detail" }, ["Opens here in Metabrowser"])', id="words"),
    pytest.param('"Opens in the served working tree"', id="working-tree"),
    pytest.param(".link-card-mark { color: red; }", id="restyled"),
)


@pytest.mark.parametrize("line", LINK_CARDS)
def test_a_link_card_outside_its_renderer_is_found(tmp_path: Path, line: str) -> None:
    path = _source(tmp_path, line)
    assert check._link_cards(path) == [check.Finding(path, 2, line)]


def test_the_renderer_and_the_shells_stylesheet_hold_the_card() -> None:
    static = check.ROOT / "src" / "metabrowser" / "static"
    for owner in ("link-previews.js", "styles.css"):
        text = (static / owner).read_text(encoding="utf-8")
        assert check._LINK_CARD.search(text), f"{owner} no longer holds the link card"
        assert check._link_cards(static / owner) == []


def test_a_second_link_card_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _source(tmp_path, '"<div class=\\"tip-detail\\">Opens here in Metabrowser</div>"')
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "_candidates", lambda: [path])
    monkeypatch.setattr(check, "_size_findings", list)
    assert check.main() == 1
    err = capsys.readouterr().err
    assert "one renderer draws every link card" in err
    assert "markup.js:2:" in err


def test_the_shipped_tree_draws_one_link_card() -> None:
    assert [finding for path in check._candidates() for finding in check._link_cards(path)] == []


def test_the_browser_tab_title_is_not_an_element_tooltip(tmp_path: Path) -> None:
    assert check._scan(_source(tmp_path, "document.title = name;")) == []
    assert check._scan(_source(tmp_path, "window.document.title = name;")) == []
    assert check._scan(_source(tmp_path, 'document.title = "Readme";')) == []
    line = "document.title = name; button.title = name;"
    path = _source(tmp_path, line)
    assert check._scan(path) == [check.Finding(path, 2, line)]
