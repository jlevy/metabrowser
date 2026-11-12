---
type: is
id: is-01m78tvmbpaf4nfs3zra15vsvy
title: "PR #379 C1: the keymap reads markup other modules own, checked only against hand-written copies"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ttv874k855zfx1arvd5vm
hold: null
hold_until: null
created_at: 2026-11-12T21:33:11.923Z
updated_at: 2026-11-12T21:33:38.216Z
started_at: 2026-11-12T21:33:38.213Z
---
Medium. PR #379, review C (https://github.com/jlevy/metabrowser/pull/379#pullrequestreview-5881899630). static/shell-keymap.js:104-131 and :274-286 read .folder-up[data-nav-dir], .folder-breadcrumb [data-nav-dir], .file-header-copy, [data-chip-menu-toggle], .chip-menu-panel, .chip-menu-item[aria-checked] emitted by app.js:351-359, :5541-5542, :5945 and static/filter-controls.js:252-317; the session renders its own copies (tests/dom/key-reveal-session.js:297-357, :444-462) and nothing pins the producers.
