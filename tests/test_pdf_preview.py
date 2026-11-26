"""The PDF preview's parts: the PNG encoder and its validator, the key, the cache's
eviction, the isolation rule, and the child's command line.

The routes over them are ``tests/test_pdf_preview_routes.py``'s, the transcript of what
they answer ``tests/golden/cli-api-pdf-preview.tryscript.md``, and the sandbox's
confinement ``tests/test_pdf_preview_sandbox.py``'s.
"""

from __future__ import annotations

import os
import struct
import sys
import zlib
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.pdf import render_child
from metabrowser.builtin_plugins.pdf.preview import (
    PREVIEW_BOX,
    REASON_MESSAGES,
    png_facts,
    preview_key,
    renderer_version,
)
from metabrowser.builtin_plugins.pdf.preview_isolation import (
    Isolation,
    Sandbox,
    child_command,
    child_environment,
    isolation_for,
    macos_profile,
)
from metabrowser.builtin_plugins.pdf.preview_store import AREA, PreviewStore

# A sandbox that confines nothing, for the rule's table: only whether there is one counts.
_SOME_SANDBOX = Sandbox(name="any", prefix=("/usr/bin/true",))


def _chunks(png: bytes) -> list[tuple[bytes, bytes]]:
    assert png.startswith(render_child.PNG_SIGNATURE)
    offset = len(render_child.PNG_SIGNATURE)
    found: list[tuple[bytes, bytes]] = []
    while offset < len(png):
        (length,) = struct.unpack_from(">I", png, offset)
        kind = png[offset + 4 : offset + 8]
        body = png[offset + 8 : offset + 8 + length]
        (crc,) = struct.unpack_from(">I", png, offset + 8 + length)
        assert crc == zlib.crc32(kind + body), kind
        found.append((kind, body))
        offset += 12 + length
    return found


def _image(width: int, height: int, stride_pad: int = 0) -> tuple[bytes, int]:
    stride = width * 3 + stride_pad
    rows = bytearray()
    for y in range(height):
        row = bytes((x * 7 + y * 13) % 256 for x in range(width * 3))
        rows += row + b"\xee" * stride_pad
    return bytes(rows), stride


def test_the_encoder_writes_a_png_whose_rows_decode_to_the_pixels() -> None:
    pixels, stride = _image(5, 3, stride_pad=4)
    png = render_child.encode_png(5, 3, pixels, stride, text={"Pages": "12"})
    chunks = _chunks(png)
    assert [kind for kind, _ in chunks] == [b"IHDR", b"tEXt", b"IDAT", b"IEND"]
    assert struct.unpack(">IIBBBBB", chunks[0][1]) == (5, 3, 8, 2, 0, 0, 0)
    assert chunks[1][1] == b"Pages\x0012"
    raw = zlib.decompress(chunks[2][1])
    # Each row is filter 0 then its pixels, without the stride's padding.
    rows = [raw[y * 16 : (y + 1) * 16] for y in range(3)]
    assert len(raw) == 3 * (1 + 15)
    for y, row in enumerate(rows):
        assert row[0] == 0
        assert row[1:] == pixels[y * stride : y * stride + 15]
    assert png_facts(png, box=(5, 3)).pages == 12


def test_the_encoder_refuses_pixels_that_do_not_cover_the_image() -> None:
    with pytest.raises(ValueError, match="pixel"):
        render_child.encode_png(0, 1, b"", 0)
    with pytest.raises(ValueError, match="cover"):
        render_child.encode_png(2, 2, b"\0" * 11, 6)


def test_the_validator_takes_only_the_encoders_own_form() -> None:
    pixels, stride = _image(4, 4)
    good = render_child.encode_png(4, 4, pixels, stride, text={"Pages": "3"})
    facts = png_facts(good)
    assert (facts.width, facts.height, facts.pages) == (4, 4, 3)
    bad: dict[str, bytes] = {
        "trailing bytes": good + b"x",
        "a wrong checksum": good[:-5] + bytes([good[-5] ^ 1]) + good[-4:],
        "no page count": render_child.encode_png(4, 4, pixels, stride),
        "other text": render_child.encode_png(4, 4, pixels, stride, text={"Author": "x"}),
        "not a PNG": b"GIF89a" + good[6:],
        "cut short": good[:-12],
    }
    for label, data in bad.items():
        with pytest.raises(ValueError):
            png_facts(data)
        assert label
    # Larger than the box: a child that drew past it wrote something else.
    wide, wide_stride = _image(PREVIEW_BOX[0] + 1, 1)
    with pytest.raises(ValueError, match="box"):
        png_facts(
            render_child.encode_png(PREVIEW_BOX[0] + 1, 1, wide, wide_stride, text={"Pages": "1"})
        )


