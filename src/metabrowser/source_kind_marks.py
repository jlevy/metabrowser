"""The glyph for each kind of root, which the shell writes into its first paint.

A root is a plain folder, a Git checkout, or a mirror
(:data:`~metabrowser.root_identity.IdentityKind`), and the mark before the root's name at the
top of the navigation draws one glyph for the kind (docs/design-system-icons.md, "Source
Kinds"). The glyphs are Lucide's or derived from their v1.17.0 artwork (ISC notice in
``static/source-kind-glyphs.license.txt``), kept in ``static/source-kind-glyphs.json``,
which is also what the macOS app's ``RootMark`` is held to (``RootMarkTests``), so the page
and the app's menus draw one set.

They are not in the browser's icon registry (``static/icons.js``). The registry is a startup
script every page fetches before its first tree, under a transfer budget that
``devtools/check_startup_scripts.py`` gates, and a page draws exactly one of the three: the
server knows which when it writes the page, so it writes that one, as markup, and the registry
and the script carry none. The page draws it with no script and no request, so it is there
from the first paint, as the mark's box is.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Final

from metabrowser.root_identity import IdentityKind

GLYPH_FILE: Final = Path(__file__).parent / "static" / "source-kind-glyphs.json"
# The attributes every Lucide glyph is drawn with (`SA` in static/icons.js). The stroke takes the
# element's ink, as every glyph of the chrome does: an icon never carries its own color.
_SVG_OPEN: Final = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
)


@functools.cache
def _glyphs() -> dict[str, dict[str, str]]:
    return json.loads(GLYPH_FILE.read_text(encoding="utf-8"))


def source_kind_svg(kind: IdentityKind) -> str:
    """The inline SVG for a root of *kind*: the glyph file's elements in Lucide's 24-point box.

    The file is the package's own and holds only bundled SVG paths, so the markup is trusted;
    no part of it comes from the folder or the repository being served.
    """

    return f"{_SVG_OPEN}{_glyphs()[kind]['elements']}</svg>"
