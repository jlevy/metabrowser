---
type: is
id: is-01m6h3va3ry0j6ct473xy5wqn2
title: Document the GitHub pull-comparison hook in the owning layer inventory
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T16:28:32.247Z
updated_at: 2026-11-03T20:17:09.776Z
closed_at: 2026-11-03T20:17:09.776Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Actual #284 CI run41672494834 job126044251116 (Python3.13) and #285 fail tests/test_views_models_routes.py::test_documented_plugin_hooks_exist because owning #284 0b9c5bbfa9293e1057ede5abb20d84ec595ba8e5 registers github/pull-comparison but omits it from the map's registered-hook inventory. Reproduced exact failure locally; full map module5pass after adding the literal hook beside github/pull. Existing parity table row is already correct and preserved. Doc-only fix on codex/pulls-284-hook-map-01a1a051; pinned Flowmark wrapping only, no product/test/normalizer changes. Durable red/green/lint logs: task evidence `ci-hook-map-284/`. Root owns forward propagation, sync and closure after CI.
