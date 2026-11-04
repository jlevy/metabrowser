---
type: is
id: is-01m6hpbyskz9sedf0bkt2t18e9
title: Distinguish an empty Open filter from a repository with no PRs
kind: bug
status: closed
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:52:12.077Z
updated_at: 2026-11-04T17:14:29.460Z
started_at: 2026-11-03T21:53:28.394Z
closed_at: 2026-11-04T17:14:29.460Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Independent landing probe found followLanding defaults its GET toOpen, while describeLanding treated fetched0 plus complete as repository-wide absence. A repository with zeroOpen and17Closed PRs therefore said No pull requests even on the Closed landing. Use exact repository_total for repository absence, or explicitly name the selected empty filter; preserve closed/all navigation without falsely claiming the repository is empty.

## Notes

Fixed repository absence to require exact repository_total zero plus complete. Unchanged independent repository17/Open0 probe red No pull requests, then green Select a pull request; reviewer rechecked clean. Permanent controls retain true zero and unknown-total behavior; Closed/All navigation is covered explicitly. Final29 affected tests/both browser type configs/9 scoped UI goldens pass. Exact hashes and raw evidence in catalog-ui-m13a/writer-report.json. Root owns final commit/full gate/closure.
