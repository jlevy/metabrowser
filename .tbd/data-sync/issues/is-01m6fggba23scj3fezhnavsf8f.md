---
type: is
id: is-01m6fggba23scj3fezhnavsf8f
title: "PR #284 A10: failed files counted as loaded; a throw in deps.render stalls the scheduler"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:15.649Z
updated_at: 2026-11-03T02:31:04.828Z
closed_at: 2026-11-03T02:31:04.827Z
close_reason: "A10 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 0aa8f047: a throwing render fails its file alone and failures are counted apart; jump session and golden."
resolution: null
duplicate_of: null
---
Low. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. diff/diff-view.js settleDeferred, hydrationHost.fail. Same as Qodo inline comment 5 https://github.com/jlevy/metabrowser/pull/284#discussion_r4449451273
