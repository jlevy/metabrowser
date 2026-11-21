---
type: is
id: is-01m7xpc7mhhkd2wdymrte05f6n
title: Validate ordinary SQLite browsing and report incomplete reads
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/676
    at: 2026-11-21T09:24:48.851Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7vtd2rax4r1pfqnb3q8f11v
hold: null
hold_until: null
created_at: 2026-11-20T23:58:56.144Z
updated_at: 2026-11-21T10:04:02.762Z
started_at: 2026-11-21T08:32:52.925Z
closed_at: 2026-11-21T10:04:02.762Z
close_reason: "Merged the seven ordinary tabular layers through #676 as 74cba363. Exact branch CI, isolated artifact checks, ordinary database browser acceptance, and post-merge main and macOS CI passed. The separate fsqlite validation remains tracked under #678."
resolution: null
duplicate_of: null
---
The core feature opens ordinary SQLite databases in place, including existing databases owned by other applications. It is independent of the fsqlite store plugin. Gate #676 on this path after integrating #674 and #675.

- Table and Schema must carry the worker's access state or give an explicit refusal when a WAL source falls back to a checkpoint-only read. A normal-looking complete page must not silently omit committed WAL frames. Preserve the private-copy size bound.
- Give a useful state for an unreadable WAL instead of a missing-file 404. Gate table reads cleanly when the linked SQLite lacks octet_length() (introduced in 3.43), or provide a bounded equivalent.
- Keep ordinary tables visible next to a virtual table on untrusted sources and pins. Test a normal table sharing an FTS table's prefix along with the actual shadow table.
- Run a complete browser smoke with ordinary SQLite fixtures for quiet, active WAL, read-only, and large databases. Include a WAL-only commit, atomic same-path replacement, and a failed or partial access state. Prove how the live-owner close race is contained or disclose the remaining sidecar risk before exercising a production database. Test positional record identity when a write lands between metadata sampling and the read.

Reference: https://github.com/jlevy/metabrowser/pull/676. Verification to date covered the exact worker transport and view models on two existing ordinary files. Browser/HTTP and active reads remain open. No local database contents are part of this issue.
