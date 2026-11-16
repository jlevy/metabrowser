---
type: is
id: is-01m7hdmnqyt7avb5rapceps67t
title: "PR #458 A4: three design-system statements say more than the code does"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjeyyagvt3h7zcvvssfks
hold: null
hold_until: null
created_at: 2026-11-16T05:35:22.365Z
updated_at: 2026-11-16T06:16:21.152Z
started_at: 2026-11-16T05:35:29.712Z
closed_at: 2026-11-16T06:16:21.151Z
close_reason: "Fixed in 3ed205983 on PR #458; disposition reply https://github.com/jlevy/metabrowser/pull/458#issuecomment-6908956491"
resolution: null
duplicate_of: null
---
Low. Review A https://github.com/jlevy/metabrowser/pull/458#pullrequestreview-5915435915. docs/design-system.md:3786-3792 (Regions Keep Their Boxes: one height, first paint), :3171-3172 (Where it breaks: each line as full as it can be, but a cluster's following control starts its own line), :3218 (every Group by and filter state, but four are swept). Fix all three.
