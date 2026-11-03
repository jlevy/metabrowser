---
type: is
id: is-01m6fggccrdpm8p1ad2wnrrmr3
title: "PR #284 A13: want() returns without recording while the tab is hidden"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:16.759Z
updated_at: 2026-11-03T02:31:05.785Z
closed_at: 2026-11-03T02:31:05.785Z
close_reason: "A13 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 0aa8f047: visibilitychange asks for the prefetch; verified in visible Chrome (a13.json)."
resolution: null
duplicate_of: null
---
Low suggestion. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. github/pull-page.js:1973-1975, comparison-prefetch.js:104-114. Call want() from onVisibilityChange.
