---
type: is
id: is-01m7hfn0xvacr892am7j82eqkv
title: "PR #470 A1: a failed read of a new comparison leaves the old counts in the pull header"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjv212191g3nw3tr8take
hold: null
hold_until: null
created_at: 2026-11-16T06:10:30.970Z
updated_at: 2026-11-16T06:58:48.903Z
started_at: 2026-11-16T06:42:50.834Z
closed_at: 2026-11-16T06:58:48.902Z
close_reason: "Fixed in 5fc9bc9 and 8fb537f; confirmed by headerSummary and the prefetch session. Disposition reply: https://github.com/jlevy/metabrowser/pull/470#issuecomment-6909694363"
resolution: null
duplicate_of: null
---
pull-page.js:5327-5362, comparison-prefetch.js:83-100, :111. The row is replaced only when a new summary draws; a refused prefetch is never retried and a null or rejected summary keeps the old handle. Severity: Medium. PR #470, review A round 1: https://github.com/jlevy/metabrowser/pull/470#pullrequestreview-5915665462
