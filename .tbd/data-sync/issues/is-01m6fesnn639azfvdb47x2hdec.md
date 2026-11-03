---
type: is
id: is-01m6fesnn639azfvdb47x2hdec
title: "PR #283 C6: _rebind runs under the store lock and not the fetch lock"
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
created_at: 2026-11-03T01:01:24.005Z
updated_at: 2026-11-03T01:54:04.957Z
started_at: 2026-11-03T01:33:07.825Z
closed_at: 2026-11-03T01:54:04.956Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: C6 _rebind takes the fetch lock"
resolution: null
duplicate_of: null
---
Low. Review C. acquire.py:1081-1094. Same as Qodo inline comment 1 https://github.com/jlevy/metabrowser/pull/283#discussion_r4449381228
