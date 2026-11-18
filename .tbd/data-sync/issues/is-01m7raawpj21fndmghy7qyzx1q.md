---
type: is
id: is-01m7raawpj21fndmghy7qyzx1q
title: "Draw the registry's glyphs where characters stand in: the inert TOC toggle's ☰ and the structured tree's ▸"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7r8jfm690nwt4rbad8ny3k2
created_at: 2026-11-18T21:52:17.105Z
updated_at: 2026-11-18T21:52:17.105Z
---
Found by the icon catalog (mb-k1k7, docs/design-system-icons.md, Known Departures). (1) An untrusted document's table of contents toggle, built by buildInertToc in builtin_plugins/markdown/inert-toc.js, types the character ☰, while a trusted render's toggle is KPress's Lucide `list` from its sprite (kpress/format/render.py, `_icon("list", css_class="kpress-toc-toggle-icon", width/height 20)`). The registry's `list` is the same drawing. Draw it there with the kpress-toc-toggle-icon class; buildInertToc takes a narrow document type (createElement/createTextNode) that tests/dom/markdown-inert-toc-session.js fakes, so build the SVG in a way that session supports, and check the toggle in tests/test_overview_readme_toc_chrome.py. (2) The structured data tree (builtin_plugins/structured/tree.js) types ▸ in .srow-chevron, colored --color-syntax-punct, where design-system.md 'One Chevron, One Row Contract' says every disclosure chevron is the registry's Lucide chevron in --muted. Use mb.icons.toggle. Caution: the shell's '.expanded .toggle-chevron { rotate }' rule rotates any toggle-chevron under an .expanded ancestor, and a structured tree is embedded inside an expanded agent log event (.log-event.expanded), so the row's own state must decide the rotation. Both need a look in Chrome; tests/test_icon_catalog.py drops the two Text rows once the characters are gone.
