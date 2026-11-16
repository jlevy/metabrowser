---
type: is
id: is-01m7jkb4mgqczq02t9x6y5czy7
title: "Files tree: a page's positionOffset is not updated when a row arrives above it, so rows drawn later may get positions one short (inferred, #464 round 2)"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T16:34:15.822Z
updated_at: 2026-11-16T16:34:15.822Z
---
Noted by the #464 review-B addressing agent, not verified: app.js around :2297/:2310. Reproduce with a live insert above a deferred page, then press its 'more' row and read aria-posinset.
