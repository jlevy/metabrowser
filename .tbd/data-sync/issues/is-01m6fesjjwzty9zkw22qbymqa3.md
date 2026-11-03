---
type: is
id: is-01m6fesjjwzty9zkw22qbymqa3
title: "PR #283 B1: lender own alternates and ownership checks run only with --checkout"
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
created_at: 2026-11-03T01:01:20.859Z
updated_at: 2026-11-03T01:54:02.432Z
started_at: 2026-11-03T01:33:05.233Z
closed_at: 2026-11-03T01:54:02.431Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: B1 lender checks run again on every open and before every fetch"
resolution: null
duplicate_of: null
---
Medium. Review B https://github.com/jlevy/metabrowser/pull/283#pullrequestreview-5745454882. acquire.py:1050-1055, update.py _overlay_preparation. Re-apply on every open that uses a recorded lender.
