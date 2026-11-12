---
type: is
id: is-01m78wsvqyv0bdk3v5gykvfzjk
title: Measure what eager startup JavaScript costs and reset startup_script_transfer_kb from it
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-12T22:07:11.101Z
updated_at: 2026-11-12T22:07:21.248Z
started_at: 2026-11-12T22:07:21.228Z
---
startup_script_transfer_kb = 175 in explorations/performance-loop/performance-budgets.toml was set as exp-014's measured 154 KB plus headroom, not from a cost. Measure in headless Chrome what the eager scripts' bytes cost on localhost and over a --remote SSH link (transfer vs parse/compile/evaluate, effect on first row and FCP), how much of the payload is comments, and set the ceiling at a measured size with the measurement beside the constant. Research brief in docs/project/research/. The keyboard stack (#376, bead mb-w0dx) waits on the reset; do not change that stack.
