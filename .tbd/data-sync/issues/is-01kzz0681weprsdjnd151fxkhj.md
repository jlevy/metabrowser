---
type: is
id: is-01kzz0681weprsdjnd151fxkhj
title: Validate all surfaces and publish the fdu adoption packet
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - validation
  - cross-project
dependencies: []
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:04:05.564Z
updated_at: 2026-08-14T02:04:05.564Z
---
Finish architecture, design-system, plugin SDK, release, and registry-maintenance documentation; update the durable file-type contract to the implemented schemas; export the normalized TOML, JSON Schemas, conformance corpus, fingerprints, and captured Registry/Breakdown examples as the versioned fdu adoption packet; and validate native and captured-producer paths. Run make format, make verify, public hygiene, browser manual checks across representative empty/high-cardinality/ignored directories, and a clean-wheel smoke test. Acceptance: every child bead is closed; schemas and examples match implementation; Metabrowser renders a captured fdu-shaped report without translation; the adoption checklist is complete; PR validation is documented and CI is green.
