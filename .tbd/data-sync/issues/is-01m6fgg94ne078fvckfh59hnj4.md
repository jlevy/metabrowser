---
type: is
id: is-01m6fgg94ne078fvckfh59hnj4
title: "PR #284 A4: fileForPath answers null for both no diff and not in comparison"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:13.428Z
updated_at: 2026-11-03T02:31:02.886Z
closed_at: 2026-11-03T02:31:02.885Z
close_reason: "A4 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 0aa8f047: fileForPath answers typed kinds (file, not_in_comparison, no_diff); jump golden and docs."
resolution: null
duplicate_of: null
---
Medium. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. github/pull-page.js:2064-2072, docs/large-content-rendering.md. Answer typed kinds matching scrollToFile.
