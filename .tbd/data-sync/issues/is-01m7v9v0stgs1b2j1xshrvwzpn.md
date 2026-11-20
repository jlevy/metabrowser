---
type: is
id: is-01m7v9v0stgs1b2j1xshrvwzpn
title: "PR #617 B10: octet_length needs SQLite 3.43; blobopen returns the storage encoding"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v9tw8y6ssgdghdyks2p5ty
hold: null
hold_until: null
created_at: 2026-11-20T01:41:20.313Z
updated_at: 2026-11-20T01:57:22.129Z
started_at: 2026-11-20T01:50:17.270Z
closed_at: 2026-11-20T01:57:22.129Z
close_reason: "fixed in 74df98ad5/7ef20c2f6: 3.43 minimum and fallback, decode by PRAGMA encoding, trim partial trailing character; storage_encoding case, values length_of_text_cast_to_blob"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:461-467, 487-492. Severity: Low. PR #617. Review: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5986230518
