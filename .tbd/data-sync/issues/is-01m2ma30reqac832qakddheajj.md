---
type: is
id: is-01m2ma30reqac832qakddheajj
title: "Phase 0C.1 dependency: select and record first-party SoftSchema"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - dependency
dependencies: []
parent_id: is-01m2krx2resarv4h36yyeje2gj
created_at: 2026-09-16T05:12:32.261Z
updated_at: 2026-09-16T07:13:41.483Z
closed_at: 2026-09-16T07:13:41.480Z
close_reason: "Implemented in 614fef15793ff7cffd0c4e85a577342472fd9686: first-party SoftSchema dependency selection, installed capability registries, 16 enforced contracts, two profiles, cross-runtime evidence, and isolated distribution validation; make verify and GitHub CI are green."
resolution: null
duplicate_of: null
---
Select the exact jlevy first-party SoftSchema release under the explicit cool-off exemption. Record predecessor, chosen version, artifact/source provenance, hashes, transitive dependency delta, and runtime reach; update pyproject.toml and uv.lock only through uv; add the narrowest installed/distribution evidence needed by Phase 0C.1.

## Notes

Selected first-party softschema==0.8.1 (tag ff0f91999ebd0c3e8e0864e76042c6d875be083e) against 0.8.0. Expected lock delta is exactly SoftSchema 0.8.1 plus frontmatter-format 0.3.0 to 0.4.0; other dependencies are already satisfied. Record the package-scoped 2026-09-11T06:03:53Z exception and reviewed wheel/sdist hashes in SUPPLY-CHAIN-SECURITY.md. Use only public root APIs: Contract, Contracts, compile_model, validate_values, validate_artifact, SchemaView. Reject any unrelated lock movement.
