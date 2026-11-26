"""The glyphs the server writes into a page's first paint, outside the browser's icon registry.

Nothing may appear or move after the first paint, so a control the server draws has its
glyph in the page it writes, as its box is, rather than waiting for a script to fill it.
The browser's icon registry (``static/icons.js``) is a startup script under a transfer
budget that ``devtools/check_startup_scripts.py`` gates, and its glyphs are drawn by script;
a glyph here costs the page's own bytes instead, with no script and no request, as a root's
mark does (``source_kind_marks.py``; docs/design-system-icons.md, "Where Icons Come From").

Each is Lucide v1.17.0 (ISC; https://lucide.dev), its Lucide id in the comment beside it. The
markup is the package's own, so it is trusted: no part of it comes from what is served.
"""

from __future__ import annotations

from typing import Final

# The attributes every Lucide glyph is drawn with (`SA` in static/icons.js). The stroke takes the
# element's ink, as every glyph of the chrome does: an icon never carries its own color.
LUCIDE_SVG_OPEN: Final = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
)

# The navigation's Refresh, on every page (server.py, `nav_refresh`): Lucide `rotate-cw`.
REFRESH_SVG: Final = (
    f'{LUCIDE_SVG_OPEN}<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/>'
    '<path d="M21 3v5h-5"/></svg>'
)
