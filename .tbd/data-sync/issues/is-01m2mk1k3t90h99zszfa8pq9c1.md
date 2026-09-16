---
type: is
id: is-01m2mk1k3t90h99zszfa8pq9c1
title: "Phase 0C.2 review R5: detect omitted capability providers independently"
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
created_at: 2026-09-16T07:49:02.713Z
updated_at: 2026-09-16T08:05:06.246Z
---
The distribution gate compares installed registries only with capability providers that survived into the same wheel, so an omitted intended entry point and its contracts/profiles can pass self-consistently. Derive the expected provider set from independent project build metadata and reconcile the installed distribution against it. Add a negative fixture or artifact mutation proving a missing declared provider is named and rejected without hard-coding hosted-review IDs.

## Notes

Implemented a provider-neutral independent authority parsed from [project.entry-points."metabrowser.capabilities.v1"] in source pyproject.toml. Wheel entry-point names and targets, sdist project metadata, and installed discovery provider IDs are reconciled against it exactly; no hosted-review provider or contract IDs are hard-coded. The negative test removes one generically named expected provider and requires a named missing-provider failure. Validation: 10 focused distribution tests passed; Ruff format/check passed; BasedPyright reported 0 errors; git diff check passed; make build passed end to end.
