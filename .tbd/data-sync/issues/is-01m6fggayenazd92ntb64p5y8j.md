---
type: is
id: is-01m6fggayenazd92ntb64p5y8j
title: "PR #284 A9: an arrived answer is discarded when the file leaves the viewport"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:15.278Z
updated_at: 2026-11-03T02:31:04.503Z
closed_at: 2026-11-03T02:31:04.502Z
close_reason: "A9 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 0aa8f047: an arrived answer renders when its file leaves the viewport; jump session."
resolution: null
duplicate_of: null
---
Low. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. diff/diff-view.js createHydrationScheduler setVisible(id,false) while arrived.
