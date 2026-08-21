"""Design-vocabulary agreements the stylesheet cannot state for itself.

Each check pins one cross-file agreement from ``docs/design-system.md``:
the disclosure chevron is one glyph everywhere it appears, row-like
activation targets share one height token, and their hover is the one
hover token. A failure here means a surface forked the vocabulary.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC = REPO_ROOT / "src" / "metabrowser" / "static"

CHEVRON_PATH = "m9 18 6-6-6-6"  # Lucide chevron-right


def _rule(css: str, selector: str) -> str:
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match is not None, f"selector not found: {selector}"
    return match.group(1)


def test_disclosure_chevron_is_one_glyph_everywhere() -> None:
    icons = (STATIC / "icons.js").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    # The registry's leading chevrons (tree rows, tally tree, diff bars);
    # icons.js quotes attributes with double quotes.
    assert icons.count(f'd="{CHEVRON_PATH}"') >= 2, "registry chevron glyphs changed shape"
    # The section-disclosure mask draws the same path (single-quoted
    # inside the data URI).
    assert f"d='{CHEVRON_PATH}'" in styles, "section-disclosure mask forked the glyph"
    # Both color from the same token family.
    assert "--section-disclosure-chevron-color: var(--muted);" in styles
    assert "color: var(--muted);" in _rule(styles, ".toggle-chevron")


def test_diff_bar_uses_the_shared_chevron_and_registry() -> None:
    view = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/diff_view.js").read_text(
        encoding="utf-8"
    )
    assert 'shellIcon("toggle")' in view, "diff bar must lead with the registry's toggle glyph"


def test_row_targets_share_the_row_height_token() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    assert "--ui-row-height: 24px;" in styles, "the row-height token moved or changed"
    assert "min-height: var(--ui-row-height);" in _rule(styles, ".tree-item")
    assert "min-height: var(--ui-row-height);" in _rule(
        diff_css, ".metabrowser-diff-host .diff-file-bar"
    )


def test_disclosure_motion_is_one_recipe_everywhere() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    overview_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )
    for css, selector in (
        (styles, ".tree-children"),
        (diff_css, ".metabrowser-diff-host .diff-file-body"),
        (diff_css, ".metabrowser-diff-host .diff-fold-group"),
        (overview_css, ".folder-overview-panel-body"),
    ):
        rule = _rule(css, selector)
        assert "height var(--transition-fast)" in rule, f"{selector} lost the travel"
        assert "interpolate-size: allow-keywords" in rule, f"{selector} lost keyword sizing"
    for css, selector in (
        (styles, ".tree-children-collapsed"),
        (diff_css, ".metabrowser-diff-host .diff-file-body-collapsed"),
        (diff_css, ".metabrowser-diff-host .diff-fold-collapsed"),
        (overview_css, ".folder-overview-panel-body-collapsed"),
    ):
        rule = _rule(css, selector)
        assert "height: 0" in rule and "visibility: hidden" in rule, f"{selector} state drifted"
    # Class-driven collapse: the tree never toggles inline display.
    for name in ("app.js", "tree_expansion.js"):
        source = (STATIC / name).read_text(encoding="utf-8")
        assert "tree-children-collapsed" in source, f"{name} lost the collapse class"


def test_inline_change_stats_are_bold() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    for css, selector in (
        (diff_css, ".metabrowser-diff-host .diff-stat-add"),
        (diff_css, ".metabrowser-diff-host .diff-stat-del"),
        (styles, ".git-stat-add"),
        (styles, ".git-stat-del"),
    ):
        assert "font-weight: var(--weight-bold)" in _rule(css, selector), f"{selector} not bold"


def test_branch_chips_are_bold_and_square() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    rule = _rule(styles, ".git-ref")
    assert "font-weight: var(--weight-bold)" in rule
    assert "border-radius: var(--radius-tag)" in rule
    assert "--radius-tag:" in styles


def test_row_targets_share_the_hover_token() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    assert "background: var(--hover-bg);" in _rule(styles, ".tree-item:hover")
    assert "background: var(--hover-bg);" in _rule(
        diff_css, ".metabrowser-diff-host .diff-file-bar:hover"
    )


def test_age_is_one_primitive_everywhere() -> None:
    """An age is an age: one formatter, one styling rule, and call sites
    that add positioning only."""
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    formatters = (STATIC / "formatters.js").read_text(encoding="utf-8")
    assert "function age(epochSeconds)" in formatters, "the shared age primitive moved"
    for name in ("git_panel.js", "app.js"):
        consumer = (STATIC / name).read_text(encoding="utf-8")
        assert "MetabrowserFormatters" in consumer and "age(" in consumer, (
            f"{name} must take its ages from the shared primitive"
        )
    tiers = _rule(
        styles, ":is(.age-live, .age-sec, .age-min, .age-hr, .age-day, .age-wk, .age-old)"
    )
    for declaration in ("color:", "font-weight:", "font-size:", "font-variant-numeric:"):
        assert declaration in tiers, f"the age primitive lost {declaration}"
    # A call site that restates color or weight has forked the vocabulary.
    graph_age = _rule(styles, ".git-graph-age")
    assert "color:" not in graph_age and "font-weight:" not in graph_age, (
        ".git-graph-age must carry positioning only"
    )


def test_branch_chips_have_their_own_ground() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "background: var(--git-ref-bg)" in _rule(styles, ".git-ref")
    assert "--git-ref-bg: var(--viz-surface-sunken)" not in styles, (
        "ref chips must not reuse the shared chip ground"
    )
    assert styles.count("--git-ref-bg:") >= 2, "both themes must define the ref-chip ground"


# ── Theming: one hue, two lightnesses ──────────────────────────────

_OKLCH_TOKEN = re.compile(r"^\s*(--[a-z0-9-]+):\s*oklch\(([^)]+)\)", re.MULTILINE)


def _oklch_tokens(block: str) -> dict[str, list[str]]:
    return {name: value.split() for name, value in _OKLCH_TOKEN.findall(block)}


def _theme_blocks() -> tuple[str, str]:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    dark_start = styles.index('[data-theme="dark"] {')
    return styles[:dark_start], styles[dark_start:]


# Hue is a color's identity; lightness and chroma are how it is rendered
# against a background. Measured across the tokens already in oklch, the
# deliberate theme adjustments move lightness and chroma while hue drifts
# at most ~2 degrees, which is tuning, not a different color.
_THEME_HUE_TOLERANCE_DEGREES = 3.0


def test_themed_colors_keep_their_hue() -> None:
    """The systematic rule for two themes.

    A token defined in both themes names one color seen against two
    backgrounds: its hue is the invariant, while lightness and chroma
    are tuned for the background it sits on (dark surfaces usually want
    less chroma, not more of it). Stating colors in oklch is what makes
    this checkable at all — the notation separates the three components,
    which hex and hsl do not — so the check covers the tokens already
    migrated and widens as the migration proceeds.
    """
    light_tokens = _oklch_tokens(_theme_blocks()[0])
    dark_tokens = _oklch_tokens(_theme_blocks()[1])
    compared = 0
    for name, dark_value in dark_tokens.items():
        light_value = light_tokens.get(name)
        if light_value is None or len(light_value) < 3 or len(dark_value) < 3:
            continue
        compared += 1
        drift = abs(float(light_value[2]) - float(dark_value[2]))
        assert drift <= _THEME_HUE_TOLERANCE_DEGREES, (
            f"{name} changes hue between themes (light {light_value[2]}, "
            f"dark {dark_value[2]}); a themed color keeps its hue and moves in "
            "lightness and chroma"
        )
        assert light_value[0] != dark_value[0] or light_value[1] != dark_value[1], (
            f"{name} is identical in both themes; drop the override instead"
        )
    assert compared >= 10, "the theming check lost its coverage"


def test_ref_colors_are_themed_and_distinguished_by_hue() -> None:
    """Three ref kinds, one lightness, three hues — each themed, since a
    single literal cannot be readable on both backgrounds."""
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    tokens = ("--git-ref-local", "--git-ref-remote", "--git-ref-tag")
    for token in tokens:
        assert styles.count(f"{token}:") >= 2, f"{token} must be defined for both themes"
    light, _dark = _theme_blocks()
    light_tokens = _oklch_tokens(light)
    hues = [light_tokens[token][2] for token in tokens if token in light_tokens]
    assert len(set(hues)) == 3, f"ref kinds must differ by hue, got {hues}"
