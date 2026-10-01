---
type: is
id: is-01m3tcz49ctsbrgmab6vxpw1k9
title: Remove the unused Hosted Review Format and provider_resources code from the v0.12 stack; keep it on a reference branch
kind: task
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T00:13:58.954Z
updated_at: 2026-10-01T00:20:13.547Z
started_at: 2026-10-01T00:20:13.544Z
---
The thin-mirror plan (Retired From Earlier Plans) leaves this code in the stack and calls removal a separate decision. #134-#139 ship about 13.5k lines (hosted_review/ 5.4k, data/hosted-review-format/ 6.5k, provider_resources/, capability/contract layer 1.4k) that the PR view does not use. It is runtime-dead for browsing but user-visible: three metabrowser.capabilities.v1 entry points (pyproject.toml), nine new public exports in plugin_api/metabrowser (ArtifactContractSpec, ResourceProfileSpec, ...), --doctor counts, and provider_resources imported at every server start. This contradicts the plan's 'no new public SDK' decision, and once released, removing it is itself a break. hosted_review is a clean leaf (~12k + ~3.4k tests; touches pyproject, doctor golden, arch inventory, test_github_coverage.py, check_distribution.py); provider_resources is tangled into CapabilitySet and the contract registry; the generic contract layer and softschema stay (cache uses them). The user decides: keep dormant, or remove in a PR above the tip.

## Notes

2026-09-30: decided by the user: remove the unused code from the stack and keep it on a separate branch with a draft PR, marked as unused reference code not on the critical path. Removal is a PR above the stack tip (no history rewrite); the reference branch re-adds exactly what was removed.
