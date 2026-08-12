---
type: is
id: is-01kzt08p0xh3yr6aa1j4rkqfm5
title: "PR #24 review R17: root commits drop every lane in flight"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies: []
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-12T03:29:13.243Z
updated_at: 2026-08-12T03:29:14.246Z
closed_at: 2026-08-12T03:29:14.245Z
close_reason: Fixed on feat/git-graph-view (59f99ba).
---
computeSwimlanes wrapped the lane carry-forward in parent_ids.length > 0, so a root commit emitted no output lanes at all rather than ending only its own. Under --all with grafted or subtree histories a root arrives mid-log and the branches beside it redraw as disconnected tips; a single-root repository puts its root last where nothing is in flight, which is why it stayed invisible. Upstream scmHistory.ts has the same guard, so this is an upstream bug and the fix is recorded as numbered divergence 5. Worth reporting upstream. Covered by a multi-root topology test that fails without it.
