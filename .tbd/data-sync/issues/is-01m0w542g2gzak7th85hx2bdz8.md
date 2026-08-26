---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
child_order_hints:
  - is-01m0x69kd73kx9jyzc6ypf4hcn
  - is-01m0x6aedksxrggn0ba4tv66v0
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-26T03:38:27.570Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Exact pushed head 79c2f18 contains the live-folder disclosure repair and standard pre-index Files/Git/Files regression gate. make format, make verify (1,559 tests plus 48 golden scenarios), pre-commit, and pre-push pass. The exact wheel is globally installed and metab --doctor reports all eight plugins healthy. Manual cold-scan reproduction passed at 214,549 indexed files. A fresh-server headed Git run recorded Files return/folder expansion at 29.5/70.4 ms, Git transitions at 446.0/368.2/149.2 ms with 0.5-0.7 ms synchronous feedback, 7.3-20.9 ms pending onset, zero blank frames, exact convergence, one mount, two-request hydration, two expected aborts, zero obsolete successes, exceptions, or forced layout. An independent settled Git rerun and file-views run also pass; file transitions were 77.4/190.8/106.6 ms with one/one/zero fetches and zero blanks or exceptions. All review channels are clear. PR #82 is cleanly stacked on open, green PR #81 and therefore has no direct checks until #81 lands and #82 is retargeted to main. Exact global build remains open at http://127.0.0.1:8755/view/.
