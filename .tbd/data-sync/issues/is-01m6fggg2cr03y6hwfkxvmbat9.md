---
type: is
id: is-01m6fggg2cr03y6hwfkxvmbat9
title: "PR #284 C3: an abandoned request late rejection marks a file failed while a fresh request is in flight"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:20.523Z
updated_at: 2026-11-03T02:31:09.008Z
closed_at: 2026-11-03T02:31:09.007Z
close_reason: "C3 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 0aa8f047: request identity in the scheduler; jump session and the reviewer's probe."
resolution: null
duplicate_of: null
---
Medium. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. diff-view.js:1421-1457 begin. Compare request identity, not entry identity; drop AbortError without fail.
