---
type: is
id: is-01m6g8865t5pqh8wc84xtkvkbp
title: "PR #287 A2: identify local changed-file lists by both endpoints"
kind: bug
status: closed
priority: 2
version: 6
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6g771qn4n0pce8m7sdmmhxy
hold: null
hold_until: null
created_at: 2026-11-03T08:26:14.073Z
updated_at: 2026-11-03T20:17:09.650Z
started_at: 2026-11-03T08:32:59.271Z
closed_at: 2026-11-03T20:17:09.650Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Independent strong review: comparison-derived list is considered current by head alone, so unchanged head with moved merge base never refreshes. Persist/compare base+head; migrate old cached lists to stale and test retarget.

## Notes

Fixed locally in be99626f; recheck same pin. Local file lists persist and compare resolved base plus head. Missing-base legacy cache files and comparison-unavailable transitions are stale; browser replacement identity includes base. Provider lists retain updated_at and account freshness, including when a local comparison appears later. Three focused freshness regressions, six recorder tests, 22 affected golden blocks, and targeted type checks pass. Awaiting independent recheck and coordinator push.

2026-11-03 independent-review integration at final tip 58270d69. Review B independently verifies A2 fixed: local list identity includes base and head; legacy missing-base and unavailable-comparison transitions are stale, provider freshness remains distinct. Retained at owning #287 0b7b62c5. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
