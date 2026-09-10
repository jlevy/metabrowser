---
type: is
id: is-01m26dfbch8646yvrtw84yx9qe
title: Upstream generic KPress TOC and typography improvements
kind: task
status: closed
priority: 1
version: 3
labels:
  - upstream
  - kpress
dependencies: []
created_at: 2026-09-10T19:42:20.042Z
updated_at: 2026-09-10T20:39:50.026Z
closed_at: 2026-09-10T20:39:50.025Z
close_reason: "Compared pinned KPress v0.3.5 and current upstream through a temporary vendor/kpress submodule. Confirmed collapsible TOC, chevron expand control, and measured monospace hierarchy already upstream. Contributed only genuine gaps in KPress PR #72 at 40ccb42c; local make verify and all six exact-head CI jobs passed. Removed the temporary submodule and .gitmodules from Metabrowser."
resolution: null
duplicate_of: null
---
Temporarily vendor the exact KPress upstream as vendor/kpress, compare Metabrowser's integration and CSS overrides with upstream, and contribute generic expandable/collapsible TOC, expand affordance, inline-code typography, and related reusable fixes through a tested KPress pull request. Keep Metabrowser-only host integration downstream.
