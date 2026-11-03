---
type: is
id: is-01m6hkbt0t0qhvrhxhktgefe38
title: Load PR catalog progressively with accurate repository totals and lazy details
kind: feature
status: in_progress
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6hkgedpcnemk1d6x6tqrwen
  - is-01m6hkgesnhsg9eg7wy0pc1qvp
  - is-01m6hkgf5ksmp2zhha4qa5ak97
  - is-01m6hkgfhcm5wmwkm6ypfg74hx
  - is-01m6hknzgxphza4kbk01qdxjka
  - is-01m6hn9qa613jm4353kpgse5zw
  - is-01m6hn9r6c5ky1jek345fd78mz
hold: null
hold_until: null
created_at: 2026-11-03T20:59:41.464Z
updated_at: 2026-11-03T21:33:31.209Z
started_at: 2026-11-03T21:00:05.436Z
---
Owner requests incremental/resumable automatic prefetch of the lightweight catalog for all repository PRs, with exact repository/filter totals. Initially show up to500 and expand the display with Fetch more. Fetch full PR description/conversation/reviews/checks only on demand or a small nearby prefetch window; derive diffs from fetched Git objects, audit actual payload sizes and avoid repeated full diff transfers. Filters Open | Closed | All, defaultOpen. Bold numeric status with repository name and Showing last500 when partial. Align Conversation/Files changed tabs with the content column at wide and narrow widths. Preserve cache-only GETs, account/rate/fair scheduling, keyboard/history/visibility ownership and main/linked checkout vsmanaged URL workflows. No compatibility aliases; forward-only childPR above288; no merge.
