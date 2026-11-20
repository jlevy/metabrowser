---
type: is
id: is-01m7vavjge1x571fxtswd8nbng
title: "Files toolbar: redraw around the ref chooser instead of detaching it (follow-ups from #625 review)"
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys615s2mfvbc93c9g2pac
created_at: 2026-11-20T01:59:07.021Z
updated_at: 2026-11-20T17:09:38.445Z
---
From #625 review A: (A1) a refill between a browser-initiated scroll (Tab focusing a row via plain focus()) and its scroll event restores a stale drawnAt, leaving the focused row out of view — route row stops through focusRow; (A2) a refill while the list is closed loses its place for the next open; (A3) docblock at source-ref-selector.js:1120-1121 wrongly says focus events don't fire in headless tests. Structural fix: renderNavFilterBar (app.js ~5935) replaces the row's other children around the chooser rather than bar.innerHTML + prepend, which would also stop disrupting IME composition, clicks straddling a refill, and scrollbar drags, and remove keepAcrossRefills. Review: attic/landing/reviews/pr625-senior-r1.txt.
