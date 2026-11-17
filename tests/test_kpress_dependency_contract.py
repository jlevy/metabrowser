"""KPress is Metabrowser's required, released rendering dependency."""

from __future__ import annotations

import re
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any

from kpress import runtime
from kpress.runtime import KPressRenderRequest, get_static_asset
from pytest import MonkeyPatch

from metabrowser.kpress_adapter import render_kpress_view
from tests.test_design_vocabulary import _rules_of

PROJECT_FILE = Path(__file__).resolve().parent.parent / "pyproject.toml"
SOURCE_DIR = PROJECT_FILE.parent / "src" / "metabrowser"


def test_kpress_is_an_exact_required_runtime_dependency() -> None:
    project = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))

    assert "kpress==0.3.8" in project["project"]["dependencies"]
    assert "kpress" not in project["project"].get("optional-dependencies", {})
    assert "kpress" not in project.get("dependency-groups", {}).get("dev", [])


def test_the_pinned_kpress_release_is_the_one_reviewed_for_the_cool_off() -> None:
    """The pin and its supply-chain record move together.

    KPress is first-party and exempt from the cool-off, but the exemption is
    per-release: each one is reviewed against its predecessor. Bumping the pin
    without updating that record would leave the exemption naming a version
    nobody ships, which reads as reviewed when it is not.
    """

    project = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))
    pins = [d for d in project["project"]["dependencies"] if d.startswith("kpress")]
    assert len(pins) == 1, pins

    policy = (PROJECT_FILE.parent / "SUPPLY-CHAIN-SECURITY.md").read_text(encoding="utf-8")
    assert f"`{pins[0]}`" in policy, f"{pins[0]} is not recorded in SUPPLY-CHAIN-SECURITY.md"


def test_kpress_does_not_resolve_from_the_monorepo_workspace() -> None:
    project = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))

    assert "kpress" not in project.get("tool", {}).get("uv", {}).get("sources", {})


def test_markdown_uses_the_kpress_toc_only_when_the_document_has_one(
    monkeypatch: MonkeyPatch,
) -> None:
    """The former reserved-rail cache entry cannot answer the auto layout."""

    render = runtime.render_view

    def seed_reserved_rail(request: KPressRenderRequest) -> dict[str, Any]:
        if request.source_path == "short.md":
            old = render(replace(request, toc_rail="reserved"))
            assert 'data-kpress-toc-rail="reserved"' in old["html"]
        return render(request)

    monkeypatch.setattr(runtime, "render_view", seed_reserved_rail)

    short = "# Short\n\nOne paragraph."
    for _ in range(2):
        html = render_kpress_view(
            source_text=short,
            source_path="short.md",
            kind="markdown",
            view="document",
            ext=".md",
            mtime_hash="toc-short",
            size=len(short.encode()),
        )["html"]
        assert "data-kpress-toc-rail" not in html
        assert "data-kpress-toc-toggle" not in html

    text = "\n\n".join(
        f"## Section {number}\n\n" + "A sentence about the document. " * 24 for number in range(9)
    )
    for _ in range(2):
        html = render_kpress_view(
            source_text=text,
            source_path="long.md",
            kind="markdown",
            view="document",
            ext=".md",
            mtime_hash="toc-long",
            size=len(text.encode()),
            frontmatter={"thumbnail_url": "thumbnail.png"},
        )["html"]
        assert "data-kpress-toc-toggle" in html
        assert "data-kpress-toc-rail" not in html
        assert html.index('class="thumbnail kpress-image"') < html.index(
            'class="kpress-prose kpress-long-text"'
        )

    rules = {
        " ".join(selector.split()): declarations
        for selector, declarations in _rules_of(
            SOURCE_DIR / "builtin_plugins" / "markdown" / "markdown.css"
        )
    }
    document = ".metabrowser-markdown-document > .kpress-doc"
    layout = f"{document} > .kpress-doc-layout"
    gutter = rules[f"{document}:has(> .kpress-doc-layout > .kpress-toc)"]
    assert gutter["--kpress-doc-gutter"] == "var(--kpress-toc-toggle-clearance)"
    assert gutter["padding-inline-start"] == "0"
    toggle = rules[f"{layout} > .kpress-toc-toggle"]
    assert toggle["left"] == "auto"
    assert toggle["right"] == "0.75rem"
    toc_layout = f"{layout}:has(> .kpress-toc)"
    assert rules[toc_layout]["grid-template-areas"] == '"prose toc"'
    assert " ".join(rules[f"{toc_layout}:has(> .thumbnail)"]["grid-template-areas"].split()) == (
        '"thumbnail toc" "prose toc"'
    )
    assert rules[f"{layout} > .thumbnail"]["grid-area"] == "thumbnail"
    table = rules[f'{document} .kpress-table-wrap[data-kpress-table-scale="wide"]']
    assert table["width"] == "max-content"
    assert table["min-width"] == "100%"
    assert (
        " ".join(table["max-width"].split())
        == "calc(100cqw - 2 * (var(--content-padding-x) + var(--kpress-column-inset)))"
    )


