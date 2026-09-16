---
type: is
id: is-01m2krwcrtg8vx2cwqh4v8ddxj
title: "Hosted review Phase 0B.3a: implement the scrubbed GitHub coverage oracle"
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b3
dependencies:
  - type: blocks
    target: is-01m2krwnemr6d0fht4kk7gsafx
parent_id: is-01m2k1jnf5t6bgg340skd537hn
created_at: 2026-09-16T00:11:49.398Z
updated_at: 2026-09-16T03:27:56.535Z
---
Implement the complete no-network Phase 0B.3 GitHub coverage oracle: scrubbed public fixtures, terminology-to-common-model mapping inventory, coverage and mapping tests, explicit observed/derived/optional-not-requested dispositions, hostile metadata, and future GitLab as a named consumer without speculative fields. Keep provider responses as test evidence only, never runtime input or a second model, on one formal branch stacked on the green Phase 0B.2 PR.

## Notes

Implementation branch codex/v011-hosted-review-phase0b3 starts at green PR #133 head 74dad3588d6de658ab2c56cf76711b39f0d3a496. Planned files: tests/fixtures/github/oracle/ allowlisted captures plus provenance/field matrix; tests/test_github_coverage.py for full field/value-state coverage, derivations, scrub hygiene, and runtime/package exclusion; architecture/spec updates. No adapter, network, cache, registry, route, kind, view, manifest, dependency, or plugin discovery change.
