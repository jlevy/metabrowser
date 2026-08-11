---
type: is
id: is-01kxhq8er9emrvtykpw66fq7xb
title: "PR #1 review A7i: narrow or justify legacy TypeScript scope"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:29.512Z
updated_at: 2026-07-17T20:20:35.425Z
closed_at: 2026-07-17T20:20:35.425Z
close_reason: "Shipped in 813304d and subsequent v0.1.0 hardening: every accepted PR #1 runtime, security, performance, tooling, documentation, fixture, and hygiene finding has regression coverage; PR #1 has 35/35 review threads resolved; the final release gate passes 705 tests plus all lint, type, audit, build, distribution, and installed-wheel checks. The strict CSP remains separately tracked as mb-gluj."
---
Review A7i (Low). Confirm the actual tsconfig.legacy.json scope and document or narrow any broad implicit-any allowance.
