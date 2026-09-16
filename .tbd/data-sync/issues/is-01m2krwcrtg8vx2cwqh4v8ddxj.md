---
type: is
id: is-01m2krwcrtg8vx2cwqh4v8ddxj
title: "Hosted review Phase 0B.3a: implement the scrubbed GitHub coverage oracle"
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b3
dependencies:
  - type: blocks
    target: is-01m2krwnemr6d0fht4kk7gsafx
parent_id: is-01m2k1jnf5t6bgg340skd537hn
created_at: 2026-09-16T00:11:49.398Z
updated_at: 2026-09-16T05:00:00.226Z
closed_at: 2026-09-16T05:00:00.225Z
close_reason: Phase 0B.3 oracle implementation and evidence-driven model reconciliation are complete; all delegated findings are addressed and full make verify is green.
resolution: null
duplicate_of: null
---
Implement the complete no-network Phase 0B.3 GitHub coverage oracle: scrubbed public fixtures, terminology-to-common-model mapping inventory, coverage and mapping tests, explicit observed/derived/optional-not-requested dispositions, hostile metadata, and future GitLab as a named consumer without speculative fields. Keep provider responses as test evidence only, never runtime input or a second model, on one formal branch stacked on the green Phase 0B.2 PR.

## Notes

Implemented the complete no-network GitHub coverage oracle and the smallest evidence-driven common-model corrections on codex/v011-hosted-review-phase0b3 from exact base 74dad3588d6de658ab2c56cf76711b39f0d3a496. The final oracle has exact reduced response/schema shapes, strict RFC 6901 pointers, exhaustive model/value dispositions, executable canonical and relationship ID recipes, public-data/secret guards across all non-synthetic files, and explicit runtime/wheel separation. Model reconciliation covers deleted-fork repository identity, nullable authors, unavailable original review revisions, and GitHub suite/run field distinctions. Three delegated review rounds are fully addressed; final oracle and delivery rereviews are clean. Focused tests: 83 passed. Full make verify: 2227 passed, 1 skipped; 124 golden scenarios passed; lint, type checks, parity, hygiene, audits, and distribution checks all green.
