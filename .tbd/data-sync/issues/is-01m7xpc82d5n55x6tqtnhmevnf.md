---
type: is
id: is-01m7xpc82d5n55x6tqtnhmevnf
title: Validate fsqlite snapshot identity and retry the complete browse request
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
delegate: codex
labels: []
dependencies: []
parent_id: is-01m7vtd571483vj430fqd5tw4y
hold: null
hold_until: null
created_at: 2026-11-20T23:58:56.588Z
updated_at: 2026-11-21T08:32:45.189Z
started_at: 2026-11-21T08:32:45.188Z
---
Optional fsqlite store browsing reuses the read-only SQLite table adapter over the snapshot named by current. Verify the opened snapshot's store identity and format against the marker before presenting tables, schema, or Info. Cover a mismatched store and a snapshot garbage-collected between catalog open and a later table/record request. Either retry the full request against the new pointer once or report an explicit moved-snapshot state with a safe retry. Keep the tests scoped to #678 so they do not gate ordinary SQLite browsing. Upstream research: https://github.com/jlevy/fsqlite/blob/e8fd2b2297/docs/research/research-2026-08-01-schema-evolution-and-workload-fit.md
