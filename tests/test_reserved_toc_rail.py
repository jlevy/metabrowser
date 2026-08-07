"""The embedded document keeps one reading-column position, TOC or no TOC.

KPress's wide band (>=75rem of pane width) left-aligns a `15rem 53rem` grid when a
document has a table of contents, and falls back to a centred, measure-capped column
when it has too few headings to earn one. Metabrowser reserves the rail in both cases
so the prose does not jump sideways from file to file (the ``── Reserved TOC rail ──``
block in ``static/styles.css``).

That reservation is a mirror of geometry Metabrowser does not own, so these tests read
the numbers back out of the installed KPress stylesheet: a KPress bump that retunes the
tracks fails here instead of silently splitting the two layouts apart again.
"""

from __future__ import annotations

import re

from kpress.runtime import get_static_asset

from metabrowser import server as proc_browser

WIDE_BAND_QUERY = "@container kpress-doc (min-width: 75rem)"


def _read_styles_css() -> str:
    return proc_browser.STATIC_DIR.joinpath("styles.css").read_text(encoding="utf-8")


def _read_kpress_components_css() -> str:
    return get_static_asset("css/components.css").content.decode("utf-8")


def _blocks(css: str, header: str) -> list[str]:
    """Return the body of every top-level block introduced by ``header``."""
    bodies: list[str] = []
    for match in re.finditer(re.escape(header) + r"\s*\{", css):
        depth = 1
        index = match.end()
        while depth and index < len(css):
            if css[index] == "{":
                depth += 1
            elif css[index] == "}":
                depth -= 1
            index += 1
        bodies.append(css[match.end() : index - 1])
    return bodies


def _root_token(css: str, name: str) -> str:
    match = re.search(rf"^\s*{re.escape(name)}:\s*([^;]+);", css, re.MULTILINE)
    assert match, f"{name} is not declared in styles.css"
    return match.group(1).strip()


def _kpress_wide_band() -> str:
    bodies = _blocks(_read_kpress_components_css(), WIDE_BAND_QUERY)
    assert len(bodies) == 1, "KPress should define exactly one wide document band"
    return bodies[0]


def test_metabrowser_mirrors_the_kpress_wide_band_tracks() -> None:
    band = _kpress_wide_band()
    styles = _read_styles_css()

    grid = re.search(r"grid-template-columns:\s*([\d.]+rem)\s+([\d.]+rem);", band)
    gap = re.search(r"column-gap:\s*([\d.]+rem);", band)
    inset = re.search(r"padding-inline:\s*([\d.]+rem);", band)
    assert grid and gap and inset, "KPress's wide TOC grid no longer states its tracks"

    assert _root_token(styles, "--embedded-toc-rail-width") == grid.group(1)
    assert _root_token(styles, "--embedded-doc-column-width") == grid.group(2)
    assert _root_token(styles, "--embedded-toc-rail-gap") == gap.group(1)
    assert _root_token(styles, "--embedded-doc-column-inset") == inset.group(1)


def test_kpress_still_centres_the_column_when_no_toc_is_rendered() -> None:
    """The premise of the override: upstream only uncaps the with-TOC case."""
    band = _kpress_wide_band()

    assert ".kpress-doc:has(.kpress-toc)" in band
    assert ".kpress-doc-layout:has(.kpress-toc)" in band
    assert ":not(:has(.kpress-toc))" not in band


def test_the_host_override_is_dropped_once_kpress_reserves_the_rail_itself() -> None:
    """Fails on the KPress bump that lands ``RenderOptions.toc_rail``.

    Upstream reserves the rail by making the wide band a grid and placing the
    prose in track 2. The host override reserves it with a left margin instead.
    Both at once double the offset, so the bump has to remove this block and
    pass ``toc_rail="reserved"`` through ``KPressRenderRequest`` in the same
    change (mb-vvxy) rather than simply upgrading the pin.
    """

    band = _kpress_wide_band()

    assert "data-kpress-toc-rail" not in band, (
        "KPress now reserves the TOC rail itself — delete the "
        "'Reserved TOC rail' block and its tokens from styles.css, pass "
        'toc_rail="reserved" in kpress_adapter.py, and delete this module'
    )


def test_reserved_rail_uncaps_and_offsets_the_no_toc_column() -> None:
    bands = _blocks(_read_styles_css(), WIDE_BAND_QUERY)
    rail = next((body for body in bands if ":not(:has(.kpress-toc))" in body), None)
    assert rail, "styles.css no longer reserves the TOC rail in the wide band"

    # Both reading-measure caps have to go; uncapping only the article leaves the
    # inner wrapper centred at the measure.
    assert ".metabrowser-kpress-host .kpress-doc:not(:has(.kpress-toc))" in rail
    assert ".metabrowser-kpress-host .kpress-doc-layout:not(:has(.kpress-toc))" in rail
    assert "max-width: none" in rail

    assert "--embedded-toc-rail-width" in rail
    assert "--embedded-toc-rail-gap" in rail
    assert "--embedded-doc-column-width" in rail
    assert "--embedded-doc-column-inset" in rail


def test_reserved_rail_neutralises_the_column_centred_table_bleed() -> None:
    bands = _blocks(_read_styles_css(), WIDE_BAND_QUERY)
    rail = next((body for body in bands if ":not(:has(.kpress-toc))" in body), None)
    assert rail

    # KPress's base wide-table rule centres on the column; a left-aligned column
    # needs the reset at or above the attribute selector's specificity.
    assert "transform: none" in rail
    assert 'data-kpress-table-scale="wide"' in rail
    assert "100cqw" in rail
