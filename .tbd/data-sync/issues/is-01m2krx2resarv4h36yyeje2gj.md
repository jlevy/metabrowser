---
type: is
id: is-01m2krx2resarv4h36yyeje2gj
title: "Hosted review Phase 0C.1a: implement enforced SoftSchema contracts"
kind: task
status: closed
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0c1
  - stack:pr134
dependencies:
  - type: blocks
    target: is-01m2krxbqajmpk9zhjm8berj18
parent_id: is-01m2k1jq7ydswdag1x08n30hvn
child_order_hints:
  - is-01m2ma30reqac832qakddheajj
  - is-01m2ma343kxrg0701jkxweee60
  - is-01m2ma3640mzk65nbbs1tdbhws
  - is-01m2ma39de2sndvdeaqde21p5p
created_at: 2026-09-16T00:12:11.915Z
updated_at: 2026-09-16T07:13:41.538Z
closed_at: 2026-09-16T07:13:41.538Z
close_reason: "Implemented in 614fef15793ff7cffd0c4e85a577342472fd9686: first-party SoftSchema dependency selection, installed capability registries, 16 enforced contracts, two profiles, cross-runtime evidence, and isolated distribution validation; make verify and GitHub CI are green."
resolution: null
duplicate_of: null
---
After the reviewed first-party SoftSchema foundation is available, implement trusted installed artifact-contract and resource-profile registries: contracts.py plus plugin_loader/artifact_contracts.py/profile registration, packaged format inventory, deterministic compiled schemas, validate_artifact, validate_record, validate_resource_set_against_profile, and compile_contracts check mode. Bind every contract ID to its envelope, frontmatter-md or pure-yaml profile, enforced maturity, model, schema digest, producer, consumer, browser parser, and fixture; bind every resource profile to target class, result contract, ordered collections, cardinality, pagination, and completeness. Reject duplicates and unknown profiles. Never select schemas or profile declarations from cached artifacts. Extend browser parsers and the portable corpus so Python and JavaScript agree. Work on one formal branch stacked on the green Phase 0B.3 PR.

## Notes

Implementation began from exact base 18ef513adc9782554d456b3ef0fbc7d02e0d975f on codex/v011-hosted-review-phase0c1. Three delegated read-only investigations are mapping the SoftSchema dependency/API, backend-only trusted plugin declaration path, and exact contract/profile/corpus parity surface before edits. The implementation must keep schemas and profiles installed-code-owned, preserve neutral identity across the later provider_resources move, avoid fake browser plugins and persisted module paths, and add no provider adapter/cache/route/view behavior.
