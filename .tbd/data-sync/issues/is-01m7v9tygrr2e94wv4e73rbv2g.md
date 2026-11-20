---
type: is
id: is-01m7v9tygrr2e94wv4e73rbv2g
title: "PR #617 B5: null-cursor branch is a scan; descending order loses rows"
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
created_at: 2026-11-20T01:41:17.975Z
updated_at: 2026-11-20T01:57:20.620Z
started_at: 2026-11-20T01:50:15.551Z
closed_at: 2026-11-20T01:57:20.620Z
close_reason: "fixed in 74df98ad5/7ef20c2f6: region paging both directions; encoding.json keyset and null_heavy_page_opcodes"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:444-450. Page each region with its own seek, both directions. Severity: Medium. PR #617. Review: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5986230518
