---
type: is
id: is-01m7p8sr3qvsj1e11zadq5vt0d
title: "Treemap tab: the same file-type legend as the File Overview, with the same hover behavior (every matching region highlighted, darker, eased, gentle shimmer on regions and the entry)"
kind: feature
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-18T02:46:57.910Z
updated_at: 2026-11-18T03:21:45.862Z
started_at: 2026-11-18T03:21:45.861Z
---
Owner, 2026-11-18 in chat: 'we should add the same legend to the treemap tab. And the same behavior'. Reuse the File Overview's legend builder and the shared hover store (distribution-hover.js) rather than a second implementation; the treemap's bars currently keep a hover of their own (noted in #516's review A). Stack on the legend-hover PR (mb-z6hb).
