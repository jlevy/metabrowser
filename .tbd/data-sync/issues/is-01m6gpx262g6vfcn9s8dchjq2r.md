---
type: is
id: is-01m6gpx262g6vfcn9s8dchjq2r
title: "PR #287: avoid forcing full layout during current-file follow subscription"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T12:42:18.176Z
updated_at: 2026-11-03T20:17:09.752Z
closed_at: 2026-11-03T20:17:09.752Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Matched final-stack performance at 8dedc142 versus f5b8eec2 has stable first-text medians (~530/536 ms versus495/528), but 1,627-file load tasks rise to207 ms [204-209] versus159 and held-key rows settle at164.3 ms. A single CPU profile attributes132.1 ms sampled inclusive time to mountDiff -> diff.onCurrentFile -> currentFile -> placeOfTopFile geometry, which forces layout immediately after attaching1,627 bars. The consumer bridge was introduced in #287. Prototype deferring only page-owned initial subscription until after paint, preserving generic diff immediate onCurrentFile and synchronous currentFile API, mount readiness even when hidden, history/landFile ordering, replacement/disposal cancellation, and latest selection. Adopt only with meaningful lifecycle tests and adjacent measured win; no broad bar virtualization or generic API break. Existing full acceptance at8ded remains diagnostic if successor is adopted. Keep remaining held-key delay unattributed until evidence identifies it; preserve all samples and budget misses.

## Notes

2026-11-03 final R5 gate finding: 4,696 Python tests passed with 9 legitimate skips, but the existing upper #288 mount transcript still recorded the pre-C1 JSON. Owning #287 has no mount transcript block, so the correction was placed at #288 after confirming both owning-layer outputs. Commit f56c36d55c7c0a3f22e06de316ab487a216bab93 changes only the existing JSON expectation to include bridgeAfterPaint, bridgeFramesOwned and hiddenReadiness=true. Focused transcript reproduced red (2 passed, 1 failed) and now passes all 3 cases; make lint-check and normal commit hooks pass. Product source is unchanged. No push or synchronization; coordinator owns forward propagation and the repeated final gate.
