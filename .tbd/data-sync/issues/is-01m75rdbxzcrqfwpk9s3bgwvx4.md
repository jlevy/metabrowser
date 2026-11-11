---
type: is
id: is-01m75rdbxzcrqfwpk9s3bgwvx4
title: "PR 1: no spinner or 'may be out of date' over rendered PR content; subtle refresh animation"
kind: feature
status: in_progress
priority: 1
version: 14
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m75rdcd4ydy6gcf8x52wzrgt
parent_id: is-01m75rdbeg7acq14dwarqb6w4k
child_order_hints:
  - is-01m75s7rn9bjwh1k50g62n076y
  - is-01m75s7s6v8eced2hg6qw1rg6h
  - is-01m75s7spe156eqdjk0tc76gjs
  - is-01m75s7tdbpy8dg4fxf9dzvwbd
  - is-01m75s7v8gfgj1nv9ydmb0yw2r
  - is-01m75z31wt2khnr26spwbyy984
hold: null
hold_until: null
created_at: 2026-11-11T16:52:44.094Z
updated_at: 2026-11-11T19:38:57.154Z
started_at: 2026-11-11T16:54:28.208Z
---

## Notes

Draft PR #354 (https://github.com/jlevy/metabrowser/pull/354), branch claude/pr-refresh-without-spinners, head bba07860 (commits 5e87db82, b0c9afe4, a1ab573e, b1ca1eb5, 47a6aebc, bba07860). CI run 43086726277 green at bba07860. Review A addressed (A1-A6 fixed, A7 declined): https://github.com/jlevy/metabrowser/pull/354#issuecomment-6805478391; bead mb-fqzk closed. Not merged; the coordinator links the stack (PR 2 = mb-wlx0).


The parent of this bead is:
---
type: is
id: is-01m75rdbeg7acq14dwarqb6w4k
title: Spinner-free PR refresh and prefetch
kind: epic
status: open
priority: P1
version: 4
labels: []
dependencies: []
child_order_hints:
  - is-01m75rdbxzcrqfwpk9s3bgwvx4
  - is-01m75rdcd4ydy6gcf8x52wzrgt
  - is-01m75rdcxakv4vm7ey8fvt1d72
created_at: 2026-11-11T16:52:43.599Z
updated_at: 2026-11-11T16:52:45.096Z
---
User request 2026-11-11: reopening the browser and expanding a PR must not show a spinner; open PRs show the cached version and refresh in the background; no spinner over rendered content; no 'may be out of date' (always refreshing, name a problem only when a refresh cannot run); prefetch a reasonable amount; a very subtle animation on names being refreshed. Two stacked PRs: PR 1 presentation (claude/pr-refresh-without-spinners), PR 2 event-based freshness, prefetch tiers and rate-limit governor (claude/pr-freshness-prefetch). Design: scratchpad freshness/report.md from the investigation of bdcfedd4.
Coordinator 2026-11-11: PR #354 draft at bba07860355c790853c4a114b06b7df6ede9b055, CI run 43086726277 green. Review A (senior r1, review-5863835475) -> reply issuecomment-6805478391: A1-A6 fixed, A7 declined with measurement. Not merged; stays draft for the user.
