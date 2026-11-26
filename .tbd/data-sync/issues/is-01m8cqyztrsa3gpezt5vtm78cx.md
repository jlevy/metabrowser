---
type: is
id: is-01m8cqyztrsa3gpezt5vtm78cx
title: Verify the released SoftSchema plugin in isolated Metabrowser installs
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cnf4sgyjn4q4psvp77emx2
hold: null
hold_until: null
created_at: 2026-11-26T20:15:15.792Z
updated_at: 2026-11-26T21:47:47.079Z
started_at: 2026-11-26T21:19:02.362Z
---
The isolated wheel now verifies the updated built-in plugin inventory and the shipped collection and catalog assets. After the published upstream collection API is available, upgrade to the released pin and exercise the actual collection and table routes from an isolated installed wheel without a source overlay.

## Notes

Exact downstream 6398a4c42 wheel (0.14.0.dev922) with reviewed SoftSchema PR #78 candidate 0.9.2.dev6+d0c286e passed without PYTHONPATH. Universe produced 18 tables and 4,971 records; the 577-row profile grid paged successfully. Nested frontmatter source matched the original bytes at line 9. The standard pin stays 0.9.1 until upstream merges and publishes.
