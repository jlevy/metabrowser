---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
child_order_hints:
  - is-01m0x69kd73kx9jyzc6ypf4hcn
  - is-01m0x6aedksxrggn0ba4tv66v0
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-25T19:37:00.138Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Exact pushed head 34cb63f includes the shared file/Git transition lifecycle, immediate claim-owned dimming, plugin useful-content readiness, file-navigation spans, trusted file-views scenario, and hover/select request deduplication. make format and make verify pass with 1554 tests and 48 golden scenarios; pre-commit and pre-push pass. Exact-head headed file-views recorded cold source 108.3 ms/one fetch, cold Markdown 225.9 ms/one fetch, cached source 111.6 ms/zero fetches, zero blank frames, exact convergence, one mount, and zero page exceptions. Exact-head git-revisions recorded 955.8 ms and 202.1 ms cold plus 66.8 ms prepared with zero click-time fetches, zero blank frames, one mounted comparison, and zero page exceptions. Precommit findings mb-4um8 and mb-ow5f are fixed and closed. PR title/body/comment are current; formal reviews, inline comments, general comments, linked issues, and review docs have no new actionable feedback. PR #81 remains open, so PR #82 stays stacked with no GitHub checks; after #81 lands, reconcile origin/main, retarget, rerun exact-head browser validation and GitHub CI, then close mb-j8ni and mb-fgcg. Exact build remains open at http://127.0.0.1:8746/view/.