def test_embedded_readme_keeps_wide_tables_inside_the_panel() -> None:
    """A clipping Overview card must leave the table's own scroll area reachable."""

    rules = {
        " ".join(selector.split()): declarations
        for selector, declarations in _rules_of(
            SOURCE_DIR / "builtin_plugins" / "markdown" / "markdown.css"
        )
    }
    embedded = (
        ".folder-overview-panel-document > .metabrowser-markdown-document > .kpress-doc "
        '.kpress-table-wrap[data-kpress-table-scale="wide"]'
    )
    assert rules[embedded]["max-width"] == "100%"
    with_toc = (
        ".metabrowser-markdown-document > .kpress-doc "
        '> .kpress-doc-layout:has(> .kpress-toc) .kpress-table-wrap[data-kpress-table-scale="wide"]'
    )
    assert rules[with_toc]["max-width"] == "100%"


def test_runtime_has_no_optional_kpress_branch() -> None:
    adapter = (SOURCE_DIR / "kpress_adapter.py").read_text(encoding="utf-8")
    server = (SOURCE_DIR / "server.py").read_text(encoding="utf-8")

    assert "KPressUnavailableError" not in adapter
    assert "KPressUnavailableError" not in server
    assert "kpress_unavailable" not in server


def _kpress_rule(css: str, selector: str) -> str:
    """The declarations of the rule whose selector list is exactly *selector*."""

    uncommented = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", uncommented):
        if selectors.strip() == selector:
            return declarations
    raise AssertionError(f"KPress ships no rule for {selector!r}")


def test_pinned_kpress_owns_the_inline_code_base_style() -> None:
    css = get_static_asset("css/document.css").content.decode("utf-8")
    code_block = _kpress_rule(css, ".kpress code,\n.kpress-code")
    inline_block = _kpress_rule(css, ".kpress code:not(pre code)")
    fenced_block = _kpress_rule(css, ".kpress-code")

    assert "background: var(--kpress-doc-surface-bg);" in code_block
    assert "font-family: var(--kpress-font-mono, ui-monospace, monospace);" in code_block
    assert "font-size: var(--kpress-font-size-mono);" in code_block
    for block in (inline_block, fenced_block):
        assert "border: 1px solid var(--kpress-code-border);" in block
        assert "border-radius: var(--kpress-code-radius);" in block
    assert "padding: 0.1em 0.25em;" in inline_block


