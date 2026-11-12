---
type: is
id: is-01m78xnsbajqmczwmc1gv1e84x
title: "PR #382 A2: --kbd-badge-bg copies --row-flash-bg's numbers instead of deriving them"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m78xnek6h8yd4znc1a47kdwm
created_at: 2026-11-12T22:22:26.153Z
updated_at: 2026-11-12T22:22:26.153Z
---
Severity: Low. PR #382, review A: https://github.com/jlevy/metabrowser/pull/382#pullrequestreview-5882884024. styles.css:235 and :1182 restate --row-flash-bg (:681, :1180) with / 0.6, and the dark override exists only to keep that copy in step. Fix: --kbd-badge-bg: color-mix(in srgb, var(--row-flash-bg) 60%, transparent) in :root, delete the dark override, and make the contrast test resolve the mix (the _MIX_OVER_TRANSPARENT pattern) with unchanged recorded ratios.