def test_the_key_names_the_content_the_renderer_and_the_box() -> None:
    renderer = renderer_version()
    assert renderer.startswith("pypdfium2 ") and "; pdfium " in renderer and "; png 1" in renderer
    key = preview_key("sha256:ab", renderer, PREVIEW_BOX)
    assert len(key) == 64 and key == preview_key("sha256:ab", renderer, PREVIEW_BOX)
    others = {
        preview_key("sha256:ac", renderer, PREVIEW_BOX),
        preview_key("git-blob:ab", renderer, PREVIEW_BOX),
        preview_key("sha256:ab", renderer + "x", PREVIEW_BOX),
        preview_key("sha256:ab", renderer, (PREVIEW_BOX[0], PREVIEW_BOX[1] + 1)),
    }
    assert key not in others and len(others) == 4


def _png(seed: int) -> bytes:
    pixels, stride = _image(2, 2)
    return render_child.encode_png(2, 2, pixels, stride, text={"Pages": str(seed)})


def _key(index: int) -> str:
    return f"{index:064x}"


def test_the_store_keeps_entries_and_evicts_the_least_recently_used(tmp_path: Path) -> None:
    store = PreviewStore(tmp_path)
    from metabrowser.home import ensure_private_directory

    ensure_private_directory(tmp_path, AREA)
    for index in range(1, 5):
        assert store.write(_key(index), _png(index))
    directory = tmp_path / AREA
    # Their uses, oldest first: 1, 2, 3, 4. Reading 1 makes it the newest.
    for index in range(1, 5):
        os.utime(directory / f"{_key(index)}.png", ns=(index * 10**9, index * 10**9))
    assert store.read(_key(1)) == _png(1)
    size = (directory / f"{_key(1)}.png").stat().st_size
    report = store.evict(max_bytes=size * 2, max_entries=100)
    assert report.removed == 2
    kept = sorted(path.name for path in directory.iterdir())
    assert kept == sorted(f"{_key(index)}.png" for index in (1, 4))
    # The entry bound works alone too, and a name of another form is never removed.
    (directory / "notes.txt").write_bytes(b"not ours")
    assert store.evict(max_bytes=10**9, max_entries=1).removed == 1
    assert sorted(path.name for path in directory.iterdir()) == [f"{_key(1)}.png", "notes.txt"]
    # A miss, a key not of the form, and an entry that is not a PNG are all None.
    assert store.read(_key(9)) is None
    (directory / f"{_key(7)}.png").write_bytes(b"not a png")
    assert store.read(_key(7)) is None
    with pytest.raises(ValueError):
        store.read("../escape")


def test_the_isolation_rule_is_threat_model_t7() -> None:
    assert isolation_for(trusted=True, sandbox=_SOME_SANDBOX) == Isolation(_SOME_SANDBOX)
    assert isolation_for(trusted=False, sandbox=_SOME_SANDBOX) == Isolation(_SOME_SANDBOX)
    assert isolation_for(trusted=True, sandbox=None) == Isolation(None)
    assert isolation_for(trusted=False, sandbox=None) == "no_sandbox"
    assert "sandbox" in REASON_MESSAGES["no_sandbox"]


def test_the_child_runs_isolated_by_path_with_a_minimal_environment() -> None:
    command = child_command(Isolation(_SOME_SANDBOX), ["1", "2"])
    assert command[:1] == ["/usr/bin/true"]
    assert command[1:5] == [sys.executable, "-I", "-B", render_child.__file__]
    assert command[5:] == ["1", "2"]
    assert child_command(Isolation(None), [])[0] == sys.executable
    env = child_environment()
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert set(env) <= {"PATH", "LC_ALL", "PYTHONDONTWRITEBYTECODE", "MIMALLOC_ARENA_RESERVE"}


def test_the_macos_profile_denies_what_it_does_not_name() -> None:
    profile = macos_profile(["/opt/interp"], ["/opt/interp/bin/python3"])
    lines = profile.splitlines()
    assert lines[:2] == ["(version 1)", "(deny default)"]
    # Nothing that writes, connects, or forks is allowed.
    for refused in ("file-write", "network", "process-fork", "mach-lookup"):
        assert refused not in profile
    assert '(allow process-exec (literal "/opt/interp/bin/python3"))' in lines
    assert '(subpath "/opt/interp")' in profile
    assert macos_profile(['/a "b'], []).count('"/a \\"b"') == 2
