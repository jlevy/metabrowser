---
type: is
id: is-01m7hfn0xvacr892am7j82eqkv
title: "PR #470 A1: a failed read of a new comparison leaves the old counts in the pull header"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7hcjv212191g3nw3tr8take
created_at: 2026-11-16T06:10:30.970Z
updated_at: 2026-11-16T06:10:30.970Z
---
pull-page.js:5327-5362, comparison-prefetch.js:83-100, :111. The row is replaced only when a new summary draws; a refused prefetch is never retried and a null or rejected summary keeps the old handle. Severity: Medium. PR #470, review A round 1: https://github.com/jlevy/metabrowser/pull/470#pullrequestreview-5915665462
