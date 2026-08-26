---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
child_order_hints:
  - is-01m0x69kd73kx9jyzc6ypf4hcn
  - is-01m0x6aedksxrggn0ba4tv66v0
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-26T01:31:45.129Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Exact pushed head 947c447 includes the single 60 ms pointer-transparent pending sheet, stable-hover request intent, O(1) selected-row feedback, deferred roving Tab anchoring, and strict pending/phase/convergence health gates. Three repeated fixed-corpus candidate captures measured selection feedback at 0.3–4.6 ms, pending onset at 7.7–18.8 ms, row-anchor work at 0.5–7.9 ms, and zero forced layout in every run. Exact-head git-revisions passed: 584.0/226.1 ms cold and 122.2 ms prepared, feedback 4.5/0.5/0.3 ms, onset 16.3/15.2/15.6 ms, zero blank frames, exact convergence, one mount, two-request hydration, two aborts, zero obsolete successes, zero page exceptions, and zero forced layout. make format, make verify (1556 tests plus 48 golden), pre-commit, and pre-push pass. PR body and exact-head comment are current; all review channels are clear. PR #81 remains open, so PR #82 stays stacked and GitHub reports no checks. Exact build runs at http://127.0.0.1:8751/view/.
