---
type: is
id: is-01m8cqyztrsa3gpezt5vtm78cx
title: Verify the released SoftSchema plugin in isolated Metabrowser installs
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cnf4sgyjn4q4psvp77emx2
hold: null
hold_until: null
created_at: 2026-11-26T20:15:15.792Z
updated_at: 2026-11-26T21:47:27.202Z
started_at: 2026-11-26T21:19:02.362Z
---
The isolated wheel now verifies the updated built-in plugin inventory and the shipped collection and catalog assets. After the published upstream collection API is available, upgrade to the released pin and exercise the actual collection and table routes from an isolated installed wheel without a source overlay.

## Notes

The repaired installation smoke passes with all 18 built-ins. SoftSchema 0.9.1 does not ship softschema.collection; development UI validation still uses the upstream preview.
