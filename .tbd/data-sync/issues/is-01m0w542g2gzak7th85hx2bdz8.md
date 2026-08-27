---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: closed
priority: 1
version: 20
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
child_order_hints:
  - is-01m0x69kd73kx9jyzc6ypf4hcn
  - is-01m0x6aedksxrggn0ba4tv66v0
  - is-01m0ztgq3910k6n9bbb6ejdpg5
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-27T00:43:35.266Z
closed_at: 2026-08-27T00:43:35.265Z
close_reason: "PR #82 was reconciled after its stack landed, merged without unresolved feedback, and its complete feature set shipped in v0.8.0 after exact-head local, headed-browser, GitHub CI, public-artifact, and global-install verification."
resolution: null
duplicate_of: null
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Exact pushed PR #82 head e080629 is green on GitHub lint, distribution, and Python 3.12/3.13/3.14. Local exact-head gates pass: make format, make verify with 1,564 tests plus 48 golden scenarios, focused tests, pre-commit, and pre-push. Standard headed file-views passes at 71.5/65.5/182.1/64.0 ms with zero blank frames, exact path/route/view convergence, one mount, expected one/one/one/zero requests, and zero exceptions. Standard headed git-revisions passes at 669.9/574.6/449.4 ms with zero blank frames, exact row/route/render convergence, one comparison, bounded two-request hydration, two expected aborts, zero obsolete successes, zero forced layout, zero page exceptions, and no task or animation frame over 200 ms. The globally installed wheel is metabrowser 0.7.2.dev50+e080629; all eight built-in plugins pass doctor; the representative large repository is served at http://127.0.0.1:8772/view/. Manual exact-wheel checks confirm standard-size sans multiline descriptions and the three-depth contract: medium pure rows, light refined rows, and darkest composite spans. PR #82 has a refreshed zero-context description and exact validation plan. Remaining gate: PR #81 is still open; after it lands, reconcile and retarget #82 to main, repeat exact-head local/browser/CI gates, then close.
