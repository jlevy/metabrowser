---
type: is
id: is-01m2mk1krjjyh70r8gjcjjkg0n
title: "Phase 0C.2 review R7: require positive and negative corpus evidence"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T07:49:03.377Z
updated_at: 2026-09-16T07:58:54.280Z
---
A selected conformance corpus with only valid cases or only invalid cases passes, allowing accept-all or reject-all validators to be vacuously certified. Require at least one selected valid and one selected invalid expectation per contract, contract-wide rather than per selector, and add valid-only and invalid-only regressions while preserving all shipped contracts.

## Notes

Implemented contract-wide selected-corpus polarity enforcement in src/metabrowser/plugin_loader/artifact_inventory.py: every installed contract must contribute at least one selected valid expectation and one selected invalid expectation, across all declared selectors rather than per selector. Added synthetic valid-only and invalid-only regressions in tests/test_artifact_inventory.py. Evidence: focused inventory suite 12 passed; focused Ruff clean; focused BasedPyright 0 errors; real installed checker reports 16 contracts and 2 profiles OK. Leave open for formal PR disposition.
