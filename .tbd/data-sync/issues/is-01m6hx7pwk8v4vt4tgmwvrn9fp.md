---
type: is
id: is-01m6hx7pwk8v4vt4tgmwvrn9fp
title: Add optional authoritative native stack metadata cache
kind: feature
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hx4w87z6r8ndnbt57avr53
hold: null
hold_until: null
created_at: 2026-11-03T23:52:12.941Z
updated_at: 2026-11-03T23:52:23.482Z
started_at: 2026-11-03T23:52:23.481Z
---
Research the installed official gh-stack extension and its read-only repository stack API, then implement reviewed bounded optional stack enrichment for managed GitHub sources and existing checkouts. No local stack tracking, checkout mutations, extension installation, per-PR catalog query fanout, or core PR-data dependency. Preserve cache-only GETs, provider/account ownership, cancellation and graceful unavailable behavior; include focused tests and actual API proof.
