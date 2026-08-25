---
type: is
id: is-01m0w542g2gzak7th85hx2bdz8
title: Complete Git revision navigation handoff
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T09:48:15.745Z
updated_at: 2026-08-25T15:24:13.510Z
---
Files/surfaces: the complete focused branch diff, PR #82 title/body/comments/review threads/checks, and tbd status for mb-fgcg and its children. Re-read the spec and diff; rerun the headed git-revisions scenario on the exact pushed head; keep the zero-context PR description and validation plan aligned; audit formal reviews, inline comments, general comments, linked issues, in-repository review documents, and required CI; use tbd shortcut address-pr-review for any actionable finding and publish fixed/rebutted/deferred dispositions on the original channel. PR #82 stays stacked on PR #81 for a focused diff; after #81 lands, retarget #82 to main without losing commits and wait for the final exact-head CI summary. Acceptance: branch clean and pushed; no unaddressed review; make format, make verify, real-browser scenario, and GitHub CI green; then close mb-j8ni and mb-fgcg and run tbd sync.

## Notes

Head d1f430b is clean and pushed. The keyboard-parity finding mb-xmkn is fixed and closed; make format and make verify pass (1,544 tests and 48 golden scenarios), pre-commit and pre-push gates pass, and exact-head browser validation over 250 Git rows confirms one Tab stop, focus/current/route/render parity, and no console errors. The exact-head headed git-revisions scenario records 180.8 ms and 180.6 ms cold transitions, 105.8 ms prepared with zero click-time fetches, zero blank frames, one mounted comparison, and zero page exceptions. Formal reviews, inline threads, general comments, linked issues, and in-repository review documents contain no actionable feedback. PR #81 remains open; PR #82 is correctly stacked, and the main-only pull_request workflow therefore has no check run yet. Keep mb-j8ni open until #81 lands, #82 is retargeted to main, and the exact head receives the final green CI summary.
