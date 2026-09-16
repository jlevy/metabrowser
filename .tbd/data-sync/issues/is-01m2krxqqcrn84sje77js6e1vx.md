---
type: is
id: is-01m2krxqqcrn84sje77js6e1vx
title: "Hosted review Phase 0C.2a: implement format inventory and parity gates"
kind: task
status: in_progress
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0c2
dependencies:
  - type: blocks
    target: is-01m2kry0g3g8hbnhr896wvqeve
parent_id: is-01m2k1jrywxceb6n3r0pbadegx
child_order_hints:
  - is-01m2mh3pyq4m362014a5eqw3zw
  - is-01m2mh3xrq6b4wbfncqvns3774
  - is-01m2mh44m99cx48f9sgwxrjf6n
created_at: 2026-09-16T00:12:33.385Z
updated_at: 2026-09-16T07:15:29.031Z
---
Implement the format/profile inventory checker, installed-wheel smoke coverage, and parity evidence for every installed artifact contract and resource profile. Require schema, digest, envelope/profile, semantic validator, producer, consumer, browser parser when consumed there, fixture/corpus, target class, collection contract/cardinality/pagination/completeness semantics, and architecture-map entry. Reject orphaned or duplicate registrations and update architecture maps without registering premature UI surfaces. Keep the no-network format/plugin boundary on one formal branch stacked on the green Phase 0C.1 PR.

## Notes

Phase 0C.2 implementation began from exact base 614fef15793ff7cffd0c4e85a577342472fd9686 on codex/v011-hosted-review-phase0c2. Build a generic inventory-driven checker over installed CapabilitySet declarations, schemas, semantic validators, evidence, and profiles; make distribution smoke consume the installed inventory rather than a hard-coded hosted-review schema list; register only current architecture/parity evidence. No provider adapter, cache path, network, route, resource kind, view, or static asset.
