---
type: is
id: is-01m6hx7pwk8v4vt4tgmwvrn9fp
title: Add optional authoritative native stack metadata cache
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hx4w87z6r8ndnbt57avr53
hold: null
hold_until: null
created_at: 2026-11-03T23:52:12.941Z
updated_at: 2026-11-04T17:14:29.490Z
started_at: 2026-11-03T23:52:23.481Z
closed_at: 2026-11-04T17:14:29.490Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Research the installed official gh-stack extension and its read-only repository stack API, then implement reviewed bounded optional stack enrichment for managed GitHub sources and existing checkouts. No local stack tracking, checkout mutations, extension installation, per-PR catalog query fanout, or core PR-data dependency. Preserve cache-only GETs, provider/account ownership, cancellation and graceful unavailable behavior; include focused tests and actual API proof.

## Notes

2026-11-03 implementation checkpoint: optional repository stacks GET/refresh routes and bounded independent JSON cache implemented on the uncommitted stack-info layer. GET is cache-only; capability/version probe, initial/final reader checks, conditional pages retaining continuation on304, source-lock revision CAS, cancellation, rate holds and separate optional failure stamps are covered. Bounds1000stacks/10000members and whole-page incomplete result are explicit.51focused tests and actual449-line CLI lifecycle transcript pass; generic discovery goldens updated from real output; independent review pending. Evidence labels: native-stack-info/backend-freeze.json, cap-measurement.json, focused-tests.log, cli-update.log. Final installed-wheel live runner prepared but paused pending coordinator commit/wheel.
