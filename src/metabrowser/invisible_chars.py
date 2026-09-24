"""Code points a renderer shows as nothing, or as a space, while they change a name.

A name holding one passes for another: ``README<U+3164>.md`` reads as ``README.md`` in
most fonts. The GitHub URL reducer refuses them raw in a URL, and the Git tree source
replaces them when it displays a path, so one table serves both.
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
# U+2800 BRAILLE PATTERN BLANK is a symbol, not default-ignorable, but a cell with no dots
# is drawn as a space.
BLANK_BRAILLE: Final = 0x2800


def is_invisible(ch: str) -> bool:
    """Whether *ch* is default-ignorable or the blank braille pattern."""

    point = ord(ch)
    return point == BLANK_BRAILLE or any(low <= point <= high for low, high in DEFAULT_IGNORABLE)
