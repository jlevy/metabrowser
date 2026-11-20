---
type: is
id: is-01m7rapxrkqdp972d6ts7ka7aq
title: "Re-derive the startup-script byte gate from first principles: the goal is first-paint latency, not bytes"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-11-18T21:58:51.404Z
updated_at: 2026-11-20T17:24:29.916Z
---
Owner, 2026-11-18: what are the size limits and what do they mean from first principles? Let's not blindly follow rules we made up; look at the actual goals and what is necessary. Context: startup_script_transfer_kb (220 KB, gate, explorations/performance-loop/performance-budgets.toml) held #550/#552 for ~10 hours over 161-500 bytes. Its own measurement (exp-084, 2026-11-12) puts 46 KB of growth at +6.6 ms loopback, -0.7 ms at 10 ms/100 Mbps and +19.4 ms at 80 ms/20 Mbps, about 0.4 ms per KB on a slow remote link and nothing measurable locally; parse is 0.01 ms/KB; warm loads show no cost. The macOS app, the main local path, sends ~630 KB uncompressed and is not budgeted at all. Proposal to decide: gate on what users feel (first-paint time on the remote paths, with a tolerance), keep the byte count as a reported trend with a soft warning, and keep the eager-tier rule (a large, narrowly used library does not belong in first paint) as review guidance.
