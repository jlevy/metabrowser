---
type: is
id: is-01m6fesevt7mp8vz7am4456h06
title: "PR #283 A3: path-spelled remote never matches a file:// source"
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
created_at: 2026-11-03T01:01:17.049Z
updated_at: 2026-11-03T01:53:59.237Z
started_at: 2026-11-03T01:33:02.026Z
closed_at: 2026-11-03T01:53:59.236Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: A3 path-spelled remote is the file:// source; negative tests"
resolution: null
duplicate_of: null
---
Medium. Review A. src/metabrowser/cache/lender.py:224-250 and acquire.py:1019. Resolve a path remote to file:// before classifying; negative test for lookalikes.
