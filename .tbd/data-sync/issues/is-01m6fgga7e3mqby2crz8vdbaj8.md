---
type: is
id: is-01m6fgga7e3mqby2crz8vdbaj8
title: "PR #284 A7: any keydown releases the pin, ordering with a nav jump implicit"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:14.541Z
updated_at: 2026-11-03T01:31:14.541Z
---
Low. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. diff/diff-view.js releasePinOnInput. Make a jump immune to the keydown that caused it, or document the ordering.
