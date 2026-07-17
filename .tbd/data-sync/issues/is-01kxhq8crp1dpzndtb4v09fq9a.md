---
type: is
id: is-01kxhq8crp1dpzndtb4v09fq9a
title: "PR #1 review A6: preserve Markdown on asset failure"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:27.477Z
updated_at: 2026-07-17T20:20:35.358Z
closed_at: 2026-07-17T20:20:35.358Z
close_reason: "Shipped in 813304d and subsequent v0.1.0 hardening: every accepted PR #1 runtime, security, performance, tooling, documentation, fixture, and hygiene finding has regression coverage; PR #1 has 35/35 review threads resolved; the final release gate passes 705 tests plus all lint, type, audit, build, distribution, and installed-wheel checks. The strict CSP remains separately tracked as mb-gluj."
---
Review A6 (Medium/Low). KPress browser asset failures should degrade optional styling/behavior without discarding already-rendered sanitized HTML; retain visible diagnostics and retries.
