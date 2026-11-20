---
type: is
id: is-01m7v9txk8kppfpj14tn09bgm3
title: "PR #617 B3: the checkpointed state can be a torn file"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v9tw8y6ssgdghdyks2p5ty
hold: null
hold_until: null
created_at: 2026-11-20T01:41:17.032Z
updated_at: 2026-11-20T01:57:20.003Z
started_at: 2026-11-20T01:50:14.902Z
closed_at: 2026-11-20T01:57:20.003Z
close_reason: "fixed in 74df98ad5/7ef20c2f6: validated private copy of main file and -wal under a cap, labeled main-file read past it; interrupted_checkpoint case"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:422; explorations/sqlite-guest-reads/README.md (Access). Interrupted checkpoint leaves main file inconsistent without its log. Severity: Medium. PR #617. Review: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5986230518
