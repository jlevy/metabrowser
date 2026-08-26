---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 15
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
child_order_hints:
  - is-01m0x69kd73kx9jyzc6ypf4hcn
  - is-01m0x6aedksxrggn0ba4tv66v0
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-26T04:28:26.046Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Final exact pushed head 1e1f5d8 removes all retained-view fading and animates only incoming foreground content from 0.98 to 1 over 50 ms; the light/dark theme canvas never animates. make format, make verify (1,559 tests plus 48 golden scenarios), pre-commit, and pre-push pass. The exact global wheel 0.7.2.dev40+1e1f5d8 is installed, doctor reports all eight plugins healthy, and the trading repo is open at http://127.0.0.1:8755/view/. Exact-head git-revisions recorded transitions at 471.4/387.8/134.7 ms with 0.4-0.9 ms feedback, 7.9-16.0 ms pending onset, 24 ms max Event Timing, zero blank frames, exact convergence, one mount, bounded hydration, zero obsolete successes, exceptions, or forced layout; Files return/folder expansion was 31.7/84.1 ms. Exact-head file-views recorded 65.5/181.4/64.1 ms with zero blanks, exceptions, Long Tasks, or forced layout. Manual light/dark file and Git checks confirm theme-matched canvas continuity. PR #82 description and disposition comment are current; formal reviews, inline comments, actionable general comments, referencing issues, and linked review docs are clear; exact-head GitHub CI is green. PR #82 remains stacked on open, green PR #81 and must be retargeted/revalidated after #81 lands before mb-j8ni and mb-fgcg close.
