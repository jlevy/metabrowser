---
type: is
id: is-01m75ctzswgxm7bb5mse31tfmn
title: "PR #349 E4: a 44 KB run of ::: lines takes 455 ms to refuse"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75ctrr5888kr3hwzkeezxc3
hold: null
hold_until: null
created_at: 2026-11-11T13:30:27.515Z
updated_at: 2026-11-11T13:33:58.057Z
started_at: 2026-11-11T13:30:34.105Z
closed_at: 2026-11-11T13:33:58.056Z
close_reason: "Fixed in 45431c6c: a side with more than 256 container lines is refused before parsing; the 11,000-line input refuses in 1.46 ms."
resolution: null
duplicate_of: null
---
Review E, E4 (Low): https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5859293936
