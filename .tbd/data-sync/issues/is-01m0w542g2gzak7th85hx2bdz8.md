---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-25T16:54:48.178Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Head 9ce7f2e is clean and pushed. Regression bead mb-k9a5 is fixed and closed: deferred file hydration is viewport-gated and capped at two active requests, while selecting another revision cancels the retained diff handle pending work immediately without removing its DOM. make format and make verify pass with 1,546 tests and 48 golden scenarios; precommit and prepush pass. Visible validation on an 88-file comparison starts zero offscreen requests, caps a 24-section viewport jump at two active requests, cancels old work on selection, and a 16-revision stress pass keeps selected row, URL, and mounted revision aligned. The exact-head headed scenario records 632.8 ms and 273.1 ms cold transitions, 96.5 ms prepared with no click-time fetch, zero blank frames, one mounted comparison, and zero page exceptions. PR #82 title/body are current and all review channels are clear. PR #81 remains open, so the main-only workflow has no run; keep this handoff open until retarget and final exact-head green CI.
