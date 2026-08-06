---
type: is
id: is-01kzcr84s67b3vq28xt30z9fgn
title: Use sans for key names and suggestion text in chrome
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01kzcr7qzp4j0x9h694b8evywa
created_at: 2026-08-06T23:58:59.365Z
updated_at: 2026-08-06T23:58:59.365Z
---
Chrome that names keys or offers suggestions/affordance hints uses the sans UI face, not monospace.

Known offender: .search-palette-hint in src/metabrowser/static/styles.css is font-family: var(--font-mono).

Its content ('↑↓ choose · Enter open · Esc close', built in search_palette.js) becomes sans text plus the KBD component from the sibling bead, rather than a monospaced string.

Sweep for other hint/suggestion chrome using mono and convert.
