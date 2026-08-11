---
type: is
id: is-01kxhq8c9qf6hk8bkzftgwbvs4
title: "PR #1 review A4: dispose agent-log charts"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:26.998Z
updated_at: 2026-07-17T20:20:35.348Z
closed_at: 2026-07-17T20:20:35.348Z
close_reason: "Shipped in 813304d and subsequent v0.1.0 hardening: every accepted PR #1 runtime, security, performance, tooling, documentation, fixture, and hygiene finding has regression coverage; PR #1 has 35/35 review threads resolved; the final release gate passes 705 tests plus all lint, type, audit, build, distribution, and installed-wheel checks. The strict CSP remains separately tracked as mb-gluj."
---
Review A4 (Medium). src/metabrowser/builtin_plugins/agent_log: destroy Chart.js instances when the view is replaced.
