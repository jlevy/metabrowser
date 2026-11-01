---
type: is
id: is-01m6c49dpdcrn0q2a8ebxkg7z6
title: A file-type label breaks mid-word in a narrow pane
kind: bug
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T18:00:02.508Z
updated_at: 2026-11-01T18:00:02.508Z
---
Seen 2026-11-01: Markdown wraps as Markd/own in File Overview at a main pane about 400 px wide, because file_type_summary.css line 65 sets overflow-wrap: anywhere on the label, which also lets the column shrink. Present on main, not from PR #275.
