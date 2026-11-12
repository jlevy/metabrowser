---
type: is
id: is-01m774rrky1bpnkwshfqy4vqrz
title: Reveal state machine and shell keymap modules
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rsh9sd7x3aygqmew3zax
  - type: blocks
    target: is-01m774rv75dzyrdjgrxs9erjth
  - type: blocks
    target: is-01m774rvt6gjeg7asxxcz60xak
parent_id: is-01m76jgfxbadse383jypkzwpm9
created_at: 2026-11-12T05:47:54.877Z
updated_at: 2026-11-12T05:47:58.149Z
---
Design > Reveal State Machine and Badge Targets. static/key-reveal.js (hold threshold, pointer slop, wheel exits, dispatch-driven badge following) and static/shell-keymap.js (view tab letters registered at commit, header, filter, source commands; reads state at creation and rebuild), both in shell-tools. Session tests/dom/key-reveal-session.js and golden cli-ui-key-reveal.tryscript.md with recorded /api/file, /api/git/repo, /api/source/status; parity row shell.key-reveal.
