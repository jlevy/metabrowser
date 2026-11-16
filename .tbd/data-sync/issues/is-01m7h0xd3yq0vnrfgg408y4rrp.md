---
type: is
id: is-01m7h0xd3yq0vnrfgg408y4rrp
title: "PR #455 A10: print the delivery decision when the server starts, as one banner line"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h0wnsjyz9enemj0de4q5wg
hold: null
hold_until: null
created_at: 2026-11-16T01:52:56.957Z
updated_at: 2026-11-16T02:11:18.755Z
started_at: 2026-11-16T01:53:14.012Z
closed_at: 2026-11-16T02:11:18.755Z
close_reason: "A10 fixed in a8bbfcc46: banner line 'Compression: off for loopback clients of this machine' when serving locally; pinned across the start matrix in tests/test_delivery.py."
resolution: null
duplicate_of: null
---
Severity: Suggestion. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review A (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5913913966), finding A10. References: src/metabrowser/cli/serve.py.
