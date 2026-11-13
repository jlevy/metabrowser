---
type: is
id: is-01m774rrky1bpnkwshfqy4vqrz
title: "Layer 3: attachTarget, reveal machine, shell keymap, targets"
kind: task
status: closed
priority: 2
version: 9
spec_path: docs/project/specs/done/plan-2026-11-11-shift-key-reveal-and-keymap.md
delegate: claude-code@spud10
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
hold: null
hold_until: null
created_at: 2026-11-12T05:47:54.877Z
updated_at: 2026-11-13T16:45:48.290Z
started_at: 2026-11-12T08:34:42.367Z
closed_at: 2026-11-12T17:35:13.683Z
close_reason: "Done in 0b2c063c, 674fe930, e14a0f54, a2f47145, f168ccae, d7b76a39: attachTarget with dispatch-time liveness (inert on both paths), targeted, context.target, target/reveal/dispatch events, observeKeys with a passive keyup, snapshot live and the reveal surface, badges via appendKey; static/key-reveal.js and static/shell-keymap.js in shell-tools and KEYBOARD_STATIC_ASSETS; main tabs targeted, stack keys and main tabs on the reveal surface. Tests: tests/dom/keyboard-shortcuts-behavior.js badge target cases, tests/dom/key-reveal-session.js with golden cli-ui-key-reveal.tryscript.md (three parts), tests/test_key_reveal_session.py recording, tests/test_keymap.py reserved-table comparison, parity row shell.key-reveal passes devtools.check_parity. REVEAL_HOLD_MS (200), REVEAL_POINTER_SLOP_PX (4), and REVEAL_STRIP_MAX_ITEMS (8) are provisional pending the human measurement in docs/qa-v012-repository-library.md 3.4 check 13."
resolution: null
duplicate_of: null
---
Spec Rollout layer 3 and Design > Reveal State Machine, Badge Targets. Registry: attachTarget() with dispatch-time liveness, targeted flag, context.target, target and dispatch events, observeKeys(), snapshot live option, reveal surface. static/key-reveal.js (hold, slop, wheel exits, badge recompute after dispatch); static/shell-keymap.js (view tab letters via commitViewTabs inside view composition commit(), header, filter, source commands; reads state at creation and rebuild); main tabs and pulls join the reveal surface; constants REVEAL_HOLD_MS, REVEAL_POINTER_SLOP_PX, strip item cap measured and recorded. Session tests/dom/key-reveal-session.js and golden cli-ui-key-reveal.tryscript.md; keymap check compares the session golden's shell keys; parity row shell.key-reveal. Docs: design-system Keyboard Commands and Help, development.md tier row, CHANGELOG.
