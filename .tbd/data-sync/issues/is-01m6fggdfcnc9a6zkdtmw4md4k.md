---
type: is
id: is-01m6fggdfcnc9a6zkdtmw4md4k
title: "PR #284 B2: Git C-style quoting of \\\\a \\\\b \\\\f \\\\r \\\\v is not undone"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:17.868Z
updated_at: 2026-11-03T02:31:06.751Z
closed_at: 2026-11-03T02:31:06.750Z
close_reason: "B2 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6: all nine C escapes undone; every byte tested through Git's own quoting."
resolution: null
duplicate_of: null
---
Medium. Review B https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745588159. diff/adapters/patch_file.py:105. Extend the table; conformance JSON; adapter test with a CR in a name.
