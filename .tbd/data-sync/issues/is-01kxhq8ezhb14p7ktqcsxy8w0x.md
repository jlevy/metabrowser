---
type: is
id: is-01kxhq8ezhb14p7ktqcsxy8w0x
title: "PR #1 review R1: refresh live root summary totals"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:29.744Z
updated_at: 2026-07-17T20:20:35.369Z
closed_at: 2026-07-17T20:20:35.369Z
close_reason: "Shipped in 813304d and subsequent v0.1.0 hardening: every accepted PR #1 runtime, security, performance, tooling, documentation, fixture, and hygiene finding has regression coverage; PR #1 has 35/35 review threads resolved; the final release gate passes 705 tests plus all lint, type, audit, build, distribution, and installed-wheel checks. The strict CSP remains separately tracked as mb-gluj."
---
Review R1 (Medium). src/metabrowser/static/app.js: live creates/removes must update root file count, byte total, and root tooltip; add behavioral regression coverage.
