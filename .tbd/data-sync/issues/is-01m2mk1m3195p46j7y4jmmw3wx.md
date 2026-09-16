---
type: is
id: is-01m2mk1m3195p46j7y4jmmw3wx
title: "Phase 0C.2 review R8: verify serialization and artifact-profile round trips"
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
created_at: 2026-09-16T07:49:03.712Z
updated_at: 2026-09-16T08:39:43.452Z
closed_at: 2026-09-16T08:39:43.452Z
close_reason: "Fixed in b907bb2734929cd0858207ba5d73639aee168636 and formally disposed on PR #136: https://github.com/jlevy/metabrowser/pull/136#issuecomment-5694591401"
resolution: null
duplicate_of: null
---
The installed evidence gate validates records but never exercises dump_record or the frontmatter-md and pure-yaml artifact profiles. A lossy or raising dumper can pass. For valid cases, validate, dump, serialize through the declared artifact profile, parse and validate again, and check semantic preservation and deterministic output. Add lossy/raising dumper regressions and coverage for both profiles.

## Notes

Implemented valid-case serialization/profile evidence in src/metabrowser/plugin_loader/artifact_inventory.py. Each selected valid case now runs semantic validation, explicit dump_record preservation, declared frontmatter-md or pure-yaml serialization twice, validate_artifact parsing/validation, semantic redump comparison, and deterministic round-trip byte comparison. Raising and lossy dumpers produce case/profile-specific problems. Added synthetic coverage for both profiles plus lossy and raising dumpers in tests/test_artifact_inventory.py. Evidence: focused inventory suite 12 passed; focused Ruff clean; focused BasedPyright 0 errors; real installed checker reports 16 contracts and 2 profiles OK. Leave open for formal PR disposition.
