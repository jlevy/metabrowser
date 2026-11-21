---
type: is
id: is-01m7xpc82d5n55x6tqtnhmevnf
title: Validate fsqlite snapshot identity and retry the complete browse request
kind: bug
status: closed
priority: 2
version: 6
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
updated_at: 2026-11-21T11:26:00.582Z
started_at: 2026-11-21T08:32:45.188Z
closed_at: 2026-11-21T11:26:00.582Z
close_reason: "All eight tabular layers landed through #678. Optional fsqlite checks passed the exact local gate, independent hot-journal and installed-package probes, browser live publication, branch workflows, and final main CI and macOS app workflows at 98c2dffd."
resolution: null
duplicate_of: null
---
Optional fsqlite store browsing reuses the read-only SQLite table adapter over the snapshot named by current. Verify the opened snapshot's store identity and format against the marker before presenting tables, schema, or Info. Cover a mismatched store and a snapshot garbage-collected between catalog open and a later table/record request. Either retry the full request against the new pointer once or report an explicit moved-snapshot state with a safe retry. Keep the tests scoped to #678 so they do not gate ordinary SQLite browsing. Upstream research: https://github.com/jlevy/fsqlite/blob/e8fd2b2297/docs/research/research-2026-08-01-schema-evolution-and-workload-fit.md

## Notes

Current local candidate for https://github.com/jlevy/metabrowser/pull/678: 9acd5e80b7af0434e989d1812c2e6192c9e32bcd. Its ancestors include both original PR head e62226463a2dcfbc0daceb9a0de683f85192ca11 and approved ordinary SQLite head 9c792b59e05e566e5c326c90c0c20f2a112757eb.

The optional guarded reader verifies the FSQL application ID, both reserved table layouts, and all four f1.0 metadata fields. The identity and format stamps must match the marker. Marker and pointer reads require a regular file, and the numbered snapshot must be at its own path. SQLite WAL/SHM companions and live rollback journals are refused. A collected snapshot triggers one initial pointer retry or a typed HTTP 409 snapshot_moved when a later table read needs the file. Fresh requests re-open the current version.

Exact-head verification passed 468 focused tests, 105 affected transcript blocks, type checks, artifact/parity/App/design contracts, the locked npm/uv audit, and installed wheel/sdist verification. In native Chrome the table stayed open at the same address and refreshed to version 2 within 429 ms after atomic publication and collection. An independent HTTP rerun refused the real 20,000-row killed-writer hot journal in Info and table rows, with unchanged hashes and entry metadata. The isolated wheel served a valid fsqlite row and likewise refused the hot journal without modifying its files.

The draft remains open. Its normal full pre-push gate and GitHub CI follow the ordinary PR publishing the approved head.
