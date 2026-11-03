---
type: is
id: is-01m6feseg1hwh5ekkqgbt8f2ff
title: "PR #283 A2: overlay refresh re-downloads what the checkout lacks every time"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T01:01:16.673Z
updated_at: 2026-11-03T01:53:58.921Z
started_at: 2026-11-03T01:33:01.704Z
closed_at: 2026-11-03T01:53:58.920Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: A2 store refs as negotiation tips; objects per refresh 75 -> 3 on the replica"
resolution: null
duplicate_of: null
---
High. Review A. src/metabrowser/cache/lender.py:657-671. Offer the store own refs as negotiation tips after the sweep; measure with transfer.unpackLimit=1. Same as Qodo inline comment 5 https://github.com/jlevy/metabrowser/pull/283#discussion_r4449381255
