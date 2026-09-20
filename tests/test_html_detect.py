"""Bounded full-page HTML sniff: default-tab selection only."""

from __future__ import annotations

import gzip
from pathlib import Path

from metabrowser.builtin_plugins.html.detect import (
    HTML_SNIFF_PREFIX_BYTES,
    looks_like_full_page_html,
    sniff_full_page_html,
)


def test_sniff_budget_is_four_kib() -> None:
    assert HTML_SNIFF_PREFIX_BYTES == 4 * 1024


def test_full_page_signals() -> None:
    assert looks_like_full_page_html(b"<!doctype html><title>x</title>")
    assert looks_like_full_page_html(b"<!DOCTYPE HTML>\n<html lang=en>")
    assert looks_like_full_page_html(b"<html>")
    assert looks_like_full_page_html(b"<head><title>x</title></head>")
    assert looks_like_full_page_html(b"<body id=main>")
    assert looks_like_full_page_html(b"<frameset cols='50%,50%'>")
    assert looks_like_full_page_html(b"<HTML LANG='en'>")


def test_fragments_and_near_misses() -> None:
    assert not looks_like_full_page_html(b"")
    assert not looks_like_full_page_html(b"<div class=card>hello</div>")
    assert not looks_like_full_page_html(b"<header>nav</header>")
    assert not looks_like_full_page_html(b"<html-fragment>")
    assert not looks_like_full_page_html(b"hello <html>")
    assert not looks_like_full_page_html(b"<!doctype svg>")
    assert not looks_like_full_page_html(b"<!doctypehtml>")


def test_bom_comments_and_whitespace() -> None:
    assert looks_like_full_page_html(b"\xef\xbb\xbf  \n<!-- note -->\n<!doctype html>")
    assert looks_like_full_page_html(b"<!-- a --><!-- b --><body>")
    assert not looks_like_full_page_html(b"<!-- unclosed")
    assert not looks_like_full_page_html(b"   \n\n")
    assert not looks_like_full_page_html(b" " * HTML_SNIFF_PREFIX_BYTES)


def test_doctype_past_the_budget_is_ignored() -> None:
    prefix = (b" " * HTML_SNIFF_PREFIX_BYTES) + b"<!doctype html>"
    assert not looks_like_full_page_html(prefix[:HTML_SNIFF_PREFIX_BYTES])


def test_sniff_reads_logical_gzip_bytes(tmp_path: Path) -> None:
    target = tmp_path / "page.html.gz"
    target.write_bytes(gzip.compress(b"<!doctype html><p>hi</p>", mtime=0))
    assert sniff_full_page_html(target)

    fragment = tmp_path / "card.html.gz"
    fragment.write_bytes(gzip.compress(b"<div>card</div>", mtime=0))
    assert not sniff_full_page_html(fragment)


def test_unreadable_file_is_a_fragment(tmp_path: Path) -> None:
    missing = tmp_path / "gone.html"
    assert not sniff_full_page_html(missing)
