---
type: is
id: is-01m2zyv9gj9f0w6esn4vnsy38s
title: "Hosted Review format: bound StableToken and stop enums coercing bytes"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr139
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T17:46:57.937Z
updated_at: 2026-09-21T02:43:20.353Z
closed_at: 2026-09-21T02:43:20.353Z
close_reason: "Both residuals fixed on the #139 layer and merged up to #140, #217 and #216 (heads 82db7a77, 5e63442d, c5da5311, c20d3f01). StableToken bounded at 128 code points with its basis recorded; enums refuse bytes through a shared base class covering all 30 enum classes, with a test that fails if a new enum is declared unprotected. Both proven by reverting: 3 tests plus 3 corpus cases for the bound, 9 tests for the enums. The architecture sentence 'every structured string is bounded' is now true: 0 of 368 string leaves accept an arbitrarily long value. Note the implementer disproved the premise that a !!binary YAML scalar reaches the model: softschema refuses explicit YAML tags on both artifact paths, so the real surface is the model-level API. Gate: 3071 passed, 2 skipped, 145 goldens."
resolution: null
duplicate_of: null
---
Two residuals from the format hardening (mb-467v), both present since the #134 layer. (1) StableToken has a regex but no length bound, so a 5 MB adapter_id, operation_id, ResourceCollection.name or CapabilityObservation value validates; the architecture sentence added by the hardening says 'Every structured string is bounded', which is therefore wider than the code. Bounding it moves four compiled schemas. (2) Pydantic lax mode decodes bytes to str before a StrEnum lookup, so 82 of 491 string leaves across the corpora accept a !!binary scalar; all are enum-valued. The four frontmatter contracts are protected by the canonical-bytes check, the six pure-YAML contracts are not. Decide and fix both, or narrow the architecture sentence.
