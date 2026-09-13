"""KPress is Metabrowser's required, released rendering dependency."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from kpress.runtime import get_static_asset

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


def test_the_toc_rail_is_reserved_through_kpress_not_reimplemented_in_host_css() -> None:
    """The reading column holds one position, and KPress is what holds it.

    Metabrowser briefly carried its own reserved-rail CSS because KPress had no
    option for it. KPress 0.3.1 does (``RenderOptions.toc_rail``), and the two
    implementations must never coexist: upstream reserves the rail by gridding
    the wide band and placing the prose in track 2, the host version used a left
    margin, and together they offset the column twice.
    """

    adapter = (SOURCE_DIR / "kpress_adapter.py").read_text(encoding="utf-8")
    styles = (SOURCE_DIR / "static" / "styles.css").read_text(encoding="utf-8")

    assert 'toc_rail="reserved"' in adapter

    # The host reimplementation and every token it needed are gone for good.
    for residue in (
        "Reserved TOC rail",
        "--embedded-toc-rail-width",
        "--embedded-doc-column-width",
        ":not(:has(.kpress-toc))",
    ):
        assert residue not in styles, (
            f"{residue!r} is host CSS reimplementing KPress's reserved rail; "
            'pass toc_rail="reserved" instead and delete it'
        )


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
