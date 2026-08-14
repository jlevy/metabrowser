---
type: is
id: is-01kzyzvh8t3hf2dngzbz89fg4z
title: Publish the normative file-type compatibility packet
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - documentation
  - compatibility
dependencies:
  - type: blocks
    target: is-01kzz02ks9eygwfy31je8z907v
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T01:58:14.552Z
updated_at: 2026-08-14T02:05:15.329Z
---
Create the durable Metabrowser-owned contract package under docs/project/architecture/file-types/. Specify registry-v1, classification-v1, breakdown-v1, conformance fixtures, ownership/versioning, and the fdu adoption boundary. Include copyable TOML/JSON shapes, invariants, compatibility rules, and a field-level mapping that can be handed to fdu without browser implementation context. Link the package from the project index and active plan. Acceptance: common-doc formatting passes; examples conserve metrics and agree with the plan; the package distinguishes normative requirements from Metabrowser-only presentation.

## Notes

Drafted the durable compatibility directory, registry and interchange contracts, fdu adoption mapping, project index link, and bead dependency map on codex/file-type-systematization. Pending formatting, consistency review, and repository validation.
