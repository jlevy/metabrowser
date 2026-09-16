---
type: is
id: is-01m2krwnemr6d0fht4kk7gsafx
title: "Hosted review Phase 0B.3b: review and publish the oracle phase"
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
    target: is-01m2k1jnf5t6bgg340skd537hn
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m2k1jnf5t6bgg340skd537hn
created_at: 2026-09-16T00:11:58.291Z
updated_at: 2026-09-16T04:21:40.759Z
---
Run independent fixture-scrubbing, common-model coverage, architecture, and delivery reviews; address every finding; run make verify; sync beads; and publish exactly one formal draft Phase 0B.3 PR with gh, based on the exact green Phase 0B.2 head. Record base/head OIDs and stack path, watch GitHub CI to a final green summary, and register the PR with mb-n2ro before Phase 0C.1 begins.

## Notes

Independent Phase 0B.3 reviews are in progress. First round found required evidence-gate fixes: exact public-safety allowlists across all oracle files; complete structured canonical-ID derivations; request-specific GraphQL schema response provenance; evidence-backed enum/literal dispositions and explicit planned-vs-current consumers; strict RFC 6901 pointers; a numeric-suite-ID to normalized-node-ID parent join; current Phase 0B.3 header/file-function scope; and pinned Flowmark formatting. Provider-neutral model corrections were reviewed as coherent. Fixes delegated back to the implementation agent; full make verify, formal gh PR, address-pr-review sweep, review record, and CI remain.
