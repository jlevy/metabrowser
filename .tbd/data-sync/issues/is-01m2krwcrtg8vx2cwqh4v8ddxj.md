---
type: is
id: is-01m2krwcrtg8vx2cwqh4v8ddxj
title: "Hosted review Phase 0B.3a: implement the scrubbed GitHub coverage oracle"
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b3
dependencies:
  - type: blocks
    target: is-01m2krwnemr6d0fht4kk7gsafx
parent_id: is-01m2k1jnf5t6bgg340skd537hn
created_at: 2026-09-16T00:11:49.398Z
updated_at: 2026-09-16T04:21:41.330Z
---
Implement the complete no-network Phase 0B.3 GitHub coverage oracle: scrubbed public fixtures, terminology-to-common-model mapping inventory, coverage and mapping tests, explicit observed/derived/optional-not-requested dispositions, hostile metadata, and future GitLab as a named consumer without speculative fields. Keep provider responses as test evidence only, never runtime input or a second model, on one formal branch stacked on the green Phase 0B.2 PR.

## Notes

Phase 0B.3 implementation is on codex/v011-hosted-review-phase0b3 from green PR #133 head 74dad3588d6de658ab2c56cf76711b39f0d3a496. The no-network oracle and evidence-driven Python/JavaScript/corpus corrections are implemented; 50 focused tests and lint/static gates passed before review. First independent reviews confirmed the model changes but requested stricter oracle guarantees: recursive public-safety allowlists across every evidence/provenance file, structured complete ID recipes, split schema-query responses, value-state evidence, strict pointers, check-suite parent joining, exact plan scope/status, and pinned Markdown formatting. Those findings are being addressed before completion.
