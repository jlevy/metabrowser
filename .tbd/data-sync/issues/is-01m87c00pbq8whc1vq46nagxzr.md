---
type: is
id: is-01m87c00pbq8whc1vq46nagxzr
title: Align the sidebar folder and Info icons with the heading text
kind: bug
status: in_progress
priority: 2
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/788
    at: 2026-11-24T18:31:01.858Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45459575260
    at: 2026-11-24T18:31:01.861Z
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T18:09:54.355Z
updated_at: 2026-11-24T19:23:19.690Z
started_at: 2026-11-24T18:11:57.408Z
---
Align the center of the Info SVG’s visible ink with the sidebar source mark across plain folders, Git checkouts, and mirrors. Keep the source mark fixed at its existing heading position. Document the layout and SVG alignment rule in the design system and keep any browser coverage based on relative geometry.

## Notes

PR 788 at ea1dfce0da471fbc1d24fba3887ac0edbcbfccee aligns SVGs with one optical token. Chrome measured the previous folder mark 1.04 px below the capital midpoint; WebKit measured both corrected glyphs within 1 px in light, dark, Clean Fonts, and System Fonts. CI 45457952781 and full verify 45457953665.
