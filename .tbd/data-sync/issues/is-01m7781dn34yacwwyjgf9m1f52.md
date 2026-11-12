---
type: is
id: is-01m7781dn34yacwwyjgf9m1f52
title: "Source view: WebKit's first Load more relays out the column when the gutter gains a digit"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T06:45:04.289Z
updated_at: 2026-11-12T06:45:04.289Z
---
From #367 (mb-551q): after text nodes are capped at 64 KiB, the source view's first Load more on the gate's 16 MiB file still measures 2.25-2.46x Chrome in WebKit. That click crosses 100,000 lines (54,241 to 109,806), so the gutter gains a digit, the code column narrows, and WebKit lays out the whole column again. With a diagnostic stylesheet holding the gutter at 8ch, the click measured 1.43-1.44x; a bare page showed the view's grid costing about 4x a plain pre. Fixing it means reserving gutter width (a visible design choice for the owner) and/or changing the view's grid. Later Load mores and scrolling pass.
