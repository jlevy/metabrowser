---
type: is
id: is-01m2k1j7c9tf5d3b0aqxhf4mdk
title: "Hosted review Phase 0A.1: freeze the ChangeRequest kernel contract"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1j89z4zp23fm2672tg92v
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:18.952Z
updated_at: 2026-09-15T17:38:44.814Z
closed_at: 2026-09-15T17:38:44.813Z
close_reason: The formal stack scope and provider-reference authority are documented; closed provider-neutral ChangeRequest models and a deterministic frontmatter codec are implemented with focused Python tests for identity, lifecycle, relationships, portable values, explicit nulls, opaque Markdown, and byte-sensitive snapshot identity.
resolution: null
duplicate_of: null
---
Resolve the Phase 0A design choices in arch-hosted-review-model.md and the GitHub plan before code: ProviderObjectRef is the minimal provider, instance, object kind, opaque ID tuple; repository, number, and canonical URL live on ChangeRequest; all checked-in contract specimens are enforced; the artifact helper is a deterministic codec rather than publication; no manifest, route, view, network, cache, or dependency change. Record the exact contract ID, frontmatter envelope, portable scalar rules, lifecycle invariants, and this stacked PR scope.

## Notes

Implementation branch codex/v011-hosted-review-phase0a created from verified design PR head fde1d9b4, which contains released origin/main c465a5f2 and tag v0.10.0 commit c97de624.
