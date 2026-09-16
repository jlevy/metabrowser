---
type: is
id: is-01m2mmgq4qcwk5xb6pxsmea8g0
title: "Phase 0C.2 review R13: use type-sensitive portable-value preservation"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T08:14:46.934Z
updated_at: 2026-09-16T08:39:43.514Z
closed_at: 2026-09-16T08:39:43.514Z
close_reason: "Fixed in b907bb2734929cd0858207ba5d73639aee168636 and formally disposed on PR #136: https://github.com/jlevy/metabrowser/pull/136#issuecomment-5694591401"
resolution: null
duplicate_of: null
---
The installed round-trip gate compares dumped and corpus records with ordinary Python equality, which treats JSON-distinct values such as integer 1 and boolean true as equal. Reuse or expose the codec type-sensitive portable-value equality for original dumps and round-trip dumps. Add top-level and nested int-to-bool regressions while exact records continue to pass.

## Notes

Implemented evidence-semantic JSON preservation for installed corpus round trips. The codec's exact portable serialization comparison is now named portable_serialization_values_equal; inventory evidence reuses it and recursively permits only numerically equal int/float normalization while keeping booleans type-distinct. Both corpus-record→dump and dump→round-trip-dump boundaries are checked. Added synthetic exact, top-level int→bool, nested int→bool, round-trip-loss, and 1.0→1 normalization regressions. Evidence: 44 passed (tests/test_artifact_inventory.py + tests/test_artifact_contract_registry.py); focused Ruff clean; focused BasedPyright 0 errors; artifact-contract inventory checker reports 16 contracts and 2 profiles OK. Status intentionally remains in_progress for PR disposition.
