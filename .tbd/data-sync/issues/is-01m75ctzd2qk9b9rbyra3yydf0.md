---
type: is
id: is-01m75ctzd2qk9b9rbyra3yydf0
title: "PR #349 E3: the route hydrates and keeps the patches of Markdown files it will refuse"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75ctrr5888kr3hwzkeezxc3
hold: null
hold_until: null
created_at: 2026-11-11T13:30:27.105Z
updated_at: 2026-11-11T13:33:57.731Z
started_at: 2026-11-11T13:30:33.789Z
closed_at: 2026-11-11T13:33:57.730Z
close_reason: "Fixed in 8e25d447: batches take only counted, small, projectable later files (1,000 lines a file, 2,000 a batch), and kept patches are bounded at 20,000 patch lines; the 4-line request takes 16.6-18.5 ms and keeps at most 0.11 MB live."
resolution: null
duplicate_of: null
---
Review E, E3 (High): one request for a 4-line file took 1.3 s and kept 102 MB. https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5859293936
