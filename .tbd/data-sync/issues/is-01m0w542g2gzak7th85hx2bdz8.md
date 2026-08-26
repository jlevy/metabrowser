---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 17
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
child_order_hints:
  - is-01m0x69kd73kx9jyzc6ypf4hcn
  - is-01m0x6aedksxrggn0ba4tv66v0
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-26T07:53:37.324Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Exact pushed PR #82 head 301b450 is green on all required GitHub checks (lint, distribution, Python 3.12/3.13/3.14). Local exact-head gates pass: make format, make verify with 1,562 tests plus 48 golden scenarios, 122 focused tests, pre-commit, and pre-push. Standard headed file-views and git-revisions scenarios pass with zero blank frames, exact row/route/render convergence, one active mount, expected request counts, bounded two-request hydration, obsolete-request cancellation, coherent Files round trip, and zero page exceptions. The globally installed wheel is metabrowser 0.7.2.dev48+301b450, all eight built-in plugins pass doctor, and the representative large repository is served at http://127.0.0.1:8770/view/. Formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required checks contain no unaddressed feedback. PR #82 has a refreshed zero-context description and exact validation plan. Remaining gate: PR #81 is still open; after it lands, reconcile and retarget #82 to main, rerun exact-head local/browser/CI gates, then close this bead.
