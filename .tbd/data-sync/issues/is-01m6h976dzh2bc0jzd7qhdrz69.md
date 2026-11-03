---
type: is
id: is-01m6h976dzh2bc0jzd7qhdrz69
title: Preserve reusable comparisons during checkout metadata refresh
kind: bug
status: closed
priority: 2
version: 5
delegate: checkout_design
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
hold: null
hold_until: null
created_at: 2026-11-03T18:02:24.575Z
updated_at: 2026-11-03T20:17:09.835Z
started_at: 2026-11-03T18:06:54.030Z
closed_at: 2026-11-03T20:17:09.835Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Investigate shared record loss when a store-less checkout refresh overwrites an existing mirror comparison. Preserve exact endpoint/account ownership and stale-head behavior. GitHub review: https://github.com/jlevy/metabrowser/pull/288#discussion_r4458533521

## Notes

2026-11-03: Implemented in 5d3391887765145cbe132f20c67ea9937f6acf4b (owning PR288). A store-less metadata refresh preserves an existing shared comparison only for the same reader, matching old/new head, matching comparison head, base SHA/ref and open/closed state. Changed reader or endpoint/policy produces no_store. Real managed store/PR record regression covers the preserving case and six negative controls. Independent reviewer reproduced the original managed comparison loss at2bd. Validation:249 affected backend tests passed137.35s;31 final checkout/CLI tests passed45.45s;make lint-check and normal commit hooks passed. Author self-review is not independent; independent review/integration/full final gates/publication/closure remain with coordinator. No push or sync.

2026-11-03 19:00 UTC correction and successor: independent review found that 5d339188 retained only the pre-network record snapshot, so overlapping managed publication could still be overwritten. Fixed in 5b69bf511dd7bf4cac065e2d2fdcf2410fc47bc5, direct child of 5d: all canonical PR-record writers now take the existing source-alias lock; metadata merges a compatible comparison from the latest shared record and fits/writes inside that atomic publication boundary. Network, Git and manifest work stay outside; readers stay lock-free. run_lock_section abandons cancelled lock waits. Real overlap failed before the fix and passes after it. Five production-boundary controls cover both writer orders, lock-free old-record visibility, cancelled waits, post-merge budget and rename failure; 180 affected backend tests pass in159.92s,2 CLI recordings pass in13.74s, full lint/types/parity and normal commit hooks pass. Four-file source/test delta; clean owned worktree. Author self-review is not independent; exact pin sent for independent recheck. Root owns integration/full final gates/publication/closure. No push or sync.
