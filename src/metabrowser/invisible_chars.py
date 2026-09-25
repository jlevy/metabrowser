"""Code points a renderer shows as nothing, or as a space, while they change a name.

A name holding one passes for another: ``README<U+3164>.md`` reads as ``README.md`` in
most fonts. The GitHub URL reducer refuses them raw in a URL, and the Git tree source
replaces them when it displays a path, so one table serves both.

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
_KEYCAP_BASES: Final = frozenset("#*0123456789")
_KEYCAP: Final = "\u20e3"


def is_variation_selector(ch: str) -> bool:
    """Whether *ch* is one of the 256 variation selectors."""

    point = ord(ch)
    return any(low <= point <= high for low, high in VARIATION_SELECTORS)


def is_invisible(ch: str) -> bool:
    """Whether *ch* is default-ignorable or the blank braille pattern, wherever it stands.

    A variation selector is not: whether one is seen depends on its base, which
    :func:`hidden_at` reads.
    """

    point = ord(ch)
    if is_variation_selector(ch):
        return False
    return point == BLANK_BRAILLE or any(low <= point <= high for low, high in DEFAULT_IGNORABLE)


def hidden_at(text: str, index: int) -> bool:
    """Whether ``text[index]`` is drawn as nothing or as a space where it stands."""

    ch = text[index]
    if not is_variation_selector(ch):
        return is_invisible(ch)
    if index == 0:
        return True
    base = text[index - 1]
    if base.isascii():
        return not (base in _KEYCAP_BASES and text[index + 1 : index + 2] == _KEYCAP)
    return (
        not base.isprintable()
        or base.isspace()
        or is_variation_selector(base)
        or is_invisible(base)
    )
