"""The Markdown document preamble must render inside the KPress content card.

KPress emits the frontmatter disclosure and the frontmatter-error alert as
siblings ahead of ``.kpress-doc-layout``, which puts them outside the content
card and above both the card and the TOC rail. The markdown plugin moves that
preamble — plus its own diagnostics disclosure — into the top of the prose
column, and styles.css strips the disclosure chrome there.

The two sides are coupled by the ``metabrowser-doc-meta`` class name, so these
assert the JS relocation target and the CSS scope agree. The DOM shim under
``tests/dom/`` cannot cover this: it stubs ``querySelector`` to null and has no
node tree to move elements within.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
MARKDOWN_PLUGIN_JS = _ROOT / "src" / "metabrowser" / "builtin_plugins" / "markdown" / "rendered.js"
STYLES_CSS = _ROOT / "src" / "metabrowser" / "static" / "styles.css"

_META_CLASS = "metabrowser-doc-meta"


def test_plugin_moves_preamble_into_the_prose_column() -> None:
    src = MARKDOWN_PLUGIN_JS.read_text(encoding="utf-8")
    assert _META_CLASS in src, "the markdown plugin must collect the preamble into one block"
    assert ".kpress-doc-layout" in src, "the preamble is everything ahead of the layout element"
    assert ".kpress-prose" in src, "the collected preamble must land in the prose column"
    assert "prose.prepend(meta)" in src, "the preamble belongs above the title, not after it"


def test_styles_strip_the_disclosure_frame_inside_the_card() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")
    assert f".{_META_CLASS}" in css, "styles.css must scope the relocated preamble"
    frame_rule = f".{_META_CLASS} > details {{\n  border: 0;\n}}"
    assert frame_rule in css, "relocated disclosures must render as toggles, not boxed panels"


def test_markdown_disclosures_use_the_shared_trailing_chevron() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert ".metabrowser-kpress-host .kpress details > summary::before" in css
    assert "content: none" in css
    assert ".metabrowser-kpress-host .kpress details > summary::after" in css
    assert ".metabrowser-kpress-host .kpress details[open] > summary::after" in css
    assert "var(--section-disclosure-chevron-color)" in css
    assert "var(--section-disclosure-chevron-size)" in css
    assert "margin-inline-start: calc(-0.85em - 0.4rem)" not in css


def test_markdown_metadata_disclosures_start_closed() -> None:
    src = MARKDOWN_PLUGIN_JS.read_text(encoding="utf-8")

    diagnostics = src.split("return `<details", maxsplit=1)[1].split("`;", maxsplit=1)[0]
    assert '<summary class="section-disclosure-trigger">Diagnostics</summary>' in diagnostics
    assert " open" not in diagnostics
