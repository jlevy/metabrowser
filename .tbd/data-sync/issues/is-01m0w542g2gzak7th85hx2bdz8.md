---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
child_order_hints:
  - is-01m0x69kd73kx9jyzc6ypf4hcn
  - is-01m0x6aedksxrggn0ba4tv66v0
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-25T19:28:27.563Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Exact pushed head 0d9d358 includes and passes automatic deferred request-storm validation. The headed trading-corpus run found 110 pending sections, deferred maximum 2, application maximum 3, two old-request aborts, zero obsolete successes, zero attribution overflow, one mounted comparison, exact row/route/view convergence, zero blank frames, and zero page exceptions. make format, make verify with 1550 tests and 48 golden scenarios, pre-commit, and pre-push pass. PR description and general-comment evidence are current. Formal reviews, inline comments, linked issues, and review docs have no actionable feedback. PR #81 remains open and green; PR #82 remains stacked on it and therefore has no GitHub checks until retargeting to main. Exact build remains open at http://127.0.0.1:8746/view/ on the trading repository.
