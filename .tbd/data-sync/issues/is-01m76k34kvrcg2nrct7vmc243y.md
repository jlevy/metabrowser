---
type: is
id: is-01m76k34kvrcg2nrct7vmc243y
title: "Research: apparent UI performance for the native app (transitions, prefetch, rendering, layout shift)"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/research/research-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-12T00:39:00.475Z
updated_at: 2026-11-12T01:48:23.399Z
started_at: 2026-11-12T00:39:06.452Z
closed_at: 2026-11-12T01:48:23.398Z
close_reason: Research doc committed on claude/ui-perf-research (03c06f96). Implementation beads to be filed after owner review of the ranking.
resolution: null
duplicate_of: null
---
Review the browser UI architecture and apparent performance with the native WKWebView app in mind: tab and main-tab switches, file transitions, prefetch policy, retained rendering, layout shift, HTTP caching, startup preloading. Deliver a research doc whose improvements are prioritized by effort and payoff in apparent speed.

## Notes

Research doc written: docs/project/research/research-2026-11-11-ui-apparent-performance.md. Measured in headless Chrome 152 (130-transition inventory, retention, memory, traces, delivery experiments through a rewriting proxy) and in a real WKWebView on macOS 26.5.2. Ranks 22 improvements by effort and payoff in three phases (quick wins 1-7, instant core 8-12, deeper retention 13-18) plus WebKit-aware measurement work and proposed budgets. Implementation beads not yet filed; awaiting owner review of the ranking.
