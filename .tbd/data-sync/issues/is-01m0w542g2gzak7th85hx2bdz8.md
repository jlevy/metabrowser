---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-25T16:21:38.691Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Head 6edbb58 is clean and pushed. Commit-summary component bead mb-lk26 is fixed and closed: renderCommitSummary owns one semantic root and complete anatomy, renderCommitChangeStats owns aggregate stats, and renderCommitDetail composes it with comparison/bounded-file siblings. The nine-phase plan and design system are current. make format and make verify pass with 1,546 tests and 48 golden scenarios; precommit and prepush pass. Visible trading-repo validation confirms one component root, correct subject/metadata/stats/optional-body order, one diff toolbar, no duplicate summary, exact copy payload, and feedback reset. The exact-head headed scenario records 490.3 ms and 325.0 ms cold transitions, 99.3 ms prepared with no click-time fetch, zero blank frames, one mounted comparison, and zero page exceptions. PR #82 title/body are current. PR #81 remains open, so the main-only workflow has no run; keep this handoff open until retarget and final exact-head green CI.
