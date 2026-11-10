---
type: is
id: is-01m718rgbk80mnnjb8d4b1r4xz
title: Render Markdown redlines within PR Changes
kind: feature
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7327d4wd92r1n5bnmr1b0zb
hold: null
hold_until: null
created_at: 2026-11-09T23:02:14.117Z
updated_at: 2026-11-10T16:38:24.330Z
started_at: 2026-11-10T15:46:31.780Z
---
Default eligible Markdown file sections to Rendered, with a per-file Rendered | Source toggle beside the filename. Use resolved base/head Git blobs in both checkout and cached modes. Map source hunks to safe rendered blocks, use existing red/green gutter and text tokens, and fall back to exact Source for unsupported or over-budget projections. Keep full revision links (mb-01s3) separate. Verify accessibility, safe relative URLs, structural changes, limits and races.

## Notes

Reviewed design in PR #346 at 63d5d7fab9fd1dadb2c1481c7ad24d4ded37ea0a (https://github.com/jlevy/metabrowser/pull/346). Astra verified the KPress source-map prerequisite, per-file fragment namespaces, and budgets before expensive rendering. Default to Rendered for eligible Markdown and preserve exact Source as fallback. Related revision links: mb-01s3.

Implemented a versioned KPress-verified projection with lazy per-file Rendered and Source controls, scoped references, and exact patch fallback. Parser timings were 58 to 72 ms warm on two documentation pairs. Functional browser checks cover both repository modes. Paired browser performance remains tracked on mb-5rth.
