---
type: is
id: is-01m8cstvdnhw32096evd6ykqdz
title: "PR #893 A1: Label stale compact treemap data after a refresh failure"
kind: bug
status: closed
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cq1k9y4w2m5320yeny38zp
hold: null
hold_until: null
created_at: 2026-11-26T20:47:57.355Z
updated_at: 2026-11-26T21:21:44.955Z
started_at: 2026-11-26T20:48:00.146Z
closed_at: 2026-11-26T21:21:44.952Z
close_reason: "Implemented and independently reviewed in merged Metabrowser PR #893. Exact-head CI passed, and the live refresh timing matched the event log."
resolution: null
duplicate_of: null
---
When the compact map has a completed rollup, its new explicit refresh can fail without indicating stale cells. Preserve the existing cells and show a small accessible warning until a successful terminal answer.