def test_the_app_owns_the_palette_and_corners_of_every_kpress_fragment() -> None:
    """Every KPress fragment in the page takes the app's color and corner tokens.

    A rendered Markdown diff mounts its `article.kpress` in the diff plugin's host, not
    under `.metabrowser-kpress-host`, so a bridge keyed on that host left it in KPress's
    own palette: with 0.3.8, KPress's border and muted tones on its quote rule, quoted
    text, and code edges, KPress's text and link colors, and a darker ground than the
    page's in the dark theme. The bridge keys on `.kpress` anywhere in the page, in one place.
    `tests/test_diff_markdown_fold_chrome.py` measures the diff's quote and code against a
    document's in both themes.
    """

    bridged = {
        "--kpress-doc-bg",
        "--kpress-doc-text",
        "--kpress-doc-muted",
        "--kpress-doc-border",
        "--kpress-doc-link",
        "--kpress-code-border",
        "--kpress-radius-sm",
        "--kpress-radius-md",
        "--kpress-radius-lg",
        "--kpress-code-radius",
    }
    keyed: dict[str, set[str]] = {}
    for selector, declarations in _rules_of(SOURCE_DIR / "static" / "styles.css"):
        for token in bridged & declarations.keys():
            keyed.setdefault(token, set()).add(selector)
    elsewhere = [
        f"{path.relative_to(PROJECT_FILE.parent)}: {token}"
        for path in sorted(SOURCE_DIR.rglob("*.css"))
        if path != SOURCE_DIR / "static" / "styles.css"
        for token in sorted(bridged)
        if re.search(rf"{re.escape(token)}\s*:", path.read_text(encoding="utf-8"))
    ]
    diff = (SOURCE_DIR / "builtin_plugins" / "diff" / "diff-markdown.js").read_text(
        encoding="utf-8"
    )

    assert keyed == {token: {":root .kpress", ":root .kpress-tooltip"} for token in bridged}
    assert elsewhere == []
    assert 'rendered.className = "kpress kpress-inert diff-markdown";' in diff


def test_host_bridges_one_mono_stack_into_kpress_documents() -> None:
    """Shell code and document code draw in one face.

    --font-mono and KPress's --kpress-host-font-mono hook both read --app-mono, a name
    only the host declares. A bridge through --font-mono would not reach the document:
    KPress redeclares --font-mono inside `.kpress` as var(--kpress-font-mono).
    """

    root: dict[str, str] = {}
    for selector, declarations in _rules_of(SOURCE_DIR / "static" / "styles.css"):
        if selector == ":root":
            root.update(declarations)
    tokens = get_static_asset("css/style-tokens.css").content.decode("utf-8")

    assert root["--font-mono"] == "var(--app-mono)"
    assert root["--kpress-host-font-mono"] == "var(--app-mono)"
    assert re.search(r"--kpress-font-mono:\s*var\(\s*--kpress-host-font-mono,", tokens)
    assert "--app-mono" not in tokens


def test_host_unifies_inline_and_block_code_chrome() -> None:
    """The host decides the code edge through KPress's two public tokens alone.

    KPress applies `--kpress-code-border` and `--kpress-code-radius` to inline and block
    code alike (the test above), so a host rule restating either on embedded code would
    be a second place the same decision lives.
    """

    styles = (SOURCE_DIR / "static" / "styles.css").read_text(encoding="utf-8")
    code_border = "--code-border: color-mix(in srgb, var(--border) 55%, transparent);"
    code_selector = re.compile(r"\b(?:code|pre)\b|kpress-code")
    restated = [
        selector
        for selector, declarations in _rules_of(SOURCE_DIR / "static" / "styles.css")
        if ".metabrowser-kpress-host .kpress" in selector
        and code_selector.search(selector)
        and {"border", "border-radius", "padding"} & declarations.keys()
    ]

    assert code_border in styles
    assert "--kpress-code-border: var(--code-border);" in styles
    assert "--kpress-code-radius: var(--radius-document);" in styles
    assert restated == []
    assert "--inline-code-border" not in styles


def test_kpress_host_monospace_css_never_uses_a_dotted_border() -> None:
    code_selector = re.compile(r"\b(?:code|pre|mono|monospace)\b", re.IGNORECASE)
    dotted_border = re.compile(
        r"(?:border(?:-[a-z-]+)?\s*:[^;{}]*\bdotted\b|border-style\s*:\s*dotted)",
        re.IGNORECASE,
    )
    offenders: list[str] = []
    for path in sorted(SOURCE_DIR.rglob("*.css")):
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            if ".metabrowser-kpress-host" not in selector or not code_selector.search(selector):
                continue
            if dotted_border.search(declarations):
                offenders.append(f"{path.relative_to(PROJECT_FILE.parent)}: {selector.strip()}")
    document = get_static_asset("css/document.css").content.decode("utf-8")

    # The host sets only the edge's color; KPress names the style, and names it solid.
    assert "border: 1px solid var(--kpress-code-border);" in _kpress_rule(
        document, ".kpress code:not(pre code)"
    )
    assert "border: 1px solid var(--kpress-code-border);" in _kpress_rule(document, ".kpress-code")
    assert not offenders, f"dotted KPress-host code borders: {offenders}"
