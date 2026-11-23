---
type: is
id: is-01m83anmkn4q6grheww9z22vva
title: Fix pre-row Files navigation chrome layout shift in main CI
kind: bug
status: in_progress
priority: 1
version: 6
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45111133543
    at: 2026-11-23T04:31:12.047Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/731
    at: 2026-11-23T04:46:39.350Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hhr2r1bmm0ve8a6qs5nnqw
hold: null
hold_until: null
created_at: 2026-11-23T04:29:48.013Z
updated_at: 2026-11-23T05:04:18.482Z
started_at: 2026-11-23T04:31:07.504Z
---
Main CI run 45111133543 at b131131a3 shows pre-row shifts at 201/207 ms in the navigation filter bar, tab and root details. Chrome 3.12 dark 300 px CLS 0.00015 and 3.14 dark 180 px CLS 0.00011. Prior known folder age and empty-tree wrap cases have different sources. Measure the source rectangles and startup ordering, then fix the cause without relaxing layout thresholds.

## Notes

Main b131131a’s Chrome run 45111133543 recorded startup movement of the tab, folder menu, and Files filter bar. Delaying the normal Source Sans font reproduced it with 2px row movement and CLS 0.00012. The first #731 implementation applied optional display globally, and hosted run 45113793364 exposed PR geometry and prose typography regressions. Final #731 head 2c04beeec81e077aedba61d6e35603314bea8aa7 scopes the alias to the folder header, sidebar tabs, and Files-specific surfaces, retaining the same stamped KPress bytes, original Pulls/Commits and prose fonts, and System Fonts selection. Exact final controlled probe delivered the font after rows and observed CLS 0 and 0px movement. Warm Chrome verified actual Source Sans glyphs, and the exact stack-heading Chrome test passed. Standard pre-commit and 90 design/font contracts passed locally. Exact CI run 45115329636 is required to run the full red-main gate.
