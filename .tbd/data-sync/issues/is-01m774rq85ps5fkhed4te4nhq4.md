---
type: is
id: is-01m774rq85ps5fkhed4te4nhq4
title: Remove Cmd main-tab bindings and move stack keys to N and P
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rtafehnx278pq5a90vgq
  - type: blocks
    target: is-01m774rv75dzyrdjgrxs9erjth
parent_id: is-01m76jgfxbadse383jypkzwpm9
created_at: 2026-11-12T05:47:53.476Z
updated_at: 2026-11-12T05:47:57.521Z
---
Design > Shift Rule Matching consequences. main-tabs.js tabBindings drops meta; main-tabs group copy without the Command sentence; main tab key runs openMainTab then the panel focusRow hook. pulls-nav.js registerKeys: pulls.stack.top N, pulls.stack.base P. J/K accept Shift in tree, Commits rows, Pulls rows, changed-file rows. Update preview-pane-state-session, cli-ui-file-lifecycle, pulls-nav-session, cli-ui-pulls-nav goldens; CHANGELOG under Unreleased, no aliases.
