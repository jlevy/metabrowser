---
type: is
id: is-01m7raatxaeyxam9feb76y6w11
title: Category shapes reuse action glyphs (Archives = copy, Media = monitor), and PDF's fileText is doc under a second name
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7r8jfm690nwt4rbad8ny3k2
created_at: 2026-11-18T21:52:15.273Z
updated_at: 2026-11-18T21:52:15.273Z
---
Found by the icon catalog (mb-k1k7, docs/design-system-icons.md, Known Departures). In src/metabrowser/data/file-rollup-format/recommended-file-types.toml the Archives group's icon is `copy`, the clipboard action every copy button draws, and the Media group's is `monitor`, the system theme segment in the Metabrowser menu: one glyph, two meanings. Separately, the PDF family declares `icon = "fileText"`, whose drawing in static/icons.js is identical to `doc`, the Documentation group's shape PDF would inherit anyway. Choosing each category's representative icon is mb-hqje's work (claude/category-icons), so resolve these as part of that choice or right after it: give Archives and Media shapes of their own, and drop the PDF override and `fileText` (a registry revision: bump registry_revision and run devtools/file_type_contract.py --write). tests/test_icon_catalog.py will then ask for the catalog rows to follow.
