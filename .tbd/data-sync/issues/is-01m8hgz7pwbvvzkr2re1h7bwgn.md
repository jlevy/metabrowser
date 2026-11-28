---
type: is
id: is-01m8hgz7pwbvvzkr2re1h7bwgn
title: Merge current origin/main into the SoftSchema collection stack
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwjx1z7rpzb8emdknjxk1
child_order_hints:
  - is-01m8hhrk32vnybr7hvjreszfhp
hold: null
hold_until: null
created_at: 2026-11-28T16:49:15.974Z
updated_at: 2026-11-28T17:31:37.901Z
started_at: 2026-11-28T16:49:39.143Z
closed_at: 2026-11-28T17:31:37.885Z
close_reason: "Merged origin/main at 5f0faf11 through both published layers of stack #916. Exact CI and macOS gates passed at 1bc64d022 and ee2d88efb. The updated preview serves the verified 577-row People table."
resolution: null
duplicate_of: null
---
Bring current upstream into #913 and then #915 without rewriting their published history, repin guided reviews, and verify hosted checks. User requested merging from upstream.
