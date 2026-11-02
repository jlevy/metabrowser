---
type: is
id: is-01m6f2m0fqdpmdkf79pf8mkxz9
title: "PR #276 A3: a zero-cap test pins a third-party library's error prose"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f2kp2dkv14cykagykcmqet
hold: null
hold_until: null
created_at: 2026-11-02T21:28:35.573Z
updated_at: 2026-11-02T21:49:01.517Z
started_at: 2026-11-02T21:29:10.010Z
closed_at: 2026-11-02T21:49:01.516Z
close_reason: "Fixed in 5c6567e: zero-cap test no longer pins json5's wording. CI run 41530107623 green at 5c6567e. Disposition: https://github.com/jlevy/metabrowser/pull/276#issuecomment-6589319967"
resolution: null
duplicate_of: null
---
Low. tests/test_structured_e2e.py:366 asserts json5's own message. Review: https://github.com/jlevy/metabrowser/pull/276#pullrequestreview-5743224957
