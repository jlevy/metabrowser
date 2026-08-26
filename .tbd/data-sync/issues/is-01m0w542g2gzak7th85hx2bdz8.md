---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
child_order_hints:
  - is-01m0x69kd73kx9jyzc6ypf4hcn
  - is-01m0x6aedksxrggn0ba4tv66v0
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-26T02:09:23.423Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Exact pushed head cdc6376 passes the corrected trusted-input scenarios on settled corpus tree-a01f4187. Git transitions were 236.4/225.6 ms cold and 476.3 ms prepared; selection feedback was 1.4/0.3/0.3 ms, pending onset 16.6/11.9/12.5 ms, zero blank frames, exact selected/route/rendered convergence, one mount, two deferred requests, two expected aborts, zero obsolete successes, zero page exceptions, and zero forced layout. File transitions were 85.3 ms cold source, 210.2 ms cold Markdown, and 96.7 ms cached source; onset 12.3–26.7 ms, correct one/one/zero request counts, exact convergence, zero blanks, zero exceptions, zero Long Tasks, and zero forced layout. make format, make verify (1557 tests plus 48 golden), pre-commit, and pre-push pass. PR body is current and every review channel is clear. PR #81 remains open, so PR #82 stays stacked and GitHub reports no checks. Exact build runs at http://127.0.0.1:8753/view/.
