---
type: is
id: is-01m87c00pbq8whc1vq46nagxzr
title: Align the sidebar folder and Info icons with the heading text
kind: bug
status: in_progress
priority: 2
version: 8
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/788
    at: 2026-11-24T18:31:01.858Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45459575260
    at: 2026-11-24T18:31:01.861Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/789
    at: 2026-11-24T19:30:05.411Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/789#pullrequestreview-6045962248
    at: 2026-11-24T19:32:33.658Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45470743556
    at: 2026-11-24T19:32:33.665Z
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T18:09:54.355Z
updated_at: 2026-11-24T19:32:35.267Z
started_at: 2026-11-24T18:11:57.408Z
---
Align the center of the Info SVG’s visible ink with the sidebar source mark across plain folders, Git checkouts, and mirrors. Keep the source mark fixed at its existing heading position. Document the layout and SVG alignment rule in the design system and keep any browser coverage based on relative geometry.

## Notes

PR #789 head c0cb5cf19 and independent review are complete. Chrome checks the relative centers of source and Info SVG artwork for the three source kinds. Native WebKit compared the previous installed build and the candidate with both fonts and themes. The source mark stayed at the same position and Info now shares its centerline. The combined local suite passed 221 checks. Hosted standard CI and exact make verify are running.
