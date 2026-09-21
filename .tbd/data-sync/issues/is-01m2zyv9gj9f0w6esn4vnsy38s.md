---
type: is
id: is-01m2zyv9gj9f0w6esn4vnsy38s
title: "Hosted Review format: bound StableToken and stop enums coercing bytes"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr139
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T17:46:57.937Z
updated_at: 2026-09-21T02:06:20.938Z
---
Two residuals from the format hardening (mb-467v), both present since the #134 layer. (1) StableToken has a regex but no length bound, so a 5 MB adapter_id, operation_id, ResourceCollection.name or CapabilityObservation value validates; the architecture sentence added by the hardening says 'Every structured string is bounded', which is therefore wider than the code. Bounding it moves four compiled schemas. (2) Pydantic lax mode decodes bytes to str before a StrEnum lookup, so 82 of 491 string leaves across the corpora accept a !!binary scalar; all are enum-valued. The four frontmatter contracts are protected by the canonical-bytes check, the six pure-YAML contracts are not. Decide and fix both, or narrow the architecture sentence.
