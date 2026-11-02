---
type: is
id: is-01m6f2kxf4re2nbhya69yk025w
title: "PR #274 qodo r4436468138: byte-exact stderr in the missing-git test"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f2kt0jwn6mx6es1wg9w3b8
hold: null
hold_until: null
created_at: 2026-11-02T21:28:32.483Z
updated_at: 2026-11-02T21:50:27.324Z
started_at: 2026-11-02T21:28:36.675Z
closed_at: 2026-11-02T21:50:27.322Z
close_reason: "rebutted: stderr is one line of 120 bytes at any COLUMNS, and the single line is what is pinned; normalizing would let a wrapped refusal pass. Reply: https://github.com/jlevy/metabrowser/pull/274#issuecomment-6589345714"
resolution: null
duplicate_of: null
---
qodo Medium. tests/test_cli_acquire.py:458-462. https://github.com/jlevy/metabrowser/pull/274#discussion_r4436468138 Review A lists it under false positives.
