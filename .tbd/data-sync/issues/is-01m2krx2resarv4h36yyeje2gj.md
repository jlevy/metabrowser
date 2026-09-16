---
type: is
id: is-01m2krx2resarv4h36yyeje2gj
title: "Hosted review Phase 0C.1a: implement enforced SoftSchema contracts"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0c1
dependencies:
  - type: blocks
    target: is-01m2krxbqajmpk9zhjm8berj18
parent_id: is-01m2k1jq7ydswdag1x08n30hvn
created_at: 2026-09-16T00:12:11.915Z
updated_at: 2026-09-16T03:29:18.270Z
---
After the reviewed first-party SoftSchema foundation is available, implement trusted installed artifact-contract and resource-profile registries: contracts.py plus plugin_loader/artifact_contracts.py/profile registration, packaged format inventory, deterministic compiled schemas, validate_artifact, validate_record, validate_resource_set_against_profile, and compile_contracts check mode. Bind every contract ID to its envelope, frontmatter-md or pure-yaml profile, enforced maturity, model, schema digest, producer, consumer, browser parser, and fixture; bind every resource profile to target class, result contract, ordered collections, cardinality, pagination, and completeness. Reject duplicates and unknown profiles. Never select schemas or profile declarations from cached artifacts. Extend browser parsers and the portable corpus so Python and JavaScript agree. Work on one formal branch stacked on the green Phase 0B.3 PR.

## Notes

Implementation review checklist: design a backend-only trusted installed capability declaration for artifact contracts/resource profiles instead of registering a fake browser plugin; preserve provider-neutral ownership across the later hosted_review to provider_resources move without module paths or compatibility shims; compile only after Phase 0B.3 exact-provenance field/value-state oracle is green; keep cached artifacts unable to select schemas/profiles; add discovery/install/distribution tests for declarations with no browser surface.
