---
type: is
id: is-01m26d2kxsnpj6wjp8zeq09s9t
title: Keep Recent authoritative across deep changes and capped backfill
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-09-10T19:35:22.807Z
updated_at: 2026-09-10T22:20:07.459Z
closed_at: 2026-09-10T22:20:07.459Z
close_reason: "Implemented and verified the release-hardening slice: Recent now filters and clusters the complete server-selected model with bounded convergence repair; functional UI parity is enforced through CLI/golden evidence over exact production JavaScript; Markdown TOC composition restores same-document scrollspy and KPress disclosure; image preview is manifest-owned. make verify passes, including 1,968 tests, 104 golden scenarios, audits, and isolated wheel smoke."
resolution: null
duplicate_of: null
---
Release review found two related convergence gaps in the refactored Recent source: root-depth-2 fs.change omits deep updates after the full-inventory snapshot settles, and a truncated top-N page cannot backfill a row removed, aged out, or made ineligible. Use the existing unscoped catalog.change signal plus reconnect sentinels to coalesce an authoritative Recent refetch without buffering per-path deltas; refetch capped pages after subtractive eligibility changes or expiry; keep retained state bounded; add deterministic production-JS tests.

## Notes

Focused release audit found one remaining capped-page ambiguity: when a shallow file outside the retained top-N changes from matching to nonmatching, the live overlay has no previous row and cannot update an exact total. Treat that unseen subtractive case as an authoritative invalidation while truncated, coalesce it through the existing repair controller, and pin the production seam in the CLI golden.
