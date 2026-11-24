---
type: is
id: is-01m87mf1r477nwhd43pjjqdpb8
title: Vertically center GitHub label text in compact chips
kind: bug
status: in_progress
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/792
    at: 2026-11-24T20:43:10.891Z
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T20:37:55.536Z
updated_at: 2026-11-24T20:43:12.085Z
started_at: 2026-11-24T20:39:00.615Z
---
Center GitHub pull request label text inside its existing compact box in both interface fonts and themes. Match the design system visual alignment rule, keep the accepted branch chip layout, and verify colored and neutral labels in a real renderer.

## Notes

The production PR fixture measured Clean label capitals 0.95 px high at baseline. Using the existing badge text-box centering brings the cap band to within 0.05 px of center in Chrome and WebKit while keeping the 16 px box and the approved branch chip geometry. The candidate passed 92 focused checks and all commit hooks.
