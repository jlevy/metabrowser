---
type: is
id: is-01m87c00pbq8whc1vq46nagxzr
title: Align the sidebar folder and Info icons with the heading text
kind: bug
status: in_progress
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T18:09:54.355Z
updated_at: 2026-11-24T18:20:01.634Z
started_at: 2026-11-24T18:11:57.408Z
---
Measure the heading’s typography and glyph positions in a real renderer. Align its folder, checkout, mirror and Info glyphs to the visual center of the name, reuse the established icon alignment rule where appropriate, and document and verify the shared treatment.

## Notes

PR 788 at ea1dfce0da471fbc1d24fba3887ac0edbcbfccee aligns SVGs with one optical token. Chrome measured the previous folder mark 1.04 px below the capital midpoint; WebKit measured both corrected glyphs within 1 px in light, dark, Clean Fonts, and System Fonts. CI 45457952781 and full verify 45457953665.
