---
type: is
id: is-01m87mf1r477nwhd43pjjqdpb8
title: Vertically center GitHub label text in compact chips
kind: bug
status: closed
priority: 2
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/792
    at: 2026-11-24T20:43:10.891Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45483617855
    at: 2026-11-24T21:29:09.660Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45490352252
    at: 2026-11-24T21:29:09.662Z
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T20:37:55.536Z
updated_at: 2026-11-24T21:29:10.175Z
started_at: 2026-11-24T20:39:00.615Z
closed_at: 2026-11-24T21:29:10.172Z
close_reason: "Merged in #792 after review and the exact full gate. Chrome and native WebKit confirmed that font-metric centering places the label text within half a pixel of center in both fonts and themes while preserving the 16 px box and branch geometry. The active development app was rebuilt and restarted, and main CI passed."
resolution: null
duplicate_of: null
---
Center GitHub pull request label text inside its existing compact box in both interface fonts and themes. Match the design system visual alignment rule, keep the accepted branch chip layout, and verify colored and neutral labels in a real renderer.

## Notes

The production PR fixture measured Clean label capitals 0.95 px high at baseline. Using the existing badge text-box centering brings the cap band to within 0.05 px of center in Chrome and WebKit while keeping the 16 px box and the approved branch chip geometry. The candidate passed 92 focused checks and all commit hooks.
