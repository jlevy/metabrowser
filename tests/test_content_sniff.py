"""Content-based classification for files whose extension does not settle it.

The interesting cases are the ones where extension and content disagree, and
the boundary conditions where a cheap check is easy to get subtly wrong.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from metabrowser.content_sniff import (
    SNIFF_PREFIX_BYTES,
    ContentClass,
    classify_prefix,
    sniff_artifact,
)
from metabrowser.file_kinds import FileContext


class TestClassifyPrefix:
    """The pure decision, which is what a future crawl would call directly."""

    def test_empty_is_text(self) -> None:
        # An empty file has nothing binary about it, and the text path renders
        # it as empty rather than as a zero-byte dump.
        assert classify_prefix(b"") is ContentClass.TEXT

    @pytest.mark.parametrize(
        "payload",
        [
            b"hello world\n",
            b"#!/bin/sh\necho hi\n",
            "héllo → 世界".encode(),
            b"\xef\xbb\xbfwith a BOM",
            b"tabs\tand\r\ncrlf\r\n",
        ],
    )
    def test_decodable_utf8_is_text(self, payload: bytes) -> None:
        assert classify_prefix(payload) is ContentClass.TEXT

    def test_nul_byte_is_binary(self) -> None:
        assert classify_prefix(b"looks like text\x00but is not") is ContentClass.BINARY

    def test_utf16_is_binary(self) -> None:
        # Valid text in another encoding, but not text this browser renders,
        # and its NULs are exactly what the check keys on.
        assert classify_prefix("hello".encode("utf-16le")) is ContentClass.BINARY

    def test_latin1_high_bytes_are_binary(self) -> None:
        # Legible as text in another encoding, but not valid UTF-8.
        assert classify_prefix(b"r\xe9sum\xe9 na\xefve") is ContentClass.BINARY

    def test_random_bytes_are_binary(self) -> None:
        payload = bytes(range(256)) * 4
        assert classify_prefix(payload) is ContentClass.BINARY

    def test_multibyte_split_across_the_boundary_is_still_text(self) -> None:
        """A character cut in half by the prefix bound must not read as binary.

        Without an incremental decoder the verdict would depend on where the
        read happened to stop, which is both wrong and hard to reproduce.
        """
        payload = ("世" * 8000).encode()[:SNIFF_PREFIX_BYTES]
        # Confirm the fixture actually lands mid-character, or it proves nothing.
        with pytest.raises(UnicodeDecodeError):
            payload.decode("utf-8")
        assert classify_prefix(payload) is ContentClass.TEXT


class TestSniffArtifact:
    """The view-time path: a bounded read, then the pure decision."""

    def test_text_file(self, tmp_path: Path) -> None:
        target = tmp_path / "notes"
        target.write_text("plain text, no extension\n")
        assert sniff_artifact(target) is ContentClass.TEXT

    def test_binary_file(self, tmp_path: Path) -> None:
        target = tmp_path / "blob.bin"
        target.write_bytes(bytes(range(256)) * 32)
        assert sniff_artifact(target) is ContentClass.BINARY

    def test_reads_logical_bytes_of_a_compressed_artifact(self, tmp_path: Path) -> None:
        """A gzipped text file is text.

        Its raw bytes are a gzip container and would classify as binary; the
        browser renders the decompressed content, so that is what is judged.
        """
        target = tmp_path / "notes.txt.gz"
        with gzip.open(target, "wb") as handle:
            handle.write(b"hello notes\n" * 500)
        assert classify_prefix(target.read_bytes()[:SNIFF_PREFIX_BYTES]) is ContentClass.BINARY
        assert sniff_artifact(target) is ContentClass.TEXT

    def test_bound_is_respected_on_a_large_file(self, tmp_path: Path) -> None:
        """Only the prefix decides, so a late NUL does not change the answer.

        This is the property that keeps the check the same cost for a 4 KB file
        and a 4 GB one.
        """
        target = tmp_path / "late-nul"
        target.write_bytes(b"a" * (SNIFF_PREFIX_BYTES * 4) + b"\x00")
        assert sniff_artifact(target) is ContentClass.TEXT

    def test_unreadable_file_is_unknown(self, tmp_path: Path) -> None:
        assert sniff_artifact(tmp_path / "does-not-exist") is ContentClass.UNKNOWN


class TestFileContextSeam:
    """The lazy property, which is where view-time classification hangs."""

    def test_sniffs_on_first_use_and_caches(self, tmp_path: Path) -> None:
        target = tmp_path / "blob"
        target.write_bytes(b"\x00\x01\x02\x03")
        ctx = FileContext(target, "")
        assert ctx.content_class is ContentClass.BINARY
        # Deleting the file cannot change a cached answer, which is how we know
        # the second read never happened.
        target.unlink()
        assert ctx.content_class is ContentClass.BINARY

    def test_supplied_value_is_used_without_reading(self, tmp_path: Path) -> None:
        """A caller that already knows supplies the answer.

        This is the seam a crawl would use: it has the bytes during inventory,
        so the view does not read them again.
        """
        missing = tmp_path / "never-read"
        ctx = FileContext(missing, "", content_class=ContentClass.TEXT)
        assert ctx.content_class is ContentClass.TEXT
        assert not missing.exists()
