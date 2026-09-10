---
type: is
id: is-01m26d2kxsnpj6wjp8zeq09s9t
title: Keep Recent authoritative across deep changes and capped backfill
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-09-10T19:35:22.807Z
updated_at: 2026-09-10T19:35:27.831Z
---
Release review found two related convergence gaps in the refactored Recent source: root-depth-2 fs.change omits deep updates after the full-inventory snapshot settles, and a truncated top-N page cannot backfill a row removed, aged out, or made ineligible. Use the existing unscoped catalog.change signal plus reconnect sentinels to coalesce an authoritative Recent refetch without buffering per-path deltas; refetch capped pages after subtractive eligibility changes or expiry; keep retained state bounded; add deterministic production-JS tests.
