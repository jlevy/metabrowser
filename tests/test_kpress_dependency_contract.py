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

    assert "kpress==0.3.5" in project["project"]["dependencies"]
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
        == "calc(100cqw - 2 * (var(--content-padding-x) + var(--pane-header-padding-x)))"
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


def test_pinned_kpress_owns_the_inline_code_base_style() -> None:
    css = get_static_asset("css/document.css").content.decode("utf-8")
    code_start = css.index(".kpress code,\n.kpress-code {")
    code_block = css[code_start : css.index("}\n", code_start) + 2]
    inline_start = css.index(".kpress code:not(pre code) {")
    inline_block = css[inline_start : css.index("}\n", inline_start) + 2]

    assert "background: var(--kpress-doc-surface-bg);" in code_block
    assert "font-family: var(--kpress-font-mono, ui-monospace, monospace);" in code_block
    assert "font-size: var(--kpress-font-size-mono);" in code_block
    assert "border: 1px solid var(--color-hint-gentle);" in inline_block
    assert "border-radius: var(--kpress-radius-sm);" in inline_block
    assert "padding: 0.25em 0.2em 0.1em 0.2em;" in inline_block


def test_host_unifies_inline_and_block_code_chrome() -> None:
    styles = (SOURCE_DIR / "static" / "styles.css").read_text(encoding="utf-8")
    code_border = "--code-border: color-mix(in srgb, var(--border) 55%, transparent);"
    code_surfaces = """.metabrowser-kpress-host .kpress code:not(pre code),
.metabrowser-kpress-host .kpress .kpress-code {
  border: 1px solid var(--code-border);
  border-radius: var(--radius-document);
}"""

    assert code_border in styles
    assert "--kpress-code-border: var(--code-border);" in styles
    assert "--kpress-code-radius: var(--radius-document);" in styles
    assert code_surfaces in styles
    assert "--inline-code-border" not in styles


def test_kpress_host_monospace_css_never_uses_a_dotted_border() -> None:
    code_selector = re.compile(r"\b(?:code|pre|mono|monospace)\b", re.IGNORECASE)
    dotted_border = re.compile(
        r"(?:border(?:-[a-z-]+)?\s*:[^;{}]*\bdotted\b|border-style\s*:\s*dotted)",
        re.IGNORECASE,
    )
    scanned: list[str] = []
    offenders: list[str] = []
    for path in sorted(SOURCE_DIR.rglob("*.css")):
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            if ".metabrowser-kpress-host" not in selector or not code_selector.search(selector):
                continue
            scanned.append(selector.strip())
            if dotted_border.search(declarations):
                offenders.append(f"{path.relative_to(PROJECT_FILE.parent)}: {selector.strip()}")

    assert any(".kpress-code" in selector for selector in scanned)
    assert any("code:not(pre code)" in selector for selector in scanned)
    assert not offenders, f"dotted KPress-host code borders: {offenders}"
