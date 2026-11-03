---
type: is
id: is-01m6fgga7e3mqby2crz8vdbaj8
title: "PR #284 A7: any keydown releases the pin, ordering with a nav jump implicit"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:14.541Z
updated_at: 2026-11-03T02:31:03.860Z
closed_at: 2026-11-03T02:31:03.859Z
close_reason: "A7 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 0aa8f047: a key older than the pin does not release it; jump session."
resolution: null
duplicate_of: null
---
Low. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. diff/diff-view.js releasePinOnInput. Make a jump immune to the keydown that caused it, or document the ordering.
