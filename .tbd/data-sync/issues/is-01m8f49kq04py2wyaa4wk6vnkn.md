---
type: is
id: is-01m8f49kq04py2wyaa4wk6vnkn
title: Report live SoftSchema collection discovery progress
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwjx1z7rpzb8emdknjxk1
hold: null
hold_until: null
created_at: 2026-11-27T18:29:15.615Z
updated_at: 2026-11-27T18:53:41.293Z
started_at: 2026-11-27T18:29:58.425Z
---
Show checked paths in the existing collection spinner and preserve visible results on refresh. Measure Universe cold and warm indexing. Track parsed-record progress separately because the published scanner exposes discovery only.

## Notes

The shared Files scan status displays checked paths during cold collection discovery. The Universe preview counted 5,472 paths, read 4,992 files, and published 577 People rows within its 4,971 records and 18 schemas. Published 0.10.0 measured 48.7 s cold pure, 21.6 s cold C-first, and 0.45 s unchanged with zero content reads. The exact implementation and its cold-cache regression are on PR #915. Parsing and binding telemetry stay in mb-9qud.
