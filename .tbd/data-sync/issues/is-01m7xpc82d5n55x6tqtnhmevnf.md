---
type: is
id: is-01m7xpc82d5n55x6tqtnhmevnf
title: Validate fsqlite snapshot identity and retry the complete browse request
kind: bug
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/678
    at: 2026-11-21T09:24:50.207Z
delegate: codex
labels: []
dependencies: []
parent_id: is-01m7vtd571483vj430fqd5tw4y
hold: null
hold_until: null
created_at: 2026-11-20T23:58:56.588Z
updated_at: 2026-11-21T09:24:50.208Z
started_at: 2026-11-21T08:32:45.188Z
---
Optional fsqlite store browsing reuses the read-only SQLite table adapter over the snapshot named by current. Verify the opened snapshot's store identity and format against the marker before presenting tables, schema, or Info. Cover a mismatched store and a snapshot garbage-collected between catalog open and a later table/record request. Either retry the full request against the new pointer once or report an explicit moved-snapshot state with a safe retry. Keep the tests scoped to #678 so they do not gate ordinary SQLite browsing. Upstream research: https://github.com/jlevy/fsqlite/blob/e8fd2b2297/docs/research/research-2026-08-01-schema-evolution-and-workload-fit.md

## Notes

Local candidate for https://github.com/jlevy/metabrowser/pull/678: 9ede74b562c0179ac2651083749eed9c6afa226e, with original PR head e62226463a2dcfbc0daceb9a0de683f85192ca11 and ordinary SQLite head 3cbc7b8624942020d4dfc1f760686c34bca725d5 in its ancestry.

The guarded optional reader checks the FSQL application ID and matches the store_id and format_version stamps to the marker before exposing snapshot content. The initial read follows current again once if the file is collected. A later missing-file failure returns HTTP 409 snapshot_moved, and a fresh request reads the new version. The store views write no files or leases.

This candidate passed 305 focused Python tests, 75 directly affected transcript blocks, the native Chrome/HTTP smoke through an atomic publish and collection, and the wheel/sdist distribution checks. An isolated install of its wheel also returned a real fsqlite table row. Full local verification and exact-head GitHub CI are pending. The PR remains a draft.
