"""SPA-side tests for logical-extension propagation + compression badge.

Mirrors the textual-assertion pattern used in ``test_browser_v2``: load
``app.js`` as text and assert the relevant helpers and dispatch sites
exist. No JS runtime in the test environment.
"""

from __future__ import annotations

from metabrowser import server as proc_browser


def _app_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("app.js").read_text()


def _styles_css() -> str:
    return proc_browser.STATIC_DIR.joinpath("styles.css").read_text()


# ── Helpers exist ─────────────────────────────────────────────────


def test_get_logical_ext_helper_defined() -> None:
    js = _app_js()
    assert "function getLogicalExt(entry)" in js
    # Falls back to getExt(name) when the field is absent — backwards
    # compatible with responses that don't carry logical_ext yet.
    assert "if (entry && entry.logical_ext) return entry.logical_ext;" in js


def test_get_logical_name_strips_gz_suffix() -> None:
    js = _app_js()
    assert "function getLogicalName(entry)" in js
    # The strip path keys off both `compressed` AND `.gz` suffix so a
    # non-gz file with a name ending in literal ".gz" doesn't get
    # silently truncated.
    assert "entry.compressed" in js
    assert 'entry.name.toLowerCase().endsWith(".gz")' in js


# ── Dispatch sites use logical name ───────────────────────────────


def test_tree_emit_uses_logical_name_for_icon_dispatch() -> None:
    """`getFileIcon(getLogicalName(node))`, not `getFileIcon(node.name)`."""
    js = _app_js()
    assert "getFileIcon(getLogicalName(node))" in js
    # Make sure the old direct call site is gone (would re-introduce
    # the .gz-classifies-wrong bug).
    assert "getFileIcon(node.name)" not in js


def test_prefetch_reads_data_logical_ext() -> None:
    """`shouldPrefetchFile` keys the JSONL skip rule off `data-logical-ext`
    when present, falling back to the path suffix otherwise."""
    js = _app_js()
    assert "item.dataset.logicalExt || getExt(path)" in js


# ── Badge rendering ───────────────────────────────────────────────


def test_tree_emit_adds_compressed_class_and_badge_for_gz_files() -> None:
    js = _app_js()
    assert 'compressed ? " is-compressed" : ""' in js
    # The Z badge HTML, only emitted when compressed is true.
    assert '<span class="compression-badge" title="gzipped">Z</span>' in js


def test_tree_emit_attaches_data_logical_ext_attr_when_present() -> None:
    """Server-attached `logical_ext` must round-trip into the DOM so
    prefetch + future scripts can read it."""
    js = _app_js()
    assert 'data-logical-ext="' in js


def test_render_badges_emits_compressed_badge_for_compressed_files() -> None:
    """Preview-pane file header gets a Compressed (or Gzip) badge whenever
    the server response says ``compressed: true``."""
    js = _app_js()
    assert "if (data && data.compressed)" in js
    assert "badge-compressed" in js


# ── CSS ───────────────────────────────────────────────────────────


def test_styles_define_compression_badge_overlay() -> None:
    css = _styles_css()
    assert ".tree-item-icon.is-compressed" in css
    assert ".compression-badge" in css
    # Uses real tokens already in this codebase (not the placeholder
    # names from the first-draft spec sketch).
    assert "var(--font-mono)" in css[css.index(".compression-badge") :]
    assert "var(--muted)" in css[css.index(".compression-badge") :]


def test_styles_define_file_header_compressed_badge() -> None:
    css = _styles_css()
    assert ".badge-compressed" in css
