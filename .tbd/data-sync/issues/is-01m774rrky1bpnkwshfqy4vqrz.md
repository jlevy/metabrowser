---
type: is
id: is-01m774rrky1bpnkwshfqy4vqrz
title: "Layer 3: attachTarget, reveal machine, shell keymap, targets"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
labels:
  - layer-3
dependencies:
  - type: blocks
    target: is-01m774rsh9sd7x3aygqmew3zax
  - type: blocks
    target: is-01m774rv75dzyrdjgrxs9erjth
  - type: blocks
    target: is-01m774rvt6gjeg7asxxcz60xak
parent_id: is-01m76jgfxbadse383jypkzwpm9
created_at: 2026-11-12T05:47:54.877Z
updated_at: 2026-11-12T07:31:11.168Z
---
Spec Rollout layer 3 and Design > Reveal State Machine, Badge Targets. Registry: attachTarget() with dispatch-time liveness, targeted flag, context.target, target and dispatch events, observeKeys(), snapshot live option, reveal surface. static/key-reveal.js (hold, slop, wheel exits, badge recompute after dispatch); static/shell-keymap.js (view tab letters via commitViewTabs inside view composition commit(), header, filter, source commands; reads state at creation and rebuild); main tabs and pulls join the reveal surface; constants REVEAL_HOLD_MS, REVEAL_POINTER_SLOP_PX, strip item cap measured and recorded. Session tests/dom/key-reveal-session.js and golden cli-ui-key-reveal.tryscript.md; keymap check compares the session golden's shell keys; parity row shell.key-reveal. Docs: design-system Keyboard Commands and Help, development.md tier row, CHANGELOG.
