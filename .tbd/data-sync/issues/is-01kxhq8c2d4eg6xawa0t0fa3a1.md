---
type: is
id: is-01kxhq8c2d4eg6xawa0t0fa3a1
title: "PR #1 review A3: bound and chunk gzip text reads"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:26.764Z
updated_at: 2026-07-17T20:20:35.335Z
closed_at: 2026-07-17T20:20:35.335Z
close_reason: "Shipped in 813304d and subsequent v0.1.0 hardening: every accepted PR #1 runtime, security, performance, tooling, documentation, fixture, and hygiene finding has regression coverage; PR #1 has 35/35 review threads resolved; the final release gate passes 705 tests plus all lint, type, audit, build, distribution, and installed-wheel checks. The strict CSP remains separately tracked as mb-gluj."
---
Review A3 and inline thread (Medium). src/metabrowser/server.py and gz_io.py: honor offset/limit and cap decompression without trusting gzip ISIZE.
