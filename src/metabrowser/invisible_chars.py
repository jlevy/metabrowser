"""Code points a renderer shows as nothing, or as a space, while they change a name.

A name holding one passes for another: ``README<U+3164>.md`` reads as ``README.md`` in
most fonts, and ``README<U+200A>.md``, with a hair space, as ``README.md`` or as
``README .md``. The GitHub URL reducer refuses them raw in a URL, and the Git tree
source replaces them when it displays a path, so one table serves both.

Three kinds are listed: Unicode's default-ignorable code points; the blank braille
pattern; and every space and line separator other than the ASCII space, which is the 16
other space separators (category Zs), U+00A0 NO-BREAK SPACE to U+3000 IDEOGRAPHIC SPACE,
with U+2028 LINE SEPARATOR (Zl) and U+2029 PARAGRAPH SEPARATOR (Zp). A reader cannot
tell one of those from a space or sees nothing at all, and the two separators break the
line for a consumer that honours Unicode line breaks. The ASCII space is an ordinary
part of a name and is not listed.

Variation selectors are default-ignorable but exempt when attached to a base: they are
part of emoji names such as ``❤️.md`` (U+2764 U+FE0F) and of ideographic variation
sequences, and a look-alike made with one needs a base character, which stays visible.
A selector with no base is not exempt, since it is drawn as nothing where it stands:
one that begins the text, follows a space, a control, an invisible character, or
another selector, or follows an ASCII character, as in ``README<U+FE0F>.md``. The one
ASCII base kept is an emoji keycap, a digit, ``#``, or ``*`` followed by the selector
and U+20E3 COMBINING ENCLOSING KEYCAP, as in ``1️⃣``. A selector after a non-ASCII base
that has no variation sequence is still drawn as nothing; telling those apart needs
Unicode's variation-sequence data, which Python's ``unicodedata`` does not carry.

Unassigned (Cn) and private-use (Co) code points are not listed, and there the reducer
and the display differ on purpose. The reducer refuses either raw, which costs a person
one retyping in the encoded spelling the refusal offers. The display keeps both.
Replacing is lossy, and which code points are unassigned depends on the Unicode data of
the Python that is running, 15.0 in Python 3.12 and 16.0 in 3.14: a name written with a
newer character, a recent emoji for one, would show as U+FFFD under one interpreter and
intact under another. Nor is either kind hidden by rule: the unassigned code points
that are default-ignorable are in the table, a private-use code point shows the glyph a
font gives it, as an icon font does, and the rest normally show a font's missing-glyph
mark, so a reader sees that the name holds something.

Every table here is literal, the format characters included, so what a path displays as
does not depend on that data, with one exception: the base of a variation selector is
judged by the running Python's ``str.isprintable`` and ``str.isspace``, so a selector
after a code point that Python calls unassigned counts as having no base.
"""

from __future__ import annotations

from typing import Final

