---
type: is
id: is-01m6g1xrp4w0n6cfkvsxrvdw4k
title: "PR #285 C7: undrawn rows are absent from Chrome's accessibility tree, and rows carry no position"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6g1x4rv0qbdqdqdz64p3qn0
created_at: 2026-11-03T06:35:41.123Z
updated_at: 2026-11-03T06:35:41.123Z
---
styles.css:396-398 content-visibility: auto keeps undrawn rows out of the AX tree; rows (pulls-panel.js:1439-1451) set no aria-posinset or aria-setsize where Files rows do. Add them unless that costs the cap's render. Review: https://github.com/jlevy/metabrowser/pull/285#pullrequestreview-5747624823 (severity Low).
