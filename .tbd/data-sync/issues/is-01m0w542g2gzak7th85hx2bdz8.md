---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 16
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
child_order_hints:
  - is-01m0x69kd73kx9jyzc6ypf4hcn
  - is-01m0x6aedksxrggn0ba4tv66v0
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-26T06:26:36.691Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Current exact pushed PR #82 head is 5caa1e0 and all required GitHub checks are green. make format, focused 63-test suite, make verify with 1,561 tests plus 48 golden scenarios, pre-commit, and pre-push pass. The final CSS-only stack tip 0bd3d5b repeated the complete headed git-revisions scenario: 370.4/429.0/156.7 ms transitions, zero blank frames, exact row/route/render convergence, one mount, two-request hydration with two expected aborts, zero obsolete successes or exceptions, 88 ms maximum trusted interaction and Long Task, 106 ms maximum animation frame, zero >200 ms blocking frame, Files return/folder expansion 38.9/92.2 ms. PR review, inline, general-comment, linked-issue, in-repository review, and required-check channels contain no new actionable feedback. PR description is refreshed for zero-context review. Remaining gate is intentional: PR #82 is still stacked on open PR #81 and must be retargeted/revalidated after #81 lands before this handoff bead closes.