# Default_Ignorable_Code_Point, from Unicode 17.0's DerivedCoreProperties.txt, as ICU
# 78.3 reports it (Node 24's `\p{Default_Ignorable_Code_Point}`): characters a renderer
# shows as nothing, such as U+034F COMBINING GRAPHEME JOINER, the Hangul fillers
# U+115F, U+1160, U+3164, and U+FFA0, and the variation selectors U+FE00..U+FE0F.
DEFAULT_IGNORABLE: Final[tuple[tuple[int, int], ...]] = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x206F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)
# VARIATION SELECTOR-1..16 and VARIATION SELECTOR-17..256: default-ignorable, but
# exempt when attached to a base (see the module docstring).
VARIATION_SELECTORS: Final[tuple[tuple[int, int], ...]] = (
    (0xFE00, 0xFE0F),
    (0xE0100, 0xE01EF),
)
# U+2800 BRAILLE PATTERN BLANK is a symbol, not default-ignorable, but a cell with no dots
# is drawn as a space.
BLANK_BRAILLE: Final = 0x2800
# Every space separator (Zs) other than U+0020, with U+2028 LINE SEPARATOR (Zl) and
# U+2029 PARAGRAPH SEPARATOR (Zp): 18 code points, the same in Unicode 15.0 to 17.0.
# U+180E MONGOLIAN VOWEL SEPARATOR left Zs for Cf in Unicode 6.3 and is default-ignorable.
SPACE_SEPARATORS: Final[tuple[tuple[int, int], ...]] = (
    (0x00A0, 0x00A0),
    (0x1680, 0x1680),
    (0x2000, 0x200A),
    (0x2028, 0x2029),
    (0x202F, 0x202F),
    (0x205F, 0x205F),
    (0x3000, 0x3000),
)
# The format characters (category Cf), which reorder or hide what is shown around them:
# 170 code points, the same in Unicode 15.0, 15.1, 16.0, and 17.0, the data Python 3.12,
# 3.13, and 3.14 and Node 24 carry. The display tests membership here instead of asking
# ``unicodedata.category`` for each character. The table is literal because the set
# cannot be made cheaply from that data: asking the category of all 1,114,112 code
# points cost 108 to 142 times the CPU time of building every set below from the tables,
# about 0.1 s against under 1 ms (CPython 3.14.7, seven back-to-back pairs, 2026-10-01).
FORMAT: Final[tuple[tuple[int, int], ...]] = (
    (0x00AD, 0x00AD),
    (0x0600, 0x0605),
    (0x061C, 0x061C),
    (0x06DD, 0x06DD),
    (0x070F, 0x070F),
    (0x0890, 0x0891),
    (0x08E2, 0x08E2),
    (0x180E, 0x180E),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x2064),
    (0x2066, 0x206F),
    (0xFEFF, 0xFEFF),
    (0xFFF9, 0xFFFB),
    (0x110BD, 0x110BD),
    (0x110CD, 0x110CD),
    (0x13430, 0x1343F),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0001, 0xE0001),
    (0xE0020, 0xE007F),
)
_KEYCAP_BASES: Final = frozenset("#*0123456789")
_KEYCAP: Final = "\u20e3"


def _chars(*tables: tuple[tuple[int, int], ...]) -> frozenset[str]:
    """The characters of *tables*, for a membership test that costs one hash lookup."""

    return frozenset(
        chr(point) for table in tables for low, high in table for point in range(low, high + 1)
    )


# The tables above as sets of characters. A path is displayed once per entry of a
# listing, so each test is one lookup and never a walk of the ranges; the measurement
# is beside ``display_segment`` in ``metabrowser.git.tree_source``.
#
# The 256 variation selectors. Whether one is seen depends on its base, which
# ``hidden_at`` reads.
SELECTOR_CHARS: Final[frozenset[str]] = _chars(VARIATION_SELECTORS)
# Drawn as nothing or as a space wherever it stands: default-ignorable, the blank
# braille pattern, or a space or line separator other than the ASCII space. A variation
# selector is not here.
INVISIBLE_CHARS: Final[frozenset[str]] = (
    _chars(DEFAULT_IGNORABLE, SPACE_SEPARATORS, ((BLANK_BRAILLE, BLANK_BRAILLE),)) - SELECTOR_CHARS
)
FORMAT_CHARS: Final[frozenset[str]] = _chars(FORMAT)


def hidden_at(text: str, index: int) -> bool:
    """Whether ``text[index]`` is drawn as nothing or as a space where it stands."""

    ch = text[index]
    if ch not in SELECTOR_CHARS:
        return ch in INVISIBLE_CHARS
    if index == 0:
        return True
    base = text[index - 1]
    if base.isascii():
        return not (base in _KEYCAP_BASES and text[index + 1 : index + 2] == _KEYCAP)
    return (
        not base.isprintable()
        or base.isspace()
        or base in SELECTOR_CHARS
        or base in INVISIBLE_CHARS
    )
