---
type: is
id: is-01m78wsvqyv0bdk3v5gykvfzjk
title: Measure what eager startup JavaScript costs and reset startup_script_transfer_kb from it
kind: task
status: closed
priority: 2
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-12T22:07:11.101Z
updated_at: 2026-11-12T23:25:02.080Z
started_at: 2026-11-12T22:07:21.228Z
closed_at: 2026-11-12T23:25:02.079Z
close_reason: Gate reset to 220 KB from measured cost in https://github.com/jlevy/metabrowser/pull/387; brief docs/project/research/research-2026-11-12-eager-startup-script-cost.md
resolution: null
duplicate_of: null
---
startup_script_transfer_kb = 175 in explorations/performance-loop/performance-budgets.toml was set as exp-014's measured 154 KB plus headroom, not from a cost. Measure in headless Chrome what the eager scripts' bytes cost on localhost and over a --remote SSH link (transfer vs parse/compile/evaluate, effect on first row and FCP), how much of the payload is comments, and set the ceiling at a measured size with the measurement beside the constant. Research brief in docs/project/research/. The keyboard stack (#376, bead mb-w0dx) waits on the reset; do not change that stack.

## Notes

Branch claude/eager-script-cost-gate (2777b82f instruments, 19794a83 gate). startup_script_transfer_kb 175 -> 220, same unit. Measured (headless Chrome 152, cold folder loads, paired, comment-only variants): 0.18 ms/KB loopback (server per-request gzip; identity encoding 32 ms faster), 0.28 ms/KB 10 ms/100 Mbps, 0.32 ms/KB 80 ms/20 Mbps; warm and CPU 4x: none measurable. Ceiling = growth costing 1.1x on the strictest path (47 KB over 174). 220 KB build measured 1.07x/0.99x/1.04x. Comments 31.6% decoded, 41% transferred. Brief: docs/project/research/research-2026-11-12-eager-startup-script-cost.md. Unblocks mb-w0dx (keyboard stack tip 180,057 bytes fits). Follow-ups: compress static scripts once; consider setting startup_script_requests from round-trip cost.
