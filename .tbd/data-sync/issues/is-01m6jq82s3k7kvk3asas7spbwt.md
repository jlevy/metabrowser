---
type: is
id: is-01m6jq82s3k7kvk3asas7spbwt
title: Verify specialist review coverage for every feature PR before merge
kind: task
status: in_progress
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6jhbnan8czw6c97gr5511mr
hold: null
hold_until: null
created_at: 2026-11-04T07:26:48.093Z
updated_at: 2026-11-04T07:33:13.378Z
started_at: 2026-11-04T07:27:10.110Z
---
Audit the published senior and dedicated security, performance and correctness review coverage across all 20 feature PRs. Reuse valid existing reviews and immutable evidence; fill genuine focused review or publication gaps at current pinned heads. Recheck all finding dispositions, unchanged-source succession, current CI and the combined stack before conditional owner-authorized merges. Do not merge the preservation-only draft PR247.

## Notes

The published-coverage audit found valid dedicated reviews on the older layers and a few remaining gaps. Add narrow performance supplements for PRs273,279,281,283,288 and the parts of287 outside its existing current-file review. New layers289-294 need the applicable separately published security, correctness and performance passes; senior Review A and the independent fix receipts remain valid and must not be relabeled. PR287 also needs its requested security and correctness passes. Fresh performance review is running at a7b964c4 against the unchanged original pins. No new code defect has been confirmed. All new review letters, source scope, actual tests and limitations must be pinned and recorded before merge. Full make verify and current-head CI remain separate gates.
