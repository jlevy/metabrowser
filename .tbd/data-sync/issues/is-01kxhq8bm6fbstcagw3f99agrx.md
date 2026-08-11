---
type: is
id: is-01kxhq8bm6fbstcagw3f99agrx
title: "PR #1 review A1: escape agent-log event kinds"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:26.309Z
updated_at: 2026-07-17T20:20:35.328Z
closed_at: 2026-07-17T20:20:35.328Z
close_reason: "Shipped in 813304d and subsequent v0.1.0 hardening: every accepted PR #1 runtime, security, performance, tooling, documentation, fixture, and hygiene finding has regression coverage; PR #1 has 35/35 review threads resolved; the final release gate passes 705 tests plus all lint, type, audit, build, distribution, and installed-wheel checks. The strict CSP remains separately tracked as mb-gluj."
---
Review A1 (High). src/metabrowser/builtin_plugins/agent_log/index.js and logutil/parsing.py: prevent file-content DOM XSS from attacker-controlled event kind values; replace inline JS interpolation with safe delegated events.
