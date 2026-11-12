---
type: is
id: is-01m78xnsbajqmczwmc1gv1e84x
title: "PR #382 A2: --kbd-badge-bg copies --row-flash-bg's numbers instead of deriving them"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78xnek6h8yd4znc1a47kdwm
hold: null
hold_until: null
created_at: 2026-11-12T22:22:26.153Z
updated_at: 2026-11-12T22:40:15.375Z
started_at: 2026-11-12T22:32:45.162Z
closed_at: 2026-11-12T22:40:15.374Z
close_reason: "fixed in 96c546f8: --kbd-badge-bg = color-mix(in srgb, var(--row-flash-bg) 60%, transparent), dark override removed; recorded ratios unchanged; identical composited pixels in Chrome. Reply: https://github.com/jlevy/metabrowser/pull/382#issuecomment-6837907014"
resolution: null
duplicate_of: null
---
Severity: Low. PR #382, review A: https://github.com/jlevy/metabrowser/pull/382#pullrequestreview-5882884024. styles.css:235 and :1182 restate --row-flash-bg (:681, :1180) with / 0.6, and the dark override exists only to keep that copy in step. Fix: --kbd-badge-bg: color-mix(in srgb, var(--row-flash-bg) 60%, transparent) in :root, delete the dark override, and make the contrast test resolve the mix (the _MIX_OVER_TRANSPARENT pattern) with unchanged recorded ratios.
