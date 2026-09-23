---
type: is
id: is-01m30x2vckrmc1c6xhtvwnnpjj
title: Bound ResourceCollectionSpec.name to match the record field it is compared against
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10
labels:
  - stack:pr139
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
hold: null
hold_until: null
created_at: 2026-09-21T02:35:22.898Z
updated_at: 2026-09-23T05:32:22.628Z
started_at: 2026-09-23T03:31:09.600Z
closed_at: 2026-09-23T05:32:22.627Z
close_reason: "Done on codex/v012-foundation-stabilization (PR #226) (a0f573fa). MAX_STABLE_TOKEN_LENGTH lives in provider_resources/profiles.py and bounds ResourceCollectionSpec.name, and hosted_review/models.py imports it. The dead _STABLE_TOKEN_RE is removed. Test test_resource_collection_declaration_shares_the_record_name_bound. CHANGELOG notes the bound for plugin authors."
resolution: null
duplicate_of: null
---
mb-vs5q bounded ResourceCollection.name (the record) to MAX_STABLE_TOKEN_LENGTH but not ResourceCollectionSpec.name in provider_resources/profiles.py (the declaration it is compared against). validate_resource_set_against_profile requires exact name equality, so a profile declaring a longer name makes every resource set for that profile invalid. It fails closed, so it is a latent trap rather than a hole, but it is an asymmetry that fix introduced. Decide: bound the declaration to the same constant, or state why the two differ. Also note _STABLE_TOKEN_RE in hosted_review/models.py is now dead code and reads as an unbounded twin of the bounded alias six lines above.
