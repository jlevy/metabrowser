---
type: is
id: is-01m30x2vckrmc1c6xhtvwnnpjj
title: Bound ResourceCollectionSpec.name to match the record field it is compared against
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - stack:pr139
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-21T02:35:22.898Z
updated_at: 2026-09-21T02:35:22.898Z
---
mb-vs5q bounded ResourceCollection.name (the record) to MAX_STABLE_TOKEN_LENGTH but not ResourceCollectionSpec.name in provider_resources/profiles.py (the declaration it is compared against). validate_resource_set_against_profile requires exact name equality, so a profile declaring a longer name makes every resource set for that profile invalid. It fails closed, so it is a latent trap rather than a hole, but it is an asymmetry that fix introduced. Decide: bound the declaration to the same constant, or state why the two differ. Also note _STABLE_TOKEN_RE in hosted_review/models.py is now dead code and reads as an unbounded twin of the bounded alias six lines above.
