---
type: is
id: is-01kzt5jx3qv3wyanzs9x6nh5wt
title: "PR #32 review R1: avoid stale recency after recovery await"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kzt5jng86n8400av6g3z666q
created_at: 2026-08-12T05:02:11.062Z
updated_at: 2026-08-12T05:06:39.278Z
closed_at: 2026-08-12T05:06:39.277Z
close_reason: "Fixed both PR #32 review findings in b9f2ec0 with regression coverage."
---
Cursor Bugbot review thread PRRT_kwDOTX174c6YcrAO. src/metabrowser/static/app.js:1952-1965 captures recency before await loadTree(), then can restore an obsolete window after the user changes the filter.
