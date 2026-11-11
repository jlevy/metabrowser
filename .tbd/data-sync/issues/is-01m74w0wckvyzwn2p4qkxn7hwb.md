---
type: is
id: is-01m74w0wckvyzwn2p4qkxn7hwb
title: "PR #348 C1: Markdown render bound bypassable, not a total bound, cites missing measurement"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:34.834Z
updated_at: 2026-11-11T10:57:51.589Z
started_at: 2026-11-11T09:24:55.991Z
closed_at: 2026-11-11T10:57:51.588Z
close_reason: "Fixed: eb71cdc7 and 54dac394. The estimate counts the whole document; no line resets it (\\x0b/\\x0c/blank/whitespace). Test: test_the_render_bound_counts_the_whole_document[vt, ff, blank, ws]. Bracket-free costs (tables, math, lists, highlighting, delimiters) are charged too. #347's opener budget admitted 6.4 s task lists; worst admitted now 373 ms."
resolution: null
duplicate_of: null
---
Medium. pull_snapshot.py:162-173, 194-217, 54-55, 371-373. Review C https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855484116
