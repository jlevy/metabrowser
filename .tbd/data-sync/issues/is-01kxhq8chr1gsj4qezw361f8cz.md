---
type: is
id: is-01kxhq8chr1gsj4qezw361f8cz
title: "PR #1 review A5/R2: freeze uv execution paths"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:27.255Z
updated_at: 2026-07-17T20:20:35.353Z
closed_at: 2026-07-17T20:20:35.353Z
close_reason: "Shipped in 813304d and subsequent v0.1.0 hardening: every accepted PR #1 runtime, security, performance, tooling, documentation, fixture, and hygiene finding has regression coverage; PR #1 has 35/35 review threads resolved; the final release gate passes 705 tests plus all lint, type, audit, build, distribution, and installed-wheel checks. The strict CSP remains separately tracked as mb-gluj."
---
Reviews A5 and R2 (Medium). Makefile, CI, publish workflow, and developer docs: assert lock freshness and prevent bare uv run commands from re-resolving or merging ambient policy.
