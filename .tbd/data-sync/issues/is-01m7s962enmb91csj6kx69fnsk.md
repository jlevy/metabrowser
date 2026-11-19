---
type: is
id: is-01m7s962enmb91csj6kx69fnsk
title: Navigation hide toggle moves to the page's top row, across from the nav title's gear
kind: task
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T06:51:25.012Z
updated_at: 2026-11-19T07:54:05.047Z
started_at: 2026-11-19T06:52:35.094Z
---
Owner, 2026-11-18, verbatim: "the toggle to hide thenav view  withthe > should actualyl be on the top row of the page, aligned with the parent folder and aligned just across from the gear icon in the nav title and main folder name". Folded into the header-rhythm PR, branch claude/nav-root-padding (with mb-48rf, mb-igva, mb-ch82, mb-tatf, mb-wcbc). The toggle came from #591/#600 (session "Nav bar hide toggle").

## Notes

PR #608 (branch claude/nav-root-padding). .nav-collapse-toggle placed by CSS at the start of the main page's top row: top (row-1-size)/2, left (padx-size)/2, size --view-header-up-size. nav-collapse.js anchor option and ResizeObserver removed (app.js, types.d.ts). .settings-toggle display:flex centers the gear (was 0.5 px high). Measured 1400 px: gear center 16.5 == chevron 16.5 == Up 16.5, chevron x 302-322, Up at 324. Kbd badge z-index rule covers Up too. nav-collapse-chrome checkChevron pins chevron center == gear center, in the gutter before Up. Parity row shell.nav-collapse-paint, design-system Hiding the Navigation Pane, keyboard-shortcuts and the unreleased mb-bhpf fragment updated.
