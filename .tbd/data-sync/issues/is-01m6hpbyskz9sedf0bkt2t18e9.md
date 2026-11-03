---
type: is
id: is-01m6hpbyskz9sedf0bkt2t18e9
title: Distinguish an empty Open filter from a repository with no PRs
kind: bug
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:52:12.077Z
updated_at: 2026-11-03T22:03:02.781Z
started_at: 2026-11-03T21:53:28.394Z
---
Independent landing probe found followLanding defaults its GET toOpen, while describeLanding treated fetched0 plus complete as repository-wide absence. A repository with zeroOpen and17Closed PRs therefore said No pull requests even on the Closed landing. Use exact repository_total for repository absence, or explicitly name the selected empty filter; preserve closed/all navigation without falsely claiming the repository is empty.

## Notes

Fixed repository absence to require exact repository_total zero plus complete. Unchanged independent repository17/Open0 probe red No pull requests, then green Select a pull request; reviewer rechecked clean. Permanent controls retain true zero and unknown-total behavior; Closed/All navigation is covered explicitly. Final29 affected tests/both browser type configs/9 scoped UI goldens pass. Exact hashes and raw evidence in catalog-ui-m13a/writer-report.json. Root owns final commit/full gate/closure.
