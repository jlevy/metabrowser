---
type: is
id: is-01m6h9761vr0ay7nfd0fcta7zg
title: Rebind checkout pull state after source publication
kind: bug
status: closed
priority: 2
version: 4
delegate: checkout_design
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
hold: null
hold_until: null
created_at: 2026-11-03T18:02:24.186Z
updated_at: 2026-11-03T20:17:09.829Z
started_at: 2026-11-03T18:06:54.015Z
closed_at: 2026-11-03T20:17:09.829Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Investigate and fix checkout source claim changing slug while existing pull state still reads the prospective slug. Preserve read-only GET and private cache publication. GitHub review: https://github.com/jlevy/metabrowser/pull/288#discussion_r4458533507

## Notes

2026-11-03: Implemented in 5d3391887765145cbe132f20c67ea9937f6acf4b (owning PR288, parent2bd58827). claim_source now performs blocking publication in its private worker and rebinds same-source resolved/kept/active state on the event loop. All four async callers updated. Regression injects the admitted longer-suffix collision choice, then uses real publication and PR route reads across two checkouts; this proves the supported disambiguation branch, not ordinary collision frequency. Validation:249 affected backend tests passed137.35s;31 final checkout/CLI tests passed45.45s;make lint-check and normal commit hooks passed. Author self-review is not independent; independent review/integration/full final gates/publication/closure remain with coordinator. No push or sync.
